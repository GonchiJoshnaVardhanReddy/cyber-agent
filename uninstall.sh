#!/bin/bash

# Cyber Agent - Complete Uninstallation Script for Linux
# This script removes all installed components, dependencies, and configurations

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     CYBER AGENT - Uninstallation Script                ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Confirmation prompt
echo -e "${YELLOW}⚠️  WARNING: This will completely remove Cyber Agent and all its data!${NC}"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo -e "${RED}❌ Uninstallation cancelled${NC}"
    exit 0
fi

echo ""

# Step 1: Deactivate virtual environment if active
echo -e "${BLUE}🔄 Step 1: Checking virtual environment...${NC}"
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate 2>/dev/null || true
    echo -e "${GREEN}✅ Virtual environment deactivated${NC}"
else
    echo -e "${GREEN}✅ No active virtual environment${NC}"
fi
echo ""

# Step 2: Remove global command alias
echo -e "${BLUE}🔧 Step 2: Removing global 'cyber-agent' command...${NC}"
if [ -f ~/.local/bin/cyber-agent ]; then
    rm -f ~/.local/bin/cyber-agent
    echo -e "${GREEN}✅ Global command removed from ~/.local/bin/${NC}"
else
    echo -e "${YELLOW}⚠️  Global command not found${NC}"
fi

# Clean up PATH in .bashrc if added by install script
if grep -q '# Add local bin to PATH' ~/.bashrc 2>/dev/null; then
    # Remove the lines added by install script
    sed -i '/# Add local bin to PATH/d' ~/.bashrc
    sed -i '/export PATH="\$HOME\/.local\/bin:\$PATH"/d' ~/.bashrc
    echo -e "${GREEN}✅ PATH cleanup in .bashrc${NC}"
fi

# Also check .zshrc
if grep -q '# Add local bin to PATH' ~/.zshrc 2>/dev/null; then
    sed -i '/# Add local bin to PATH/d' ~/.zshrc
    sed -i '/export PATH="\$HOME\/.local\/bin:\$PATH"/d' ~/.zshrc
    echo -e "${GREEN}✅ PATH cleanup in .zshrc${NC}"
fi
echo ""

# Step 3: Remove virtual environment
echo -e "${BLUE}🗑️  Step 3: Removing virtual environment...${NC}"
if [ -d "venv" ]; then
    rm -rf venv
    echo -e "${GREEN}✅ Virtual environment directory removed${NC}"
else
    echo -e "${YELLOW}⚠️  Virtual environment directory not found${NC}"
fi
echo ""

# Step 4: Remove Python package installation
echo -e "${BLUE}🗑️  Step 4: Uninstalling Python package...${NC}"
if pip show cyber-agent &>/dev/null; then
    pip uninstall -y cyber-agent
    echo -e "${GREEN}✅ Python package uninstalled${NC}"
else
    echo -e "${YELLOW}⚠️  Python package not found (may already be uninstalled)${NC}"
fi
echo ""

# Step 5: Remove generated data files (optional)
echo -e "${BLUE}🗑️  Step 5: Cleaning data files...${NC}"
echo -e "${YELLOW}Choose what to remove:${NC}"
echo "  1) Keep all data (agent.db, audit.log, etc.)"
echo "  2) Remove only database files"
echo "  3) Remove ALL data including logs and reports"
read -p "Enter choice (1/2/3): " DATA_CHOICE

case $DATA_CHOICE in
    2)
        if [ -f "data/agent.db" ]; then
            rm -f data/agent.db
            echo -e "${GREEN}✅ Database file removed${NC}"
        fi
        ;;
    3)
        if [ -d "data" ]; then
            rm -rf data
            mkdir -p data/procedures
            mkdir -p data/semantic_seed
            echo -e "${GREEN}✅ All data files removed (empty directories recreated)${NC}"
        fi
        if [ -f "*.log" ]; then
            rm -f *.log
            echo -e "${GREEN}✅ Log files removed${NC}"
        fi
        ;;
    *)
        echo -e "${YELLOW}ℹ️  Data files preserved${NC}"
        ;;
esac
echo ""

# Step 6: Remove configuration files (optional)
echo -e "${BLUE}🗑️  Step 6: Cleaning configuration files...${NC}"
echo -e "${YELLOW}Choose what to do with configuration:${NC}"
echo "  1) Keep config.yaml and .env (recommended if reinstalling)"
echo "  2) Remove config.yaml (keep .env with API keys)"
echo "  3) Remove ALL configuration including .env"
read -p "Enter choice (1/2/3): " CONFIG_CHOICE

case $CONFIG_CHOICE in
    2)
        if [ -f "config.yaml" ]; then
            rm -f config.yaml
            echo -e "${GREEN}✅ config.yaml removed${NC}"
        fi
        ;;
    3)
        if [ -f "config.yaml" ]; then
            rm -f config.yaml
            echo -e "${GREEN}✅ config.yaml removed${NC}"
        fi
        if [ -f ".env" ]; then
            rm -f .env
            echo -e "${GREEN}✅ .env removed${NC}"
        fi
        ;;
    *)
        echo -e "${YELLOW}ℹ️  Configuration files preserved${NC}"
        ;;
esac
echo ""

# Step 7: Remove build artifacts
echo -e "${BLUE}🗑️  Step 7: Cleaning build artifacts...${NC}"
rm -rf build/ dist/ *.egg-info __pycache__/ .pytest_cache/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo -e "${GREEN}✅ Build artifacts cleaned${NC}"
echo ""

# Step 8: Remove Docker containers (if any)
echo -e "${BLUE}🗑️  Step 8: Checking for Docker containers...${NC}"
if command -v docker &>/dev/null; then
    if docker ps -a --format '{{.Names}}' | grep -q "cyber-agent"; then
        docker stop cyber-agent 2>/dev/null || true
        docker rm cyber-agent 2>/dev/null || true
        echo -e "${GREEN}✅ Docker container removed${NC}"
    else
        echo -e "${YELLOW}ℹ️  No Cyber Agent Docker containers found${NC}"
    fi
    
    # Remove Cyber Agent images if they exist
    if docker images --format '{{.Repository}}' | grep -q "cyber-agent"; then
        docker rmi $(docker images | grep "cyber-agent" | awk '{print $3}') 2>/dev/null || true
        echo -e "${GREEN}✅ Docker images removed${NC}"
    fi
else
    echo -e "${YELLOW}ℹ️  Docker not installed, skipping${NC}"
fi
echo ""

# Summary
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           UNINSTALLATION COMPLETE                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}✓${NC} Cyber Agent has been uninstalled."
echo ""
echo "The following were removed:"
echo "  • Virtual environment (venv/)"
echo "  • Global command alias (~/.local/bin/cyber-agent)"
echo "  • Python package installation"
echo "  • Build artifacts and cache files"
echo ""
echo "The following were preserved (based on your choices):"
if [ -d "data" ]; then
    echo "  • Data directory (data/)"
fi
if [ -f "config.yaml" ] || [ -f ".env" ]; then
    echo "  • Configuration files"
fi
echo ""
echo -e "${YELLOW}Note:${NC} The source code directory still exists. To remove it completely:"
echo "  rm -rf $(pwd)"
echo ""
echo -e "${YELLOW}Note:${NC} You may need to restart your terminal or run:"
echo "  source ~/.bashrc  # or source ~/.zshrc"
echo "to update your PATH."
echo ""
