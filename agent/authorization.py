"""agent/authorization.py — Rules of Engagement enforcement + scope checking.

The agent refuses to act without a valid, signed RoE. Every tool call is checked
against the scope before execution. This is the ethical backbone of the agent.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ScopeRule:
    """One in-scope target. Can be a hostname glob, IP, IP range, or URL prefix."""
    pattern: str
    kind: str  # "hostname" | "ip" | "cidr" | "url" | "regex"

    def matches(self, target: str) -> bool:
        target = target.strip().lower()
        if self.kind == "hostname":
            # Support wildcard like *.example.com
            if self.pattern.startswith("*."):
                suffix = self.pattern[1:]  # .example.com
                return target == self.pattern[2:] or target.endswith(suffix)
            return target == self.pattern
        if self.kind == "ip":
            return target == self.pattern
        if self.kind == "cidr":
            try:
                return ipaddress.ip_address(target) in ipaddress.ip_network(self.pattern)
            except ValueError:
                return False
        if self.kind == "url":
            return target.startswith(self.pattern) or target.rstrip("/") == self.pattern.rstrip("/")
        if self.kind == "regex":
            return bool(re.search(self.pattern, target))
        return False


def _classify_target(pattern: str) -> ScopeRule:
    """Auto-detect what kind of scope pattern this is."""
    pattern = pattern.strip()
    # CIDR
    if "/" in pattern:
        try:
            ipaddress.ip_network(pattern, strict=False)
            return ScopeRule(pattern=pattern, kind="cidr")
        except ValueError:
            pass
    # Bare IP
    try:
        ipaddress.ip_address(pattern)
        return ScopeRule(pattern=pattern, kind="ip")
    except ValueError:
        pass
    # URL
    if pattern.startswith(("http://", "https://")):
        return ScopeRule(pattern=pattern, kind="url")
    # Hostname (possibly wildcard)
    return ScopeRule(pattern=pattern.lower(), kind="hostname")


@dataclass
class RulesOfEngagement:
    """Parsed RoE file. The agent holds one of these for the duration of an engagement."""

    engagement_id: str
    engagement_type: str
    client: str
    start_time: datetime
    end_time: datetime
    lead_operator: str
    authorization_reference: str
    in_scope: list[ScopeRule] = field(default_factory=list)
    out_of_scope: list[ScopeRule] = field(default_factory=list)
    allowed_activities: list[str] = field(default_factory=list)
    prohibited_actions: list[str] = field(default_factory=list)
    signed_by: str = ""
    signed_date: str = ""
    file_hash: str = ""
    hard_blocklist: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path, hard_blocklist: list[str] | None = None) -> "RulesOfEngagement":
        """Load RoE from YAML file. Raises ValueError if file is missing or invalid."""
        path = Path(path)
        if not path.exists():
            raise ValueError(f"Rules of Engagement file not found: {path}")
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ValueError("RoE file is not valid YAML mapping")

        # Required fields
        engagement_id = data.get("Engagement ID", "").strip()
        if not engagement_id:
            raise ValueError("RoE missing 'Engagement ID'")

        scope = data.get("Authorized Scope", {}) or {}
        in_scope_raw = scope.get("In-Scope Targets", []) or []
        out_scope_raw = scope.get("Out-of-Scope", []) or []

        in_scope = [_classify_target(t) for t in in_scope_raw]
        out_of_scope = [_classify_target(t) for t in out_scope_raw]

        # Compute file hash for tamper detection
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        return cls(
            engagement_id=engagement_id,
            engagement_type=data.get("Engagement Type", ""),
            client=data.get("Client / Program Name", ""),
            start_time=datetime.fromisoformat(
                data.get("Engagement Start", "2000-01-01 00:00").replace(" (UTC)", "")
            ),
            end_time=datetime.fromisoformat(
                data.get("Engagement End", "2099-12-31 23:59").replace(" (UTC)", "")
            ),
            lead_operator=data.get("Lead Operator", ""),
            authorization_reference=data.get("Authorization Reference", ""),
            in_scope=in_scope,
            out_of_scope=out_of_scope,
            allowed_activities=scope.get("Allowed Activity Types", []) or [],
            prohibited_actions=scope.get("Prohibited Actions", []) or [],
            signed_by=data.get("Signed", ""),
            signed_date=data.get("Date", ""),
            file_hash=file_hash,
            hard_blocklist=hard_blocklist or [],
        )

    def is_target_in_scope(self, target: str) -> tuple[bool, str]:
        """Check if a target is in scope. Returns (allowed, reason)."""
        target = target.strip().lower()

        # 1. Hard blocklist always wins
        for blocked in self.hard_blocklist:
            if blocked.lower() in target:
                return False, f"Target '{target}' matches hard blocklist pattern '{blocked}'"

        # 2. Out-of-scope wins over in-scope
        for rule in self.out_of_scope:
            if rule.matches(target):
                return False, f"Target '{target}' is explicitly out-of-scope"

        # 3. Must be in-scope
        for rule in self.in_scope:
            if rule.matches(target):
                return True, f"Target '{target}' is in scope"

        return False, f"Target '{target}' is not in scope"

    def is_activity_allowed(self, activity: str) -> bool:
        """Check if an activity type is allowed by the RoE."""
        activity = activity.strip().lower()
        for allowed in self.allowed_activities:
            if activity in allowed.lower():
                return True
        return False

    def is_active(self) -> bool:
        """Check if current time is within the engagement window."""
        now = datetime.utcnow()
        return self.start_time <= now <= self.end_time

    def summary(self) -> str:
        """Human-readable summary for the system prompt."""
        in_scope_str = "\n".join(f"    - {r.pattern}" for r in self.in_scope) or "    (none)"
        return (
            f"Engagement ID: {self.engagement_id}\n"
            f"Type: {self.engagement_type}\n"
            f"Client: {self.client}\n"
            f"Operator: {self.lead_operator}\n"
            f"Window: {self.start_time} to {self.end_time} (UTC)\n"
            f"In-Scope Targets:\n{in_scope_str}\n"
            f"Allowed Activities: {', '.join(self.allowed_activities)}\n"
            f"RoE File SHA-256: {self.file_hash[:16]}..."
        )
