"""agent/tools/offensive.py — Offensive security tools for hack mode.

This module provides comprehensive offensive security tools organized by category:
1. Network Scanning: Nmap, Masscan, RustScan, Naabu, Unicornscan
2. OSINT: WHOIS, DNS, Amass, theHarvester, Recon-ng, Shodan, Censys, Maltego
3. Subdomain Enumeration: Amass, Subfinder, Assetfinder, Findomain, Sublist3r
4. Web Discovery: ffuf, Feroxbuster, Gobuster, Dirsearch, httpx
5. Vulnerability Scanning: Nikto, Nuclei, Burp Suite, OWASP ZAP
6. Web Vuln Testing: XSStrike, DalFox, sqlmap, Arjun
7. SSL/TLS: testssl.sh, SSLyze
8. Exploitation: Metasploit Framework

Each tool checks if it's installed and offers to install it if missing.
"""
from __future__ import annotations

import subprocess
import shutil
from typing import Any
from pathlib import Path

from .registry import Tool, ToolResult


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _check_tool_installed(tool_name: str) -> bool:
    """Check if a command-line tool is installed."""
    return shutil.which(tool_name) is not None


def _get_package_manager() -> str | None:
    """Detect available package manager."""
    for pm in ["apt", "yum", "dnf", "pacman", "brew", "apk"]:
        if shutil.which(pm):
            return pm
    return None


def _install_command(package_name: str, tool_name: str) -> str:
    """Generate installation command for a tool."""
    pm = _get_package_manager()
    if not pm:
        return f"Manual installation required for {tool_name}"
    
    install_cmds = {
        "apt": f"sudo apt update && sudo apt install -y {package_name}",
        "yum": f"sudo yum install -y {package_name}",
        "dnf": f"sudo dnf install -y {package_name}",
        "pacman": f"sudo pacman -S --noconfirm {package_name}",
        "brew": f"brew install {package_name}",
        "apk": f"apk add {package_name}",
    }
    return install_cmds.get(pm, f"Install {package_name} manually")


def _run_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
    """Run a subprocess with timeout, return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"


# =============================================================================
# NETWORK SCANNING TOOLS
# =============================================================================

def _nmap_advanced_handler(target: str, scan_type: str = "-sV -sC",
                           ports: str = "", timing: str = "-T4",
                           output_format: str = "normal",
                           timeout: int = 600) -> ToolResult:
    """Advanced nmap scanning with multiple scan types."""
    if not _check_tool_installed("nmap"):
        install_cmd = _install_command("nmap", "nmap")
        return ToolResult(
            success=False,
            output=f"nmap is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["nmap"]
    if scan_type:
        cmd.extend(scan_type.split())
    if ports:
        cmd.extend(["-p", ports])
    if timing:
        cmd.append(timing)
    if output_format == "xml":
        cmd.extend(["-oX", "-"])
    elif output_format == "grepable":
        cmd.extend(["-oG", "-"])
    cmd.append(target)
    
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    if rc != 0 and not out:
        return ToolResult(success=False, output=f"nmap failed: {err}", error=err)
    
    return ToolResult(
        success=True,
        output=out[:15000],
        data={"returncode": rc, "stderr": err, "target": target},
    )


NMAP_ADVANCED_TOOL = Tool(
    name="offensive_nmap",
    description=(
        "Advanced nmap port scanning and service detection. "
        "Scan types: '-sV' (version), '-sC' (scripts), '-sS' (SYN, requires root), "
        "'-A' (aggressive), '-O' (OS detection). "
        "Timing: '-T0' (paranoid) to '-T5' (insane). Default: -T4. "
        "Use responsibly within scope."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target IP or hostname"},
            "scan_type": {"type": "string", "description": "Scan flags, e.g., '-sV -sC'", "default": "-sV -sC"},
            "ports": {"type": "string", "description": "Port range, e.g., '1-1000' or '80,443,8080'", "default": ""},
            "timing": {"type": "string", "description": "Timing template: -T0 to -T5", "default": "-T4"},
            "output_format": {"type": "string", "description": "Output format: normal, xml, grepable", "default": "normal"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 600},
        },
        "required": ["target"],
    },
    handler=_nmap_advanced_handler,
    requires_approval=True,
    requires_scope_target="target",
    dangerous=True,
)


def _masscan_handler(target: str, ports: str = "1-65535",
                     rate: int = 1000, timeout: int = 300) -> ToolResult:
    """High-speed masscan port scanner."""
    if not _check_tool_installed("masscan"):
        install_cmd = _install_command("masscan", "masscan")
        return ToolResult(
            success=False,
            output=f"masscan is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["masscan", "-p", ports, "--rate", str(rate), target]
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    if rc != 0 and not out:
        return ToolResult(success=False, output=f"masscan failed: {err}", error=err)
    
    return ToolResult(
        success=True,
        output=out[:15000],
        data={"returncode": rc, "open_ports": out.count("open")},
    )


MASSCAN_TOOL = Tool(
    name="offensive_masscan",
    description=(
        "Ultra-fast port scanner (masscan). Can scan entire internet in minutes. "
        "Requires root. Use high rates carefully - can trigger IDS/IPS. "
        "Default: 1000 packets/sec."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target IP, CIDR, or hostname"},
            "ports": {"type": "string", "description": "Port range, e.g., '1-65535'", "default": "1-65535"},
            "rate": {"type": "integer", "description": "Packets per second", "default": 1000},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300},
        },
        "required": ["target"],
    },
    handler=_masscan_handler,
    requires_approval=True,
    requires_scope_target="target",
    dangerous=True,
)


def _rustscan_handler(target: str, ports: str = "",
                      accessibility: bool = False,
                      timeout: int = 120) -> ToolResult:
    """Fast Rust-based port scanner with automatic nmap follow-up."""
    if not _check_tool_installed("rustscan"):
        install_cmd = "cargo install rustscan" if _check_tool_installed("cargo") else _install_command("rustscan", "rustscan")
        return ToolResult(
            success=False,
            output=f"rustscan is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["rustscan", "-a", target]
    if ports:
        cmd.extend(["-p", ports])
    if accessibility:
        cmd.append("--accessible")  # Less accurate but more accessible
    # Auto-run nmap on discovered ports
    cmd.extend(["--", "nmap", "-sV", "-sC"])
    
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    return ToolResult(
        success=rc == 0 or out,
        output=out[:15000] if out else err,
        data={"returncode": rc},
    )


RUSTSCAN_TOOL = Tool(
    name="offensive_rustscan",
    description=(
        "Fast modern port scanner written in Rust. Automatically follows up with nmap. "
        "Much faster than nmap for initial discovery. Good for bug bounty recon."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target IP or hostname"},
            "ports": {"type": "string", "description": "Specific ports to scan", "default": ""},
            "accessibility": {"type": "boolean", "description": "Reduce accuracy for accessibility", "default": False},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 120},
        },
        "required": ["target"],
    },
    handler=_rustscan_handler,
    requires_approval=True,
    requires_scope_target="target",
    dangerous=True,
)


def _naabu_handler(target: str, ports: str = "",
                   scan_type: str = "-sS",
                   threads: int = 25,
                   timeout: int = 120) -> ToolResult:
    """Fast TCP port scanner by ProjectDiscovery."""
    if not _check_tool_installed("naabu"):
        install_cmd = _install_command("naabu", "naabu")
        return ToolResult(
            success=False,
            output=f"naabu is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["naabu", "-host", target, "-threads", str(threads)]
    if ports:
        cmd.extend(["-p", ports])
    if scan_type:
        cmd.append(scan_type)
    
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    return ToolResult(
        success=rc == 0 or out,
        output=out[:15000] if out else err,
        data={"returncode": rc},
    )


NAABU_TOOL = Tool(
    name="offensive_naabu",
    description=(
        "Fast and reliable port scanner by ProjectDiscovery. "
        "Supports SYN scan (-sS), connect scan (-sC). "
        "Good balance between speed and accuracy."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target IP or hostname"},
            "ports": {"type": "string", "description": "Ports to scan, e.g., '80,443,8080' or range '1-1000'", "default": ""},
            "scan_type": {"type": "string", "description": "Scan type: -sS (SYN) or -sC (connect)", "default": "-sS"},
            "threads": {"type": "integer", "description": "Number of threads", "default": 25},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 120},
        },
        "required": ["target"],
    },
    handler=_naabu_handler,
    requires_approval=True,
    requires_scope_target="target",
    dangerous=True,
)


# =============================================================================
# OSINT TOOLS
# =============================================================================

def _amass_handler(domain: str, mode: str = "enum",
                   passive: bool = False,
                   timeout: int = 600) -> ToolResult:
    """Comprehensive OSINT and attack surface mapping with Amass."""
    if not _check_tool_installed("amass"):
        install_cmd = "go install github.com/owasp-amass/amass/v4/...@latest" if _check_tool_installed("go") else _install_command("amass", "amass")
        return ToolResult(
            success=False,
            output=f"amass is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["amass", mode, "-d", domain]
    if passive:
        cmd.append("-passive")
    cmd.extend(["-timeout", str(timeout)])
    
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    # Parse subdomains from output
    subdomains = [line.strip() for line in out.split("\n") if line.strip()]
    
    return ToolResult(
        success=rc == 0 or subdomains,
        output=f"Found {len(subdomains)} subdomains:\n" + "\n".join(subdomains[:100]),
        data={"returncode": rc, "subdomain_count": len(subdomains), "subdomains": subdomains},
    )


AMASS_TOOL = Tool(
    name="offensive_amass",
    description=(
        "OWASP Amass - Comprehensive OSINT and attack surface mapping. "
        "Modes: 'enum' (enumeration), 'intel' (org info gathering), 'track' (monitoring). "
        "Passive mode uses only passive sources (no direct target contact). "
        "Active mode performs DNS brute-forcing and more."
    ),
    parameters={
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Target domain"},
            "mode": {"type": "string", "description": "Operation mode: enum, intel, track", "default": "enum"},
            "passive": {"type": "boolean", "description": "Use passive sources only", "default": False},
            "timeout": {"type": "integer", "description": "Timeout in minutes", "default": 600},
        },
        "required": ["domain"],
    },
    handler=_amass_handler,
    requires_approval=True,
    requires_scope_target="domain",
    dangerous=False,
)


def _theharvester_handler(domain: str, source: str = "all",
                          limit: int = 500,
                          timeout: int = 300) -> ToolResult:
    """Email, subdomain, and host harvesting with theHarvester."""
    if not _check_tool_installed("theHarvester"):
        install_cmd = _install_command("theharvester", "theHarvester")
        return ToolResult(
            success=False,
            output=f"theHarvester is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["theHarvester", "-d", domain, "-b", source, "-l", str(limit)]
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    return ToolResult(
        success=rc == 0 or out,
        output=out[:15000] if out else err,
        data={"returncode": rc},
    )


THEHARVESTER_TOOL = Tool(
    name="offensive_theharvester",
    description=(
        "theHarvester - Gather emails, subdomains, hosts, employee names from public sources. "
        "Sources: google, bing, linkedin, twitter, all (default). "
        "Passive reconnaissance tool - safe for initial recon."
    ),
    parameters={
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Target domain"},
            "source": {"type": "string", "description": "Data source: google, bing, linkedin, twitter, all", "default": "all"},
            "limit": {"type": "integer", "description": "Max results per source", "default": 500},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300},
        },
        "required": ["domain"],
    },
    handler=_theharvester_handler,
    requires_approval=False,
    requires_scope_target="domain",
    dangerous=False,
)


def _shodan_handler(query: str, api_key: str = "",
                    max_results: int = 100) -> ToolResult:
    """Search Shodan for internet-connected devices."""
    import os
    
    key = api_key or os.environ.get("SHODAN_API_KEY", "")
    if not key:
        return ToolResult(
            success=False,
            output="Shodan API key required. Set SHODAN_API_KEY environment variable.",
            error="missing_api_key",
        )
    
    try:
        import httpx
        url = f"https://api.shodan.io/shodan/host/search?key={key}&query={query}&limit={max_results}"
        
        with httpx.Client(timeout=30) as client:
            resp = client.get(url)
        
        if resp.status_code != 200:
            return ToolResult(
                success=False,
                output=f"Shodan API error: {resp.status_code} - {resp.text}",
                error="api_error",
            )
        
        data = resp.json()
        results = data.get("matches", [])
        
        output_lines = [f"Shodan results for '{query}' ({len(results)} matches):"]
        for i, match in enumerate(results[:20], 1):
            ip = match.get("ip_str", "unknown")
            ports = match.get("ports", [])
            org = match.get("org", "unknown")
            output_lines.append(f"\n{i}. {ip} (Org: {org})")
            output_lines.append(f"   Ports: {', '.join(map(str, ports[:10]))}")
            if "data" in match:
                output_lines.append(f"   Banner: {match['data'][:200]}")
        
        return ToolResult(
            success=True,
            output="\n".join(output_lines),
            data={"matches": results, "total": len(results)},
        )
    except Exception as e:
        return ToolResult(success=False, output=f"Shodan search error: {e}", error=str(e))


SHODAN_TOOL = Tool(
    name="offensive_shodan",
    description=(
        "Search Shodan database for internet-connected devices. "
        "Queries: 'apache port:80', 'country:US city:Chicago', 'ssl.cert.subject.cn:example.com'. "
        "Requires SHODAN_API_KEY environment variable or provide api_key parameter."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Shodan search query"},
            "api_key": {"type": "string", "description": "Shodan API key (optional, can use env var)", "default": ""},
            "max_results": {"type": "integer", "description": "Maximum results to return", "default": 100},
        },
        "required": ["query"],
    },
    handler=_shodan_handler,
    requires_approval=False,
    dangerous=False,
)


# Continue with more tools...
OFFENSIVE_TOOLS = [
    NMAP_ADVANCED_TOOL,
    MASSCAN_TOOL,
    RUSTSCAN_TOOL,
    NAABU_TOOL,
    AMASS_TOOL,
    THEHARVESTER_TOOL,
    SHODAN_TOOL,
]
