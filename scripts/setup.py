#!/usr/bin/env python3
"""scripts/setup.py — Interactive Smart Installer for Cyber Agent.

This script provides an interactive menu-driven interface for:
1. Selecting security tools to install using arrow keys and spacebar
2. Choosing Docker/Kali container setup
3. Configuring LLM providers (Ollama, OpenAI, Anthropic, etc.)
4. Auto-detecting and pulling Ollama models
5. Setting up API keys for cloud providers

Usage:
    python scripts/setup.py
    
Navigation:
    ↑/↓ : Move up/down in menu
    Space : Select/deselect item
    Enter : Confirm selection
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
import json

# Try to import readchar for interactive menu, fallback to basic input
try:
    import readchar
    HAS_READCHAR = True
except ImportError:
    HAS_READCHAR = False
    print("[!] Installing readchar for interactive menus...")
    subprocess.run([sys.executable, "-m", "pip", "install", "readchar", "-q"])
    import readchar
    HAS_READCHAR = True


@dataclass
class ToolInfo:
    """Information about a security tool."""
    name: str
    description: str
    category: str  # network_scanner | osint | subdomain_enum | web_scanner | exploitation
    package_names: dict[str, str] = field(default_factory=dict)  # os -> package name
    install_url: str = ""  # fallback installation URL
    requires_root: bool = False
    installed: bool = False


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
# INTERACTIVE MENU FUNCTIONS
# =============================================================================

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title: str):
    """Print a styled header."""
    clear_screen()
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def interactive_tool_menu(tools: list[ToolInfo]) -> list[ToolInfo]:
    """Interactive menu for selecting tools to install.
    
    Navigation:
        UP/DOWN arrows: Move selection
        SPACE: Toggle selection
        ENTER: Confirm and continue
    """
    selected_indices = set()
    current_index = 0
    
    # Mark already installed tools
    for i, tool in enumerate(tools):
        if check_tool_installed(tool.name):
            tool.installed = True
            selected_indices.add(i)  # Auto-select installed tools
    
    while True:
        print_header("SELECT TOOLS TO INSTALL")
        print("Navigation: ↑/↓ = Move | SPACE = Select/Deselect | ENTER = Confirm\n")
        print("Already installed tools are pre-selected (✓).\n")
        
        # Display tools
        for i, tool in enumerate(tools):
            cursor = "► " if i == current_index else "  "
            
            if tool.installed:
                status = "✓"
                color_code = "\033[92m"  # Green
            elif i in selected_indices:
                status = "☑"
                color_code = "\033[94m"  # Blue
            else:
                status = "☐"
                color_code = "\033[90m"  # Gray
            
            reset = "\033[0m"
            category_tag = f"[{tool.category}]"
            
            print(f"{cursor}{color_code}{status} {tool.name:<25} {category_tag:<18} {tool.description}{reset}")
        
        print(f"\n\nSelected: {len(selected_indices)}/{len(tools)} tools")
        print("Press ENTER to proceed with installation...")
        
        # Get key input
        try:
            key = readchar.readkey()
            
            if key == readchar.key.UP:
                current_index = max(0, current_index - 1)
            elif key == readchar.key.DOWN:
                current_index = min(len(tools) - 1, current_index + 1)
            elif key == " ":
                # Toggle selection (skip already installed tools)
                if not tools[current_index].installed:
                    if current_index in selected_indices:
                        selected_indices.remove(current_index)
                    else:
                        selected_indices.add(current_index)
            elif key in (readchar.key.ENTER, "\n", "\r"):
                break
        except KeyboardInterrupt:
            print("\n\nInstallation cancelled.")
            sys.exit(0)
    
    # Return selected tools that aren't already installed
    return [tools[i] for i in selected_indices if not tools[i].installed]


def interactive_docker_menu() -> bool:
    """Interactive menu for Docker/Kali setup."""
    print_header("DOCKER SETUP")
    
    if not check_docker_installed():
        print("⚠️  Docker is NOT installed on your system.\n")
        print("Docker provides an isolated Kali Linux environment with all tools pre-installed.")
        print("This is recommended to avoid polluting your host OS.\n")
        choice = input("Would you like to install Docker first? [y/N]: ").strip().lower()
        
        if choice in ("y", "yes"):
            print("\n[*] Installing Docker...")
            if sys.platform == "linux":
                try:
                    subprocess.run([
                        "curl", "-fsSL", "https://get.docker.com", "|", "sh"
                    ], shell=True, check=True)
                    print("[+] Docker installed successfully!")
                    print("[!] You may need to log out and log back in for changes to take effect.")
                except subprocess.CalledProcessError:
                    print("[!] Failed to install Docker automatically.")
                    print("[*] Please install Docker manually from https://docs.docker.com/get-docker/")
            else:
                print("[*] Please install Docker Desktop from https://www.docker.com/products/docker-desktop/")
            return False
        else:
            return False
    
    print("✓ Docker is installed and ready.\n")
    print("Using Docker with Kali Linux provides:")
    print("  • Pre-configured security tools environment")
    print("  • Isolation from your host system")
    print("  • Consistent tool versions across systems\n")
    
    print("Navigation: ↑/↓ = Move | ENTER = Select\n")
    print("  ► Use Docker with Kali Linux container (Recommended)")
    print("    Skip Docker setup (Install tools directly on host)\n")
    
    current = 0
    while True:
        try:
            key = readchar.readkey()
            
            if key == readchar.key.UP:
                current = 0
            elif key == readchar.key.DOWN:
                current = 1
            elif key in (readchar.key.ENTER, "\n", "\r"):
                if current == 0:
                    return True
                else:
                    return False
        except KeyboardInterrupt:
            return False


def interactive_provider_menu() -> dict:
    """Interactive menu for LLM provider configuration."""
    print_header("LLM PROVIDER CONFIGURATION")
    
    providers = [
        {"name": "Ollama (Local)", "type": "ollama", "desc": "Run models locally, free, no API keys"},
        {"name": "OpenAI", "type": "openai", "desc": "GPT-4, GPT-3.5-turbo via API"},
        {"name": "Anthropic", "type": "anthropic", "desc": "Claude models via API"},
        {"name": "Groq", "type": "groq", "desc": "Fast inference for open models"},
        {"name": "Custom OpenAI-compatible", "type": "custom", "desc": "vLLM, LM Studio, etc."},
    ]
    
    current = 0
    while True:
        print_header("SELECT LLM PROVIDER")
        print("Navigation: ↑/↓ = Move | ENTER = Select\n")
        
        for i, provider in enumerate(providers):
            cursor = "► " if i == current else "  "
            name_color = "\033[96m" if i == current else "\033[0m"
            reset = "\033[0m"
            print(f"{cursor}{name_color}{provider['name']:<30} {provider['desc']}{reset}")
        
        try:
            key = readchar.readkey()
            
            if key == readchar.key.UP:
                current = max(0, current - 1)
            elif key == readchar.key.DOWN:
                current = min(len(providers) - 1, current + 1)
            elif key in (readchar.key.ENTER, "\n", "\r"):
                selected = providers[current]
                
                if selected["type"] == "ollama":
                    return configure_ollama()
                elif selected["type"] in ("openai", "anthropic", "groq"):
                    return configure_api_provider(selected)
                elif selected["type"] == "custom":
                    return configure_custom_provider()
        except KeyboardInterrupt:
            print("\n\nSetup cancelled.")
            sys.exit(0)


def get_ollama_models() -> list[str]:
    """Get list of installed Ollama models."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            models = []
            for line in lines:
                if line.strip():
                    model_name = line.split()[0].split(":")[0]
                    models.append(model_name)
            return models
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


def pull_ollama_model(model_name: str) -> bool:
    """Pull an Ollama model."""
    print(f"\n[*] Pulling {model_name}... This may take a few minutes.")
    try:
        subprocess.run(["ollama", "pull", model_name], check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"[!] Failed to pull {model_name}")
        return False


def interactive_ollama_model_menu(installed_models: list[str], recommended: list[str]) -> dict:
    """Interactive menu for selecting/pulling Ollama models.
    
    Navigation:
        UP/DOWN arrows: Move selection
        SPACE: Select/deselect model to pull
        ENTER: Confirm selection
        P: Pull selected model
        C: Enter custom model name
        B: Go back to provider selection
    """
    current_index = 0
    selected_for_pull = set()
    
    while True:
        print_header("OLLAMA MODEL SELECTION")
        print("Navigation: ↑/↓ = Move | SPACE = Select to pull | ENTER = Use model")
        print("            P = Pull selected | C = Custom model | B = Back\n")
        
        if installed_models:
            print("\033[92m═══ INSTALLED MODELS ═══\033[0m\n")
            for i, model in enumerate(installed_models):
                cursor = "► " if i == current_index else "  "
                print(f"{cursor}\033[96m{model}\033[0m")
            print()
        
        print("\033[93m═══ RECOMMENDED MODELS (for Cyber Agent) ═══\033[0m\n")
        rec_start_idx = len(installed_models)
        for i, model in enumerate(recommended):
            actual_idx = rec_start_idx + i
            cursor = "► " if actual_idx == current_index else "  "
            
            is_installed = model.split(":")[0] in [m.split(":")[0] for m in installed_models]
            is_selected = i in selected_for_pull
            
            if is_installed:
                status = "✓"
                color = "\033[92m"  # Green
            elif is_selected:
                status = "☑"
                color = "\033[94m"  # Blue
            else:
                status = "☐"
                color = "\033[90m"  # Gray
            
            reset = "\033[0m"
            print(f"{cursor}{color}{status} {model}{reset}")
        
        print(f"\n\nCursor: {current_index}/{len(installed_models) + len(recommended) - 1}")
        print(f"Selected to pull: {len(selected_for_pull)} model(s)")
        print("\nPress ENTER to use highlighted model, SPACE to select for pulling")
        
        try:
            key = readchar.readkey()
            
            if key == readchar.key.UP:
                current_index = max(0, current_index - 1)
            elif key == readchar.key.DOWN:
                current_index = min(len(installed_models) + len(recommended) - 1, current_index + 1)
            elif key == " ":
                # Toggle selection for pulling (only for recommended, not installed)
                if current_index >= len(installed_models):
                    rec_idx = current_index - len(installed_models)
                    if rec_idx in selected_for_pull:
                        selected_for_pull.remove(rec_idx)
                    else:
                        selected_for_pull.add(rec_idx)
            elif key in (readchar.key.ENTER, "\n", "\r"):
                # Use the currently highlighted model
                if current_index < len(installed_models):
                    return {"provider": "ollama", "model": installed_models[current_index]}
                else:
                    rec_idx = current_index - len(installed_models)
                    model_to_use = recommended[rec_idx]
                    # Check if it's installed, if not pull it
                    if model_to_use not in installed_models:
                        print(f"\n[*] Pulling {model_to_use}...")
                        if pull_ollama_model(model_to_use):
                            return {"provider": "ollama", "model": model_to_use}
                        else:
                            print("[!] Failed to pull model. Try another.")
                            time.sleep(2)
                    else:
                        return {"provider": "ollama", "model": model_to_use}
            elif key.lower() == 'p':
                # Pull selected models
                if selected_for_pull:
                    print("\n[*] Pulling selected models...")
                    for rec_idx in selected_for_pull:
                        if pull_ollama_model(recommended[rec_idx]):
                            print(f"[+] {recommended[rec_idx]} pulled successfully!")
                    selected_for_pull.clear()
                    # Refresh installed models
                    installed_models = get_ollama_models()
                    current_index = 0
                    input("\nPress ENTER to continue...")
            elif key.lower() == 'c':
                # Custom model entry
                clear_screen()
                print_header("CUSTOM OLLAMA MODEL")
                model_name = input("Enter model name (e.g., qwen2.5-coder:7b): ").strip()
                if model_name:
                    pull_choice = input(f"\nPull {model_name} now? [Y/n]: ").strip().lower()
                    if pull_choice != "n":
                        if pull_ollama_model(model_name):
                            return {"provider": "ollama", "model": model_name}
                    return {"provider": "ollama", "model": model_name}
            elif key.lower() == 'b':
                return interactive_provider_menu()
        except KeyboardInterrupt:
            print("\n\nSetup cancelled.")
            sys.exit(0)
    
    # Fallback if no models and user doesn't enter custom
    return interactive_provider_menu()


def configure_ollama() -> dict:
    """Configure Ollama provider."""
    print_header("OLLAMA CONFIGURATION")
    
    # Check if Ollama is running
    try:
        subprocess.run(["curl", "-s", "http://localhost:11434/api/tags"], 
                      capture_output=True, timeout=2, check=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        print("⚠️  Ollama doesn't appear to be running.")
        print("\nStarting Ollama service...")
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
    
    # Get available models
    models = get_ollama_models()
    
    # Recommended models for Cyber Agent (7B to 32B range as requested)
    recommended = [
        "qwen2.5-coder:7b",
        "qwen2.5-coder:14b", 
        "qwen2.5-coder:32b",
        "llama3.2:3b",
        "llama3.1:8b",
        "mistral:7b",
        "codellama:7b",
        "deepseek-coder:6.7b",
        "phi3:mini"
    ]
    
    if models:
        print(f"\033[92m✓ Found {len(models)} installed model(s)\033[0m\n")
    else:
        print("\033[93m⚠️  No Ollama models found installed.\033[0m\n")
        print("Don't worry! You can pull recommended models below.\n")
    
    time.sleep(1)
    
    # Launch interactive model selection menu
    return interactive_ollama_model_menu(models, recommended)


def configure_api_provider(provider_info: dict) -> dict:
    """Configure cloud API provider with interactive model selection."""
    print_header(f"{provider_info['name']} CONFIGURATION")
    
    api_key_var = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "groq": "GROQ_API_KEY"
    }.get(provider_info["type"], "API_KEY")
    
    print(f"To use {provider_info['name']}, you need an API key.\n")
    print(f"Get your API key from:")
    if provider_info["type"] == "openai":
        print("  https://platform.openai.com/api-keys\n")
    elif provider_info["type"] == "anthropic":
        print("  https://console.anthropic.com/settings/keys\n")
    elif provider_info["type"] == "groq":
        print("  https://console.groq.com/keys\n")
    
    api_key = input(f"Enter your {provider_info['name']} API key: ").strip()
    
    if not api_key:
        print("[!] API key required. Returning to provider selection.\n")
        time.sleep(1)
        return interactive_provider_menu()
    
    # Get available models for this provider
    models = get_provider_models(provider_info["type"], api_key)
    
    if models:
        print(f"\n\033[92m✓ Connected! Found {len(models)} model(s)\033[0m\n")
        time.sleep(1)
        # Launch interactive model selection
        return _interactive_api_model_menu(provider_info, api_key, models)
    
    # If no models fetched, use defaults
    print("\n[!] Could not fetch models. Using default model.")
    default_models = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-sonnet-20241022",
        "groq": "llama-3.3-70b-versatile"
    }
    default = default_models.get(provider_info["type"], "default-model")
    print(f"Default model: {default}")
    return {
        "provider": provider_info["type"],
        "api_key": api_key,
        "model": default
    }


def _interactive_api_model_menu(provider_info: dict, api_key: str, models: list[str]) -> dict:
    """Interactive menu for selecting a model from API provider.
    
    Navigation:
        UP/DOWN arrows: Move selection
        ENTER: Confirm selection
        C: Enter custom model name
        B: Go back
    """
    current_index = 0
    
    while True:
        print_header(f"{provider_info['name'].upper()} MODEL SELECTION")
        print("Navigation: ↑/↓ = Move | ENTER = Select | C = Custom model | B = Back\n")
        
        # Display models
        for i, model in enumerate(models[:20]):  # Show up to 20 models
            cursor = "► " if i == current_index else "  "
            color = "\033[96m" if i == current_index else "\033[0m"
            reset = "\033[0m"
            print(f"{cursor}{color}{model}{reset}")
        
        if len(models) > 20:
            print(f"\n... and {len(models) - 20} more models")
        
        print(f"\n\nCursor: {current_index}/{min(len(models), 20) - 1}")
        print("Press ENTER to select the highlighted model")
        
        try:
            key = readchar.readkey()
            
            if key == readchar.key.UP:
                current_index = max(0, current_index - 1)
            elif key == readchar.key.DOWN:
                current_index = min(min(len(models), 20) - 1, current_index + 1)
            elif key in (readchar.key.ENTER, "\n", "\r"):
                return {
                    "provider": provider_info["type"],
                    "api_key": api_key,
                    "model": models[current_index]
                }
            elif key.lower() == 'c':
                clear_screen()
                print_header("CUSTOM MODEL NAME")
                custom_model = input("Enter model name: ").strip()
                if custom_model:
                    return {
                        "provider": provider_info["type"],
                        "api_key": api_key,
                        "model": custom_model
                    }
            elif key.lower() == 'b':
                return interactive_provider_menu()
        except KeyboardInterrupt:
            print("\n\nSetup cancelled.")
            sys.exit(0)
    
    # Fallback
    default_models = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-sonnet-20241022",
        "groq": "llama-3.3-70b-versatile"
    }
    return {
        "provider": provider_info["type"],
        "api_key": api_key,
        "model": default_models.get(provider_info["type"], "default-model")
    }


def get_provider_models(provider: str, api_key: str) -> list[str]:
    """Fetch available models from provider."""
    import requests
    
    try:
        if provider == "openai":
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return [m["id"] for m in data.get("data", []) if "gpt" in m["id"]]
        
        elif provider == "anthropic":
            # Anthropic doesn't have a simple models endpoint, use known models
            return ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", 
                    "claude-3-haiku-20240307"]
        
        elif provider == "groq":
            response = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return [m["id"] for m in data.get("data", [])]
    
    except Exception as e:
        print(f"[!] Could not fetch models: {e}")
    
    return []


def configure_custom_provider() -> dict:
    """Configure custom OpenAI-compatible provider."""
    print_header("CUSTOM PROVIDER CONFIGURATION")
    
    base_url = input("Enter base URL (e.g., http://localhost:11434/v1): ").strip()
    
    if not base_url:
        print("[!] Base URL required. Returning to provider selection.\n")
        time.sleep(1)
        return interactive_provider_menu()
    
    has_key = input("Does this provider require an API key? [y/N]: ").strip().lower()
    api_key = ""
    if has_key == "y":
        api_key = input("Enter API key: ").strip()
    
    model = input("Enter model name to use: ").strip()
    
    if not model:
        print("[!] Model name required. Returning to provider selection.\n")
        time.sleep(1)
        return interactive_provider_menu()
    
    return {
        "provider": "custom",
        "base_url": base_url,
        "api_key": api_key,
        "model": model
    }


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
    # Check if we have a package name for this OS
    if package_manager and os_type in tool.package_names:
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
# INSTALL TOOLS FUNCTION
# =============================================================================

def install_selected_tools(tools_to_install: list[ToolInfo], os_type: str, package_manager: str | None) -> bool:
    """Install the selected tools."""
    if not tools_to_install:
        print("\n[+] No new tools to install.")
        return True
    
    print_header("INSTALLING SELECTED TOOLS")
    print(f"Installing {len(tools_to_install)} tool(s)...\n")
    
    successful = 0
    failed = 0
    
    for i, tool in enumerate(tools_to_install, 1):
        cmd = generate_install_command(tool, os_type, package_manager)
        print(f"[{i}/{len(tools_to_install)}] Installing {tool.name}...")
        print(f"    Command: {cmd}")
        
        try:
            if cmd.startswith("sudo") or "|" in cmd or cmd.startswith("curl"):
                subprocess.run(cmd, shell=True, check=True, timeout=300)
            elif "go install" in cmd or "cargo install" in cmd:
                subprocess.run(cmd, shell=True, check=True, timeout=300)
            else:
                parts = cmd.split()
                subprocess.run(parts, check=True, timeout=300)
            
            print(f"    ✓ Success!\n")
            successful += 1
        except subprocess.TimeoutExpired:
            print(f"    ✗ Timeout during installation\n")
            failed += 1
        except subprocess.CalledProcessError as e:
            print(f"    ✗ Failed: {e}\n")
            failed += 1
        except Exception as e:
            print(f"    ✗ Error: {e}\n")
            failed += 1
    
    print(f"\nInstallation Summary: {successful} succeeded, {failed} failed")
    return failed == 0


def save_config(config_data: dict):
    """Save configuration to .env file."""
    env_file = Path(".env")
    env_content = ""
    
    if env_file.exists():
        env_content = env_file.read_text()
    
    # Update or add configuration
    if config_data.get("provider"):
        provider_line = f"LLM_PROVIDER={config_data['provider']}\n"
        if "LLM_PROVIDER=" in env_content:
            env_content = "\n".join(
                line if not line.startswith("LLM_PROVIDER=") else provider_line.rstrip()
                for line in env_content.split("\n")
            )
        else:
            env_content += provider_line
    
    if config_data.get("model"):
        model_line = f"LLM_MODEL={config_data['model']}\n"
        if "LLM_MODEL=" in env_content:
            env_content = "\n".join(
                line if not line.startswith("LLM_MODEL=") else model_line.rstrip()
                for line in env_content.split("\n")
            )
        else:
            env_content += model_line
    
    if config_data.get("api_key"):
        if config_data["provider"] == "openai":
            key_line = f"OPENAI_API_KEY={config_data['api_key']}\n"
            if "OPENAI_API_KEY=" in env_content:
                env_content = "\n".join(
                    line if not line.startswith("OPENAI_API_KEY=") else key_line.rstrip()
                    for line in env_content.split("\n")
                )
            else:
                env_content += key_line
        elif config_data["provider"] == "anthropic":
            key_line = f"ANTHROPIC_API_KEY={config_data['api_key']}\n"
            if "ANTHROPIC_API_KEY=" in env_content:
                env_content = "\n".join(
                    line if not line.startswith("ANTHROPIC_API_KEY=") else key_line.rstrip()
                    for line in env_content.split("\n")
                )
            else:
                env_content += key_line
        elif config_data["provider"] == "groq":
            key_line = f"GROQ_API_KEY={config_data['api_key']}\n"
            if "GROQ_API_KEY=" in env_content:
                env_content = "\n".join(
                    line if not line.startswith("GROQ_API_KEY=") else key_line.rstrip()
                    for line in env_content.split("\n")
                )
            else:
                env_content += key_line
    
    if config_data.get("base_url"):
        url_line = f"LLM_BASE_URL={config_data['base_url']}\n"
        if "LLM_BASE_URL=" in env_content:
            env_content = "\n".join(
                line if not line.startswith("LLM_BASE_URL=") else url_line.rstrip()
                for line in env_content.split("\n")
            )
        else:
            env_content += url_line
    
    env_file.write_text(env_content)
    print(f"\n[+] Configuration saved to {env_file}")


def print_welcome_message(config: dict):
    """Print a welcome message after setup completion."""
    print_header("SETUP COMPLETE! 🎉")
    
    print("Cyber Agent is now ready to use!\n")
    print("Configuration Summary:")
    print(f"  • LLM Provider: {config.get('provider', 'Not configured')}")
    print(f"  • Model: {config.get('model', 'Not configured')}")
    if config.get('provider') == 'ollama':
        print(f"  • Mode: Local (no API key required)")
    elif config.get('api_key'):
        print(f"  • Mode: Cloud API (API key configured)")
    print()
    
    print("Quick Start Guide:")
    print("  1. Activate your virtual environment (if using one):")
    print("     source venv/bin/activate\n")
    print("  2. Launch Cyber Agent:")
    print("     python cli/main.py\n")
    print("  3. Try these commands:")
    print("     /help          - Show all available commands")
    print("     /hack          - Enter offensive security mode")
    print("     /scope         - View engagement scope")
    print("     /tools         - List available tools\n")
    
    print("Safety Reminder:")
    print("  • Always ensure you have written authorization before testing")
    print("  • Review RULES_OF_ENGAGEMENT.md before starting")
    print("  • Use /hack mode only on authorized targets\n")
    
    print("=" * 70)
    print("Happy (ethical) hacking! 🔒")
    print("=" * 70 + "\n")


# =============================================================================
# MAIN INSTALLER
# =============================================================================

def main():
    """Main installer function with interactive menus."""
    clear_screen()
    print("\n" + "=" * 70)
    print("  CYBER AGENT - INTERACTIVE SETUP WIZARD")
    print("=" * 70)
    print("\nThis wizard will guide you through:")
    print("  1. Selecting security tools to install")
    print("  2. Configuring Docker/Kali container (optional)")
    print("  3. Setting up your LLM provider")
    print("\nPress ENTER to begin...")
    input()
    
    # Step 1: Detect OS
    os_type, package_manager = detect_os()
    print(f"\n[*] Detected OS: {os_type}")
    print(f"[*] Package manager: {package_manager or 'None detected'}")
    time.sleep(1)
    
    # Step 2: Interactive tool selection menu
    tools_to_install = interactive_tool_menu(TOOL_INVENTORY)
    
    # Install selected tools
    if tools_to_install:
        install_selected_tools(tools_to_install, os_type, package_manager)
    else:
        print("\n[+] All selected tools are already installed!")
    
    time.sleep(2)
    
    # Step 3: Docker/Kali container setup
    use_docker = interactive_docker_menu()
    if use_docker:
        print_header("SETTING UP DOCKER KALI CONTAINER")
        if setup_kali_container():
            print("\n[+] Docker container setup complete!")
            print("[*] You can run './run_in_kali.sh' to start Cyber Agent in Kali")
        time.sleep(2)
    
    # Step 4: LLM Provider Configuration
    llm_config = interactive_provider_menu()
    
    # Save configuration
    if llm_config:
        save_config(llm_config)
    
    # Step 5: Welcome message
    print_welcome_message(llm_config)


if __name__ == "__main__":
    main()
