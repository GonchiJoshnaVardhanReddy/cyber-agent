"""cli/main.py — CLI entry point. Interactive REPL with Rich rendering.

Usage:
    cyber-agent                # interactive REPL
    cyber-agent --status       # show agent status and exit
    cyber-agent --run "objective"  # single objective, then exit
    
Commands:
    /hack <target> <scope>     # Enter hack mode with target and scope
    /scope                     # Show current scope
    /memory                    # Show world memory graph state
    /report                    # Generate findings report
    /status                    # Show agent status
    /exit                      # Exit the agent
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

import typer
import yaml
from rich.console import Console, Group
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.layout import Layout
from rich.syntax import Syntax
from rich.align import Align
from rich.rule import Rule
from rich.style import Style

app = typer.Typer(
    name="cyber-agent",
    help="Autonomous offensive security agent for authorized engagements.",
    no_args_is_help=False,
    add_completion=False,
)
console = Console(force_terminal=True, color_system="auto")

# Mode colors and styles
MODE_STYLES = {
    "normal": Style(color="bright_blue", bold=True),
    "hack": Style(color="bright_red", bold=True),
    "warning": Style(color="yellow", bold=True),
    "success": Style(color="green", bold=True),
    "error": Style(color="red", bold=True),
    "info": Style(color="cyan", dim=True),
}


def _load_config() -> dict:
    """Load config.yaml, falling back to config.yaml.example if needed."""
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
        console.print(Panel(
            "[red]No config.yaml found.[/red]\n\n"
            "[dim]Copy config.yaml.example to config.yaml and edit it.[/dim]",
            title="⚠️ Configuration Error",
            border_style="red",
        ))
        raise typer.Exit(1)
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def _create_banner(agent) -> Panel:
    """Create an attractive banner display."""
    mode = "HACK" if hasattr(agent, 'mode_manager') and agent.mode_manager.is_in_hack_mode() else "NORMAL"
    mode_color = "bright_red" if mode == "HACK" else "bright_blue"
    
    banner_text = (
        f"[bold {mode_color}]╔══════════════════════════════════════════════════════════╗[/bold {mode_color}]\n"
        f"[bold {mode_color}]║[/bold {mode_color}]  [bold]CYBER AGENT[/bold] — Autonomous Security Operator           [bold {mode_color}]║[/bold {mode_color}]\n"
        f"[bold {mode_color}]╠══════════════════════════════════════════════════════════╣[/bold {mode_color}]\n"
        f"[bold {mode_color}]║[/bold {mode_color}]  Mode:          [{mode_color}]{mode:^20}[/{mode_color}]                   [bold {mode_color}]║[/bold {mode_color}]\n"
        f"[bold {mode_color}]║[/bold {mode_color}]  Engagement:    [cyan]{agent.engagement_id:^20}[/cyan]          [bold {mode_color}]║[/bold {mode_color}]\n"
        f"[bold {mode_color}]║[/bold {mode_color}]  Provider:      [dim]{agent.config.provider.name}/{agent.config.model:^12}[/dim]    [bold {mode_color}]║[/bold {mode_color}]\n"
        f"[bold {mode_color}]║[/bold {mode_color}]  RoE Hash:      [dim]{agent.roe.file_hash[:16]:^20}...[/dim]         [bold {mode_color}]║[/bold {mode_color}]\n"
        f"[bold {mode_color}]╚══════════════════════════════════════════════════════════╝[/bold {mode_color}]"
    )
    return Panel(banner_text, border_style=mode_color, padding=(0, 0))


def _create_status_table(agent) -> Table:
    """Create a formatted status table."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    
    table.add_row("Engagement ID", str(agent.engagement_id))
    table.add_row("Provider", f"{agent.config.provider.name} / {agent.config.model}")
    table.add_row("RoE File", agent.roe.path if hasattr(agent.roe, 'path') else "N/A")
    
    if hasattr(agent, 'mode_manager'):
        mode_info = agent.mode_manager.get_status()
        table.add_row("Mode Status", mode_info.split('\n')[0])
    
    return table


def _cli_approval_prompt(prompt: str, is_dangerous: bool = False) -> str:
    """Render an enhanced approval prompt and get user input."""
    border_style = "red" if is_dangerous else "yellow"
    icon = "⚠️" if is_dangerous else "ℹ️"
    title = "DANGEROUS ACTION" if is_dangerous else "Approval Required"
    
    console.print()
    console.print(Panel(
        f"{icon} {prompt}",
        title=title,
        border_style=border_style,
        subtitle="Respond with: [green]yes[/green] | [yellow]no[/yellow] | [cyan]always[/cyan]",
    ))
    return Prompt.ask(
        "[bold]Allow?[/bold]",
        choices=["yes", "no", "always"],
        default="no",
        console=console,
    )


async def _stream_callback(text: str) -> None:
    """Print streaming text from the agent with typing effect."""
    console.print(Text(text), end="", highlight=False)


def _show_help():
    """Display enhanced help information."""
    help_table = Table(title="Available Commands", box=None, padding=(0, 1))
    help_table.add_column("Command", style="bright_cyan", no_wrap=True)
    help_table.add_column("Description", style="white")
    help_table.add_column("Example", style="dim", no_wrap=True)
    
    commands = [
        ("/hack", "Enter hack mode for offensive operations", "/hack example.com 192.168.1.0/24"),
        ("/scope", "Display current engagement scope", "/scope"),
        ("/memory", "View graph memory state", "/memory"),
        ("/report", "Generate findings report", "/report"),
        ("/status", "Show detailed agent status", "/status"),
        ("/tools", "List available tools", "/tools"),
        ("/help", "Show this help message", "/help"),
        ("/exit", "Exit the agent", "/exit"),
    ]
    
    for cmd, desc, example in commands:
        help_table.add_row(cmd, desc, example)
    
    console.print()
    console.print(Panel(help_table, title="📖 Command Reference", border_style="blue"))
    console.print()


def _show_tools_list(agent):
    """Display available tools in a formatted table."""
    if not hasattr(agent, 'registry') or not hasattr(agent.registry, 'tools'):
        console.print("[dim]No tools available.[/dim]")
        return
    
    tools_table = Table(title="Available Tools", box=None, padding=(0, 1))
    tools_table.add_column("Tool", style="bright_green", no_wrap=True)
    tools_table.add_column("Category", style="cyan", no_wrap=True)
    tools_table.add_column("Description", style="white")
    
    categories = {}
    for tool_name, tool_obj in agent.registry.tools.items():
        category = getattr(tool_obj, 'category', 'general')
        if category not in categories:
            categories[category] = []
        categories[category].append(tool_name)
    
    for category in sorted(categories.keys()):
        tools = sorted(categories[category])
        for i, tool in enumerate(tools):
            desc = ""
            if i == 0:
                desc = f"[{category.upper()}]"
            tools_table.add_row(tool, category if i == 0 else "", desc)
    
    console.print()
    console.print(Panel(tools_table, title="🛠️ Tool Inventory", border_style="green"))
    console.print()


def _show_scope_display(agent):
    """Display current scope in a formatted way."""
    if hasattr(agent, 'mode_manager') and agent.mode_manager.is_in_hack_mode():
        session = agent.mode_manager.get_hack_session()
        if session:
            scope_table = Table(title=f"Engagement Scope: {session.target}", box=None)
            scope_table.add_column("Type", style="cyan", no_wrap=True)
            scope_table.add_column("Items", style="white")
            
            scope_table.add_row("Target", session.target)
            scope_table.add_row("Type", session.engagement_type)
            scope_table.add_row(
                "In Scope", 
                "\n".join(session.scope[:10]) + (f"\n...and {len(session.scope) - 10} more" if len(session.scope) > 10 else "")
            )
            if session.excluded_targets:
                scope_table.add_row(
                    "Excluded",
                    "\n".join(f"[red]{item}[/red]" for item in session.excluded_targets[:5])
                )
            
            console.print()
            console.print(Panel(scope_table, title="🎯 Current Scope", border_style="blue"))
            return
    
    console.print("[yellow]Not in hack mode. Use /hack <target> <scope> to start an engagement.[/yellow]")


def _show_memory_summary(agent):
    """Display memory graph summary."""
    if hasattr(agent, 'memory') and 'world' in agent.memory:
        world_memory = agent.memory['world']
        if hasattr(world_memory, '_graph'):
            graph = world_memory._graph
            nodes = list(graph.nodes(data=True))
            edges = list(graph.edges(data=True))
            
            node_types = {}
            for _, data in nodes:
                kind = data.get('kind', 'unknown')
                node_types[kind] = node_types.get(kind, 0) + 1
            
            mem_table = Table(title="Memory Graph Summary", box=None)
            mem_table.add_column("Node Type", style="cyan")
            mem_table.add_column("Count", style="green", justify="right")
            
            for node_type, count in sorted(node_types.items()):
                mem_table.add_row(node_type.capitalize(), str(count))
            
            mem_table.add_row("Total Nodes", str(len(nodes)), style="bold")
            mem_table.add_row("Total Edges", str(len(edges)), style="bold")
            
            console.print()
            console.print(Panel(mem_table, title="🧠 World Memory", border_style="magenta"))
            return
    
    console.print("[dim]No world memory data available.[/dim]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    status: bool = typer.Option(False, "--status", help="Show agent status and exit"),
    run: str = typer.Option(None, "--run", "-r", help="Run a single objective, then exit"),
    no_approval: bool = typer.Option(False, "--no-approval", help="Disable approval prompts (DANGEROUS)"),
):
    """Start the cyber agent."""
    config = _load_config()

    try:
        from agent import build_agent_from_env
        agent = build_agent_from_env(config)
    except Exception as e:
        console.print(Panel(
            f"[red]Failed to initialize agent:[/red] {e}\n\n"
            "[dim]Make sure RULES_OF_ENGAGEMENT.md exists and .env is configured.[/dim]",
            title="❌ Initialization Error",
            border_style="red",
        ))
        raise typer.Exit(1)

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
        console.print(Panel(
            "[yellow bold]WARNING:[/yellow bold] Approval prompts disabled.\n"
            "[red]All tools will run without confirmation.[/red]",
            title="⚠️ Safety Disabled",
            border_style="yellow",
        ))
        agent.approval_policy = None
        agent.registry.approval_policy = None

    console.print(_create_banner(agent))
    console.print()

    if status:
        console.print(Panel(_create_status_table(agent), title="Agent Status", border_style="cyan"))
        return

    if run:
        console.print(f"\n[bold]Objective:[/bold] {run}\n")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=None)
            result = asyncio.run(agent.run(run, stream_callback=_stream_callback))
            progress.update(task, completed=True)
        
        console.print("\n")
        console.print(Panel(Markdown(result), title="Agent Response", border_style="green"))
        return

    console.print(Rule(style="dim"))
    console.print("[dim]Type your objective, or use commands like [/dim][cyan]/help[/cyan] [dim]to see available options.[/dim]\n")

    while True:
        try:
            mode = "hack" if hasattr(agent, 'mode_manager') and agent.mode_manager.is_in_hack_mode() else "normal"
            prompt_style = MODE_STYLES[mode]
            user_input = Prompt.ask(f"[{prompt_style}]operator ({mode})> [/{prompt_style}]", console=console)
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue
        
        if user_input.startswith("/"):
            cmd_parts = user_input.split()
            cmd = cmd_parts[0].lower()
            
            if cmd in ("exit", "quit", ":q", "/exit"):
                break
            elif cmd in ("status", ":s", "/status"):
                console.print(Panel(_create_status_table(agent), title="Agent Status", border_style="cyan"))
                continue
            elif cmd == "/hack":
                if len(cmd_parts) < 3:
                    console.print(Panel(
                        "[red]/hack requires target and scope.[/red]\n\n"
                        "[dim]Usage: /hack <target> <scope1>,<scope2>,...</dim>",
                        title="Usage Error",
                        border_style="red",
                    ))
                    continue
                
                target = cmd_parts[1]
                scope_items = cmd_parts[2].split(",") if len(cmd_parts) > 2 else []
                
                try:
                    from agent.modes import ModeManager, AgentMode
                    if not hasattr(agent, 'mode_manager'):
                        agent.mode_manager = ModeManager()
                    
                    session = agent.mode_manager.switch_to_hack_mode(
                        target=target,
                        scope=scope_items,
                        engagement_type="bug_bounty"
                    )
                    
                    console.print(Panel(
                        f"[green]✓ Hack mode activated[/green]\n\n"
                        f"Target: [cyan]{target}[/cyan]\n"
                        f"Scope: {len(scope_items)} items\n"
                        f"\n[dim]Offensive tools are now available. Remember to stay within scope.[/dim]",
                        title="🔴 HACK MODE ACTIVE",
                        border_style="red",
                    ))
                except Exception as e:
                    console.print(Panel(
                        f"[red]Error entering hack mode:[/red] {e}",
                        title="Error",
                        border_style="red",
                    ))
                continue
            elif cmd == "/scope":
                _show_scope_display(agent)
                continue
            elif cmd == "/memory":
                _show_memory_summary(agent)
                continue
            elif cmd == "/report":
                console.print("[dim]Generating report...[/dim]")
                try:
                    if hasattr(agent, 'registry') and 'generate_report' in agent.registry.tools:
                        result = asyncio.run(agent.run("Generate a comprehensive findings report", stream_callback=_stream_callback))
                        console.print("\n")
                        console.print(Panel(Markdown(result), title="Findings Report", border_style="green"))
                    else:
                        console.print("[yellow]Report tool not available. Try asking the agent to generate a report.[/yellow]")
                except Exception as e:
                    console.print(f"[red]Error generating report:[/red] {e}")
                continue
            elif cmd == "/tools":
                _show_tools_list(agent)
                continue
            elif cmd == "/help":
                _show_help()
                continue
            else:
                console.print(Panel(
                    f"[red]Unknown command:[/red] {cmd}\n\n"
                    "[dim]Type [cyan]/help[/cyan] to see available commands.[/dim]",
                    title="Command Error",
                    border_style="red",
                ))
                continue

        console.print()
        try:
            result = asyncio.run(agent.run(user_input, stream_callback=_stream_callback))
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            continue
        except Exception as e:
            console.print(Panel(f"[red]Error:[/red] {e}", title="Execution Error", border_style="red"))
            continue

        console.print("\n\n")
        console.print(Panel(Markdown(result), title="Agent Response", border_style="green"))
        console.print()

    if hasattr(agent, 'memory') and 'episodic' in agent.memory:
        agent.memory["episodic"].end_episode(
            episode_id=agent.engagement_id,
            summary=f"Session ended. {len(agent.plan_manager.tasks) if hasattr(agent, 'plan_manager') else 0} tasks.",
        )


if __name__ == "__main__":
    app()
