"""agent/memory/procedural.py — Procedural Memory (YAML playbooks).

Reusable workflows and methodologies: enumeration workflows, privilege
escalation techniques, API testing procedures, assessment playbooks.
Versioned, easy to extend, easy to share.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Playbook:
    """One procedural playbook loaded from YAML."""
    name: str
    description: str
    category: str  # recon | web | api | privesc | cloud | cred | report
    steps: list[dict]
    prerequisites: list[str]
    outputs: list[str]
    file_path: str


class ProceduralMemory:
    """Loads YAML playbooks from a directory."""

    def __init__(self, procedures_dir: str | Path):
        self.procedures_dir = Path(procedures_dir)
        self._playbooks: dict[str, Playbook] = {}
        self.reload()

    def reload(self) -> None:
        self._playbooks.clear()
        if not self.procedures_dir.exists():
            return
        for yaml_file in self.procedures_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                pb = Playbook(
                    name=data.get("name", yaml_file.stem),
                    description=data.get("description", ""),
                    category=data.get("category", "general"),
                    steps=data.get("steps", []) or [],
                    prerequisites=data.get("prerequisites", []) or [],
                    outputs=data.get("outputs", []) or [],
                    file_path=str(yaml_file),
                )
                self._playbooks[pb.name] = pb
            except yaml.YAMLError:
                continue

    def list_playbooks(self, category: str | None = None) -> list[Playbook]:
        if category:
            return [p for p in self._playbooks.values() if p.category == category]
        return list(self._playbooks.values())

    def get(self, name: str) -> Playbook | None:
        return self._playbooks.get(name)

    def summary(self) -> str:
        if not self._playbooks:
            return "## Procedural Memory\n(no playbooks loaded)"
        lines = ["## Procedural Memory (playbooks)"]
        by_cat: dict[str, list[str]] = {}
        for pb in self._playbooks.values():
            by_cat.setdefault(pb.category, []).append(pb.name)
        for cat, names in by_cat.items():
            lines.append(f"  {cat}:")
            for n in names:
                lines.append(f"    - {n}")
        return "\n".join(lines)
