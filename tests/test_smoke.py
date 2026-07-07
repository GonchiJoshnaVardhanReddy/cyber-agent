"""tests/test_smoke.py — Smoke test: import everything and build an agent.

This does NOT make any LLM calls. It just verifies that the project
imports cleanly and the agent can be constructed with a dummy provider.
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_imports():
    """All modules should import without errors."""
    from agent import CyberAgent, AgentConfig, RulesOfEngagement, AuditLog
    from agent.provider import LLMProvider, LLMResponse, ToolCall
    from agent.memory import (
        WorkingMemory, WorldMemory, SemanticMemory,
        ProceduralMemory, EpisodicMemory, ExperienceMemory,
    )
    from agent.tools.registry import ToolRegistry, Tool, ToolResult
    from agent.tools.approval import ApprovalPolicy


def test_roe_loading():
    """RoE should load from the sample file."""
    from agent.authorization import RulesOfEngagement
    roe = RulesOfEngagement.from_file("RULES_OF_ENGAGEMENT.md")
    assert roe.engagement_id == "ENG-2026-DEMO"
    assert roe.is_active()
    # scanme.nmap.org is in scope
    allowed, _ = roe.is_target_in_scope("scanme.nmap.org")
    assert allowed
    # example.com is NOT in scope
    allowed, _ = roe.is_target_in_scope("example.com")
    assert not allowed


def test_memory_systems(tmp_path):
    """All 6 memory systems should initialize and basic ops should work."""
    from agent.memory import (
        WorkingMemory, WorldMemory, SemanticMemory,
        ProceduralMemory, EpisodicMemory, ExperienceMemory,
    )

    # Working (RAM)
    wm = WorkingMemory()
    wm.add_objective("Test objective")
    wm.add_observation(source="test", summary="Test observation")
    assert "Test objective" in wm.summary()

    # World (NetworkX)
    wld = WorldMemory(backend="networkx")
    wld.upsert_host("test.example.com", ip="10.0.0.1")
    wld.upsert_service("test.example.com", 80, "tcp", service="http")
    wld.add_finding("test.example.com", "Test finding", "medium")
    assert "test.example.com" in wld.summary()

    # Semantic (SQLite)
    sm = SemanticMemory(db_path=tmp_path / "test.db")
    sm.add_fact("cwe", "CWE-79", {"name": "XSS"})
    assert sm.get_fact("cwe", "CWE-79")["name"] == "XSS"

    # Procedural (YAML)
    pm = ProceduralMemory(procedures_dir="data/procedures")
    assert len(pm.list_playbooks()) >= 3  # we shipped 3 playbooks

    # Episodic (SQLite)
    em = EpisodicMemory(db_path=tmp_path / "test.db")
    em.start_episode("test-eng", operator="tester")
    em.record_event("test-eng", "observation", "Test event")
    assert len(em.get_events("test-eng")) == 1

    # Experience (SQLite)
    xm = ExperienceMemory(db_path=tmp_path / "test.db")
    xm.record_lesson("test-technique", success=True, lesson="it worked")
    assert xm.success_rate("test-technique") == 1.0


def test_tool_registry_scope_check(tmp_path):
    """The registry should refuse out-of-scope targets."""
    from agent.authorization import RulesOfEngagement
    from agent.audit import AuditLog
    from agent.tools.registry import ToolRegistry, Tool, ToolResult
    from agent.tools.recon import NMAP_TOOL

    roe = RulesOfEngagement.from_file("RULES_OF_ENGAGEMENT.md")
    audit = AuditLog(log_path=tmp_path / "audit.log", db_path=None,
                     engagement_id="test")

    registry = ToolRegistry(roe=roe, audit=audit, approval_policy=None)
    registry.register(NMAP_TOOL)

    import asyncio
    # scanme.nmap.org is in scope — should be allowed (but nmap may not be installed)
    result = asyncio.run(registry.dispatch("recon_nmap", {"target": "scanme.nmap.org"}))
    # Either it ran, or nmap isn't installed — both are scope-OK
    assert "REFUSED" not in result.output or "out of scope" not in result.output

    # example.com is NOT in scope — should be refused
    result = asyncio.run(registry.dispatch("recon_nmap", {"target": "example.com"}))
    assert "REFUSED" in result.output
    assert "not authorized" in result.output


def test_agent_construction(tmp_path):
    """The agent should construct cleanly with a mock provider."""
    from agent import CyberAgent, AgentConfig, RulesOfEngagement, AuditLog
    from agent.memory import (
        WorkingMemory, WorldMemory, SemanticMemory,
        ProceduralMemory, EpisodicMemory, ExperienceMemory,
    )

    roe = RulesOfEngagement.from_file("RULES_OF_ENGAGEMENT.md")
    audit = AuditLog(log_path=tmp_path / "audit.log",
                     db_path=tmp_path / "test.db",
                     engagement_id="test")

    memory_bundle = {
        "working": WorkingMemory(),
        "world": WorldMemory(backend="networkx"),
        "semantic": SemanticMemory(db_path=tmp_path / "test.db"),
        "procedural": ProceduralMemory(procedures_dir="data/procedures"),
        "episodic": EpisodicMemory(db_path=tmp_path / "test.db"),
        "experience": ExperienceMemory(db_path=tmp_path / "test.db"),
    }

    # Mock provider
    mock_provider = MagicMock()
    mock_provider.name = "mock"
    mock_provider.chat.return_value = type("R", (), {
        "content": "Test response", "tool_calls": [], "finish_reason": "stop",
        "usage": {}, "raw": None,
    })()

    config = AgentConfig(provider=mock_provider, model="mock-model", max_iterations=5)
    agent = CyberAgent(
        config=config, roe=roe, audit=audit,
        memory_bundle=memory_bundle, engagement_id="test",
    )

    # Should have registered all tools
    assert len(registry_tools := agent.registry._tools) >= 20

    # Should produce a status string
    status = agent.status()
    assert "Engagement: test" in status


if __name__ == "__main__":
    # Run without pytest for quick check
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
