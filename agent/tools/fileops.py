"""agent/tools/fileops.py — File read/write/list tools.

Files are restricted to the agent's workspace directory (./workspace by default).
This prevents the agent from reading arbitrary system files. Reads of files
outside the workspace require approval.
"""
from __future__ import annotations

import os
from pathlib import Path

from .registry import Tool, ToolResult


WORKSPACE = Path("./workspace").resolve()


def _safe_path(path_str: str) -> Path:
    """Resolve a path, ensuring it's inside the workspace."""
    p = Path(path_str)
    if not p.is_absolute():
        p = WORKSPACE / p
    p = p.resolve()
    # Prevent path traversal
    try:
        p.relative_to(WORKSPACE)
    except ValueError:
        raise PermissionError(f"Path '{path_str}' is outside the workspace ({WORKSPACE})")
    return p


def _file_read_handler(path: str, max_bytes: int = 65536) -> ToolResult:
    try:
        p = _safe_path(path)
        if not p.exists():
            return ToolResult(success=False, output=f"File not found: {path}", error="not_found")
        if p.is_dir():
            return ToolResult(success=False, output=f"Path is a directory: {path}", error="is_dir")
        content = p.read_bytes()[:max_bytes]
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = f"[binary file, {len(content)} bytes, not displayed]"
        if len(text) >= max_bytes:
            text = text[:max_bytes] + f"\n... [truncated at {max_bytes} bytes]"
        return ToolResult(success=True, output=text, data={"size": p.stat().st_size, "path": str(p)})
    except PermissionError as e:
        return ToolResult(success=False, output=f"Permission denied: {e}", error="permission")
    except Exception as e:
        return ToolResult(success=False, output=f"Error: {e}", error=str(e))


FILE_READ_TOOL = Tool(
    name="file_read",
    description="Read a file from the agent's workspace (./workspace/). Paths are sandboxed; traversal is blocked.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to workspace, or absolute within workspace"},
            "max_bytes": {"type": "integer", "description": "Maximum bytes to read", "default": 65536},
        },
        "required": ["path"],
    },
    handler=_file_read_handler,
)


def _file_write_handler(path: str, content: str, append: bool = False) -> ToolResult:
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)
        return ToolResult(
            success=True,
            output=f"Wrote {len(content)} chars to {p.relative_to(WORKSPACE)}",
            data={"path": str(p), "bytes": len(content)},
        )
    except PermissionError as e:
        return ToolResult(success=False, output=f"Permission denied: {e}", error="permission")
    except Exception as e:
        return ToolResult(success=False, output=f"Error: {e}", error=str(e))


FILE_WRITE_TOOL = Tool(
    name="file_write",
    description="Write content to a file in the agent's workspace. Use append=true to add to an existing file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to workspace"},
            "content": {"type": "string", "description": "Content to write"},
            "append": {"type": "boolean", "description": "Append instead of overwrite", "default": False},
        },
        "required": ["path", "content"],
    },
    handler=_file_write_handler,
    requires_approval=True,
    dangerous=False,
)


def _file_list_handler(path: str = ".") -> ToolResult:
    try:
        p = _safe_path(path)
        if not p.exists():
            return ToolResult(success=False, output=f"Path not found: {path}", error="not_found")
        if not p.is_dir():
            return ToolResult(success=False, output=f"Not a directory: {path}", error="not_dir")
        entries = []
        for child in sorted(p.iterdir()):
            kind = "dir" if child.is_dir() else "file"
            size = child.stat().st_size if child.is_file() else 0
            entries.append(f"  [{kind}] {child.name} ({size} bytes)")
        return ToolResult(
            success=True,
            output=f"Contents of {p.relative_to(WORKSPACE)}:\n" + "\n".join(entries),
            data={"path": str(p), "entries": [e.name for e in p.iterdir()]},
        )
    except PermissionError as e:
        return ToolResult(success=False, output=f"Permission denied: {e}", error="permission")
    except Exception as e:
        return ToolResult(success=False, output=f"Error: {e}", error=str(e))


FILE_LIST_TOOL = Tool(
    name="file_list",
    description="List files in a directory within the agent's workspace.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path relative to workspace", "default": "."},
        },
    },
    handler=_file_list_handler,
)


FILEOPS_TOOLS = [FILE_READ_TOOL, FILE_WRITE_TOOL, FILE_LIST_TOOL]
