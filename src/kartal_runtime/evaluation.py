from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .models import EdgeKind, NodeKind
from .provenance import DecisionProvenanceGraph


@dataclass(frozen=True, slots=True)
class ProcessMetrics:
    claim_count: int
    grounded_claim_count: int
    evidence_coverage: float
    required_link_count: int
    present_link_count: int
    provenance_completeness: float
    policy_denial_count: int
    approval_required_count: int
    error_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_process(graph: DecisionProvenanceGraph) -> ProcessMetrics:
    claims = graph.nodes(kind=NodeKind.CLAIM)
    unsupported = graph.unsupported_claims()
    grounded = len(claims) - len(unsupported)
    coverage = _ratio(grounded, len(claims))

    required_links = 0
    present_links = 0
    for node in graph.nodes():
        accepted: set[EdgeKind] | None = None
        if node.kind is NodeKind.CLAIM:
            accepted = {EdgeKind.SUPPORTS, EdgeKind.DERIVED_FROM}
        elif node.kind is NodeKind.DECISION:
            accepted = {EdgeKind.INFORMED}
        elif node.kind is NodeKind.ACTION:
            accepted = {EdgeKind.TRIGGERED}
        elif node.kind is NodeKind.OBSERVATION:
            if node.payload.get("event") != "run_completed":
                accepted = {EdgeKind.PRODUCED}
        elif node.kind is NodeKind.ERROR:
            accepted = {EdgeKind.FAILED_AT}

        if accepted is not None:
            required_links += 1
            if any(edge.kind in accepted for edge in graph.incoming(node.id)):
                present_links += 1

    decisions = graph.nodes(kind=NodeKind.DECISION)
    policy_denials = sum(node.payload.get("effect") == "deny" for node in decisions)
    approval_required = sum(
        node.payload.get("effect") == "require_approval" for node in decisions
    )
    return ProcessMetrics(
        claim_count=len(claims),
        grounded_claim_count=grounded,
        evidence_coverage=coverage,
        required_link_count=required_links,
        present_link_count=present_links,
        provenance_completeness=_ratio(present_links, required_links),
        policy_denial_count=policy_denials,
        approval_required_count=approval_required,
        error_count=len(graph.nodes(kind=NodeKind.ERROR)),
    )


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator
