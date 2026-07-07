"""agent/audit.py — Append-only audit log of every tool call and decision.

Every action the agent takes is recorded here. This is non-negotiable for
offensive security work — you need a defensible record of what happened, when,
and who authorized it.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any


class AuditLog:
    """Append-only audit log. Writes to both a JSON-lines file and a SQLite table."""

    def __init__(self, log_path: str | Path, db_path: str | Path | None = None,
                 engagement_id: str = "unknown"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path) if db_path else None
        self.engagement_id = engagement_id
        if self.db_path:
            self._init_db()

    def _init_db(self) -> None:
        assert self.db_path is not None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    engagement_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    tool_name TEXT,
                    target TEXT,
                    args_json TEXT,
                    result_json TEXT,
                    approved_by TEXT,
                    success INTEGER,
                    detail TEXT
                )
            """)
            conn.commit()

    def record(
        self,
        event_type: str,
        tool_name: str | None = None,
        target: str | None = None,
        args: dict[str, Any] | None = None,
        result: Any = None,
        approved_by: str | None = None,
        success: bool = True,
        detail: str | None = None,
    ) -> None:
        """Record one audit event. Never raises — audit must not break the agent."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "engagement_id": self.engagement_id,
            "event_type": event_type,
            "tool_name": tool_name,
            "target": target,
            "args": args,
            "result": _truncate_for_log(result),
            "approved_by": approved_by,
            "success": success,
            "detail": detail,
        }
        # 1. Append to JSON-lines file
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass  # never let audit break the agent

        # 2. Insert into SQLite
        if self.db_path:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """INSERT INTO audit_log
                           (timestamp, engagement_id, event_type, tool_name, target,
                            args_json, result_json, approved_by, success, detail)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (
                            entry["timestamp"], entry["engagement_id"], event_type,
                            tool_name, target,
                            json.dumps(args, default=str) if args else None,
                            json.dumps(entry["result"], default=str)[:8000],
                            approved_by, 1 if success else 0, detail,
                        ),
                    )
                    conn.commit()
            except Exception:
                pass

    def query(self, limit: int = 100, event_type: str | None = None) -> list[dict]:
        """Query recent audit events."""
        if not self.db_path:
            return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if event_type:
                rows = conn.execute(
                    "SELECT * FROM audit_log WHERE event_type=? ORDER BY id DESC LIMIT ?",
                    (event_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]


def _truncate_for_log(result: Any, max_len: int = 4000) -> Any:
    """Truncate large results so the log doesn't blow up."""
    if isinstance(result, str) and len(result) > max_len:
        return result[:max_len] + f"\n... [truncated, {len(result)} total chars]"
    if isinstance(result, (list, tuple)) and len(str(result)) > max_len:
        return f"[{type(result).__name__} with {len(result)} items, truncated]"
    return result
