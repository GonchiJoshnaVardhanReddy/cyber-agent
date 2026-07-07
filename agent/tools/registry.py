"""agent/tools/registry.py — Tool registry and dispatch.

Tools are the agent's hands. Each tool declares a JSON schema (what arguments
it accepts) and a handler function. The registry routes tool calls from the
LLM to the right handler, enforces scope checks, and records everything to
the audit log.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from ..authorization import RulesOfEngagement
from ..audit import AuditLog


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str  # text the LLM will see
    data: Any = None  # structured data (for audit, not sent to LLM)
    error: str = ""


@dataclass
class Tool:
    """One tool definition."""
    name: str
    description: str
    parameters: dict  # JSON schema
    handler: Callable[..., ToolResult | Awaitable[ToolResult]]
    requires_approval: bool = False
    requires_scope_target: str | None = None  # name of the arg that holds the target
    dangerous: bool = False


class ToolRegistry:
    """Holds all registered tools. The agent loop asks it for the JSON schema
    list and dispatches tool calls through it."""

    def __init__(self, roe: RulesOfEngagement, audit: AuditLog,
                 approval_policy: "ApprovalPolicy | None" = None):
        self.roe = roe
        self.audit = audit
        self.approval_policy = approval_policy
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def list_for_llm(self) -> list[dict]:
        """Return the JSON schema list the LLM expects."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    async def dispatch(self, name: str, args: dict[str, Any],
                       approved_by: str | None = None) -> ToolResult:
        """Execute a tool by name with given args. Enforces scope + approval."""
        tool = self._tools.get(name)
        if not tool:
            self.audit.record("tool_not_found", tool_name=name, args=args, success=False,
                              detail=f"Unknown tool: {name}")
            return ToolResult(success=False, output=f"Error: unknown tool '{name}'", error="not_found")

        # 1. Scope check: if the tool declares a target arg, verify it's in scope
        if tool.requires_scope_target:
            target = str(args.get(tool.requires_scope_target, ""))
            if target:
                allowed, reason = self.roe.is_target_in_scope(target)
                if not allowed:
                    self.audit.record(
                        "scope_violation", tool_name=name, target=target, args=args,
                        success=False, detail=reason,
                    )
                    return ToolResult(
                        success=False,
                        output=f"REFUSED: {reason}. This target is not authorized by the Rules of Engagement.",
                        error="out_of_scope",
                    )

        # 2. Approval check: if the tool requires approval, ask the user
        if tool.requires_approval and self.approval_policy:
            approved, approver = await self.approval_policy.request(
                tool_name=name, args=args, dangerous=tool.dangerous,
            )
            if not approved:
                self.audit.record(
                    "tool_denied", tool_name=name, args=args, success=False,
                    approved_by=approver, detail="User denied approval",
                )
                return ToolResult(success=False, output="REFUSED: user denied approval.", error="denied")
            approved_by = approver

        # 3. Execute the handler
        try:
            result = tool.handler(**args)
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, ToolResult):
                # handler returned a plain string — wrap it
                result = ToolResult(success=True, output=str(result))
        except Exception as e:
            result = ToolResult(success=False, output=f"Tool error: {e}", error=str(e))

        # 4. Audit
        self.audit.record(
            "tool_call", tool_name=name,
            target=str(args.get(tool.requires_scope_target, "")) if tool.requires_scope_target else None,
            args=args, result=result.output[:2000], approved_by=approved_by,
            success=result.success, detail=result.error or None,
        )
        return result
