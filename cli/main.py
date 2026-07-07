"""cli/main.py — CLI entry point. Interactive REPL with Rich rendering.

Usage:
    cyber-agent                # interactive REPL
    cyber-agent --status       # show agent status and exit
    cyber-agent --run "objective"  # single objective, then exit
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.live import Live
from rich.text import Text

app = typer.Typer(
    name="cyber-agent",
    help="Autonomous offensive cybersecurity agent for authorized engagements.",
    no_args_is_help=False,
    add_completion=False,
)
console = Console()


def _load_config() -> dict:
    """Load config.yaml, falling back to config.yaml.example if needed."""
    # Load .env if present
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

    config_path = Path("config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml.example")
    if not config_path.exists():
        console.print("[red]No config.yaml found. Copy config.yaml.example to config.yaml and edit it.[/red]")
        raise typer.Exit(1)
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def _cli_approval_prompt(prompt: str) -> str:
    """Render an approval prompt and get user input."""
    console.print(Panel(prompt, title="Approval Required", border_style="yellow"))
    return Prompt.ask("[bold]Allow?[/bold] (yes/no/always)", default="no", console=console)


async def _stream_callback(text: str) -> None:
    """Print streaming text from the agent."""
    console.print(Text(text), end="")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    status: bool = typer.Option(False, "--status", help="Show agent status and exit"),
    run: str = typer.Option(None, "--run", "-r", help="Run a single objective, then exit"),
    no_approval: bool = typer.Option(False, "--no-approval", help="Disable approval prompts (DANGEROUS)"),
):
    """Start the cyber agent."""
    config = _load_config()

    # Build the agent
    try:
        from agent import build_agent_from_env
        agent = build_agent_from_env(config)
    except Exception as e:
        console.print(f"[red]Failed to initialize agent: {e}[/red]")
        console.print("[dim]Make sure RULES_OF_ENGAGEMENT.md exists and .env is configured.[/dim]")
        raise typer.Exit(1)

    # Set up approval policy
    if not no_approval:
        from agent.tools.approval import ApprovalPolicy, cli_approval_callback
        approval_cfg = config.get("approval", {})
        agent.approval_policy = ApprovalPolicy(
            callback=cli_approval_callback(_cli_approval_prompt),
            timeout=approval_cfg.get("timeout", 120),
            always_require=set(approval_cfg.get("always_require_approval", [])),
        )
        agent.registry.approval_policy = agent.approval_policy
    else:
        console.print("[yellow bold]WARNING:[/yellow bold] Approval prompts disabled. All tools will run without confirmation.")
        agent.approval_policy = None
        agent.registry.approval_policy = None

    # Show banner
    console.print(Panel.fit(
        f"[bold]Cyber Agent[/bold] — Autonomous Offensive Security Operator\n"
        f"Engagement: [cyan]{agent.engagement_id}[/cyan]\n"
        f"Provider:   [cyan]{agent.config.provider.name} / {agent.config.model}[/cyan]\n"
        f"RoE hash:   [dim]{agent.roe.file_hash[:16]}...[/dim]",
        border_style="bright_blue",
    ))

    if status:
        console.print(agent.status())
        return

    if run:
        # Single-objective mode
        console.print(f"\n[bold]Objective:[/bold] {run}\n")
        result = asyncio.run(agent.run(run, stream_callback=_stream_callback))
        console.print("\n")
        console.print(Panel(Markdown(result), title="Agent Response", border_style="green"))
        return

    # Interactive REPL
    console.print("[dim]Type your objective, or 'exit' to quit, 'status' for agent status.[/dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]operator>[/bold cyan]", console=console)
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", ":q"):
            break
        if user_input.lower() in ("status", ":s"):
            console.print(agent.status())
            continue

        # Run the agent
        console.print()
        try:
            result = asyncio.run(agent.run(user_input, stream_callback=_stream_callback))
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            continue
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            continue

        console.print("\n")
        console.print(Panel(Markdown(result), title="Agent Response", border_style="green"))
        console.print()

    # End the episode
    agent.memory["episodic"].end_episode(
        episode_id=agent.engagement_id,
        summary=f"Session ended. {len(agent.plan_manager.tasks)} tasks, "
                f"{sum(1 for _, d in agent.memory['world']._graph.nodes(data=True) if d.get('kind') == 'finding')} findings.",
    )


if __name__ == "__main__":
    app()
