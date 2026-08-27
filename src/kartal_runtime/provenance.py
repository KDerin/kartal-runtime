from __future__ import annotations

import hashlib
from collections import deque
from threading import RLock
from typing import Any, Iterable, Mapping

from ._utils import canonical_json, ensure_jsonable, utc_now
from .models import EdgeKind, JournalEvent, NodeKind, ProvenanceEdge, ProvenanceNode

GENESIS_HASH = "0" * 64


class ProvenanceIntegrityError(ValueError):
    """Raised when a snapshot's event chain is inconsistent or has been modified."""


class DecisionProvenanceGraph:
    """Append-only typed provenance graph with a tamper-evident event journal."""

    def __init__(self, run_id: str) -> None:
        if not run_id.strip():
            raise ValueError("run_id cannot be empty")
        self.run_id = run_id
        self._nodes: dict[str, ProvenanceNode] = {}
        self._edges: list[ProvenanceEdge] = []
        self._events: list[JournalEvent] = []
        self._lock = RLock()

    @property
    def head_hash(self) -> str:
        with self._lock:
            return self._events[-1].event_hash if self._events else GENESIS_HASH

    def add_node(self, node: ProvenanceNode) -> None:
        if node.run_id != self.run_id:
            raise ValueError("node run_id does not match graph run_id")
        if not node.id.strip():
            raise ValueError("node id cannot be empty")
        if node.confidence is not None and not 0.0 <= node.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        ensure_jsonable(node.to_dict(), label="node")

        with self._lock:
            if node.id in self._nodes:
                raise ValueError(f"duplicate node id: {node.id}")
            self._nodes[node.id] = node
            self._append_event("add_node", node.to_dict())

    def add_edge(self, edge: ProvenanceEdge) -> None:
        ensure_jsonable(edge.to_dict(), label="edge")
        with self._lock:
            if edge.source_id not in self._nodes:
                raise KeyError(f"unknown source node: {edge.source_id}")
            if edge.target_id not in self._nodes:
                raise KeyError(f"unknown target node: {edge.target_id}")
            self._edges.append(edge)
            self._append_event("add_edge", edge.to_dict())

    def node(self, node_id: str) -> ProvenanceNode:
        with self._lock:
            try:
                return self._nodes[node_id]
            except KeyError as exc:
                raise KeyError(f"unknown node: {node_id}") from exc

    def nodes(self, *, kind: NodeKind | None = None) -> tuple[ProvenanceNode, ...]:
        with self._lock:
            values = tuple(self._nodes.values())
        if kind is None:
            return values
        return tuple(node for node in values if node.kind is kind)

    def edges(self, *, kind: EdgeKind | None = None) -> tuple[ProvenanceEdge, ...]:
        with self._lock:
            values = tuple(self._edges)
        if kind is None:
            return values
        return tuple(edge for edge in values if edge.kind is kind)

    def incoming(self, node_id: str) -> tuple[ProvenanceEdge, ...]:
        self.node(node_id)
        with self._lock:
            return tuple(edge for edge in self._edges if edge.target_id == node_id)

    def outgoing(self, node_id: str) -> tuple[ProvenanceEdge, ...]:
        self.node(node_id)
        with self._lock:
            return tuple(edge for edge in self._edges if edge.source_id == node_id)

    def ancestors(self, node_id: str) -> tuple[ProvenanceNode, ...]:
        """Return all nodes that can reach ``node_id`` in breadth-first order."""

        self.node(node_id)
        visited: set[str] = set()
        queue = deque(edge.source_id for edge in self.incoming(node_id))
        ordered: list[ProvenanceNode] = []
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            ordered.append(self.node(current))
            queue.extend(edge.source_id for edge in self.incoming(current))
        return tuple(ordered)

    def unsupported_claims(self) -> tuple[ProvenanceNode, ...]:
        grounding_edges = {EdgeKind.SUPPORTS, EdgeKind.DERIVED_FROM}
        return tuple(
            claim
            for claim in self.nodes(kind=NodeKind.CLAIM)
            if not any(edge.kind in grounding_edges for edge in self.incoming(claim.id))
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema_version": "kartal.provenance.v0.1",
                "run_id": self.run_id,
                "nodes": [node.to_dict() for node in self._nodes.values()],
                "edges": [edge.to_dict() for edge in self._edges],
                "events": [event.to_dict() for event in self._events],
                "head_hash": self.head_hash,
            }

    def verify_integrity(self) -> bool:
        return self.verify_snapshot(self.snapshot())

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> DecisionProvenanceGraph:
        cls.verify_snapshot(snapshot)
        graph = cls(str(snapshot["run_id"]))

        nodes = snapshot.get("nodes", [])
        edges = snapshot.get("edges", [])
        events = snapshot.get("events", [])
        if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(events, list):
            raise ProvenanceIntegrityError("snapshot collections must be lists")

        graph._nodes = {
            node.id: node
            for node in (ProvenanceNode.from_dict(value) for value in nodes)
        }
        if len(graph._nodes) != len(nodes):
            raise ProvenanceIntegrityError("snapshot contains duplicate node ids")
        graph._edges = [ProvenanceEdge.from_dict(value) for value in edges]
        graph._events = [JournalEvent.from_dict(value) for value in events]

        for node in graph._nodes.values():
            if node.run_id != graph.run_id:
                raise ProvenanceIntegrityError("node belongs to a different run")
        for edge in graph._edges:
            if edge.source_id not in graph._nodes or edge.target_id not in graph._nodes:
                raise ProvenanceIntegrityError("edge references an unknown node")
        return graph

    @staticmethod
    def verify_snapshot(snapshot: Mapping[str, Any]) -> bool:
        raw_events = snapshot.get("events", [])
        if not isinstance(raw_events, list):
            raise ProvenanceIntegrityError("events must be a list")

        previous = GENESIS_HASH
        for expected_sequence, raw in enumerate(raw_events, start=1):
            if not isinstance(raw, Mapping):
                raise ProvenanceIntegrityError("event must be an object")
            event = JournalEvent.from_dict(raw)
            if event.sequence != expected_sequence:
                raise ProvenanceIntegrityError("event sequence is not contiguous")
            if event.previous_hash != previous:
                raise ProvenanceIntegrityError("event previous_hash does not match chain")
            expected_hash = _event_hash(
                sequence=event.sequence,
                timestamp=event.timestamp,
                operation=event.operation,
                data=event.data,
                previous_hash=event.previous_hash,
            )
            if event.event_hash != expected_hash:
                raise ProvenanceIntegrityError("event hash verification failed")
            previous = event.event_hash

        if str(snapshot.get("head_hash", GENESIS_HASH)) != previous:
            raise ProvenanceIntegrityError("head_hash does not match final event")

        DecisionProvenanceGraph._verify_materialized_state(snapshot, raw_events)
        return True

    @staticmethod
    def _verify_materialized_state(
        snapshot: Mapping[str, Any], raw_events: Iterable[Mapping[str, Any]]
    ) -> None:
        event_nodes: list[Mapping[str, Any]] = []
        event_edges: list[Mapping[str, Any]] = []
        for raw in raw_events:
            operation = str(raw["operation"])
            data = raw.get("data", {})
            if not isinstance(data, Mapping):
                raise ProvenanceIntegrityError("event data must be an object")
            if operation == "add_node":
                event_nodes.append(data)
            elif operation == "add_edge":
                event_edges.append(data)
            else:
                raise ProvenanceIntegrityError(f"unknown journal operation: {operation}")

        if canonical_json(snapshot.get("nodes", [])) != canonical_json(event_nodes):
            raise ProvenanceIntegrityError("materialized nodes do not match journal")
        if canonical_json(snapshot.get("edges", [])) != canonical_json(event_edges):
            raise ProvenanceIntegrityError("materialized edges do not match journal")

    def _append_event(self, operation: str, data: Mapping[str, Any]) -> None:
        timestamp = utc_now()
        sequence = len(self._events) + 1
        previous_hash = self._events[-1].event_hash if self._events else GENESIS_HASH
        event_hash = _event_hash(
            sequence=sequence,
            timestamp=timestamp,
            operation=operation,
            data=data,
            previous_hash=previous_hash,
        )
        self._events.append(
            JournalEvent(
                sequence=sequence,
                timestamp=timestamp,
                operation=operation,
                data=dict(data),
                previous_hash=previous_hash,
                event_hash=event_hash,
            )
        )


def _event_hash(
    *,
    sequence: int,
    timestamp: str,
    operation: str,
    data: Mapping[str, Any],
    previous_hash: str,
) -> str:
    body = {
        "sequence": sequence,
        "timestamp": timestamp,
        "operation": operation,
        "data": dict(data),
        "previous_hash": previous_hash,
    }
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
