from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .provenance import DecisionProvenanceGraph


@dataclass(frozen=True, slots=True)
class ReplayReport:
    run_id: str
    integrity_valid: bool
    node_count: int
    edge_count: int
    unsupported_claim_ids: tuple[str, ...]
    head_hash: str


class DryReplay:
    """Reconstruct an execution graph without repeating recorded side effects."""

    @staticmethod
    def reconstruct(snapshot: Mapping[str, Any]) -> tuple[DecisionProvenanceGraph, ReplayReport]:
        graph = DecisionProvenanceGraph.from_snapshot(snapshot)
        report = ReplayReport(
            run_id=graph.run_id,
            integrity_valid=True,
            node_count=len(graph.nodes()),
            edge_count=len(graph.edges()),
            unsupported_claim_ids=tuple(node.id for node in graph.unsupported_claims()),
            head_hash=graph.head_hash,
        )
        return graph, report
