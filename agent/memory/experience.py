"""agent/memory/experience.py — Experience Memory (SQLite).

Captures lessons learned and improves future decision-making: successful
techniques, failed approaches, strategy effectiveness, planner feedback.
Continuously updated and consulted during planning.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path


class ExperienceMemory:
    """SQLite-backed lessons learned."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    episode_id TEXT,
                    technique TEXT NOT NULL,    -- e.g., "nmap-full-scan", "sqlmap-default"
                    target_kind TEXT,           -- e.g., "web-app", "linux-host"
                    success INTEGER NOT NULL,   -- 1 or 0
                    context TEXT,               -- description of when this was tried
                    outcome TEXT,               -- what happened
                    lesson TEXT,                -- the takeaway
                    reuse_advice TEXT,          -- when to use this technique again
                    tags_json TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lessons_technique ON lessons(technique)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lessons_target_kind ON lessons(target_kind)"
            )
            conn.commit()

    def record_lesson(
        self, technique: str, success: bool, context: str = "", outcome: str = "",
        lesson: str = "", reuse_advice: str = "", target_kind: str = "",
        episode_id: str = "", tags: list[str] | None = None,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO lessons (created_at, episode_id, technique, target_kind,
                   success, context, outcome, lesson, reuse_advice, tags_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (datetime.utcnow().isoformat() + "Z", episode_id, technique, target_kind,
                 1 if success else 0, context, outcome, lesson, reuse_advice,
                 json.dumps(tags or [])),
            )
            conn.commit()

    def lookup(self, technique: str | None = None, target_kind: str | None = None,
               limit: int = 10) -> list[dict]:
        sql = "SELECT * FROM lessons WHERE 1=1"
        params: list = []
        if technique:
            sql += " AND technique=?"
            params.append(technique)
        if target_kind:
            sql += " AND target_kind=?"
            params.append(target_kind)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def success_rate(self, technique: str) -> float:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) as n, SUM(success) as s FROM lessons WHERE technique=?",
                (technique,),
            ).fetchone()
            if not row or not row[0]:
                return 0.5  # unknown — neutral prior
            return row[1] / row[0]

    def summary(self) -> str:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT technique, COUNT(*) as n, SUM(success) as s "
                "FROM lessons GROUP BY technique ORDER BY n DESC LIMIT 5"
            ).fetchall()
        if not rows:
            return "## Experience Memory\n(no lessons yet)"
        lines = ["## Experience Memory (recent lessons)"]
        for tech, n, s in rows:
            lines.append(f"  - {tech}: {s}/{n} successful ({(s/n)*100:.0f}%)")
        return "\n".join(lines)
