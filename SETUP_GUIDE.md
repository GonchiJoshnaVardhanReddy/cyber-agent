# Cyber Agent Setup & Configuration Guide

## Quick Start Options

### Option 1: Using OpenAI (Recommended for most users)

1. **Get your OpenAI API key** from https://platform.openai.com/api-keys

2. **Create `.env` file**:
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env`**:
   ```
   CYBER_AGENT_PROVIDER=openai
   OPENAI_API_KEY=sk-your-actual-api-key-here
   ```

4. **Edit `config.yaml`**:
   ```yaml
   agent:
     provider: openai
     model: gpt-4o  # or gpt-4o-mini, gpt-3.5-turbo
   ```

5. **Run Cyber Agent**:
   ```bash
   cyber-agent
   ```

### Option 2: Using Ollama (Local, free, requires setup)

**⚠️ IMPORTANT**: Ollama must be installed and running for this to work!

1. **Install Ollama**:
   - Linux/Mac: `curl -fsSL https://ollama.ai/install.sh | sh`
   - Windows: Download from https://ollama.ai/download

2. **Pull a model** (choose one):
   ```bash
   ollama pull llama3.1        # Meta's Llama 3.1 (8B)
   ollama pull mistral         # Mistral 7B
   ollama pull qwen2.5         # Qwen 2.5 (good alternative)
   ollama pull codellama       # Code-specialized model
   ```

3. **Verify Ollama is running**:
   ```bash
   curl http://localhost:11434/api/tags
   ```
   You should see your pulled models listed.

4. **Create `.env` file**:
   ```bash
   cp .env.example .env
   ```

5. **Edit `.env`**:
   ```
   CYBER_AGENT_PROVIDER=ollama
   # No API key needed for Ollama
   ```

6. **Edit `config.yaml`**:
   ```yaml
   agent:
     provider: ollama
     model: llama3.1  # Must match the model you pulled!
   ```

7. **Run Cyber Agent**:
   ```bash
   cyber-agent
   ```

---

## Common Issues & Solutions

### Issue: "model 'llama3.1' not found"

**Cause**: You're using Ollama but either:
- Ollama is not installed
- Ollama server is not running
- You haven't pulled the model
- The model name in config doesn't match what you pulled

**Solution**:
```bash
# 1. Install Ollama if not installed
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Pull the model
ollama pull llama3.1

# 3. Verify it's available
ollama list

# 4. Make sure Ollama is running (it should auto-start)
ollama serve

# 5. Check config matches
grep "model:" config.yaml  # Should say llama3.1
```

### Issue: Connection refused to localhost:11434

**Cause**: Ollama server is not running

**Solution**:
```bash
# Start Ollama server
ollama serve

# Or check if it's already running
ps aux | grep ollama
```

### Issue: "OPENAI_API_KEY not set"

**Cause**: You're using OpenAI provider but haven't set the API key

**Solution**:
```bash
# Create .env file with your key
cat > .env << EOF
CYBER_AGENT_PROVIDER=openai
OPENAI_API_KEY=sk-your-actual-key-here
EOF
```

---

## Understanding Modes

### Normal Mode (Default)
- General assistant capabilities
- File operations, web search, code execution
- Basic reconnaissance tools
- Safe for general use

### Hack Mode (`/hack`)
- **NOT just a command** - switches the entire agent interface
- Offensive security operations
- Advanced recon and scanning tools
- Structured penetration testing methodology
- **Requires explicit target and scope**

**Usage**:
```
/hack <target> <scope-items>

Examples:
/hack example.com example.com,www.example.com,192.168.1.0/24
/hack test.local 10.0.0.1,10.0.0.2,test.local
```

When you enter `/hack` mode:
1. Interface changes (prompt shows "hack" instead of "normal")
2. Offensive tools become available
3. All actions are scope-checked against your specified targets
4. Agent follows structured methodology: Recon → Hypothesis → Testing → Reporting

**Exit hack mode**: Just switch back to normal objectives or restart the agent

---

## Configuration Files

### `config.yaml`
Main configuration file. Key settings:
```yaml
agent:
  provider: openai  # or ollama, anthropic, openrouter
  model: gpt-4o     # must match your provider
  max_iterations: 50
  temperature: 0.2
```

### `.env`
Environment variables (overrides config.yaml):
```
CYBER_AGENT_PROVIDER=openai
OPENAI_API_KEY=sk-...
CYBER_AGENT_MODEL=gpt-4o
```

### `RULES_OF_ENGAGEMENT.md`
**REQUIRED** - Authorization document for engagements
- Defines authorized targets
- Sets engagement boundaries
- Provides legal authorization

---

## Security Reminders

1. **Only test systems you own or have written authorization for**
2. **Review RULES_OF_ENGAGEMENT.md before each engagement**
3. **Hack mode is for authorized testing only**
4. **The agent will refuse out-of-scope actions**
5. **Some tools require manual approval before execution**

---

## Troubleshooting Checklist

If Cyber Agent isn't working:

- [ ] Check provider setting in config.yaml matches your setup
- [ ] If using OpenAI: Verify API key in .env
- [ ] If using Ollama: Verify `ollama list` shows your model
- [ ] If using Ollama: Verify `curl http://localhost:11434/api/tags` works
- [ ] Check RULES_OF_ENGAGEMENT.md exists and has valid dates
- [ ] Ensure virtual environment is activated (if using one)
- [ ] Try: `python cli/main.py --status`

---

## Getting Help

```bash
# See all commands
/help

# Check agent status
/status

# List available tools
/tools

# View current scope (in hack mode)
/scope
```
