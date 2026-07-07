"""agent/memory/episodic.py — Episodic Memory (SQLite).

Records complete histories of previous engagements: assessment timelines,
actions performed, findings, reports, evidence references.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class EpisodicMemory:
    """SQLite-backed engagement history. One row per episode + per action."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,           -- engagement id
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    operator TEXT,
                    client TEXT,
                    summary TEXT,
                    findings_count INTEGER DEFAULT 0,
                    metadata_json TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episode_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,    -- observation | action | finding | decision
                    actor TEXT,                  -- agent | operator | tool
                    description TEXT,
                    target TEXT,
                    data_json TEXT,
                    FOREIGN KEY (episode_id) REFERENCES episodes(id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ep_events_episode ON episode_events(episode_id)"
            )
            conn.commit()

    def start_episode(self, episode_id: str, operator: str = "", client: str = "",
                      metadata: dict | None = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO episodes (id, started_at, operator, client, metadata_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (episode_id, datetime.utcnow().isoformat() + "Z", operator, client,
                 json.dumps(metadata or {})),
            )
            conn.commit()

    def end_episode(self, episode_id: str, summary: str = "", findings_count: int = 0) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE episodes SET ended_at=?, summary=?, findings_count=? WHERE id=?",
                (datetime.utcnow().isoformat() + "Z", summary, findings_count, episode_id),
            )
            conn.commit()

    def record_event(self, episode_id: str, event_type: str, description: str,
                     actor: str = "agent", target: str | None = None,
                     data: dict | None = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO episode_events (episode_id, timestamp, event_type, actor, "
                "description, target, data_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (episode_id, datetime.utcnow().isoformat() + "Z", event_type, actor,
                 description, target, json.dumps(data or {}, default=str)),
            )
            conn.commit()

    def list_episodes(self, limit: int = 20) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM episodes ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_events(self, episode_id: str, limit: int = 100) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM episode_events WHERE episode_id=? ORDER BY id DESC LIMIT ?",
                (episode_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def summary(self) -> str:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) as n, MAX(started_at) as last FROM episodes"
            ).fetchone()
            n, last = row if row else (0, None)
        if n == 0:
            return "## Episodic Memory\n(no previous engagements)"
        return f"## Episodic Memory\nPast engagements: {n} (last: {last})"
