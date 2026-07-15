#!/usr/bin/env python3
"""scripts/setup.py — Smart installer for Cyber Agent.

This script detects your OS and installs missing security tools automatically.
It supports Linux (Ubuntu/Debian/Kali), macOS, and Windows (WSL).

Features:
1. OS Detection: Automatically detects your operating system
2. Tool Inventory: Maintains a manifest of ~15 critical security tools
3. State Check: Checks if each tool is installed via `which <tool>` or `<tool> --version`
4. Auto-Remediation: Generates specific install commands for your OS
5. Docker Option: Offers to run inside a pre-configured Kali Linux Docker container
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class ToolInfo:
    """Information about a security tool."""
    name: str
    description: str
    category: str  # network_scanner | osint | subdomain_enum | web_scanner | exploitation
    package_names: dict[str, str] = field(default_factory=dict)  # os -> package name
    install_url: str = ""  # fallback installation URL
    requires_root: bool = False


# =============================================================================
# TOOL INVENTORY
# =============================================================================

TOOL_INVENTORY = [
    ToolInfo(
        name="nmap",
        description="Network exploration and security auditing",
        category="network_scanner",
        package_names={
            "debian": "nmap",
            "arch": "nmap",
            "macos": "nmap",
        },
        requires_root=False,
    ),
    ToolInfo(
        name="masscan",
        description="Fastest port scanner (TCP SYN scanner)",
        category="network_scanner",
        package_names={
            "debian": "masscan",
            "arch": "masscan",
            "macos": "masscan",
        },
        requires_root=True,
    ),
    ToolInfo(
        name="rustscan",
        description="Modern fast port scanner written in Rust",
        category="network_scanner",
        package_names={
            "debian": "rustscan",
            "arch": "rustscan",
        },
        install_url="cargo install rustscan",
        requires_root=False,
    ),
    ToolInfo(
        name="naabu",
        description="Fast port scanner by ProjectDiscovery",
        category="network_scanner",
        package_names={
            "debian": "naabu",
            "arch": "naabu",
        },
        install_url="go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest",
        requires_root=False,
    ),
    ToolInfo(
        name="amass",
        description="Comprehensive attack surface mapping and OSINT",
        category="osint",
        package_names={
            "debian": "amass",
            "arch": "amass",
        },
        install_url="go install github.com/owasp-amass/amass/v4/...@latest",
        requires_root=False,
    ),
    ToolInfo(
        name="theHarvester",
        description="Email, subdomain, and host harvesting from public sources",
        category="osint",
        package_names={
            "debian": "theharvester",
            "arch": "theharvester",
            "macos": "theHarvester",
        },
        requires_root=False,
    ),
    ToolInfo(
        name="subfinder",
        description="Fast subdomain enumeration tool",
        category="subdomain_enum",
        package_names={
            "debian": "subfinder",
            "arch": "subfinder",
        },
        install_url="go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
        requires_root=False,
    ),
    ToolInfo(
        name="assetfinder",
        description="Find domains and subdomains related to a target",
        category="subdomain_enum",
        package_names={},
        install_url="go install github.com/tomnomnom/assetfinder@latest",
        requires_root=False,
    ),
    ToolInfo(
        name="dnsrecon",
        description="DNS enumeration and reconnaissance",
        category="subdomain_enum",
        package_names={
            "debian": "dnsrecon",
            "arch": "dnsrecon",
            "macos": "dnsrecon",
        },
        requires_root=False,
    ),
    ToolInfo(
        name="nikto",
        description="Web server scanner for vulnerabilities",
        category="web_scanner",
        package_names={
            "debian": "nikto",
            "arch": "nikto",
            "macos": "nikto",
        },
        requires_root=False,
    ),
    ToolInfo(
        name="nuclei",
        description="Fast and customizable vulnerability scanner",
        category="web_scanner",
        package_names={
            "debian": "nuclei",
            "arch": "nuclei",
        },
        install_url="go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
        requires_root=False,
    ),
    ToolInfo(
        name="ffuf",
        description="Fast web fuzzer for directory/file discovery",
        category="web_scanner",
        package_names={
            "debian": "ffuf",
            "arch": "ffuf",
        },
        install_url="go install -v github.com/ffuf/ffuf/v2@latest",
        requires_root=False,
    ),
    ToolInfo(
        name="gobuster",
        description="Directory/file and DNS busting tool",
        category="web_scanner",
        package_names={
            "debian": "gobuster",
            "arch": "gobuster",
            "macos": "gobuster",
        },
        install_url="go install github.com/OJ/gobuster/v3@latest",
        requires_root=False,
    ),
    ToolInfo(
        name="sqlmap",
        description="Automatic SQL injection and database takeover tool",
        category="exploitation",
        package_names={
            "debian": "sqlmap",
            "arch": "sqlmap",
            "macos": "sqlmap",
        },
        requires_root=False,
    ),
    ToolInfo(
        name="metasploit-framework",
        description="Penetration testing framework",
        category="exploitation",
        package_names={
            "debian": "metasploit-framework",
            "arch": "metasploit",
            "macos": "metasploit",
        },
        install_url="https://docs.rapid7.com/metasploit/installing-the-metasploit-framework/",
        requires_root=True,
    ),
]


# =============================================================================
# OS DETECTION
# =============================================================================

def detect_os() -> tuple[str, str]:
    """Detect the operating system and package manager.
    
    Returns:
        Tuple of (os_type, package_manager)
        os_type: 'debian', 'arch', 'macos', 'windows'
        package_manager: 'apt', 'pacman', 'brew', None
    """
    os_type = "unknown"
    package_manager = None
    
    # Check for Windows
    if sys.platform == "win32":
        return "windows", None
    
    # Check for macOS
    if sys.platform == "darwin":
        os_type = "macos"
        if shutil.which("brew"):
            package_manager = "brew"
        return os_type, package_manager
    
    # Check for Linux
    if sys.platform == "linux":
        # Try to read /etc/os-release
        os_release = Path("/etc/os-release")
        if os_release.exists():
            content = os_release.read_text()
            if "ID=kali" in content or "ID=kali" in content:
                os_type = "debian"
                package_manager = "apt"
            elif "ID=ubuntu" in content or "ID_LIKE=ubuntu" in content:
                os_type = "debian"
                package_manager = "apt"
            elif "ID=debian" in content or "ID=debian" in content:
                os_type = "debian"
                package_manager = "apt"
            elif "ID=arch" in content or "ID_LIKE=arch" in content:
                os_type = "arch"
                package_manager = "pacman"
            elif "ID=fedora" in content:
                os_type = "fedora"
                package_manager = "dnf"
        
        # Fallback: check for package managers
        if not package_manager:
            if shutil.which("apt"):
                os_type = "debian"
                package_manager = "apt"
            elif shutil.which("pacman"):
                os_type = "arch"
                package_manager = "pacman"
            elif shutil.which("dnf"):
                os_type = "fedora"
                package_manager = "dnf"
            elif shutil.which("yum"):
                os_type = "fedora"
                package_manager = "yum"
    
    return os_type, package_manager


# =============================================================================
# TOOL CHECKING
# =============================================================================

def check_tool_installed(tool_name: str) -> bool:
    """Check if a tool is installed using which command."""
    return shutil.which(tool_name) is not None


def get_missing_tools(tools: list[ToolInfo]) -> list[ToolInfo]:
    """Return list of tools that are not installed."""
    missing = []
    for tool in tools:
        if not check_tool_installed(tool.name):
            missing.append(tool)
    return missing


def generate_install_command(tool: ToolInfo, os_type: str, package_manager: str | None) -> str:
    """Generate the installation command for a tool on the current OS."""
    if package_manager and tool.name in tool.package_names.get(os_type, []):
        package = tool.package_names[os_type]
        if package_manager == "apt":
            return f"sudo apt update && sudo apt install -y {package}"
        elif package_manager == "pacman":
            return f"sudo pacman -S --noconfirm {package}"
        elif package_manager == "dnf":
            return f"sudo dnf install -y {package}"
        elif package_manager == "brew":
            return f"brew install {package}"
    
    # Fallback to custom install URL
    if tool.install_url:
        return tool.install_url
    
    return f"# Manual installation required for {tool.name}"


# =============================================================================
# DOCKER SETUP
# =============================================================================

def check_docker_installed() -> bool:
    """Check if Docker is installed and running."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def setup_kali_container() -> bool:
    """Set up a Kali Linux Docker container for running the agent.
    
    Returns:
        True if successful, False otherwise
    """
    print("\n[+] Setting up Kali Linux Docker container...")
    
    # Pull the Kali image
    print("[*] Pulling kalilinux/kali-rolling image...")
    try:
        subprocess.run(
            ["docker", "pull", "kalilinux/kali-rolling"],
            check=True,
            timeout=300,
        )
    except subprocess.CalledProcessError as e:
        print(f"[!] Failed to pull Kali image: {e}")
        return False
    except subprocess.TimeoutExpired:
        print("[!] Timeout pulling Kali image")
        return False
    
    # Create a run script
    run_script = Path("run_in_kali.sh")
    run_script.write_text("""\
#!/bin/bash
# Run Cyber Agent inside Kali Linux Docker container

echo "[*] Starting Kali Linux container with Cyber Agent..."

docker run -it --rm \\
    -v "$(pwd)":/workspace \\
    -w /workspace \\
    -e OPENAI_API_KEY="$OPENAI_API_KEY" \\
    -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \\
    -e GROQ_API_KEY="$GROQ_API_KEY" \\
    kalilinux/kali-rolling \\
    bash -c "
        apt update && \\
        apt install -y python3 python3-pip git curl wget nmap masscan nikto sqlmap && \\
        pip3 install cyber-agent && \\
        cyber-agent
    "
""")
    run_script.chmod(0o755)
    
    print(f"[+] Created {run_script}")
    print("[*] You can now run: ./run_in_kali.sh")
    
    return True


# =============================================================================
# MAIN INSTALLER
# =============================================================================

def main():
    """Main installer function."""
    print("=" * 60)
    print("Cyber Agent - Smart Installer")
    print("=" * 60)
    
    # Detect OS
    os_type, package_manager = detect_os()
    print(f"\n[*] Detected OS: {os_type}")
    print(f"[*] Package manager: {package_manager or 'None detected'}")
    
    # Check for missing tools
    print("\n[*] Checking for installed tools...")
    missing_tools = get_missing_tools(TOOL_INVENTORY)
    
    if not missing_tools:
        print("[+] All security tools are already installed!")
        print("\nYou can start using Cyber Agent right away.")
        return
    
    print(f"\n[!] Found {len(missing_tools)} missing tools:")
    for tool in missing_tools:
        root_marker = " [requires root]" if tool.requires_root else ""
        print(f"  - {tool.name}: {tool.description}{root_marker}")
    
    # Ask user if they want to install
    print("\n" + "=" * 60)
    choice = input("Install missing tools now? [Y/n]: ").strip().lower()
    
    if choice in ("", "y", "yes"):
        print("\n[*] Generating installation commands...")
        
        for tool in missing_tools:
            cmd = generate_install_command(tool, os_type, package_manager)
            print(f"\n  {tool.name}:")
            print(f"    {cmd}")
            
            # Ask to run this specific command
            if tool.requires_root and "sudo" not in cmd:
                print(f"    [!] This tool requires root privileges")
            
            run_choice = input(f"    Run this command now? [Y/n]: ").strip().lower()
            if run_choice in ("", "y", "yes"):
                try:
                    # Split command for subprocess
                    if cmd.startswith("sudo"):
                        # For sudo commands, we need to run in shell
                        subprocess.run(cmd, shell=True, check=True)
                    elif "go install" in cmd or "cargo install" in cmd:
                        # For go/cargo installs, run in shell
                        subprocess.run(cmd, shell=True, check=True)
                    else:
                        parts = cmd.split()
                        subprocess.run(parts, check=True)
                    print(f"    [+] Installation successful!")
                except subprocess.CalledProcessError as e:
                    print(f"    [!] Installation failed: {e}")
                except Exception as e:
                    print(f"    [!] Error: {e}")
    
    # Offer Docker alternative
    print("\n" + "=" * 60)
    print("\nAlternative: Run inside a pre-configured Kali Linux Docker container?")
    print("This ensures all tools are present without polluting your host OS.")
    
    if check_docker_installed():
        docker_choice = input("Set up Kali Docker container? [y/N]: ").strip().lower()
        if docker_choice in ("y", "yes"):
            success = setup_kali_container()
            if success:
                print("\n[+] Docker setup complete!")
                print("[*] Run './run_in_kali.sh' to start Cyber Agent in Kali container")
    else:
        print("[!] Docker is not installed or not running")
        print("[*] Install Docker from https://docs.docker.com/get-docker/")
    
    print("\n" + "=" * 60)
    print("\nInstallation complete!")
    print("\nNext steps:")
    print("1. Copy config.yaml.example to config.yaml and edit it")
    print("2. Set up your .env file with API keys")
    print("3. Create and sign your RULES_OF_ENGAGEMENT.md file")
    print("4. Run: cyber-agent")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
