"""agent/__init__.py — Agent package."""
from .agent import CyberAgent, AgentConfig, build_agent_from_env
from .authorization import RulesOfEngagement
from .audit import AuditLog
from .provider import LLMProvider, LLMResponse, ToolCall, make_provider_from_env, make_provider_from_config
from .modes import (
    AgentMode, ReconStage, TestStage,
    HackSession, ModeManager, ModeTransition,
)

__all__ = [
    "CyberAgent", "AgentConfig", "build_agent_from_env",
    "RulesOfEngagement", "AuditLog",
    "LLMProvider", "LLMResponse", "ToolCall", "make_provider_from_env", "make_provider_from_config",
    # Mode management
    "AgentMode", "ReconStage", "TestStage",
    "HackSession", "ModeManager", "ModeTransition",
]
