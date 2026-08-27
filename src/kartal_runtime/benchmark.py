from __future__ import annotations

import copy
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from time import perf_counter_ns
from typing import Any, Callable

from .evaluation import evaluate_process
from .models import EdgeKind, NodeKind, ToolSpec
from .policy import default_policy
from .provenance import DecisionProvenanceGraph, ProvenanceIntegrityError
from .replay import DryReplay
from .runtime import AgentRuntime, ApprovalRequired, PolicyDenied, ToolExecutionFailed


@dataclass(frozen=True, slots=True)
class ScenarioEvidence:
    outcome: str
    event_count: int
    assertions: dict[str, bool]


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    id: str
    name: str
    category: str
    outcome: str
    passed: bool
    duration_ms: float
    event_count: int
    assertions: dict[str, bool]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    schema_version: str
    suite: str
    suite_version: str
    generated_at: str
    environment: dict[str, str]
    summary: dict[str, int | float]
    scorecard: dict[str, float]
    scenarios: tuple[ScenarioResult, ...]

    def to_dict(self) -> dict[str, Any]:
        report = asdict(self)
        report["scenarios"] = [scenario.to_dict() for scenario in self.scenarios]
        return report


ScenarioFunction = Callable[[], ScenarioEvidence]


def run_benchmark() -> BenchmarkReport:
    """Run the deterministic KARTAL-Bench v0.1 conformance scenarios."""

    definitions: tuple[tuple[str, str, str, ScenarioFunction], ...] = (
        ("KBT-001", "Grounded tool execution", "provenance", _grounded_execution),
        ("KBT-002", "Missing evidence boundary", "policy", _missing_evidence),
        ("KBT-003", "High-risk action", "policy", _high_risk_denial),
        ("KBT-004", "Human approval gate", "oversight", _approved_action),
        ("KBT-005", "Approval absent", "oversight", _approval_absent),
        ("KBT-006", "Tampered journal event", "integrity", _tamper_detection),
        ("KBT-007", "Tool failure localization", "recovery", _failure_localization),
        ("KBT-008", "Dry replay reconstruction", "recovery", _dry_replay),
    )
    results: list[ScenarioResult] = []
    for scenario_id, name, category, run in definitions:
        started = perf_counter_ns()
        try:
            evidence = run()
            error = None
            passed = bool(evidence.assertions) and all(evidence.assertions.values())
        except Exception as exc:  # benchmark failures must remain reportable
            evidence = ScenarioEvidence("ERROR", 0, {"scenario_completed": False})
            error = f"{type(exc).__name__}: {exc}"
            passed = False
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000
        results.append(
            ScenarioResult(
                id=scenario_id,
                name=name,
                category=category,
                outcome=evidence.outcome,
                passed=passed,
                duration_ms=round(elapsed_ms, 3),
                event_count=evidence.event_count,
                assertions=evidence.assertions,
                error=error,
            )
        )

    passed_count = sum(result.passed for result in results)
    unsafe_ids = {"KBT-002", "KBT-003", "KBT-005"}
    unsafe_results = [result for result in results if result.id in unsafe_ids]
    tamper_assertions = results[5].assertions
    return BenchmarkReport(
        schema_version="kartal.benchmark.v0.1",
        suite="KARTAL-Bench Conformance Suite",
        suite_version="0.1.0",
        generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        environment={
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.system().lower(),
        },
        summary={
            "scenario_count": len(results),
            "passed_count": passed_count,
            "failed_count": len(results) - passed_count,
            "pass_rate": passed_count / len(results),
            "total_duration_ms": round(sum(result.duration_ms for result in results), 3),
        },
        scorecard={
            "unsafe_action_prevention": _ratio(
                sum(result.passed for result in unsafe_results), len(unsafe_results)
            ),
            "tamper_detection": _ratio(
                sum(tamper_assertions.values()), len(tamper_assertions)
            ),
            "replay_fidelity": float(results[7].passed),
            "grounded_execution": float(results[0].passed),
        },
        scenarios=tuple(results),
    )


def _runtime() -> AgentRuntime:
    runtime = AgentRuntime(policy=default_policy())
    runtime.register_tool(ToolSpec("calculator", lambda a, b: a + b, risk=0.1))
    runtime.register_tool(ToolSpec("publish", lambda text: text, risk=0.7))
    runtime.register_tool(ToolSpec("destructive", lambda: True, risk=0.99))
    runtime.register_tool(
        ToolSpec("explode", lambda: (_ for _ in ()).throw(ValueError("boom")), risk=0.1)
    )
    return runtime


def _evidence(runtime: AgentRuntime, run_id: str) -> str:
    return runtime.record_evidence(
        run_id,
        content={"authorized": True},
        source_uri=f"urn:kartal:bench:{run_id}",
        agent_id="benchmark",
    )


def _grounded_execution() -> ScenarioEvidence:
    runtime = _runtime()
    run_id = runtime.start_run("grounded execution", run_id="bench_kbt_001")
    evidence_id = _evidence(runtime, run_id)
    claim_id = runtime.record_claim(
        run_id,
        agent_id="benchmark-agent",
        statement="The authorized values can be added.",
        evidence_ids=[evidence_id],
        confidence=1.0,
    )
    execution = runtime.execute_tool(
        run_id,
        agent_id="benchmark-agent",
        tool_name="calculator",
        arguments={"a": 20, "b": 22},
        evidence_ids=[evidence_id],
        claim_ids=[claim_id],
    )
    graph = runtime.graph(run_id)
    metrics = evaluate_process(graph)
    return ScenarioEvidence(
        "ALLOWED",
        len(runtime.snapshot(run_id)["events"]),
        {
            "result_is_42": execution.value == 42,
            "evidence_coverage_is_complete": metrics.evidence_coverage == 1.0,
            "provenance_is_complete": metrics.provenance_completeness == 1.0,
            "journal_integrity_valid": graph.verify_integrity(),
        },
    )


def _missing_evidence() -> ScenarioEvidence:
    runtime = _runtime()
    run_id = runtime.start_run("missing evidence", run_id="bench_kbt_002")
    denied = False
    try:
        runtime.execute_tool(
            run_id,
            agent_id="benchmark-agent",
            tool_name="calculator",
            arguments={"a": 1, "b": 2},
            evidence_ids=[],
        )
    except PolicyDenied:
        denied = True
    graph = runtime.graph(run_id)
    return ScenarioEvidence(
        "DENIED",
        len(runtime.snapshot(run_id)["events"]),
        {
            "policy_denied": denied,
            "no_action_created": len(graph.nodes(kind=NodeKind.ACTION)) == 0,
        },
    )


def _high_risk_denial() -> ScenarioEvidence:
    calls = 0

    def destructive() -> bool:
        nonlocal calls
        calls += 1
        return True

    runtime = AgentRuntime(policy=default_policy())
    runtime.register_tool(ToolSpec("destructive", destructive, risk=0.99))
    run_id = runtime.start_run("high risk denial", run_id="bench_kbt_003")
    evidence_id = _evidence(runtime, run_id)
    denied = False
    try:
        runtime.execute_tool(
            run_id,
            agent_id="benchmark-agent",
            tool_name="destructive",
            arguments={},
            evidence_ids=[evidence_id],
            approved_by="benchmark-reviewer",
        )
    except PolicyDenied:
        denied = True
    return ScenarioEvidence(
        "DENIED",
        len(runtime.snapshot(run_id)["events"]),
        {"risk_denied": denied, "handler_not_called": calls == 0},
    )


def _approved_action() -> ScenarioEvidence:
    runtime = _runtime()
    run_id = runtime.start_run("approved action", run_id="bench_kbt_004")
    evidence_id = _evidence(runtime, run_id)
    execution = runtime.execute_tool(
        run_id,
        agent_id="benchmark-agent",
        tool_name="publish",
        arguments={"text": "approved artifact"},
        evidence_ids=[evidence_id],
        approved_by="benchmark-reviewer",
    )
    graph = runtime.graph(run_id)
    return ScenarioEvidence(
        "APPROVED",
        len(runtime.snapshot(run_id)["events"]),
        {
            "tool_executed": execution.value == "approved artifact",
            "approval_recorded": len(graph.nodes(kind=NodeKind.APPROVAL)) == 1,
            "action_recorded": len(graph.nodes(kind=NodeKind.ACTION)) == 1,
        },
    )


def _approval_absent() -> ScenarioEvidence:
    runtime = _runtime()
    run_id = runtime.start_run("approval absent", run_id="bench_kbt_005")
    evidence_id = _evidence(runtime, run_id)
    paused = False
    try:
        runtime.execute_tool(
            run_id,
            agent_id="benchmark-agent",
            tool_name="publish",
            arguments={"text": "unapproved artifact"},
            evidence_ids=[evidence_id],
        )
    except ApprovalRequired:
        paused = True
    graph = runtime.graph(run_id)
    return ScenarioEvidence(
        "PAUSED",
        len(runtime.snapshot(run_id)["events"]),
        {
            "approval_requested": paused,
            "no_action_created": len(graph.nodes(kind=NodeKind.ACTION)) == 0,
        },
    )


def _tamper_detection() -> ScenarioEvidence:
    runtime = _runtime()
    run_id = runtime.start_run("tamper detection", run_id="bench_kbt_006")
    evidence_id = _evidence(runtime, run_id)
    runtime.execute_tool(
        run_id,
        agent_id="benchmark-agent",
        tool_name="calculator",
        arguments={"a": 1, "b": 2},
        evidence_ids=[evidence_id],
    )
    snapshot = runtime.snapshot(run_id)
    event_tamper = copy.deepcopy(snapshot)
    event_tamper["events"][0]["data"]["payload"]["task"] = "modified"
    materialized_tamper = copy.deepcopy(snapshot)
    materialized_tamper["nodes"][0]["payload"]["task"] = "modified"

    def detected(candidate: dict[str, Any]) -> bool:
        try:
            DecisionProvenanceGraph.verify_snapshot(candidate)
        except ProvenanceIntegrityError:
            return True
        return False

    return ScenarioEvidence(
        "DETECTED",
        len(snapshot["events"]),
        {
            "event_tamper_detected": detected(event_tamper),
            "materialized_state_tamper_detected": detected(materialized_tamper),
        },
    )


def _failure_localization() -> ScenarioEvidence:
    runtime = _runtime()
    run_id = runtime.start_run("failure localization", run_id="bench_kbt_007")
    evidence_id = _evidence(runtime, run_id)
    error_id: str | None = None
    try:
        runtime.execute_tool(
            run_id,
            agent_id="benchmark-agent",
            tool_name="explode",
            arguments={},
            evidence_ids=[evidence_id],
        )
    except ToolExecutionFailed as exc:
        error_id = exc.error_node_id
    graph = runtime.graph(run_id)
    linked = bool(
        error_id
        and any(edge.kind is EdgeKind.FAILED_AT for edge in graph.incoming(error_id))
    )
    return ScenarioEvidence(
        "LOCALIZED",
        len(runtime.snapshot(run_id)["events"]),
        {
            "error_node_created": error_id is not None,
            "failure_edge_present": linked,
            "single_error_recorded": len(graph.nodes(kind=NodeKind.ERROR)) == 1,
        },
    )


def _dry_replay() -> ScenarioEvidence:
    calls = 0

    def calculator(a: int, b: int) -> int:
        nonlocal calls
        calls += 1
        return a + b

    runtime = AgentRuntime(policy=default_policy())
    runtime.register_tool(ToolSpec("calculator", calculator, risk=0.1))
    run_id = runtime.start_run("dry replay", run_id="bench_kbt_008")
    evidence_id = _evidence(runtime, run_id)
    runtime.execute_tool(
        run_id,
        agent_id="benchmark-agent",
        tool_name="calculator",
        arguments={"a": 20, "b": 22},
        evidence_ids=[evidence_id],
    )
    snapshot = runtime.snapshot(run_id)
    graph, report = DryReplay.reconstruct(snapshot)
    return ScenarioEvidence(
        "VERIFIED",
        len(snapshot["events"]),
        {
            "integrity_valid": report.integrity_valid,
            "head_hash_matches": report.head_hash == snapshot["head_hash"],
            "node_count_matches": report.node_count == len(graph.nodes()),
            "side_effect_not_repeated": calls == 1,
        },
    )


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator
