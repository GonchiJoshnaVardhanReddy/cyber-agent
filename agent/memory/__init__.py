"""agent/memory/__init__.py — Memory system coordinator.

Six memory types, each with its own storage and access pattern:
- Working:   RAM        — current execution context (per-session)
- World:     NetworkX   — live model of the target environment (graph)
- Semantic:  SQLite     — cybersecurity facts (CVE, CWE, ATT&CK)
- Procedural: YAML      — reusable playbooks and workflows
- Episodic:  SQLite     — engagement history
- Experience: SQLite    — lessons learned
"""
from .working import WorkingMemory
from .world import WorldMemory
from .semantic import SemanticMemory
from .procedural import ProceduralMemory
from .episodic import EpisodicMemory
from .experience import ExperienceMemory

__all__ = [
    "WorkingMemory", "WorldMemory", "SemanticMemory",
    "ProceduralMemory", "EpisodicMemory", "ExperienceMemory",
]
