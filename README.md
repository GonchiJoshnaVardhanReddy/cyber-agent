<p align="center">
  <img src="assets/logo.png" alt="Cyber Agent Logo" width="280">
</p>

<h1 align="center">🦾 Cyber Agent</h1>

<p align="center">
  <em>An autonomous offensive security agent that thinks, plans, and executes — for <strong>authorized</strong> work only.</em>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/tests-5%2F5-brightgreen.svg" alt="Tests: 5/5">
</p>

---

Tired of running `nmap`, copying output into ChatGPT, asking "what does this mean?", running another tool, pasting that back... yeah, me too. Cyber Agent closes the loop. You give it an objective and a signed Rules of Engagement; it does the recon, reasoning, and reporting itself, using whatever LLM you point it at.

---

## 🧠 What it actually does

Give it something like:

> *"Recon scanme.nmap.org — find open ports, fingerprint services, look up any CVEs for the versions you find, and write me a report."*

…and the agent will:

1. 📋 Build a plan (`plan_create`)
2. 🔍 Run passive recon — DNS, WHOIS (`recon_dns`, `recon_whois`)
3. 🛰️ Run active recon — nmap with version detection (`recon_nmap`)
4. 🧩 Record every host, service, and finding in its world model (`memory_record_*`)
5. 🐛 Look up CVEs for the versions it found (`cve_search`)
6. 📝 Generate a Markdown pentest report (`report_generate`)

All while asking for your approval before anything dangerous, refusing anything out of scope, and logging every step to an audit trail.

---

## ✨ Features at a glance

- **ReAct-style loop** — LLM proposes tool calls, agent runs them, results feed back, repeat
- **20+ tools** — nmap, HTTP, crawl, Python/Bash/PowerShell exec, web search, CVE lookup, memory ops, planning, reporting
- **6 memory systems** — Working (RAM), World (graph), Semantic (facts), Procedural (YAML playbooks), Episodic (history), Experience (lessons learned)
- **Provider-agnostic** — OpenAI, Anthropic, Ollama, OpenRouter, vLLM — switch with one env var
- **3 surfaces** — CLI REPL, Telegram bot (with inline approval buttons), Discord bot (reaction-based approvals)
- **Rules of Engagement enforced** — refuses to act without a signed RoE, scope-checks every tool call
- **Sandboxed file ops** — agent can only touch `./workspace/` (path traversal blocked)
- **Audit log** — every tool call, scope violation, and approval decision logged to file + SQLite
- **5/5 tests passing** 🟢

---

## 🚀 Quick start

### 1. Install

```bash
git clone <your-repo> cyber-agent
cd cyber-agent
for win
pip install -e ".[all]"   # core + Telegram + Discord deps
for linux
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set your API key and provider
```

Pick your LLM in `.env`:

```bash
# OpenAI (default)
CYBER_AGENT_PROVIDER=openai
OPENAI_API_KEY=sk-...
CYBER_AGENT_MODEL=gpt-4o

# Anthropic
CYBER_AGENT_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Local Ollama (free, no API key)
CYBER_AGENT_PROVIDER=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
CYBER_AGENT_MODEL=llama3.1:70b
```

```bash
cp config.yaml.example config.yaml
# Review — defaults are usually fine
```

### 3. Sign your Rules of Engagement

**The agent will refuse to run without this.** That's the point.

```bash
cp RULES_OF_ENGAGEMENT.md.template RULES_OF_ENGAGEMENT.md
```

Edit `RULES_OF_ENGAGEMENT.md` — fill in:
- Engagement ID, type, client, dates
- **In-scope targets** (hostnames, IPs, CIDRs, URL prefixes)
- Out-of-scope targets
- Allowed activity types
- Sign and date it

Every tool that takes a target is checked against this file. Out-of-scope = refused + logged.

### 4. Run

```bash
# Interactive REPL
cyber-agent

# Single objective, then exit
cyber-agent --run "Recon scanme.nmap.org and report open ports"

# Show status
cyber-agent --status

# Disable approval prompts (DANGEROUS — only in isolated envs)
cyber-agent --no-approval --run "..."
```

---

## 🗂️ The 6 memory systems

The agent doesn't just remember the conversation — it has six specialized memory types:

| Memory | What it stores | Where |
|---|---|---|
| **Working** | Current objectives, observations, hypotheses | RAM |
| **World** | Live graph of the target — hosts, services, findings, attack paths | NetworkX (Neo4j-ready) |
| **Semantic** | Cybersecurity facts — CWEs, MITRE ATT&CK techniques | SQLite |
| **Procedural** | Reusable playbooks (YAML files) | `data/procedures/` |
| **Episodic** | Full engagement history | SQLite |
| **Experience** | Lessons learned — what worked, what didn't | SQLite |

The agent accesses these via tools (`memory_record_finding`, `memory_lookup_lesson`, etc.). Before trying a technique, it can check `memory_lookup_lesson` to see if it's worked before. After a finding, `memory_record_finding` persists it with evidence.

---

## 🔧 Tools (20+)

| Category | Tools |
|---|---|
| **Recon** | `recon_nmap`, `recon_dns`, `recon_whois` |
| **Web** | `http_request`, `web_crawl` |
| **File ops** | `file_read`, `file_write`, `file_list` (sandboxed to `./workspace/`) |
| **Code exec** | `code_execute_python`, `code_execute_bash`, `code_execute_powershell` |
| **Search** | `web_search` (DuckDuckGo, no key needed), `cve_search` (NVD API) |
| **Memory** | `memory_record_host/service/finding/lesson`, `memory_lookup_lesson`, `memory_add_hypothesis` |
| **Planning** | `plan_create`, `plan_update_task`, `plan_view` |
| **Reporting** | `report_generate`, `report_list_findings` |

Dangerous tools (`recon_nmap`, `code_execute_*`, `file_write`) require operator approval before running. Approve via CLI prompt, Telegram inline buttons, or Discord reactions.

---

## 🤖 Surfaces

Three ways to talk to the same agent:

### CLI (default)
```bash
cyber-agent
```
Rich-rendered REPL. Type objectives, get responses, approve dangerous ops with `yes`/`no`/`always`.

### Telegram
```bash
python surfaces/telegram_bot.py
```
Approval prompts show as inline keyboard buttons (✅ Allow / 🚫 Deny). Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USERS` in `.env`.

### Discord
```bash
python surfaces/discord_bot.py
```
Approval via ✅/❌ reactions. Set `DISCORD_BOT_TOKEN` and `DISCORD_ALLOWED_USERS`. Enable the Message Content Intent in the Discord dev portal. Use `!run <objective>`.

---

## 🔄 How one turn works

```
1. You send an objective
   ↓
2. Agent builds system prompt (RoE + 6 memory summaries + tool list)
   ↓
3. Agent calls LLM with: prompt + history + tool schemas
   ↓
4. LLM returns either:
   a) Final text → done, return to you
   b) Tool call(s) → continue
   ↓
5. For each tool call:
   • Scope check (target in RoE?) — refuse if not
   • Approval check (dangerous?) — ask you
   • Execute, log to audit, feed result back to LLM
   ↓
6. Loop back to step 3
   ↓
7. Final response → save to episodic memory → return
```

Iteration budget defaults to 50 (configurable). When the budget runs out, the agent suggests generating a report.

---

## 🛡️ Security model (the short version)

1. **RoE required** — no signed Rules of Engagement, no agent
2. **Scope enforcement** — every tool with a target arg is checked
3. **Hard blocklist** — `.gov`, `.mil`, etc. never touched regardless of RoE
4. **Approval layer** — dangerous tools need your yes/no
5. **Default-deny on timeout** — 120s with no answer = denied
6. **Audit log** — every tool call, scope violation, approval decision logged
7. **Sandboxed files** — agent can only read/write `./workspace/`
8. **No plaintext secrets** — credential nodes store SHA-256 hashes only

---

## 📁 Project structure

```
cyber-agent/
├── agent/
│   ├── agent.py             # the loop (brain)
│   ├── authorization.py     # RoE parser + scope enforcement
│   ├── audit.py             # append-only audit log
│   ├── provider.py          # LLM provider abstraction
│   ├── memory/              # 6 memory systems
│   └── tools/               # 20+ tools + registry + approval
├── cli/main.py              # interactive REPL
├── surfaces/                # Telegram + Discord bots
├── data/
│   ├── procedures/          # YAML playbooks
│   └── semantic_seed/       # CWE + ATT&CK seed data
├── tests/test_smoke.py      # 5/5 passing
├── RULES_OF_ENGAGEMENT.md   # ← you sign this
├── config.yaml
├── .env
└── README.md                # this file
```

---

## 🧪 Testing

```bash
python -m pytest tests/test_smoke.py -v
```

5 tests, all passing. They cover imports, RoE parsing, all 6 memory systems, scope enforcement, and agent construction. No LLM calls — uses mocks.

---

## 🔌 Extending

### Add a tool

```python
# agent/tools/my_tool.py
from .registry import Tool, ToolResult

def my_handler(target: str) -> ToolResult:
    return ToolResult(success=True, output="done")

MY_TOOL = Tool(
    name="my_tool",
    description="Does something cool.",
    parameters={"type": "object", "properties": {
        "target": {"type": "string"}
    }, "required": ["target"]},
    handler=my_handler,
    requires_scope_target="target",  # scope-checked
    requires_approval=True,           # asks operator
)

MY_TOOLS = [MY_TOOL]
```

Register in `agent/agent.py` → `_register_tools()`, restart, done.

### Add a playbook

Drop a YAML file in `data/procedures/`. See the 3 included playbooks for the format.

### Swap to Neo4j for World Memory

The `WorldMemory` class already has the `backend="neo4j"` branch stubbed. Implement the Cypher queries, keep the interface — the rest of the agent doesn't change.

---

## 🗺️ Roadmap (v2)

- [ ] Neo4j backing for World Memory
- [ ] Docker sandbox for code execution
- [ ] MCP integration (consume external MCP servers)
- [ ] Multi-agent coordination (subagent spawning)
- [ ] Attack-path visualization (Graphviz — `export_dot()` is ready)
- [ ] Cloud tools (AWS, Azure, GCP enumeration)
- [ ] Browser automation (Playwright)
- [ ] Streaming LLM responses
- [ ] Web dashboard surface
- [ ] Cron scheduler

---

## 📜 License

MIT. See [LICENSE](LICENSE).

---

## ⚠️ Legal Disclaimer (read this before you use it)

Okay, here's the serious part. **This software is for authorized security testing only.** That means:

- ✅ You have **written authorization** from the asset owner, OR
- ✅ You're operating under an **authorized bug bounty program** with clear scope and rules, OR
- ✅ You're testing on **your own infrastructure** that you own

If none of those are true, **don't use this**. Unauthorized scanning, enumeration, or testing of systems you don't own is a crime — under the Computer Fraud and Abuse Act (US), the Computer Misuse Act (UK), and similar laws pretty much everywhere else. Penalties include fines and prison time. Not a joke.

The Rules of Engagement file exists for a reason: it documents what you're authorized to do, and the agent enforces it. If you're tempted to bypass the RoE or disable scope checks, **stop and ask yourself whether you actually have permission**. If you're not sure, you don't.

By using this software:
- You accept **full responsibility** for any actions performed with it
- You warrant that you have the **legal authority** to test your targets
- You agree that the authors and contributors are **not liable** for misuse

The audit log is your friend — it produces a defensible record of what was done, when, and under what authorization. If you ever need to explain your actions to a client, employer, or court, that log is what saves you. Don't disable it.

**Stay legal. Stay authorized. Do good security work.** 🛡️
