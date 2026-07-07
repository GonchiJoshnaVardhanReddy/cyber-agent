"""agent/memory/world.py — World Memory (graph).

Maintains the agent's live understanding of the target environment: hosts,
networks, services, technologies, users, credentials, trust relationships,
findings, attack paths. Backed by NetworkX for v1 (in-memory). The interface
is abstracted so you can swap in Neo4j/FalkorDB later without changing callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx


@dataclass
class Node:
    """A node in the world graph."""
    id: str  # unique id (e.g., "host:scanme.nmap.org")
    kind: str  # host | service | user | credential | technology | finding | network
    label: str
    properties: dict[str, Any] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}


@dataclass
class Edge:
    """An edge in the world graph."""
    source: str
    target: str
    kind: str  # runs | has_service | trusts | has_credential | exposes | finds
    properties: dict[str, Any] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}


class WorldMemory:
    """Graph-backed world memory. v1: NetworkX (in-memory). v2: Neo4j."""

    def __init__(self, backend: str = "networkx", neo4j_config: dict | None = None):
        self.backend = backend
        if backend == "networkx":
            self._graph: nx.DiGraph = nx.DiGraph()
        elif backend == "neo4j":
            # TODO v2: implement Neo4j backing
            # from neo4j import GraphDatabase
            # self._driver = GraphDatabase.driver(**neo4j_config)
            raise NotImplementedError("Neo4j backend is a v2 roadmap item. Use networkx for now.")
        else:
            raise ValueError(f"Unknown world memory backend: {backend}")

    # ---- Mutation ----

    def add_node(self, node: Node) -> None:
        self._graph.add_node(node.id, kind=node.kind, label=node.label, **node.properties)

    def add_edge(self, edge: Edge) -> None:
        self._graph.add_edge(
            edge.source, edge.target, kind=edge.kind, **edge.properties
        )

    def upsert_host(self, hostname: str, **props) -> str:
        """Add or update a host node. Returns its id."""
        node_id = f"host:{hostname}"
        if node_id not in self._graph:
            self._graph.add_node(node_id, kind="host", label=hostname, **props)
        else:
            self._graph.nodes[node_id].update(props)
        return node_id

    def upsert_service(self, host: str, port: int, proto: str, **props) -> str:
        """Add or update a service node + RUNS edge. Returns the service id."""
        host_id = self.upsert_host(host)
        svc_id = f"service:{host}:{port}:{proto}"
        self._graph.add_node(svc_id, kind="service", label=f"{host}:{port}/{proto}", **props)
        self._graph.add_edge(host_id, svc_id, kind="has_service")
        return svc_id

    def add_finding(self, host: str, title: str, severity: str, **props) -> str:
        """Add a finding node + FINDS edge. Returns the finding id."""
        host_id = self.upsert_host(host) if f"host:{host}" not in self._graph else f"host:{host}"
        finding_id = f"finding:{len(self._graph.nodes):04d}"
        self._graph.add_node(
            finding_id, kind="finding", label=title,
            severity=severity, **props,
        )
        self._graph.add_edge(f"host:{host}", finding_id, kind="finds")
        return finding_id

    def add_credential(self, host: str, username: str, secret: str, secret_type: str = "password") -> str:
        """Add a credential node (NEVER stores the secret in plaintext — only a hash)."""
        import hashlib
        host_id = self.upsert_host(host)
        cred_id = f"cred:{host}:{username}"
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()[:16]
        self._graph.add_node(
            cred_id, kind="credential", label=f"{username}@{host}",
            username=username, secret_hash=secret_hash, secret_type=secret_type,
            # NEVER store plaintext secret in the world model
        )
        self._graph.add_edge(host_id, cred_id, kind="has_credential")
        return cred_id

    # ---- Query ----

    def get_node(self, node_id: str) -> dict | None:
        if node_id not in self._graph:
            return None
        return dict(self._graph.nodes[node_id])

    def find_hosts(self) -> list[str]:
        return [n for n, d in self._graph.nodes(data=True) if d.get("kind") == "host"]

    def find_services_on(self, host: str) -> list[dict]:
        host_id = f"host:{host}"
        if host_id not in self._graph:
            return []
        result = []
        for _, target, data in self._graph.out_edges(host_id, data=True):
            if data.get("kind") == "has_service":
                result.append({"id": target, **self._graph.nodes[target]})
        return result

    def find_findings_on(self, host: str) -> list[dict]:
        host_id = f"host:{host}"
        if host_id not in self._graph:
            return []
        result = []
        for _, target, data in self._graph.out_edges(host_id, data=True):
            if data.get("kind") == "finds":
                result.append({"id": target, **self._graph.nodes[target]})
        return result

    def attack_paths(self, source_host: str, target_host: str | None = None) -> list[list[str]]:
        """Find all simple paths from source to target (or any reachable host)."""
        source_id = f"host:{source_host}"
        if source_id not in self._graph:
            return []
        paths = []
        targets = [f"host:{target_host}"] if target_host else [
            n for n, d in self._graph.nodes(data=True) if d.get("kind") == "host"
        ]
        for t in targets:
            if t == source_id or t not in self._graph:
                continue
            try:
                for path in nx.all_simple_paths(self._graph, source_id, t, cutoff=6):
                    paths.append(path)
            except nx.NetworkXError:
                continue
        return paths[:20]  # cap

    def summary(self) -> str:
        """Compact summary for the system prompt."""
        n_hosts = sum(1 for _, d in self._graph.nodes(data=True) if d.get("kind") == "host")
        n_services = sum(1 for _, d in self._graph.nodes(data=True) if d.get("kind") == "service")
        n_findings = sum(1 for _, d in self._graph.nodes(data=True) if d.get("kind") == "finding")
        n_creds = sum(1 for _, d in self._graph.nodes(data=True) if d.get("kind") == "credential")
        lines = [
            "## World Memory (target environment)",
            f"Hosts: {n_hosts}, Services: {n_services}, Findings: {n_findings}, Credentials: {n_creds}",
        ]
        if n_hosts:
            lines.append("Known hosts:")
            for h in self.find_hosts()[:10]:
                lines.append(f"  - {h.replace('host:', '')}")
        return "\n".join(lines)

    def export_dot(self) -> str:
        """Export the graph as Graphviz DOT format (for attack-path visualization)."""
        lines = ["digraph world {", '  rankdir=LR;']
        for node_id, data in self._graph.nodes(data=True):
            kind = data.get("kind", "node")
            label = data.get("label", node_id)
            color = {
                "host": "#4675a4", "service": "#3d7f53", "finding": "#ab524a",
                "credential": "#a6884d", "technology": "#6f4fce",
            }.get(kind, "#8e8c85")
            lines.append(f'  "{node_id}" [label="{label}", color="{color}", style=filled, fillcolor="{color}33"];')
        for u, v, data in self._graph.edges(data=True):
            kind = data.get("kind", "edge")
            lines.append(f'  "{u}" -> "{v}" [label="{kind}"];')
        lines.append("}")
        return "\n".join(lines)
