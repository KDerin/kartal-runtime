from __future__ import annotations

import unittest

from kartal_runtime import (
    AgentRuntime,
    ApprovalRequired,
    DryReplay,
    NodeKind,
    PolicyDenied,
    ToolExecutionFailed,
    ToolSpec,
    default_policy,
    evaluate_process,
)


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = AgentRuntime(policy=default_policy())
        self.runtime.register_tool(ToolSpec("add", lambda a, b: a + b, risk=0.1))
        self.runtime.register_tool(ToolSpec("publish", lambda text: text, risk=0.7))
        self.runtime.register_tool(ToolSpec("destructive", lambda: True, risk=0.99))
        self.runtime.register_tool(
            ToolSpec("explode", lambda: (_ for _ in ()).throw(ValueError("boom")), risk=0.1)
        )

    def _run_with_evidence(self) -> tuple[str, str]:
        run_id = self.runtime.start_run("test")
        evidence_id = self.runtime.record_evidence(
            run_id,
            content={"approved": True},
            source_uri="urn:test:evidence",
        )
        return run_id, evidence_id

    def test_allowed_tool_records_decision_action_and_observation(self) -> None:
        run_id, evidence_id = self._run_with_evidence()
        execution = self.runtime.execute_tool(
            run_id,
            agent_id="agent",
            tool_name="add",
            arguments={"a": 20, "b": 22},
            evidence_ids=[evidence_id],
        )
        self.assertEqual(execution.value, 42)
        graph = self.runtime.graph(run_id)
        self.assertEqual(len(graph.nodes(kind=NodeKind.DECISION)), 1)
        self.assertEqual(len(graph.nodes(kind=NodeKind.ACTION)), 1)
        self.assertEqual(len(graph.nodes(kind=NodeKind.OBSERVATION)), 1)

    def test_approval_required_prevents_tool_execution(self) -> None:
        run_id, evidence_id = self._run_with_evidence()
        with self.assertRaises(ApprovalRequired):
            self.runtime.execute_tool(
                run_id,
                agent_id="agent",
                tool_name="publish",
                arguments={"text": "draft"},
                evidence_ids=[evidence_id],
            )
        self.assertEqual(len(self.runtime.graph(run_id).nodes(kind=NodeKind.ACTION)), 0)

    def test_human_approval_allows_moderate_risk_tool(self) -> None:
        run_id, evidence_id = self._run_with_evidence()
        execution = self.runtime.execute_tool(
            run_id,
            agent_id="agent",
            tool_name="publish",
            arguments={"text": "approved"},
            evidence_ids=[evidence_id],
            approved_by="reviewer-123",
        )
        self.assertEqual(execution.value, "approved")
        self.assertEqual(len(self.runtime.graph(run_id).nodes(kind=NodeKind.APPROVAL)), 1)

    def test_denied_tool_never_creates_action(self) -> None:
        run_id, evidence_id = self._run_with_evidence()
        with self.assertRaises(PolicyDenied):
            self.runtime.execute_tool(
                run_id,
                agent_id="agent",
                tool_name="destructive",
                arguments={},
                evidence_ids=[evidence_id],
                approved_by="reviewer-123",
            )
        self.assertEqual(len(self.runtime.graph(run_id).nodes(kind=NodeKind.ACTION)), 0)

    def test_tool_failure_is_localized(self) -> None:
        run_id, evidence_id = self._run_with_evidence()
        with self.assertRaises(ToolExecutionFailed) as caught:
            self.runtime.execute_tool(
                run_id,
                agent_id="agent",
                tool_name="explode",
                arguments={},
                evidence_ids=[evidence_id],
            )
        self.assertTrue(caught.exception.error_node_id.startswith("error_"))
        self.assertEqual(len(self.runtime.graph(run_id).nodes(kind=NodeKind.ERROR)), 1)

    def test_snapshot_can_be_reconstructed_without_side_effects(self) -> None:
        run_id, evidence_id = self._run_with_evidence()
        self.runtime.execute_tool(
            run_id,
            agent_id="agent",
            tool_name="add",
            arguments={"a": 1, "b": 2},
            evidence_ids=[evidence_id],
        )
        snapshot = self.runtime.snapshot(run_id)
        graph, report = DryReplay.reconstruct(snapshot)
        self.assertTrue(report.integrity_valid)
        self.assertEqual(report.head_hash, graph.head_hash)
        self.assertEqual(report.node_count, len(self.runtime.graph(run_id).nodes()))

    def test_metrics_distinguish_grounded_and_unsupported_claims(self) -> None:
        run_id, evidence_id = self._run_with_evidence()
        self.runtime.record_claim(
            run_id,
            agent_id="agent",
            statement="grounded",
            evidence_ids=[evidence_id],
        )
        self.runtime.record_claim(
            run_id,
            agent_id="agent",
            statement="unsupported",
        )
        metrics = evaluate_process(self.runtime.graph(run_id))
        self.assertEqual(metrics.claim_count, 2)
        self.assertEqual(metrics.grounded_claim_count, 1)
        self.assertEqual(metrics.evidence_coverage, 0.5)


if __name__ == "__main__":
    unittest.main()
