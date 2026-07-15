"""agent/tools/__init__.py — Tools package."""
from .registry import ToolRegistry, Tool, ToolResult
from .approval import ApprovalPolicy, ApprovalCallback

# Import all tool categories
from .offensive import OFFENSIVE_TOOLS
from .fileops import FILEOPS_TOOLS
from .web import WEB_TOOLS
from .search import SEARCH_TOOLS
from .codeexec import CODE_EXEC_TOOLS
from .recon import RECON_TOOLS
from .reporting import REPORTING_TOOLS
from .planning import PLANNING_TOOLS
from .memory_ops import MEMORY_TOOLS

__all__ = [
    "ToolRegistry", "Tool", "ToolResult", 
    "ApprovalPolicy", "ApprovalCallback",
    # Tool category exports
    "OFFENSIVE_TOOLS",
    "FILEOPS_TOOLS",
    "WEB_TOOLS",
    "SEARCH_TOOLS",
    "CODE_EXEC_TOOLS",
    "RECON_TOOLS",
    "REPORTING_TOOLS",
    "PLANNING_TOOLS",
    "MEMORY_TOOLS",
]
