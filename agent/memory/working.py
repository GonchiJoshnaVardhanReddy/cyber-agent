"""agent/memory/working.py — Working Memory (RAM).

Holds the current execution context: objectives, active tasks, recent
observations, temporary hypotheses, and execution state. Fast, in-process,
cleared at the end of each session.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Hypothesis:
    """A working hypothesis the agent is currently testing."""
    id: str
    statement: str
    confidence: float = 0.5  # 0.0 to 1.0
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    status: str = "open"  # open | confirmed | refuted


@dataclass
class Observation:
    """A recent observation from a tool call."""
    id: str
    timestamp: str
    source: str  # tool name
    target: str | None
    summary: str
    data: Any = None


class WorkingMemory:
    """Per-session working memory. Lives in RAM only."""

    def __init__(self) -> None:
        self.objectives: list[str] = []
        self.active_tasks: list[dict[str, Any]] = []
        self.recent_observations: list[Observation] = []
        self.hypotheses: list[Hypothesis] = []
        self.execution_state: dict[str, Any] = {}
        self.started_at: datetime = datetime.utcnow()

    def add_objective(self, objective: str) -> None:
        self.objectives.append(objective)

    def add_observation(self, source: str, summary: str, target: str | None = None,
                        data: Any = None) -> Observation:
        obs = Observation(
            id=f"obs-{len(self.recent_observations)+1:04d}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            source=source, target=target, summary=summary, data=data,
        )
        self.recent_observations.append(obs)
        # Keep the rolling window bounded
        if len(self.recent_observations) > 100:
            self.recent_observations = self.recent_observations[-100:]
        return obs

    def add_hypothesis(self, statement: str, confidence: float = 0.5) -> Hypothesis:
        h = Hypothesis(
            id=f"hyp-{len(self.hypotheses)+1:04d}",
            statement=statement, confidence=confidence,
        )
        self.hypotheses.append(h)
        return h

    def add_evidence(self, hypothesis_id: str, evidence: str, supports: bool = True) -> None:
        for h in self.hypotheses:
            if h.id == hypothesis_id:
                if supports:
                    h.evidence_for.append(evidence)
                    h.confidence = min(1.0, h.confidence + 0.1)
                else:
                    h.evidence_against.append(evidence)
                    h.confidence = max(0.0, h.confidence - 0.15)
                break

    def summary(self) -> str:
        """Compact summary for the system prompt."""
        lines = ["## Working Memory"]
        if self.objectives:
            lines.append("Objectives:")
            for o in self.objectives:
                lines.append(f"  - {o}")
        if self.active_tasks:
            lines.append("Active Tasks:")
            for t in self.active_tasks:
                lines.append(f"  - {t.get('description', t)}")
        if self.hypotheses:
            lines.append("Hypotheses:")
            for h in self.hypotheses[-5:]:
                lines.append(f"  - [{h.confidence:.0%}] {h.statement} ({h.status})")
        if self.recent_observations:
            lines.append(f"Recent Observations: {len(self.recent_observations)} (showing last 5)")
            for obs in self.recent_observations[-5:]:
                lines.append(f"  - [{obs.source}] {obs.summary}")
        return "\n".join(lines) if len(lines) > 1 else "Working Memory: (empty)"
