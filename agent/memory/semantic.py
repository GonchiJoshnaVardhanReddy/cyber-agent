"""agent/memory/semantic.py — Semantic Memory (SQLite).

Stores factual cybersecurity knowledge shared across engagements: CVEs, CWEs,
MITRE ATT&CK techniques, technology fingerprints, cloud service identifiers.
Structured, rarely changes, queryable.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class SemanticMemory:
    """SQLite-backed fact store. Schema is flexible (key-value with type tag)."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_type TEXT NOT NULL,    -- cve | cwe | attack | tech | cloud | concept
                    key TEXT NOT NULL,          -- e.g., "CVE-2024-1234" or "T1190"
                    value TEXT NOT NULL,        -- JSON-encoded payload
                    source TEXT,                -- NVD | MITRE | manual
                    created_at TEXT NOT NULL,
                    UNIQUE(fact_type, key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_type ON facts(fact_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key)")
            conn.commit()

    def add_fact(self, fact_type: str, key: str, value: dict[str, Any],
                 source: str = "manual") -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO facts (fact_type, key, value, source, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (fact_type, key, json.dumps(value), source, datetime.utcnow().isoformat() + "Z"),
            )
            conn.commit()

    def get_fact(self, fact_type: str, key: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM facts WHERE fact_type=? AND key=?",
                (fact_type, key),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def search_facts(self, fact_type: str | None = None, query: str | None = None,
                     limit: int = 20) -> list[dict]:
        sql = "SELECT fact_type, key, value, source FROM facts WHERE 1=1"
        params: list[Any] = []
        if fact_type:
            sql += " AND fact_type=?"
            params.append(fact_type)
        if query:
            sql += " AND (key LIKE ? OR value LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])
        sql += " LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
            return [
                {"fact_type": r[0], "key": r[1], "value": json.loads(r[2]), "source": r[3]}
                for r in rows
            ]

    def seed_if_empty(self, seed_dir: str | Path) -> None:
        """Seed the DB from JSON files in seed_dir if the DB is empty."""
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        if count > 0:
            return
        seed_dir = Path(seed_dir)
        if not seed_dir.exists():
            return
        for json_file in seed_dir.glob("*.json"):
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                continue
            for item in data:
                self.add_fact(
                    fact_type=item.get("type", "concept"),
                    key=item.get("key", ""),
                    value=item.get("value", {}),
                    source=item.get("source", "seed"),
                )

    def summary(self) -> str:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT fact_type, COUNT(*) FROM facts GROUP BY fact_type"
            ).fetchall()
        if not rows:
            return "## Semantic Memory\n(empty)"
        lines = ["## Semantic Memory (cybersecurity facts)"]
        for fact_type, count in rows:
            lines.append(f"  - {fact_type}: {count} facts")
        return "\n".join(lines)
