from __future__ import annotations

import copy
import unittest

from kartal_runtime import (
    DecisionProvenanceGraph,
    EdgeKind,
    NodeKind,
    ProvenanceEdge,
    ProvenanceIntegrityError,
    ProvenanceNode,
)


class ProvenanceTests(unittest.TestCase):
    def test_round_trip_preserves_integrity(self) -> None:
        graph = DecisionProvenanceGraph("run_test")
        run = ProvenanceNode("run_test", NodeKind.RUN, {"task": "test"}, "run_test")
        evidence = ProvenanceNode(
            "evidence_1",
            NodeKind.EVIDENCE,
            {"content": "source"},
            "run_test",
            source_uri="urn:test:source",
        )
        claim = ProvenanceNode(
            "claim_1",
            NodeKind.CLAIM,
            {"statement": "supported"},
            "run_test",
            agent_id="agent",
        )
        graph.add_node(run)
        graph.add_node(evidence)
        graph.add_node(claim)
        graph.add_edge(ProvenanceEdge(evidence.id, claim.id, EdgeKind.SUPPORTS))

        self.assertTrue(graph.verify_integrity())
        rebuilt = DecisionProvenanceGraph.from_snapshot(graph.snapshot())
        self.assertEqual(rebuilt.head_hash, graph.head_hash)
        self.assertEqual(rebuilt.node("claim_1").payload["statement"], "supported")

    def test_modified_payload_fails_verification(self) -> None:
        graph = DecisionProvenanceGraph("run_test")
        graph.add_node(ProvenanceNode("run_test", NodeKind.RUN, {"task": "test"}, "run_test"))
        snapshot = copy.deepcopy(graph.snapshot())
        snapshot["nodes"][0]["payload"]["task"] = "tampered"

        with self.assertRaises(ProvenanceIntegrityError):
            DecisionProvenanceGraph.verify_snapshot(snapshot)

    def test_modified_event_fails_verification(self) -> None:
        graph = DecisionProvenanceGraph("run_test")
        graph.add_node(ProvenanceNode("run_test", NodeKind.RUN, {"task": "test"}, "run_test"))
        snapshot = copy.deepcopy(graph.snapshot())
        snapshot["events"][0]["data"]["payload"]["task"] = "tampered"

        with self.assertRaises(ProvenanceIntegrityError):
            DecisionProvenanceGraph.verify_snapshot(snapshot)

    def test_unsupported_claim_detection(self) -> None:
        graph = DecisionProvenanceGraph("run_test")
        graph.add_node(ProvenanceNode("run_test", NodeKind.RUN, {"task": "test"}, "run_test"))
        graph.add_node(
            ProvenanceNode(
                "claim_1",
                NodeKind.CLAIM,
                {"statement": "unsupported"},
                "run_test",
            )
        )
        self.assertEqual([node.id for node in graph.unsupported_claims()], ["claim_1"])

    def test_rejects_edge_to_unknown_node(self) -> None:
        graph = DecisionProvenanceGraph("run_test")
        graph.add_node(ProvenanceNode("run_test", NodeKind.RUN, {"task": "test"}, "run_test"))
        with self.assertRaises(KeyError):
            graph.add_edge(ProvenanceEdge("run_test", "missing", EdgeKind.PART_OF))


if __name__ == "__main__":
    unittest.main()
