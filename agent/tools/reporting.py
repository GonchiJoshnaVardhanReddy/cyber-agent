"""agent/tools/reporting.py — Generate reports from World Memory findings."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .registry import Tool, ToolResult
from .fileops import _safe_path  # reuse the workspace sandbox


def _make_reporting_tools(world_memory, episodic_memory) -> list[Tool]:

    def _generate_report(format: str = "markdown", include_evidence: bool = True) -> ToolResult:
        """Generate a pentest report from recorded findings."""
        # Gather all findings from the world graph
        findings = []
        for node_id, data in world_memory._graph.nodes(data=True):
            if data.get("kind") != "finding":
                continue
            # Find the host this finding is attached to
            host = ""
            for source, _, edge_data in world_memory._graph.in_edges(node_id, data=True):
                if edge_data.get("kind") == "finds":
                    host = source.replace("host:", "")
                    break
            findings.append({
                "host": host,
                "title": data.get("label", "Untitled"),
                "severity": data.get("severity", "info"),
                "description": data.get("description", ""),
                "cve": data.get("cve", ""),
                "evidence": data.get("evidence", "") if include_evidence else "(omitted)",
            })

        # Sort by severity (critical first)
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        findings.sort(key=lambda f: (sev_order.get(f["severity"], 99), f["host"]))

        if format == "markdown":
            report = _render_markdown(findings, world_memory)
        elif format == "json":
            import json
            report = json.dumps({"findings": findings, "generated_at": datetime.utcnow().isoformat()}, indent=2)
        else:
            return ToolResult(success=False, output=f"Unknown format: {format}. Use 'markdown' or 'json'.", error="bad_format")

        # Write report to workspace
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.{('md' if format == 'markdown' else 'json')}"
        try:
            p = _safe_path(f"reports/{filename}")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(report, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Report generated: {len(findings)} findings written to {p.relative_to(_safe_path('.'))}\n\n{report[:3000]}",
                data={"path": str(p), "findings_count": len(findings)},
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to write report: {e}", error=str(e))

    generate_report_tool = Tool(
        name="report_generate",
        description=(
            "Generate a penetration test report from recorded findings. Output format: 'markdown' "
            "(default) or 'json'. The report is saved to workspace/reports/ and a preview is returned. "
            "Make sure to call memory_record_finding for every issue before generating the report."
        ),
        parameters={
            "type": "object",
            "properties": {
                "format": {"type": "string", "description": "Output format: markdown or json", "default": "markdown", "enum": ["markdown", "json"]},
                "include_evidence": {"type": "boolean", "description": "Include evidence in the report", "default": True},
            },
        },
        handler=_generate_report,
    )

    def _list_findings() -> ToolResult:
        findings = []
        for node_id, data in world_memory._graph.nodes(data=True):
            if data.get("kind") != "finding":
                continue
            host = ""
            for source, _, edge_data in world_memory._graph.in_edges(node_id, data=True):
                if edge_data.get("kind") == "finds":
                    host = source.replace("host:", "")
                    break
            findings.append({
                "host": host,
                "title": data.get("label", ""),
                "severity": data.get("severity", "info"),
                "cve": data.get("cve", ""),
            })
        if not findings:
            return ToolResult(success=True, output="No findings recorded yet. Use memory_record_finding to add them.")
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        findings.sort(key=lambda f: (sev_order.get(f["severity"], 99), f["host"]))
        lines = [f"Findings recorded: {len(findings)}"]
        for f in findings:
            lines.append(f"  [{f['severity'].upper():8s}] {f['host']:30s} {f['title']}" + (f" ({f['cve']})" if f["cve"] else ""))
        return ToolResult(success=True, output="\n".join(lines), data={"findings": findings})

    list_findings_tool = Tool(
        name="report_list_findings",
        description="List all recorded findings with their host and severity. Useful before generating a report.",
        parameters={"type": "object", "properties": {}},
        handler=_list_findings,
    )

    return [generate_report_tool, list_findings_tool]


def _render_markdown(findings: list[dict], world_memory) -> str:
    """Render findings as a Markdown pentest report."""
    from datetime import datetime
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Severity counts
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    lines = [
        "# Penetration Test Report",
        "",
        f"**Generated:** {now}",
        f"**Total Findings:** {len(findings)}",
        "",
        "## Severity Summary",
        "",
    ]
    for sev in ["critical", "high", "medium", "low", "info"]:
        if sev in counts:
            lines.append(f"- **{sev.upper()}:** {counts[sev]}")
    lines.append("")

    # World memory summary
    lines.append("## Target Summary")
    lines.append("```")
    lines.append(world_memory.summary())
    lines.append("```")
    lines.append("")

    # Findings detail
    lines.append("## Findings Detail")
    lines.append("")
    for i, f in enumerate(findings, 1):
        lines.append(f"### {i}. [{f['severity'].upper()}] {f['title']}")
        lines.append("")
        lines.append(f"**Host:** `{f['host']}`")
        if f["cve"]:
            lines.append(f"**CVE:** {f['cve']}")
        lines.append("")
        if f["description"]:
            lines.append(f"**Description:**")
            lines.append("")
            lines.append(f["description"])
            lines.append("")
        if f["evidence"]:
            lines.append("**Evidence:**")
            lines.append("```")
            lines.append(f["evidence"][:2000])
            lines.append("```")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)
