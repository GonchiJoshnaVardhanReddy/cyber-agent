"""agent/tools/codeexec.py — Sandboxed code execution (Python, Bash, PowerShell, JS).

v1: subprocess sandbox. Code runs in a child process with a timeout and
captured stdout/stderr. The sandbox is NOT a true security boundary — for
untrusted code, use the Docker backend (TODO v2).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from .registry import Tool, ToolResult


def _python_handler(code: str, timeout: int = 30) -> ToolResult:
    """Execute Python code in a subprocess."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        script_path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        output = ""
        if proc.stdout:
            output += f"stdout:\n{proc.stdout}\n"
        if proc.stderr:
            output += f"stderr:\n{proc.stderr}\n"
        output += f"(exit code: {proc.returncode})"
        return ToolResult(
            success=proc.returncode == 0, output=output[:8000],
            data={"returncode": proc.returncode},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, output=f"Timeout after {timeout}s", error="timeout")
    finally:
        Path(script_path).unlink(missing_ok=True)


PYTHON_EXEC_TOOL = Tool(
    name="code_execute_python",
    description=(
        "Execute Python code in a sandboxed subprocess. Use for data processing, "
        "parsing tool output, computing exploit payloads, etc. The code has access "
        "to the standard library only — no agent internals. Timeout: 30s default."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
        },
        "required": ["code"],
    },
    handler=_python_handler,
    requires_approval=True,
    dangerous=True,
)


def _bash_handler(command: str, timeout: int = 30) -> ToolResult:
    """Execute a bash command."""
    proc = subprocess.run(
        ["bash", "-c", command],
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    output = ""
    if proc.stdout:
        output += f"stdout:\n{proc.stdout}\n"
    if proc.stderr:
        output += f"stderr:\n{proc.stderr}\n"
    output += f"(exit code: {proc.returncode})"
    return ToolResult(
        success=proc.returncode == 0, output=output[:8000],
        data={"returncode": proc.returncode},
    )


BASH_EXEC_TOOL = Tool(
    name="code_execute_bash",
    description="Execute a bash command. Use for running security tools (curl, dig, gobuster, etc.).",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Bash command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
        },
        "required": ["command"],
    },
    handler=_bash_handler,
    requires_approval=True,
    dangerous=True,
)


def _powershell_handler(command: str, timeout: int = 30) -> ToolResult:
    """Execute a PowerShell command (Windows only)."""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        output = ""
        if proc.stdout:
            output += f"stdout:\n{proc.stdout}\n"
        if proc.stderr:
            output += f"stderr:\n{proc.stderr}\n"
        output += f"(exit code: {proc.returncode})"
        return ToolResult(
            success=proc.returncode == 0, output=output[:8000],
            data={"returncode": proc.returncode},
        )
    except FileNotFoundError:
        return ToolResult(success=False, output="PowerShell is not available on this system.", error="not_installed")
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, output=f"Timeout after {timeout}s", error="timeout")


POWERSHELL_EXEC_TOOL = Tool(
    name="code_execute_powershell",
    description="Execute a PowerShell command (Windows targets only).",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "PowerShell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
        },
        "required": ["command"],
    },
    handler=_powershell_handler,
    requires_approval=True,
    dangerous=True,
)


CODE_EXEC_TOOLS = [PYTHON_EXEC_TOOL, BASH_EXEC_TOOL, POWERSHELL_EXEC_TOOL]
