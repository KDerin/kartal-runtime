from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .benchmark import run_benchmark
from .evaluation import evaluate_process
from .models import ToolSpec
from .policy import default_policy
from .runtime import AgentRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kartal",
        description="KARTAL Runtime — auditable execution for agentic systems",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("demo", help="run a deterministic provenance demo")
    bench = subparsers.add_parser(
        "bench", help="run the KARTAL-Bench v0.1 conformance suite"
    )
    bench.add_argument(
        "--output",
        type=Path,
        help="optional path for a machine-readable JSON report",
    )
    bench.add_argument(
        "--compact",
        action="store_true",
        help="emit compact JSON instead of indented JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        print(json.dumps(_demo(), indent=2, ensure_ascii=False))
        return 0
    if args.command == "bench":
        report = run_benchmark().to_dict()
        rendered = json.dumps(
            report,
            indent=None if args.compact else 2,
            ensure_ascii=False,
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(f"{rendered}\n", encoding="utf-8")
        print(rendered)
        return 0 if report["summary"]["failed_count"] == 0 else 1
    return 2


def _demo() -> dict[str, object]:
    runtime = AgentRuntime(policy=default_policy())
    runtime.register_tool(ToolSpec("calculator", lambda a, b: a + b, risk=0.1))
    run_id = runtime.start_run("Add two values with evidence-backed execution")
    evidence_id = runtime.record_evidence(
        run_id,
        content={"a": 20, "b": 22},
        source_uri="urn:kartal:demo:approved-input",
    )
    claim_id = runtime.record_claim(
        run_id,
        agent_id="demo-analyst",
        statement="The approved values can be added.",
        evidence_ids=[evidence_id],
        confidence=0.99,
    )
    execution = runtime.execute_tool(
        run_id,
        agent_id="demo-analyst",
        tool_name="calculator",
        arguments={"a": 20, "b": 22},
        evidence_ids=[evidence_id],
        claim_ids=[claim_id],
    )
    runtime.complete_run(run_id)
    snapshot = runtime.snapshot(run_id)
    metrics = evaluate_process(runtime.graph(run_id))
    return {
        "project": "KARTAL Runtime",
        "run_id": run_id,
        "result": execution.value,
        "status": snapshot["runtime_status"],
        "head_hash": snapshot["head_hash"],
        "metrics": metrics.to_dict(),
    }
