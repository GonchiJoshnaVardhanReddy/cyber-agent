"""agent/tools/__init__.py — Tools package."""
from .registry import ToolRegistry, Tool, ToolResult
from .approval import ApprovalPolicy, ApprovalCallback
from .offensive import OFFENSIVE_TOOLS

__all__ = [
    "ToolRegistry", "Tool", "ToolResult", 
    "ApprovalPolicy", "ApprovalCallback",
    "OFFENSIVE_TOOLS",
]
