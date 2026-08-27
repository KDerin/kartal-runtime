from __future__ import annotations

import unittest

from kartal_runtime import (
    EvidenceRequiredRule,
    PolicyEffect,
    PolicyEngine,
    PolicyRequest,
    RiskThresholdRule,
    ToolAllowlistRule,
)


def request(*, tool: str = "safe", risk: float = 0.1, evidence: tuple[str, ...] = ("e1",)):
    return PolicyRequest(
        run_id="run",
        agent_id="agent",
        action="execute_tool",
        tool_name=tool,
        risk=risk,
        evidence_ids=evidence,
    )


class PolicyTests(unittest.TestCase):
    def test_deny_wins_over_approval(self) -> None:
        engine = PolicyEngine(
            (
                ToolAllowlistRule(frozenset({"safe"})),
                RiskThresholdRule(approval_threshold=0.5, deny_threshold=0.9),
            )
        )
        result = engine.evaluate(request(tool="blocked", risk=0.7))
        self.assertIs(result.effect, PolicyEffect.DENY)

    def test_high_risk_requires_approval(self) -> None:
        engine = PolicyEngine((RiskThresholdRule(approval_threshold=0.5, deny_threshold=0.9),))
        self.assertIs(engine.evaluate(request(risk=0.7)).effect, PolicyEffect.REQUIRE_APPROVAL)

    def test_missing_evidence_is_denied(self) -> None:
        engine = PolicyEngine((EvidenceRequiredRule(),))
        self.assertIs(engine.evaluate(request(evidence=())).effect, PolicyEffect.DENY)

    def test_low_risk_with_evidence_is_allowed(self) -> None:
        engine = PolicyEngine((EvidenceRequiredRule(), RiskThresholdRule()))
        self.assertIs(engine.evaluate(request()).effect, PolicyEffect.ALLOW)


if __name__ == "__main__":
    unittest.main()
