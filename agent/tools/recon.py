"""agent/tools/recon.py — Reconnaissance tools (nmap, dns, whois)."""
from __future__ import annotations

import asyncio
import socket
import subprocess
from typing import Any

from .registry import Tool, ToolResult


def _run_subprocess(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """Run a subprocess, return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"


# ── nmap ────────────────────────────────────────────────────────────────

def _nmap_handler(target: str, ports: str = "", scan_type: str = "-sV",
                  timeout: int = 120) -> ToolResult:
    """Run nmap against an in-scope target."""
    cmd = ["nmap"]
    if scan_type:
        cmd.extend(scan_type.split())
    if ports:
        cmd.extend(["-p", ports])
    cmd.append(target)
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    if rc == 127:
        return ToolResult(success=False, output="nmap is not installed.", error="not_installed")
    if rc != 0 and not out:
        return ToolResult(success=False, output=f"nmap failed: {err}", error=err)
    return ToolResult(success=True, output=out[:8000], data={"returncode": rc, "stderr": err})


NMAP_TOOL = Tool(
    name="recon_nmap",
    description=(
        "Run nmap against a target. Requires the target to be in scope per the Rules of Engagement. "
        "Use scan_type to control aggressiveness: '-sV' (default, version detection), "
        "'-sS' (syn scan, requires root), '-A' (aggressive, noisy), '--top-ports 100'. "
        "Always prefer the least noisy scan that achieves the objective."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Hostname or IP to scan"},
            "ports": {"type": "string", "description": "Port range, e.g., '1-1000' or '80,443,8080'. Optional."},
            "scan_type": {"type": "string", "description": "nmap flags, e.g., '-sV' (default) or '-A' or '--top-ports 100'", "default": "-sV"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 120},
        },
        "required": ["target"],
    },
    handler=_nmap_handler,
    requires_approval=True,
    requires_scope_target="target",
    dangerous=True,
)


# ── DNS ─────────────────────────────────────────────────────────────────

def _dns_handler(target: str, record_type: str = "A") -> ToolResult:
    """Resolve DNS records for a hostname."""
    record_type = record_type.upper()
    try:
        # Use socket for A records; subprocess for others
        if record_type == "A":
            try:
                ips = socket.getaddrinfo(target, None, socket.AF_INET)
                result_lines = [f"{target} has address {ip[4][0]}" for ip in ips]
                return ToolResult(success=True, output="\n".join(result_lines) or f"No A records for {target}")
            except socket.gaierror as e:
                return ToolResult(success=False, output=f"DNS resolution failed: {e}", error=str(e))
        # Use dig if available
        rc, out, err = _run_subprocess(["dig", "+short", target, record_type], timeout=10)
        if rc == 127:
            return ToolResult(success=False, output="dig is not installed; only A records supported.", error="not_installed")
        return ToolResult(success=True, output=out or f"No {record_type} records for {target}")
    except Exception as e:
        return ToolResult(success=False, output=f"DNS error: {e}", error=str(e))


DNS_TOOL = Tool(
    name="recon_dns",
    description="Resolve DNS records for a hostname (passive recon, no packets sent to target).",
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Hostname to resolve"},
            "record_type": {"type": "string", "description": "DNS record type: A, AAAA, MX, NS, TXT, CNAME, SOA", "default": "A"},
        },
        "required": ["target"],
    },
    handler=_dns_handler,
    requires_scope_target="target",
)


# ── whois ───────────────────────────────────────────────────────────────

def _whois_handler(target: str) -> ToolResult:
    rc, out, err = _run_subprocess(["whois", target], timeout=20)
    if rc == 127:
        return ToolResult(success=False, output="whois is not installed.", error="not_installed")
    return ToolResult(success=True, output=out[:5000], data={"stderr": err})


WHOIS_TOOL = Tool(
    name="recon_whois",
    description="Run whois on a domain (passive recon). Returns registration info.",
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Domain name to look up"},
        },
        "required": ["target"],
    },
    handler=_whois_handler,
    requires_scope_target="target",
)


RECON_TOOLS = [NMAP_TOOL, DNS_TOOL, WHOIS_TOOL]
