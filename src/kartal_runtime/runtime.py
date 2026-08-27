from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from uuid import uuid4

from ._utils import ensure_jsonable
from .models import (
    EdgeKind,
    NodeKind,
    PolicyEffect,
    PolicyRequest,
    ProvenanceEdge,
    ProvenanceNode,
    RunStatus,
    ToolExecution,
    ToolSpec,
)
from .policy import PolicyEngine, default_policy
from .provenance import DecisionProvenanceGraph


class RuntimeErrorBase(RuntimeError):
    def __init__(self, message: str, *, decision_node_id: str | None = None) -> None:
        super().__init__(message)
        self.decision_node_id = decision_node_id


class PolicyDenied(RuntimeErrorBase):
    """Raised before execution when policy denies an action."""


class ApprovalRequired(RuntimeErrorBase):
    """Raised before execution when a human approval artifact is required."""


class ToolExecutionFailed(RuntimeErrorBase):
    """Raised after a tool failure has been recorded in provenance."""

    def __init__(self, message: str, *, error_node_id: str, decision_node_id: str) -> None:
        super().__init__(message, decision_node_id=decision_node_id)
        self.error_node_id = error_node_id


@dataclass(slots=True)
class _Run:
    graph: DecisionProvenanceGraph
    task: str
    status: RunStatus


class AgentRuntime:
    """Model-independent runtime for governed tool execution and provenance."""

    def __init__(self, *, policy: PolicyEngine | None = None) -> None:
        self.policy = policy or default_policy()
        self._tools: dict[str, ToolSpec] = {}
        self._runs: dict[str, _Run] = {}

    def register_tool(self, tool: ToolSpec) -> None:
        if not tool.name.strip():
            raise ValueError("tool name cannot be empty")
        if not callable(tool.handler):
            raise TypeError("tool handler must be callable")
        if not 0.0 <= tool.risk <= 1.0:
            raise ValueError("tool risk must be between 0 and 1")
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def start_run(self, task: str, *, run_id: str | None = None) -> str:
        if not task.strip():
            raise ValueError("task cannot be empty")
        selected_id = run_id or _id("run")
        if selected_id in self._runs:
            raise ValueError(f"run already exists: {selected_id}")

        graph = DecisionProvenanceGraph(selected_id)
        graph.add_node(
            ProvenanceNode(
                id=selected_id,
                kind=NodeKind.RUN,
                payload={"task": task},
                run_id=selected_id,
            )
        )
        self._runs[selected_id] = _Run(graph=graph, task=task, status=RunStatus.RUNNING)
        return selected_id

    def complete_run(self, run_id: str) -> str:
        run = self._run(run_id)
        if run.status is not RunStatus.RUNNING:
            raise ValueError(f"run is already {run.status.value}")
        node = ProvenanceNode(
            id=_id("observation"),
            kind=NodeKind.OBSERVATION,
            payload={"event": "run_completed"},
            run_id=run_id,
            agent_id="runtime",
        )
        self._add_child(run, node)
        run.status = RunStatus.COMPLETED
        return node.id

    def record_evidence(
        self,
        run_id: str,
        *,
        content: Any,
        source_uri: str,
        agent_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        if not source_uri.strip():
            raise ValueError("source_uri cannot be empty")
        payload = {"content": content, "metadata": dict(metadata or {})}
        ensure_jsonable(payload, label="evidence")
        node = ProvenanceNode(
            id=_id("evidence"),
            kind=NodeKind.EVIDENCE,
            payload=payload,
            run_id=run_id,
            agent_id=agent_id,
            source_uri=source_uri,
        )
        self._add_child(self._active_run(run_id), node)
        return node.id

    def record_claim(
        self,
        run_id: str,
        *,
        agent_id: str,
        statement: str,
        evidence_ids: Sequence[str] = (),
        derived_from_claim_ids: Sequence[str] = (),
        confidence: float | None = None,
    ) -> str:
        if not statement.strip():
            raise ValueError("claim statement cannot be empty")
        run = self._active_run(run_id)
        self._require_nodes(run.graph, evidence_ids, NodeKind.EVIDENCE)
        self._require_nodes(run.graph, derived_from_claim_ids, NodeKind.CLAIM)
        node = ProvenanceNode(
            id=_id("claim"),
            kind=NodeKind.CLAIM,
            payload={"statement": statement},
            run_id=run_id,
            agent_id=agent_id,
            confidence=confidence,
        )
        self._add_child(run, node)
        for evidence_id in evidence_ids:
            run.graph.add_edge(ProvenanceEdge(evidence_id, node.id, EdgeKind.SUPPORTS))
        for claim_id in derived_from_claim_ids:
            run.graph.add_edge(ProvenanceEdge(claim_id, node.id, EdgeKind.DERIVED_FROM))
        return node.id

    def execute_tool(
        self,
        run_id: str,
        *,
        agent_id: str,
        tool_name: str,
        arguments: Mapping[str, Any],
        evidence_ids: Sequence[str],
        claim_ids: Sequence[str] = (),
        approved_by: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ToolExecution:
        run = self._active_run(run_id)
        try:
            tool = self._tools[tool_name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {tool_name}") from exc

        ensure_jsonable(arguments, label="tool arguments")
        metadata_dict = dict(metadata or {})
        ensure_jsonable(metadata_dict, label="tool metadata")
        self._require_nodes(run.graph, evidence_ids, NodeKind.EVIDENCE)
        self._require_nodes(run.graph, claim_ids, NodeKind.CLAIM)

        request = PolicyRequest(
            run_id=run_id,
            agent_id=agent_id,
            action="execute_tool",
            tool_name=tool_name,
            risk=tool.risk,
            evidence_ids=tuple(evidence_ids),
            metadata=metadata_dict,
        )
        policy_decision = self.policy.evaluate(request)
        decision_node = ProvenanceNode(
            id=_id("decision"),
            kind=NodeKind.DECISION,
            payload={
                "action": request.action,
                "tool_name": tool_name,
                "risk": tool.risk,
                "effect": policy_decision.effect.value,
                "reasons": list(policy_decision.reasons),
                "rules": [
                    {
                        "rule": result.rule,
                        "effect": result.effect.value,
                        "reason": result.reason,
                    }
                    for result in policy_decision.rule_results
                ],
            },
            run_id=run_id,
            agent_id=agent_id,
        )
        self._add_child(run, decision_node)
        for source_id in (*evidence_ids, *claim_ids):
            run.graph.add_edge(ProvenanceEdge(source_id, decision_node.id, EdgeKind.INFORMED))

        if policy_decision.effect is PolicyEffect.DENY:
            raise PolicyDenied(
                "; ".join(policy_decision.reasons),
                decision_node_id=decision_node.id,
            )

        if policy_decision.effect is PolicyEffect.REQUIRE_APPROVAL:
            if approved_by is None or not approved_by.strip():
                raise ApprovalRequired(
                    "; ".join(policy_decision.reasons),
                    decision_node_id=decision_node.id,
                )
            approval_node = ProvenanceNode(
                id=_id("approval"),
                kind=NodeKind.APPROVAL,
                payload={"reviewer": approved_by, "decision": "approved"},
                run_id=run_id,
                agent_id=approved_by,
            )
            self._add_child(run, approval_node)
            run.graph.add_edge(
                ProvenanceEdge(approval_node.id, decision_node.id, EdgeKind.APPROVED)
            )

        action_node = ProvenanceNode(
            id=_id("action"),
            kind=NodeKind.ACTION,
            payload={"tool_name": tool_name, "arguments": dict(arguments), "risk": tool.risk},
            run_id=run_id,
            agent_id=agent_id,
        )
        self._add_child(run, action_node)
        run.graph.add_edge(
            ProvenanceEdge(decision_node.id, action_node.id, EdgeKind.TRIGGERED)
        )

        try:
            value = tool.handler(**dict(arguments))
        except Exception as exc:
            error_node = ProvenanceNode(
                id=_id("error"),
                kind=NodeKind.ERROR,
                payload={"type": type(exc).__name__, "message": str(exc)},
                run_id=run_id,
                agent_id=agent_id,
            )
            self._add_child(run, error_node)
            run.graph.add_edge(
                ProvenanceEdge(action_node.id, error_node.id, EdgeKind.FAILED_AT)
            )
            raise ToolExecutionFailed(
                f"tool '{tool_name}' failed: {exc}",
                error_node_id=error_node.id,
                decision_node_id=decision_node.id,
            ) from exc

        observation_node = ProvenanceNode(
            id=_id("observation"),
            kind=NodeKind.OBSERVATION,
            payload={"tool_name": tool_name, "result": _recordable(value)},
            run_id=run_id,
            agent_id=agent_id,
        )
        self._add_child(run, observation_node)
        run.graph.add_edge(
            ProvenanceEdge(action_node.id, observation_node.id, EdgeKind.PRODUCED)
        )
        return ToolExecution(
            value=value,
            decision_node_id=decision_node.id,
            action_node_id=action_node.id,
            observation_node_id=observation_node.id,
        )

    def graph(self, run_id: str) -> DecisionProvenanceGraph:
        return self._run(run_id).graph

    def snapshot(self, run_id: str) -> dict[str, Any]:
        run = self._run(run_id)
        snapshot = run.graph.snapshot()
        snapshot["runtime_status"] = run.status.value
        snapshot["task"] = run.task
        return snapshot

    def _run(self, run_id: str) -> _Run:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise KeyError(f"unknown run: {run_id}") from exc

    def _active_run(self, run_id: str) -> _Run:
        run = self._run(run_id)
        if run.status is not RunStatus.RUNNING:
            raise ValueError(f"run is not active: {run.status.value}")
        return run

    @staticmethod
    def _add_child(run: _Run, node: ProvenanceNode) -> None:
        run.graph.add_node(node)
        run.graph.add_edge(ProvenanceEdge(run.graph.run_id, node.id, EdgeKind.PART_OF))

    @staticmethod
    def _require_nodes(
        graph: DecisionProvenanceGraph,
        node_ids: Sequence[str],
        expected_kind: NodeKind,
    ) -> None:
        for node_id in node_ids:
            node = graph.node(node_id)
            if node.kind is not expected_kind:
                raise ValueError(
                    f"node '{node_id}' is {node.kind.value}, expected {expected_kind.value}"
                )


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _recordable(value: Any) -> Any:
    try:
        ensure_jsonable(value)
    except TypeError:
        return {"non_json_result": True, "type": type(value).__name__, "repr": repr(value)}
    return value
