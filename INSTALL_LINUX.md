# Cyber Agent - Linux Installation Guide

## Quick Start (Recommended)

Run the automated installation script that handles everything:

```bash
cd /workspace
chmod +x install.sh
./install.sh
```

This script will:
1. Install system dependencies (Python, git, build tools)
2. Create a virtual environment
3. Install all Python packages
4. Run the interactive setup wizard (tool selection, Docker config, LLM provider)
5. Set up the global `cyber-agent` command
6. Launch the agent automatically

## Manual Installation

If you prefer to install manually:

### 1. System Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git build-essential libssl-dev libffi-dev python3-dev
```

### 2. Clone & Setup
```bash
cd /workspace
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Run Interactive Setup
```bash
python scripts/setup.py
```

### 4. Create Global Command
```bash
# Create wrapper script
mkdir -p ~/.local/bin
cat > ~/.local/bin/cyber-agent << 'EOF'
#!/bin/bash
source /workspace/venv/bin/activate
cd /workspace
python cli/main.py "$@"
EOF

chmod +x ~/.local/bin/cyber-agent

# Add to PATH (add this line to ~/.bashrc if not already there)
export PATH="$HOME/.local/bin:$PATH"
```

### 5. Launch the Agent
```bash
# From anywhere after setup:
cyber-agent

# Or from the project directory:
cd /workspace
source venv/bin/activate
python cli/main.py
```

## Using Docker (Alternative)

If you chose Docker during setup:

```bash
# Install Docker
sudo apt install -y docker.io
sudo usermod -aG docker $USER
newgrp docker

# Run the agent in Kali container
./run_in_kali.sh
```

## Running After Installation

Once installed, you can run the agent from **anywhere** in your terminal:

```bash
cyber-agent
```

Or with options:
```bash
cyber-agent --status      # Show current configuration
cyber-agent --help        # Show available commands
cyber-agent -r "Scan network"  # Run single objective
```

## Troubleshooting

### "command not found: cyber-agent"
```bash
# Reload your bashrc
source ~/.bashrc

# Or add to PATH manually
export PATH="$HOME/.local/bin:$PATH"
```

### Virtual environment issues
```bash
cd /workspace
source venv/bin/activate
```

### Permission denied on Docker
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Missing tools
```bash
cd /workspace
source venv/bin/activate
python scripts/setup.py
```

## Uninstallation

To completely remove Cyber Agent:

```bash
# Remove global command
rm -f ~/.local/bin/cyber-agent

# Remove project directory
rm -rf /workspace

# Remove Docker image (if used)
docker rmi kalilinux/kali-rolling

# Remove security tools (optional)
sudo apt remove --purge -y nmap masscan nikto sqlmap rustscan
sudo apt autoremove -y
```
