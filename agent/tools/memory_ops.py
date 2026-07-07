"""agent/tools/memory_ops.py — Tools that let the agent read/write its own memories.

These tools are how the agent populates World, Episodic, and Experience memory
during an engagement. Without them, the agent would observe things via other
tools but never remember them.
"""
from __future__ import annotations

from typing import Any

from .registry import Tool, ToolResult


def _make_memory_tools(memory_bundle) -> list[Tool]:
    """Build memory tools, binding the memory bundle at construction time.
    We do this factory pattern so the tools close over the actual memory instances
    rather than looking them up on every call.
    """
    working = memory_bundle["working"]
    world = memory_bundle["world"]
    episodic = memory_bundle["episodic"]
    experience = memory_bundle["experience"]
    semantic = memory_bundle["semantic"]
    procedural = memory_bundle["procedural"]

    # ── record_host ────────────────────────────────────────────────
    def _record_host(hostname: str, ip: str = "", os_type: str = "",
                     notes: str = "") -> ToolResult:
        props = {k: v for k, v in {"ip": ip, "os": os_type, "notes": notes}.items() if v}
        node_id = world.upsert_host(hostname, **props)
        working.add_observation(
            source="memory_ops", target=hostname,
            summary=f"Recorded host {hostname}" + (f" ({ip})" if ip else ""),
        )
        return ToolResult(success=True, output=f"Recorded host: {hostname} (id={node_id})")

    record_host_tool = Tool(
        name="memory_record_host",
        description="Record a discovered host in World Memory. Use after recon to build the target model.",
        parameters={
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "Hostname or FQDN"},
                "ip": {"type": "string", "description": "IP address if known", "default": ""},
                "os_type": {"type": "string", "description": "Detected OS (linux, windows, etc.)", "default": ""},
                "notes": {"type": "string", "description": "Free-form notes", "default": ""},
            },
            "required": ["hostname"],
        },
        handler=_record_host,
        requires_scope_target="hostname",
    )

    # ── record_service ─────────────────────────────────────────────
    def _record_service(host: str, port: int, proto: str = "tcp",
                        service: str = "", version: str = "",
                        notes: str = "") -> ToolResult:
        props = {k: v for k, v in {
            "service": service, "version": version, "notes": notes,
        }.items() if v}
        svc_id = world.upsert_service(host, port, proto, **props)
        working.add_observation(
            source="memory_ops", target=f"{host}:{port}",
            summary=f"Service on {host}:{port}/{proto} = {service} {version}".strip(),
        )
        return ToolResult(success=True, output=f"Recorded service: {host}:{port}/{proto} (id={svc_id})")

    record_service_tool = Tool(
        name="memory_record_service",
        description="Record a discovered service (port + protocol) on a host in World Memory.",
        parameters={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Hostname"},
                "port": {"type": "integer", "description": "Port number"},
                "proto": {"type": "string", "description": "Protocol: tcp or udp", "default": "tcp"},
                "service": {"type": "string", "description": "Service name (http, ssh, etc.)", "default": ""},
                "version": {"type": "string", "description": "Service version if detected", "default": ""},
                "notes": {"type": "string", "description": "Free-form notes", "default": ""},
            },
            "required": ["host", "port"],
        },
        handler=_record_service,
        requires_scope_target="host",
    )

    # ── record_finding ─────────────────────────────────────────────
    def _record_finding(host: str, title: str, severity: str, description: str = "",
                        cve: str = "", evidence: str = "") -> ToolResult:
        if severity.lower() not in {"info", "low", "medium", "high", "critical"}:
            return ToolResult(success=False, output="severity must be one of: info, low, medium, high, critical", error="bad_severity")
        props = {k: v for k, v in {
            "description": description, "cve": cve, "evidence": evidence,
        }.items() if v}
        finding_id = world.add_finding(host, title, severity, **props)
        working.add_observation(
            source="memory_ops", target=host,
            summary=f"[{severity.upper()}] {title} on {host}",
        )
        episodic.record_event(
            episode_id=working.execution_state.get("engagement_id", "unknown"),
            event_type="finding", description=f"{severity.upper()}: {title} on {host}",
            target=host, data={"finding_id": finding_id, "cve": cve},
        )
        return ToolResult(success=True, output=f"Recorded finding: [{severity}] {title} on {host} (id={finding_id})")

    record_finding_tool = Tool(
        name="memory_record_finding",
        description=(
            "Record a security finding. Severity must be one of: info, low, medium, high, critical. "
            "Include a CVE if applicable. Evidence should be a short proof string (request/response, "
            "command output, etc.). This is how the agent builds the final report."
        ),
        parameters={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Affected host"},
                "title": {"type": "string", "description": "Short title (e.g., 'SQL Injection in /login')"},
                "severity": {"type": "string", "description": "info | low | medium | high | critical", "enum": ["info", "low", "medium", "high", "critical"]},
                "description": {"type": "string", "description": "Detailed description", "default": ""},
                "cve": {"type": "string", "description": "CVE ID if applicable", "default": ""},
                "evidence": {"type": "string", "description": "Proof (request/response/output)", "default": ""},
            },
            "required": ["host", "title", "severity"],
        },
        handler=_record_finding,
        requires_scope_target="host",
    )

    # ── record_lesson ──────────────────────────────────────────────
    def _record_lesson(technique: str, success: bool, context: str = "",
                       outcome: str = "", lesson: str = "",
                       reuse_advice: str = "", target_kind: str = "") -> ToolResult:
        experience.record_lesson(
            technique=technique, success=success, context=context, outcome=outcome,
            lesson=lesson, reuse_advice=reuse_advice, target_kind=target_kind,
            episode_id=working.execution_state.get("engagement_id", ""),
        )
        return ToolResult(success=True, output=f"Recorded lesson for technique '{technique}': {'success' if success else 'failure'}")

    record_lesson_tool = Tool(
        name="memory_record_lesson",
        description=(
            "Record a lesson learned in Experience Memory. Call this after trying a technique "
            "(successful or not) so future engagements can benefit. Be specific about context "
            "and reuse_advice."
        ),
        parameters={
            "type": "object",
            "properties": {
                "technique": {"type": "string", "description": "Technique name, e.g., 'nmap-full-scan' or 'sqlmap-default'"},
                "success": {"type": "boolean", "description": "Did the technique achieve its objective?"},
                "context": {"type": "string", "description": "When/where was it tried?", "default": ""},
                "outcome": {"type": "string", "description": "What happened?", "default": ""},
                "lesson": {"type": "string", "description": "What did you learn?", "default": ""},
                "reuse_advice": {"type": "string", "description": "When to use this technique again", "default": ""},
                "target_kind": {"type": "string", "description": "web-app, linux-host, api, cloud, etc.", "default": ""},
            },
            "required": ["technique", "success"],
        },
        handler=_record_lesson,
    )

    # ── lookup_lesson ──────────────────────────────────────────────
    def _lookup_lesson(technique: str = "", target_kind: str = "") -> ToolResult:
        rows = experience.lookup(technique=technique or None, target_kind=target_kind or None)
        if not rows:
            return ToolResult(success=True, output="No prior lessons found for this technique/target.")
        lines = [f"Found {len(rows)} prior lessons:"]
        for r in rows[:5]:
            lines.append(
                f"\n  [{r['technique']}] success={bool(r['success'])} target={r['target_kind'] or '?'}\n"
                f"    context: {r['context'][:100]}\n"
                f"    outcome: {r['outcome'][:100]}\n"
                f"    lesson:  {r['lesson'][:100]}\n"
                f"    reuse:   {r['reuse_advice'][:100]}"
            )
        return ToolResult(success=True, output="\n".join(lines), data={"lessons": rows})

    lookup_lesson_tool = Tool(
        name="memory_lookup_lesson",
        description="Look up prior experience with a technique or target kind before trying it. Helps prioritize.",
        parameters={
            "type": "object",
            "properties": {
                "technique": {"type": "string", "description": "Technique to look up", "default": ""},
                "target_kind": {"type": "string", "description": "Target kind to filter by", "default": ""},
            },
        },
        handler=_lookup_lesson,
    )

    # ── add_hypothesis ─────────────────────────────────────────────
    def _add_hypothesis(statement: str, confidence: float = 0.5) -> ToolResult:
        h = working.add_hypothesis(statement, confidence)
        return ToolResult(success=True, output=f"Recorded hypothesis: {statement} (id={h.id}, confidence={confidence:.0%})")

    add_hypothesis_tool = Tool(
        name="memory_add_hypothesis",
        description="Record a hypothesis to test (e.g., 'Login page is vulnerable to SQL injection'). Track confidence as evidence accumulates.",
        parameters={
            "type": "object",
            "properties": {
                "statement": {"type": "string", "description": "Hypothesis statement"},
                "confidence": {"type": "number", "description": "Initial confidence 0.0-1.0", "default": 0.5},
            },
            "required": ["statement"],
        },
        handler=_add_hypothesis,
    )

    return [
        record_host_tool, record_service_tool, record_finding_tool,
        record_lesson_tool, lookup_lesson_tool, add_hypothesis_tool,
    ]
