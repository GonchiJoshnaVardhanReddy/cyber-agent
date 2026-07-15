#!/bin/bash

# Cyber Agent - Complete Installation Script for Linux
# This script installs all dependencies, runs the interactive setup, and launches the agent

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     CYBER AGENT - Installation Script                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}❌ Please do not run this script as root${NC}"
    echo "   Run: ./install.sh"
    exit 1
fi

# Step 1: System Dependencies
echo -e "${BLUE}📦 Step 1: Installing system dependencies...${NC}"
sudo apt update -qq
sudo apt install -y -qq python3 python3-pip python3-venv git build-essential libssl-dev libffi-dev python3-dev > /dev/null 2>&1
echo -e "${GREEN}✅ System dependencies installed${NC}"
echo ""

# Step 2: Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${BLUE}🐍 Step 2: Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${GREEN}✅ Virtual environment already exists${NC}"
fi
echo ""

# Step 3: Activate virtual environment
echo -e "${BLUE}🔄 Step 3: Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✅ Virtual environment activated${NC}"
echo ""

# Step 4: Install Python dependencies
echo -e "${BLUE}📥 Step 4: Installing Python dependencies...${NC}"
pip install --upgrade pip -q
pip install -e ".[dev]" -q
echo -e "${GREEN}✅ Python dependencies installed${NC}"
echo ""

# Step 5: Run interactive setup
echo -e "${BLUE}⚙️  Step 5: Running interactive setup...${NC}"
echo -e "${YELLOW}💡 Follow the prompts to configure tools, Docker, and LLM provider${NC}"
echo ""
python scripts/setup.py
echo ""

# Step 6: Create global alias
echo -e "${BLUE}🔧 Step 6: Setting up global 'cyber-agent' command...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_ACTIVATE="$SCRIPT_DIR/venv/bin/activate"

# Create a wrapper script in user's local bin
mkdir -p ~/.local/bin
cat > ~/.local/bin/cyber-agent << EOF
#!/bin/bash
source $VENV_ACTIVATE
cd $SCRIPT_DIR
python cli/main.py "\$@"
EOF

chmod +x ~/.local/bin/cyber-agent

# Add ~/.local/bin to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "" >> ~/.bashrc
    echo '# Add local bin to PATH' >> ~/.bashrc
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
fi

echo -e "${GREEN}✅ Global command 'cyber-agent' installed${NC}"
echo ""

# Step 7: Launch the agent
echo -e "${BLUE}🚀 Step 7: Launching Cyber Agent...${NC}"
echo -e "${YELLOW}💡 Tip: Next time, just run 'cyber-agent' from anywhere${NC}"
echo ""
sleep 2

# Launch the agent
cyber-agent
