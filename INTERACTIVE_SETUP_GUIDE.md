# Cyber Agent - Interactive Setup Guide

## Overview

The Cyber Agent now features an **interactive setup wizard** with menu-driven interfaces for:
1. Selecting security tools to install (arrow keys + spacebar)
2. Configuring Docker/Kali container options
3. Setting up LLM providers (Ollama, OpenAI, Anthropic, Groq, Custom)
4. Auto-detecting and pulling Ollama models
5. Managing API keys for cloud providers

## Quick Start

```bash
# Navigate to the project directory
cd /workspace

# Run the interactive setup
python scripts/setup.py
```

## Navigation Controls

All menus use consistent keyboard controls:

| Key | Action |
|-----|--------|
| `↑` (Up Arrow) | Move selection up |
| `↓` (Down Arrow) | Move selection down |
| `Space` | Toggle selection (checkboxes) |
| `Enter` | Confirm selection / Proceed |
| `Ctrl+C` | Cancel setup |

## Setup Flow

### Step 1: OS Detection
The wizard automatically detects your operating system and package manager:
- **Linux**: Ubuntu, Debian, Kali, Arch, Fedora
- **macOS**: Homebrew detection
- **Windows**: WSL support

### Step 2: Tool Selection Menu

You'll see an interactive list of 15 security tools organized by category:

```
SELECT TOOLS TO INSTALL
Navigation: ↑/↓ = Move | SPACE = Select/Deselect | ENTER = Confirm

Already installed tools are pre-selected (✓).

► ✓ nmap                    [network_scanner]  Network exploration and security auditing
  ☐ masscan                 [network_scanner]  Fastest port scanner (TCP SYN scanner)
  ☐ rustscan                [network_scanner]  Modern fast port scanner written in Rust
  ...
```

**Features:**
- Already installed tools are marked with `✓` and pre-selected
- Use `Space` to toggle selection for tools you want to install
- Green (`✓`) = installed, Blue (`☑`) = selected for install, Gray (`☐`) = not selected
- Press `Enter` when ready to proceed

**Tool Categories:**
- **Network Scanners**: nmap, masscan, rustscan, naabu
- **OSINT**: amass, theHarvester
- **Subdomain Enumeration**: subfinder, assetfinder, dnsrecon
- **Web Scanners**: nikto, nuclei, ffuf, gobuster
- **Exploitation**: sqlmap, metasploit-framework

### Step 3: Installation Progress

Selected tools are installed with real-time feedback:

```
INSTALLING SELECTED TOOLS
Installing 5 tool(s)...

[1/5] Installing nmap...
    Command: sudo apt update && sudo apt install -y nmap
    ✓ Success!

[2/5] Installing rustscan...
    Command: cargo install rustscan
    ✓ Success!
```

**Installation Summary** shows succeeded/failed counts at the end.

### Step 4: Docker/Kali Container Setup

Choose whether to use Docker with Kali Linux:

```
DOCKER SETUP

✓ Docker is installed and ready.

Using Docker with Kali Linux provides:
  • Pre-configured security tools environment
  • Isolation from your host system
  • Consistent tool versions across systems

Navigation: ↑/↓ = Move | ENTER = Select

  ► Use Docker with Kali Linux container (Recommended)
    Skip Docker setup (Install tools directly on host)
```

**Benefits of Docker:**
- All tools pre-installed in isolated environment
- No pollution of your host OS
- Consistent across different machines
- Easy cleanup

If you choose Docker, a `run_in_kali.sh` script is created for easy launching.

### Step 5: LLM Provider Configuration

Select your preferred LLM provider:

```
SELECT LLM PROVIDER
Navigation: ↑/↓ = Move | ENTER = Select

► Ollama (Local)               Run models locally, free, no API keys
  OpenAI                       GPT-4, GPT-3.5-turbo via API
  Anthropic                    Claude models via API
  Groq                         Fast inference for open models
  Custom OpenAI-compatible     vLLM, LM Studio, etc.
```

#### Option A: Ollama (Local)

If you select Ollama:

1. **Auto-detection**: Checks if Ollama is running, starts it if needed
2. **Model Discovery**: Shows already installed models
3. **Recommendations**: Suggests optimal models for Cyber Agent:
   - `qwen2.5-coder:7b` - Best balance of speed/capability
   - `qwen2.5-coder:14b` - Better reasoning, moderate speed
   - `qwen2.5-coder:32b` - Maximum capability (requires more RAM)
   - `llama3.2:3b` - Lightweight option
   - `mistral:7b` - General purpose
   - `codellama:7b` - Code-focused

4. **Model Options**:
   ```
   Choose an option:
     1. Select from installed models
     2. Install a recommended model
     3. Enter custom model name
     4. Go back to provider selection
   ```

5. **Auto-pull**: If you choose a model that's not installed, it will be downloaded automatically

#### Option B: Cloud Providers (OpenAI, Anthropic, Groq)

For cloud providers:

1. **API Key Entry**: Prompts for your API key with helpful links
2. **Model Discovery**: Fetches available models from your account
3. **Model Selection**: Choose from available models
4. **Defaults**: Sensible defaults if you skip selection:
   - OpenAI: `gpt-4o-mini`
   - Anthropic: `claude-3-5-sonnet-20241022`
   - Groq: `llama-3.3-70b-versatile`

#### Option C: Custom Provider

For self-hosted or other OpenAI-compatible APIs:

1. Enter base URL (e.g., `http://localhost:11434/v1`)
2. Specify if API key is required
3. Enter model name

### Step 6: Configuration Saved

Your choices are automatically saved to `.env`:

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5-coder:7b
```

Or for cloud providers:
```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

### Step 7: Welcome Message

A final summary screen shows:
- Configuration overview
- Quick start commands
- Safety reminders
- Next steps

```
SETUP COMPLETE! 🎉

Cyber Agent is now ready to use!

Configuration Summary:
  • LLM Provider: ollama
  • Model: qwen2.5-coder:7b
  • Mode: Local (no API key required)

Quick Start Guide:
  1. Activate your virtual environment (if using one):
     source venv/bin/activate

  2. Launch Cyber Agent:
     python cli/main.py

  3. Try these commands:
     /help          - Show all available commands
     /hack          - Enter offensive security mode
     /scope         - View engagement scope
     /tools         - List available tools

Safety Reminder:
  • Always ensure you have written authorization before testing
  • Review RULES_OF_ENGAGEMENT.md before starting
  • Use /hack mode only on authorized targets

======================================================================
Happy (ethical) hacking! 🔒
======================================================================
```

## Troubleshooting

### "readchar" Installation Issues
If the interactive menu doesn't work:
```bash
pip install readchar
```

### Docker Permission Denied
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Ollama Not Running
The setup script auto-starts Ollama, but if issues persist:
```bash
ollama serve
```

### Tool Installation Fails
Some tools may fail due to:
- Missing dependencies: Install build essentials (`sudo apt install build-essential`)
- Network issues: Check your internet connection
- Permissions: Some tools need `sudo` (the installer handles this)

### API Key Errors
- Double-check your API key for typos
- Ensure you have billing enabled on your account
- Check rate limits and quotas

## Manual Configuration

If you need to reconfigure later:

1. **Edit .env file**:
   ```bash
   nano .env
   ```

2. **Re-run setup**:
   ```bash
   python scripts/setup.py
   ```

3. **Test configuration**:
   ```bash
   python cli/main.py --status
   ```

## Advanced Usage

### Skipping Steps

You can interrupt the setup at any time with `Ctrl+C` and resume later.

### Installing Additional Tools Later

Run the setup again and select additional tools in the tool selection menu.

### Multiple Ollama Models

You can switch between Ollama models by editing `.env`:
```env
LLM_MODEL=qwen2.5-coder:14b
```

### Custom Tool Installation

For tools not in the inventory, install them manually:
```bash
# Example: Install a custom tool
go install github.com/example/tool@latest
```

## Support

For issues or questions:
1. Check the main `README.md`
2. Review `RULES_OF_ENGAGEMENT.md` for safety guidelines
3. Examine logs in `logs/audit.json` for debugging

---

**Remember**: Always use Cyber Agent responsibly and only on systems you have explicit written authorization to test.
