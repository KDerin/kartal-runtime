from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._utils import utc_now


class NodeKind(str, Enum):
    RUN = "run"
    EVIDENCE = "evidence"
    CLAIM = "claim"
    DECISION = "decision"
    ACTION = "action"
    OBSERVATION = "observation"
    APPROVAL = "approval"
    ERROR = "error"


class EdgeKind(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    INFORMED = "informed"
    TRIGGERED = "triggered"
    PRODUCED = "produced"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED_AT = "failed_at"
    PART_OF = "part_of"


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PolicyEffect(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ProvenanceNode:
    id: str
    kind: NodeKind
    payload: Mapping[str, Any]
    run_id: str
    created_at: str = field(default_factory=utc_now)
    agent_id: str | None = None
    confidence: float | None = None
    source_uri: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "payload": dict(self.payload),
            "run_id": self.run_id,
            "created_at": self.created_at,
            "agent_id": self.agent_id,
            "confidence": self.confidence,
            "source_uri": self.source_uri,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ProvenanceNode:
        return cls(
            id=str(value["id"]),
            kind=NodeKind(str(value["kind"])),
            payload=dict(value.get("payload", {})),
            run_id=str(value["run_id"]),
            created_at=str(value["created_at"]),
            agent_id=_optional_string(value.get("agent_id")),
            confidence=_optional_float(value.get("confidence")),
            source_uri=_optional_string(value.get("source_uri")),
        )


@dataclass(frozen=True, slots=True)
class ProvenanceEdge:
    source_id: str
    target_id: str
    kind: EdgeKind
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "kind": self.kind.value,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ProvenanceEdge:
        return cls(
            source_id=str(value["source_id"]),
            target_id=str(value["target_id"]),
            kind=EdgeKind(str(value["kind"])),
            metadata=dict(value.get("metadata", {})),
            created_at=str(value["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class JournalEvent:
    sequence: int
    timestamp: str
    operation: str
    data: Mapping[str, Any]
    previous_hash: str
    event_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "operation": self.operation,
            "data": dict(self.data),
            "previous_hash": self.previous_hash,
            "event_hash": self.event_hash,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> JournalEvent:
        return cls(
            sequence=int(value["sequence"]),
            timestamp=str(value["timestamp"]),
            operation=str(value["operation"]),
            data=dict(value.get("data", {})),
            previous_hash=str(value["previous_hash"]),
            event_hash=str(value["event_hash"]),
        )


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    run_id: str
    agent_id: str
    action: str
    tool_name: str
    risk: float
    evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuleResult:
    rule: str
    effect: PolicyEffect
    reason: str


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    effect: PolicyEffect
    reasons: tuple[str, ...]
    rule_results: tuple[RuleResult, ...]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    handler: Any
    risk: float = 0.0
    description: str = ""


@dataclass(frozen=True, slots=True)
class ToolExecution:
    value: Any
    decision_node_id: str
    action_node_id: str
    observation_node_id: str


def _optional_string(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
