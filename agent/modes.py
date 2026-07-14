"""agent/modes.py — Agent mode management (Normal vs Hack mode).

This module implements the two-mode operation:
1. NORMAL MODE: General assistant capabilities (file ops, web search, code execution, etc.)
2. HACK MODE: Offensive security operations with structured methodology

HACK MODE WORKFLOW:
1. INITIALIZATION: Set target, scope, restrictions
2. RECON: Comprehensive reconnaissance using all available tools
3. HYPOTHESIS: LLM generates hypotheses from recon data
4. TESTING: Vulnerability scanning and validation
5. REPORTING: Generate findings report
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AgentMode(Enum):
    """Agent operating mode."""
    NORMAL = "normal"
    HACK = "hack"


class ReconStage(Enum):
    """Reconnaissance stages."""
    NOT_STARTED = "not_started"
    PASSIVE_OSINT = "passive_osint"  # WHOIS, DNS, Shodan, etc.
    ACTIVE_SCAN = "active_scan"  # Nmap, Masscan, etc.
    SUBDOMAIN_ENUM = "subdomain_enum"  # Subfinder, Amass, etc.
    WEB_DISCOVERY = "web_discovery"  # Dirbusting, crawling
    COMPLETE = "complete"


class TestStage(Enum):
    """Vulnerability testing stages."""
    NOT_STARTED = "not_started"
    WEB_VULN_SCAN = "web_vuln_scan"  # Nikto, Nuclei, ZAP
    SERVICE_ENUM = "service_enum"  # Service-specific tests
    EXPLOITATION = "exploitation"  # Metasploit, custom exploits
    COMPLETE = "complete"


@dataclass
class HackSession:
    """State container for hack mode operations."""
    
    # Engagement details
    target: str = ""
    scope: list[str] = field(default_factory=list)
    excluded_targets: list[str] = field(default_factory=list)
    engagement_type: str = "bug_bounty"  # bug_bounty | red_team | pentest
    start_time: datetime | None = None
    
    # Recon state
    recon_stage: ReconStage = ReconStage.NOT_STARTED
    recon_data: dict[str, Any] = field(default_factory=dict)
    
    # Hypotheses
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    
    # Testing state
    test_stage: TestStage = TestStage.NOT_STARTED
    findings: list[dict[str, Any]] = field(default_factory=list)
    
    # Tools used
    tools_executed: list[str] = field(default_factory=list)
    
    def add_hypothesis(self, title: str, description: str, 
                       confidence: str = "medium", 
                       related_hosts: list[str] | None = None) -> None:
        """Add a hypothesis to test."""
        self.hypotheses.append({
            "title": title,
            "description": description,
            "confidence": confidence,
            "related_hosts": related_hosts or [],
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        })
    
    def update_hypothesis_status(self, title: str, status: str, 
                                  evidence: str | None = None) -> None:
        """Update hypothesis status after testing."""
        for hyp in self.hypotheses:
            if hyp["title"] == title:
                hyp["status"] = status
                if evidence:
                    hyp["evidence"] = evidence
                break
    
    def add_finding(self, title: str, severity: str, description: str,
                    affected_host: str, evidence: str, 
                    cve: str | None = None, 
                    remediation: str | None = None) -> None:
        """Add a confirmed finding."""
        self.findings.append({
            "title": title,
            "severity": severity,  # critical | high | medium | low | info
            "description": description,
            "affected_host": affected_host,
            "evidence": evidence,
            "cve": cve,
            "remediation": remediation,
            "discovered_at": datetime.now().isoformat(),
        })
    
    def get_scope_summary(self) -> str:
        """Get human-readable scope summary."""
        lines = [f"Target: {self.target}"]
        lines.append(f"Engagement Type: {self.engagement_type}")
        lines.append(f"Scope ({len(self.scope)} items):")
        for item in self.scope[:10]:
            lines.append(f"  - {item}")
        if len(self.scope) > 10:
            lines.append(f"  ... and {len(self.scope) - 10} more")
        if self.excluded_targets:
            lines.append(f"Excluded ({len(self.excluded_targets)} items):")
            for item in self.excluded_targets[:5]:
                lines.append(f"  - {item}")
        return "\n".join(lines)


@dataclass
class ModeTransition:
    """Record of mode transitions for audit."""
    from_mode: AgentMode
    to_mode: AgentMode
    timestamp: datetime
    reason: str
    user: str


class ModeManager:
    """Manages agent mode transitions and hack session state."""
    
    def __init__(self):
        self.current_mode = AgentMode.NORMAL
        self.hack_session: HackSession | None = None
        self.transition_history: list[ModeTransition] = []
    
    def switch_to_hack_mode(self, target: str, scope: list[str],
                            excluded: list[str] | None = None,
                            engagement_type: str = "bug_bounty",
                            user: str = "operator") -> HackSession:
        """Switch agent to hack mode with specified parameters."""
        if self.current_mode == AgentMode.HACK and self.hack_session:
            raise RuntimeError(
                "Already in hack mode. Use exit_hack_mode() first."
            )
        
        # Validate inputs
        if not target:
            raise ValueError("Target is required")
        if not scope:
            raise ValueError("Scope cannot be empty")
        
        # Create hack session
        self.hack_session = HackSession(
            target=target,
            scope=scope,
            excluded_targets=excluded or [],
            engagement_type=engagement_type,
            start_time=datetime.now(),
        )
        
        # Record transition
        self._record_transition(
            AgentMode.NORMAL, 
            AgentMode.HACK,
            f"Starting hack mode for target: {target}",
            user,
        )
        
        self.current_mode = AgentMode.HACK
        return self.hack_session
    
    def exit_hack_mode(self, user: str = "operator") -> None:
        """Exit hack mode, returning to normal mode."""
        if self.current_mode != AgentMode.HACK:
            raise RuntimeError("Not in hack mode")
        
        self._record_transition(
            AgentMode.HACK,
            AgentMode.NORMAL,
            "Exiting hack mode",
            user,
        )
        
        self.current_mode = AgentMode.NORMAL
        # Keep hack_session for reference but mark as inactive
        if self.hack_session:
            self.hack_session.recon_stage = ReconStage.COMPLETE
            self.hack_session.test_stage = TestStage.COMPLETE
    
    def _record_transition(self, from_mode: AgentMode, to_mode: AgentMode,
                           reason: str, user: str) -> None:
        """Record a mode transition."""
        self.transition_history.append(ModeTransition(
            from_mode=from_mode,
            to_mode=to_mode,
            timestamp=datetime.now(),
            reason=reason,
            user=user,
        ))
    
    def is_in_hack_mode(self) -> bool:
        """Check if agent is in hack mode."""
        return self.current_mode == AgentMode.HACK
    
    def get_current_mode(self) -> AgentMode:
        """Get current agent mode."""
        return self.current_mode
    
    def get_hack_session(self) -> HackSession | None:
        """Get current hack session (only valid in hack mode)."""
        if not self.is_in_hack_mode():
            return None
        return self.hack_session
    
    def update_recon_stage(self, stage: ReconStage) -> None:
        """Update recon stage."""
        if self.hack_session:
            self.hack_session.recon_stage = stage
    
    def update_test_stage(self, stage: TestStage) -> None:
        """Update testing stage."""
        if self.hack_session:
            self.hack_session.test_stage = stage
    
    def record_tool_execution(self, tool_name: str) -> None:
        """Record that a tool was executed."""
        if self.hack_session:
            self.hack_session.tools_executed.append(tool_name)
    
    def get_status(self) -> str:
        """Get human-readable status."""
        if self.current_mode == AgentMode.NORMAL:
            return "Mode: NORMAL (general assistant)"
        
        if not self.hack_session:
            return "Mode: HACK (no active session)"
        
        lines = [
            "Mode: HACK (offensive security)",
            self.hack_session.get_scope_summary(),
            f"\nRecon Stage: {self.hack_session.recon_stage.value}",
            f"Test Stage: {self.hack_session.test_stage.value}",
            f"Hypotheses: {len(self.hack_session.hypotheses)}",
            f"Findings: {len(self.hack_session.findings)}",
            f"Tools Executed: {len(self.hack_session.tools_executed)}",
        ]
        return "\n".join(lines)
