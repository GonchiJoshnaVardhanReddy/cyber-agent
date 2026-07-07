"""agent/tools/approval.py — Human-in-the-loop approval for dangerous tools.

Approval callbacks are surface-specific:
- CLI: prompt the user with a yes/no question
- Telegram: send a message with inline keyboard
- Discord: send a message with reaction buttons

The policy holds a single async callback that returns (approved, approver).
Default-deny on timeout.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

ApprovalCallback = Callable[[str, dict, bool], Awaitable[tuple[bool, str]]]


@dataclass
class ApprovalPolicy:
    """Approval policy + callback wrapper."""
    callback: ApprovalCallback
    timeout: float = 120.0
    always_require: set[str] = None  # tool names that always need approval

    def __post_init__(self):
        if self.always_require is None:
            self.always_require = set()

    async def request(self, tool_name: str, args: dict, dangerous: bool = False) -> tuple[bool, str]:
        """Ask for approval. Default-deny on timeout."""
        try:
            result = await asyncio.wait_for(
                self.callback(tool_name, args, dangerous),
                timeout=self.timeout,
            )
            return result
        except asyncio.TimeoutError:
            return False, "timeout"
        except Exception as e:
            return False, f"error: {e}"


def cli_approval_callback(prompt_fn: Callable[[str], str]) -> ApprovalCallback:
    """Build an approval callback that uses a sync prompt function (the CLI's input()).

    prompt_fn is called with the rendered prompt and returns "yes" / "no" / "always".
    """
    async def callback(tool_name: str, args: dict, dangerous: bool) -> tuple[bool, str]:
        prompt = _format_approval_prompt(tool_name, args, dangerous)
        response = prompt_fn(prompt).strip().lower()
        if response in ("yes", "y", "1", "true"):
            return True, "operator"
        if response == "always":
            return True, "operator:always"
        return False, "operator:denied"
    return callback


def _format_approval_prompt(tool_name: str, args: dict, dangerous: bool) -> str:
    """Render a human-readable approval prompt."""
    args_str = "\n".join(f"  {k} = {v!r}" for k, v in args.items())
    danger_marker = " [DANGEROUS]" if dangerous else ""
    return (
        f"\n┌─ APPROVAL REQUIRED{danger_marker}\n"
        f"│ Tool: {tool_name}\n"
        f"│ Args:\n{args_str}\n"
        f"└─ Allow? (yes/no/always): "
    )
