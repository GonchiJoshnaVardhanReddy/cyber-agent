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


# =============================================================================
# SUBDOMAIN ENUMERATION TOOLS
# =============================================================================

def _subfinder_handler(domain: str, timeout: int = 300) -> ToolResult:
    """Fast subdomain enumeration with Subfinder."""
    if not _check_tool_installed("subfinder"):
        install_cmd = "go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
        return ToolResult(
            success=False,
            output=f"subfinder is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["subfinder", "-d", domain, "-timeout", str(timeout)]
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    subdomains = [line.strip() for line in out.split("\n") if line.strip()]
    
    return ToolResult(
        success=rc == 0 or subdomains,
        output=f"Found {len(subdomains)} subdomains:\\n" + "\\n".join(subdomains[:100]),
        data={"returncode": rc, "subdomain_count": len(subdomains), "subdomains": subdomains},
    )


SUBFINDER_TOOL = Tool(
    name="offensive_subfinder",
    description=(
        "Subfinder - Fast passive subdomain enumeration tool. "
        "Uses multiple sources like certificate transparency, DNS, etc. "
        "Good for initial recon phase. Returns list of discovered subdomains."
    ),
    parameters={
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Target domain"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300},
        },
        "required": ["domain"],
    },
    handler=_subfinder_handler,
    requires_approval=False,
    requires_scope_target="domain",
    dangerous=False,
)


def _assetfinder_handler(domain: str, timeout: int = 120) -> ToolResult:
    """Find domains and subdomains related to a target with assetfinder."""
    if not _check_tool_installed("assetfinder"):
        install_cmd = "go install github.com/tomnomnom/assetfinder@latest"
        return ToolResult(
            success=False,
            output=f"assetfinder is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["assetfinder", "--subs-only", domain]
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    subdomains = [line.strip() for line in out.split("\n") if line.strip()]
    
    return ToolResult(
        success=rc == 0 or subdomains,
        output=f"Found {len(subdomains)} subdomains:\\n" + "\\n".join(subdomains[:100]),
        data={"returncode": rc, "subdomain_count": len(subdomains)},
    )


ASSETFINDER_TOOL = Tool(
    name="offensive_assetfinder",
    description=(
        "assetfinder - Find domains and subdomains related to a target. "
        "Passive only, uses various public sources. "
        "Fast and lightweight, good for quick subdomain discovery."
    ),
    parameters={
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Target domain"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 120},
        },
        "required": ["domain"],
    },
    handler=_assetfinder_handler,
    requires_approval=False,
    requires_scope_target="domain",
    dangerous=False,
)


# =============================================================================
# WEB VULNERABILITY SCANNERS
# =============================================================================

def _nikto_handler(target: str, port: int = 80, ssl: bool = False,
                   timeout: int = 600) -> ToolResult:
    """Web server scanner with Nikto."""
    if not _check_tool_installed("nikto"):
        install_cmd = _install_command("nikto", "nikto")
        return ToolResult(
            success=False,
            output=f"nikto is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["nikto", "-h", target, "-p", str(port), "-T", "1"]
    if ssl:
        cmd.extend(["-ssl"])
    
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    # Parse findings from nikto output
    findings = []
    for line in out.split("\n"):
        if "+ " in line:
            findings.append(line.strip())
    
    return ToolResult(
        success=rc == 0 or out,
        output=out[:15000] if out else err,
        data={"returncode": rc, "findings_count": len(findings)},
    )


NIKTO_TOOL = Tool(
    name="offensive_nikto",
    description=(
        "Nikto - Web server scanner that tests for dangerous files, CGI, "
        "outdated software, and other vulnerabilities. "
        "Comprehensive but can be noisy. Good for initial web assessment."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target IP or hostname"},
            "port": {"type": "integer", "description": "Target port", "default": 80},
            "ssl": {"type": "boolean", "description": "Use SSL/HTTPS", "default": False},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 600},
        },
        "required": ["target"],
    },
    handler=_nikto_handler,
    requires_approval=True,
    requires_scope_target="target",
    dangerous=False,
)


def _nuclei_handler(target: str, templates: str = "",
                    severity: str = "", timeout: int = 600) -> ToolResult:
    """Fast vulnerability scanner with Nuclei."""
    if not _check_tool_installed("nuclei"):
        install_cmd = "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
        return ToolResult(
            success=False,
            output=f"nuclei is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["nuclei", "-u", target, "-json"]
    if templates:
        cmd.extend(["-t", templates])
    if severity:
        cmd.extend(["-severity", severity])
    
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    # Parse JSON output
    findings = []
    for line in out.split("\n"):
        if line.strip():
            try:
                import json
                findings.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # Skip malformed JSON lines
    
    return ToolResult(
        success=rc == 0 or findings,
        output=f"Found {len(findings)} potential vulnerabilities:\n" + 
               "\n".join([f"- {f.get('template-id', 'unknown')}: {f.get('name', '')} [{f.get('severity', 'unknown')}]" for f in findings[:20]]),
        data={"returncode": rc, "findings": findings},
    )


NUCLEI_TOOL = Tool(
    name="offensive_nuclei",
    description=(
        "Nuclei - Fast and customizable vulnerability scanner. "
        "Uses template-based scanning for thousands of known vulnerabilities. "
        "Supports severity filtering. Returns structured findings."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target URL or IP"},
            "templates": {"type": "string", "description": "Specific templates to use (comma-separated)", "default": ""},
            "severity": {"type": "string", "description": "Filter by severity: critical,high,medium,low,info", "default": ""},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 600},
        },
        "required": ["target"],
    },
    handler=_nuclei_handler,
    requires_approval=True,
    requires_scope_target="target",
    dangerous=False,
)


def _ffuf_handler(url: str, wordlist: str = "",
                  extensions: str = "", timeout: int = 300) -> ToolResult:
    """Fast web fuzzer for directory/file discovery with ffuf."""
    if not _check_tool_installed("ffuf"):
        install_cmd = "go install -v github.com/ffuf/ffuf/v2@latest"
        return ToolResult(
            success=False,
            output=f"ffuf is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    wl = wordlist or "/usr/share/wordlists/dirb/common.txt"
    cmd = ["ffuf", "-u", url, "-w", f"{wl}:FUZZ", "-mc", "200,204,301,302,307,401,403", "-json"]
    if extensions:
        cmd.extend(["-e", extensions])
    
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    # Parse JSON output
    results = []
    for line in out.split("\n"):
        if line.strip():
            try:
                import json
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # Skip malformed JSON lines
    
    found_paths = [r.get('url', '') for r in results if r.get('status') in [200, 301, 302]]
    
    return ToolResult(
        success=rc == 0 or results,
        output=f"Found {len(found_paths)} interesting paths:\\n" + "\\n".join(found_paths[:30]),
        data={"returncode": rc, "results": results},
    )


FFUF_TOOL = Tool(
    name="offensive_ffuf",
    description=(
        "ffuf - Fast web fuzzer written in Go. "
        "Used for directory/file discovery, parameter fuzzing, vhost discovery. "
        "Uses wordlists. Default wordlist: /usr/share/wordlists/dirb/common.txt"
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target URL with FUZZ keyword, e.g., 'https://example.com/FUZZ'"},
            "wordlist": {"type": "string", "description": "Path to wordlist file", "default": ""},
            "extensions": {"type": "string", "description": "File extensions to test, e.g., '.php,.asp,.txt'", "default": ""},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300},
        },
        "required": ["url"],
    },
    handler=_ffuf_handler,
    requires_approval=True,
    requires_scope_target="url",
    dangerous=False,
)


def _gobuster_handler(target: str, mode: str = "dir",
                      wordlist: str = "", timeout: int = 300) -> ToolResult:
    """Directory/file and DNS busting with Gobuster."""
    if not _check_tool_installed("gobuster"):
        install_cmd = "go install github.com/OJ/gobuster/v3@latest"
        return ToolResult(
            success=False,
            output=f"gobuster is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    wl = wordlist or "/usr/share/wordlists/dirb/common.txt"
    
    if mode == "dir":
        cmd = ["gobuster", "dir", "-u", target, "-w", wl]
    elif mode == "dns":
        cmd = ["gobuster", "dns", "-d", target, "-w", wl]
    else:
        return ToolResult(success=False, output=f"Unknown mode: {mode}", error="invalid_mode")
    
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    return ToolResult(
        success=rc == 0 or out,
        output=out[:15000] if out else err,
        data={"returncode": rc},
    )


GOBUSTER_TOOL = Tool(
    name="offensive_gobuster",
    description=(
        "Gobuster - Directory/file and DNS busting tool. "
        "Modes: 'dir' (directory brute-forcing), 'dns' (subdomain brute-forcing). "
        "Uses wordlists for brute-force attacks."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target URL (for dir mode) or domain (for dns mode)"},
            "mode": {"type": "string", "description": "Operation mode: dir or dns", "default": "dir"},
            "wordlist": {"type": "string", "description": "Path to wordlist file", "default": ""},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300},
        },
        "required": ["target"],
    },
    handler=_gobuster_handler,
    requires_approval=True,
    requires_scope_target="target",
    dangerous=False,
)


# =============================================================================
# EXPLOITATION TOOLS
# =============================================================================

def _sqlmap_handler(url: str, data: str = "", dbms: str = "",
                    level: int = 1, risk: int = 1,
                    timeout: int = 600) -> ToolResult:
    """SQL injection detection and exploitation with sqlmap."""
    if not _check_tool_installed("sqlmap"):
        install_cmd = _install_command("sqlmap", "sqlmap")
        return ToolResult(
            success=False,
            output=f"sqlmap is not installed. Install with: {install_cmd}",
            error="not_installed",
        )
    
    cmd = ["sqlmap", "-u", url, "--batch", "--level", str(level), "--risk", str(risk)]
    if data:
        cmd.extend(["--data", data])
    if dbms:
        cmd.extend(["--dbms", dbms])
    
    rc, out, err = _run_subprocess(cmd, timeout=timeout)
    
    return ToolResult(
        success=rc == 0 or out,
        output=out[:15000] if out else err,
        data={"returncode": rc},
    )


SQLMAP_TOOL = Tool(
    name="offensive_sqlmap",
    description=(
        "⚠️ sqlmap - Automatic SQL injection and database takeover tool. "
        "DANGEROUS: Can cause data loss or service disruption. "
        "ALWAYS requires explicit human approval. "
        "Use only on authorized targets with proper scope. "
        "Level (1-5) and risk (1-3) control aggressiveness."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target URL with vulnerable parameter"},
            "data": {"type": "string", "description": "POST data (optional)", "default": ""},
            "dbms": {"type": "string", "description": "Force DBMS type: mysql, postgresql, mssql, oracle", "default": ""},
            "level": {"type": "integer", "description": "Test level 1-5 (higher = more tests)", "default": 1},
            "risk": {"type": "integer", "description": "Risk level 1-3 (higher = more aggressive)", "default": 1},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 600},
        },
        "required": ["url"],
    },
    handler=_sqlmap_handler,
    requires_approval=True,
    requires_scope_target="url",
    dangerous=True,
)


# =============================================================================
# COMPLETE TOOL LIST
# =============================================================================

OFFENSIVE_TOOLS = [
    # Network Scanners
    NMAP_ADVANCED_TOOL,
    MASSCAN_TOOL,
    RUSTSCAN_TOOL,
    NAABU_TOOL,
    
    # OSINT
    AMASS_TOOL,
    THEHARVESTER_TOOL,
    SHODAN_TOOL,
    
    # Subdomain Enumeration
    SUBFINDER_TOOL,
    ASSETFINDER_TOOL,
    
    # Web Vulnerability Scanners
    NIKTO_TOOL,
    NUCLEI_TOOL,
    FFUF_TOOL,
    GOBUSTER_TOOL,
    
    # Exploitation
    SQLMAP_TOOL,
]
