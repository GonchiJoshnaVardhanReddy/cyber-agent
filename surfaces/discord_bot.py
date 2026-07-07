"""surfaces/discord_bot.py — Discord bot surface.

Allows the operator to interact with the agent via Discord. Approval prompts
use reaction-based yes/no.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import yaml


async def run_discord_bot(agent) -> None:
    """Run the Discord bot."""
    try:
        import discord
        from discord.ext import commands
    except ImportError:
        print("Discord dependencies not installed. Run: pip install 'cyber-agent[discord]'")
        sys.exit(1)

    token = os.getenv("DISCORD_BOT_TOKEN", "")
    if not token:
        print("DISCORD_BOT_TOKEN not set")
        sys.exit(1)

    allowed_users_str = os.getenv("DISCORD_ALLOWED_USERS", "")
    allowed_users = set()
    for u in allowed_users_str.split(","):
        u = u.strip()
        if u:
            allowed_users.add(int(u))

    pending_approvals: dict[int, asyncio.Future] = {}

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    async def approval_callback(tool_name: str, args: dict, dangerous: bool) -> tuple[bool, str]:
        from agent.tools.approval import _format_approval_prompt
        prompt = _format_approval_prompt(tool_name, args, dangerous)

        # Find a channel with the operator
        if not bot.application or not bot.application.owner:
            return False, "no_owner"
        owner = bot.application.owner

        msg = await owner.send(f"```\n{prompt}\n``` React with ✅ to allow or ❌ to deny.")

        # Add reactions
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        loop = asyncio.get_event_loop()
        future: asyncio.Future[tuple[bool, str]] = loop.create_future()
        pending_approvals[msg.id] = future

        try:
            return await asyncio.wait_for(future, timeout=120)
        except asyncio.TimeoutError:
            return False, "timeout"

    from agent.tools.approval import ApprovalPolicy
    agent.approval_policy = ApprovalPolicy(callback=approval_callback, timeout=120)
    agent.registry.approval_policy = agent.approval_policy

    @bot.event
    async def on_ready():
        print(f"Discord bot logged in as {bot.user} (ID: {bot.user.id})")
        if allowed_users:
            print(f"Allowed users: {allowed_users}")

    @bot.command(name="start")
    async def start_cmd(ctx):
        if allowed_users and ctx.author.id not in allowed_users:
            await ctx.send("Unauthorized.")
            return
        await ctx.send(f"Cyber Agent online. Engagement: {agent.engagement_id}\nSend `!run <objective>` to start.")

    @bot.command(name="run")
    async def run_cmd(ctx, *, objective: str):
        if allowed_users and ctx.author.id not in allowed_users:
            return
        await ctx.send(f"Working on: {objective}")
        try:
            result = await agent.run(objective)
        except Exception as e:
            result = f"Error: {e}"
        # Discord has a 2000-char limit
        for i in range(0, len(result), 1900):
            await ctx.send(f"```\n{result[i:i+1900]}\n```")

    @bot.event
    async def on_reaction_add(reaction, user):
        if user == bot.user:
            return
        msg_id = reaction.message.id
        if msg_id not in pending_approvals:
            return
        if allowed_users and user.id not in allowed_users:
            return
        future = pending_approvals.pop(msg_id)
        if future.done():
            return
        if str(reaction.emoji) == "✅":
            future.set_result((True, f"operator:{user.name}"))
        elif str(reaction.emoji) == "❌":
            future.set_result((False, f"operator:{user.name}:denied"))

    agent._discord_bot = bot
    await bot.start(token)


def main():
    """Entry point for the Discord bot."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml.example")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

    from agent import build_agent_from_env
    agent = build_agent_from_env(config)
    asyncio.run(run_discord_bot(agent))


if __name__ == "__main__":
    main()
