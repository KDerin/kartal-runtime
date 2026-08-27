from __future__ import annotations

import json
import unittest

from kartal_runtime import run_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_reference_suite_passes_all_scenarios(self) -> None:
        report = run_benchmark()
        self.assertEqual(report.summary["scenario_count"], 8)
        self.assertEqual(report.summary["passed_count"], 8)
        self.assertEqual(report.summary["failed_count"], 0)
        self.assertEqual(report.summary["pass_rate"], 1.0)
        self.assertTrue(all(scenario.passed for scenario in report.scenarios))

    def test_report_is_json_serializable_and_machine_readable(self) -> None:
        report = run_benchmark().to_dict()
        encoded = json.dumps(report)
        self.assertIn("kartal.benchmark.v0.1", encoded)
        self.assertEqual(report["scorecard"]["tamper_detection"], 1.0)
        self.assertEqual(report["scorecard"]["replay_fidelity"], 1.0)


if __name__ == "__main__":
    unittest.main()
