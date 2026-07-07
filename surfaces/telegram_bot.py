"""surfaces/telegram_bot.py — Telegram bot surface.

Allows the operator to interact with the agent via Telegram. Useful for
long-running engagements where you want to check in from your phone.

Security: Only allowed user IDs can interact with the bot. Set
TELEGRAM_ALLOWED_USERS env var to a comma-separated list of Telegram user IDs.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import yaml


async def run_telegram_bot(agent) -> None:
    """Run the Telegram bot, forwarding messages to the agent."""
    try:
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import (
            Application, CommandHandler, MessageHandler, CallbackQueryHandler,
            filters, ContextTypes,
        )
    except ImportError:
        print("Telegram dependencies not installed. Run: pip install 'cyber-agent[telegram]'")
        sys.exit(1)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    allowed_users_str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
    allowed_users = set()
    for u in allowed_users_str.split(","):
        u = u.strip()
        if u.isdigit():
            allowed_users.add(int(u))

    # Pending approval requests: {callback_id: (future, response)}
    pending_approvals: dict[str, asyncio.Future] = {}

    async def approval_callback(tool_name: str, args: dict, dangerous: bool) -> tuple[bool, str]:
        """Send an approval request to the operator via Telegram."""
        from agent.tools.approval import _format_approval_prompt
        prompt = _format_approval_prompt(tool_name, args, dangerous)

        # Send to the first allowed user
        if not allowed_users:
            return False, "no_allowed_users"
        user_id = next(iter(allowed_users))

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Allow once", callback_data=f"approve:once:{user_id}"),
                InlineKeyboardButton("🔓 Allow session", callback_data=f"approve:session:{user_id}"),
            ],
            [InlineKeyboardButton("🚫 Deny", callback_data=f"deny:{user_id}")],
        ])
        msg = await agent._telegram_app.bot.send_message(
            chat_id=user_id, text=f"```\n{prompt}\n```", parse_mode="Markdown",
            reply_markup=keyboard,
        )

        # Create a future and wait for the callback
        loop = asyncio.get_event_loop()
        future: asyncio.Future[tuple[bool, str]] = loop.create_future()
        pending_approvals[str(msg.message_id)] = future

        try:
            return await asyncio.wait_for(future, timeout=120)
        except asyncio.TimeoutError:
            return False, "timeout"

    # Set the approval policy on the agent
    from agent.tools.approval import ApprovalPolicy
    agent.approval_policy = ApprovalPolicy(callback=approval_callback, timeout=120)
    agent.registry.approval_policy = agent.approval_policy

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if allowed_users and user.id not in allowed_users:
            await update.message.reply_text("Unauthorized. Your Telegram user ID is not in TELEGRAM_ALLOWED_USERS.")
            return
        await update.message.reply_text(
            f"Cyber Agent online. Engagement: {agent.engagement_id}\n"
            f"Send me an objective and I'll work on it."
        )

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if allowed_users and user.id not in allowed_users:
            return
        text = update.message.text
        if not text:
            return

        await update.message.reply_text(f"Working on: {text}")
        try:
            result = await agent.run(text)
        except Exception as e:
            result = f"Error: {e}"

        # Telegram has a 4096-char limit; chunk if needed
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i+4000])

    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        message_id = str(query.message.message_id)

        if message_id not in pending_approvals:
            await query.edit_message_reply_markup(reply_markup=None)
            return

        future = pending_approvals.pop(message_id)
        if future.done():
            return

        if data.startswith("approve:once"):
            future.set_result((True, "operator:once"))
            await query.edit_message_text(query.message.text + "\n\n✅ APPROVED (once)")
        elif data.startswith("approve:session"):
            future.set_result((True, "operator:session"))
            await query.edit_message_text(query.message.text + "\n\n✅ APPROVED (session)")
        elif data.startswith("deny"):
            future.set_result((False, "operator:denied"))
            await query.edit_message_text(query.message.text + "\n\n🚫 DENIED")

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    agent._telegram_app = application

    print(f"Telegram bot started. Allowed users: {allowed_users or 'ANYONE (insecure!)'}")
    await application.run_polling()


def main():
    """Entry point for the Telegram bot."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml.example")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    # Load .env
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
    asyncio.run(run_telegram_bot(agent))


if __name__ == "__main__":
    main()
