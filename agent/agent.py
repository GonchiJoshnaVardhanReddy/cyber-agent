"""agent/agent.py — The core agent loop.

This is the brain. It:
1. Builds the system prompt (RoE + memory summaries + tool guidance)
2. Sends user message + tool schemas to the LLM
3. If the LLM returns tool calls, dispatches them (with scope + approval checks)
4. Feeds tool results back to the LLM
5. Loops until the LLM returns a final text response (no tool calls) or budget exhausted
6. Persists the conversation to episodic memory
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .provider import LLMProvider, LLMResponse, make_provider_from_env
from .authorization import RulesOfEngagement
from .audit import AuditLog
from .memory import (
    WorkingMemory, WorldMemory, SemanticMemory, ProceduralMemory,
    EpisodicMemory, ExperienceMemory,
)
from .tools.registry import ToolRegistry, ToolResult
from .tools.approval import ApprovalPolicy
from .tools.recon import RECON_TOOLS
from .tools.web import WEB_TOOLS
from .tools.fileops import FILEOPS_TOOLS
from .tools.codeexec import CODE_EXEC_TOOLS
from .tools.search import SEARCH_TOOLS
from .tools.memory_ops import _make_memory_tools
from .tools.planning import PlanManager, _make_planning_tools
from .tools.reporting import _make_reporting_tools


SYSTEM_PROMPT_TEMPLATE = """\
You are an autonomous offensive cybersecurity agent for AUTHORIZED bug bounty,
red team, and penetration testing engagements. You think, reason, plan, and
execute tools to achieve objectives within an authorized scope.

# CRITICAL RULES

1. SCOPE: You ONLY act against targets in the Rules of Engagement (RoE). Every
   tool that takes a target is scope-checked. Attempting out-of-scope actions is
   a violation and will be refused.

2. ETHICS: You are an assistant to a human operator. You do NOT have authority
   to act on your own. The operator authorized this engagement. You follow the
   RoE exactly. If you're unsure whether something is allowed, ASK.

3. EVIDENCE: Every finding must have evidence (request/response, command output).
   Use memory_record_finding to record findings with evidence as you find them.

4. METHODOLOGY: Follow a structured approach — recon first, then enumeration,
   then vulnerability identification, then validation, then reporting. Use the
   plan_create tool to decompose objectives into tasks.

5. LEARNING: Use memory_record_lesson after trying techniques (success or failure)
   so future engagements benefit. Use memory_lookup_lesson before trying a
   technique to see if you've done it before.

6. SAFETY: Prefer the least noisy, least invasive technique that achieves the
   objective. Never cause denial of service. Never modify production data. Never
   attack authentication infrastructure without explicit approval.

7. APPROVAL: Some tools require human approval. When approval is requested, the
   operator will approve or deny. Respect denials.

# CURRENT ENGAGEMENT (Rules of Engagement)

{roe_summary}

# YOUR MEMORY (current state)

{memory_summary}

# YOUR TOOLS

You have access to the following tools. Each tool is scope-checked and may
require approval. Use them strategically — do not call a tool unless you have a
specific hypothesis you're testing or a clear task to accomplish.

- Recon: recon_nmap, recon_dns, recon_whois
- Web: http_request, web_crawl
- File ops: file_read, file_write, file_list (sandboxed to ./workspace)
- Code execution: code_execute_python, code_execute_bash, code_execute_powershell
- Search: web_search, cve_search
- Memory: memory_record_host, memory_record_service, memory_record_finding,
  memory_record_lesson, memory_lookup_lesson, memory_add_hypothesis
- Planning: plan_create, plan_update_task, plan_view
- Reporting: report_generate, report_list_findings

# OPERATING STYLE

- Be methodical. Plan before acting. Use plan_create to decompose objectives.
- Record observations as you go. Don't rely on your conversation history alone.
- When you find something interesting, form a hypothesis (memory_add_hypothesis),
  test it with a tool, then record the result (memory_record_finding or update
  the hypothesis).
- Prefer passive recon (DNS, WHOIS, certificate transparency) before active
  recon (nmap, HTTP).
- When in doubt, ask the operator for clarification rather than guessing.
- At the end of an engagement, call report_generate to produce the final report.
"""


@dataclass
class AgentConfig:
    """Agent configuration."""
    provider: LLMProvider
    model: str
    max_iterations: int = 50
    temperature: float = 0.2
    max_tokens: int = 4096


class CyberAgent:
    """The autonomous cybersecurity agent. One instance per engagement."""

    def __init__(
        self,
        config: AgentConfig,
        roe: RulesOfEngagement,
        audit: AuditLog,
        memory_bundle: dict,
        approval_policy: ApprovalPolicy | None = None,
        engagement_id: str | None = None,
    ):
        self.config = config
        self.roe = roe
        self.audit = audit
        self.memory = memory_bundle
        self.approval_policy = approval_policy
        self.engagement_id = engagement_id or roe.engagement_id

        # Working memory holds the plan manager and execution state
        self.plan_manager = PlanManager()
        self.memory["working"].execution_state["engagement_id"] = self.engagement_id

        # Build the tool registry with all tools
        self.registry = ToolRegistry(roe=roe, audit=audit, approval_policy=approval_policy)
        self._register_tools()

        # Conversation history (for the current turn)
        self.history: list[dict[str, Any]] = []

    def _register_tools(self) -> None:
        """Register all built-in tools."""
        # Static tool lists
        for tool in RECON_TOOLS + WEB_TOOLS + FILEOPS_TOOLS + CODE_EXEC_TOOLS + SEARCH_TOOLS:
            self.registry.register(tool)
        # Tools that need memory bound at construction
        for tool in _make_memory_tools(self.memory):
            self.registry.register(tool)
        for tool in _make_planning_tools(self.plan_manager):
            self.registry.register(tool)
        for tool in _make_reporting_tools(self.memory["world"], self.memory["episodic"]):
            self.registry.register(tool)

    def _build_system_prompt(self) -> str:
        """Assemble the system prompt with RoE + memory summaries."""
        memory_summary = "\n\n".join([
            self.memory["working"].summary(),
            self.memory["world"].summary(),
            self.memory["semantic"].summary(),
            self.memory["procedural"].summary(),
            self.memory["episodic"].summary(),
            self.memory["experience"].summary(),
        ])
        return SYSTEM_PROMPT_TEMPLATE.format(
            roe_summary=self.roe.summary(),
            memory_summary=memory_summary,
        )

    async def run(self, user_message: str, stream_callback=None) -> str:
        """Run one turn: user message -> agent final response.

        Args:
            user_message: The user's objective or instruction.
            stream_callback: Optional async callback(text_delta: str) for streaming.

        Returns:
            The agent's final text response.
        """
        # Record the start of the turn
        self.audit.record("turn_start", detail=f"User: {user_message[:200]}")
        self.memory["episodic"].record_event(
            episode_id=self.engagement_id,
            event_type="observation",
            actor="operator",
            description=f"Objective: {user_message}",
        )

        # Build messages
        system_prompt = self._build_system_prompt()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        # Add any prior history (from previous turns in this session)
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})

        tools = self.registry.list_for_llm()
        final_response = ""
        iteration = 0

        while iteration < self.config.max_iterations:
            iteration += 1
            self.audit.record("llm_call", detail=f"iteration {iteration}")

            # Call the LLM
            try:
                llm_resp: LLMResponse = self.config.provider.chat(
                    messages=messages,
                    tools=tools,
                    model=self.config.model,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
            except Exception as e:
                error_msg = f"LLM call failed: {e}"
                self.audit.record("llm_error", success=False, detail=error_msg)
                return f"[Agent error: {error_msg}]"

            # Stream the content if a callback is set
            if stream_callback and llm_resp.content:
                await stream_callback(llm_resp.content)

            # Append assistant message to history
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": llm_resp.content}
            if llm_resp.tool_calls:
                # OpenAI format
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id, "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": __import__("json").dumps(tc.arguments),
                        },
                    }
                    for tc in llm_resp.tool_calls
                ]
            messages.append(assistant_msg)

            # If no tool calls, we're done
            if not llm_resp.tool_calls:
                final_response = llm_resp.content
                break

            # Execute each tool call
            for tc in llm_resp.tool_calls:
                self.audit.record("tool_dispatch", tool_name=tc.name, args=tc.arguments)
                result: ToolResult = await self.registry.dispatch(
                    name=tc.name, args=tc.arguments,
                )
                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result.output if result.success else f"ERROR: {result.output}",
                })
                # Record observation in working memory
                self.memory["working"].add_observation(
                    source=tc.name,
                    target=str(tc.arguments.get("target", tc.arguments.get("host", tc.arguments.get("url", "")))),
                    summary=result.output[:200],
                )
                # Stream the tool result if callback set
                if stream_callback:
                    await stream_callback(f"\n[Tool {tc.name}: {result.output[:200]}]\n")
        else:
            # Loop exhausted without a final response
            final_response = (
                f"[Agent reached max iterations ({self.config.max_iterations}) without "
                f"a final response. Last task: see plan_view. Use report_generate to "
                f"produce a report of findings so far.]"
            )

        # Save conversation history for next turn
        self.history = messages[1:]  # drop system prompt
        self.history.append({"role": "assistant", "content": final_response})

        # Record the end of the turn
        self.audit.record("turn_end", detail=f"Agent: {final_response[:200]}")
        self.memory["episodic"].record_event(
            episode_id=self.engagement_id,
            event_type="action",
            actor="agent",
            description=f"Response: {final_response[:500]}",
        )

        return final_response

    def status(self) -> str:
        """Human-readable status for the CLI / surfaces."""
        return (
            f"Engagement: {self.engagement_id}\n"
            f"Provider: {self.config.provider.name} / {self.config.model}\n"
            f"Iterations left: {self.config.max_iterations}\n\n"
            f"Plan:\n{self.plan_manager.summary()}\n\n"
            f"{self.memory['world'].summary()}"
        )


def build_agent_from_env(config_dict: dict) -> CyberAgent:
    """Build a fully-wired CyberAgent from config + env.

    config_dict is the parsed config.yaml.
    """
    from pathlib import Path

    # 1. Load RoE
    agent_cfg = config_dict.get("agent", {})
    authz_cfg = config_dict.get("authorization", {})
    roe_path = authz_cfg.get("roe_path", "./RULES_OF_ENGAGEMENT.md")
    hard_blocklist = authz_cfg.get("hard_blocklist", [])
    roe = RulesOfEngagement.from_file(roe_path, hard_blocklist=hard_blocklist)

    if authz_cfg.get("require_roe", True) and not roe.is_active():
        raise RuntimeError(
            f"Rules of Engagement is not active (window: {roe.start_time} to {roe.end_time}). "
            f"Update the RoE file dates or set authorization.require_roe=false for testing."
        )

    # 2. Audit log
    audit_cfg = config_dict.get("audit", {})
    memory_cfg = config_dict.get("memory", {})
    db_path = memory_cfg.get("db_path", "./data/agent.db")
    audit = AuditLog(
        log_path=audit_cfg.get("log_path", "./data/audit.log"),
        db_path=db_path if audit_cfg.get("log_to_db", True) else None,
        engagement_id=roe.engagement_id,
    )

    # 3. Memory systems
    memory_bundle = {
        "working": WorkingMemory(),
        "world": WorldMemory(backend=memory_cfg.get("world_backend", "networkx"),
                             neo4j_config=memory_cfg.get("neo4j", {})),
        "semantic": SemanticMemory(db_path=db_path),
        "procedural": ProceduralMemory(
            procedures_dir=memory_cfg.get("procedures_dir", "./data/procedures")
        ),
        "episodic": EpisodicMemory(db_path=db_path),
        "experience": ExperienceMemory(db_path=db_path),
    }
    # Seed semantic memory if empty
    memory_bundle["semantic"].seed_if_empty("./data/semantic_seed")
    # Start episodic episode
    memory_bundle["episodic"].start_episode(
        episode_id=roe.engagement_id, operator=roe.lead_operator, client=roe.client,
        metadata={"roe_hash": roe.file_hash, "type": roe.engagement_type},
    )

    # 4. Provider
    provider, model = make_provider_from_env()

    # 5. Approval policy (will be set by the surface — CLI/Telegram/Discord)
    approval_policy = None  # surfaces set this via agent.approval_policy = ...

    # 6. Build the agent
    agent_config = AgentConfig(
        provider=provider,
        model=agent_cfg.get("model", model),
        max_iterations=agent_cfg.get("max_iterations", 50),
        temperature=agent_cfg.get("temperature", 0.2),
        max_tokens=agent_cfg.get("max_tokens", 4096),
    )

    return CyberAgent(
        config=agent_config,
        roe=roe,
        audit=audit,
        memory_bundle=memory_bundle,
        approval_policy=approval_policy,
        engagement_id=roe.engagement_id,
    )
