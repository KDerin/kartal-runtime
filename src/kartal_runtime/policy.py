from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .models import PolicyDecision, PolicyEffect, PolicyRequest, RuleResult


class PolicyRule(Protocol):
    name: str

    def evaluate(self, request: PolicyRequest) -> RuleResult: ...


class PolicyEngine:
    """Evaluate action-boundary rules with deny-wins semantics."""

    def __init__(self, rules: Sequence[PolicyRule] = ()) -> None:
        self._rules = tuple(rules)

    @property
    def rules(self) -> tuple[PolicyRule, ...]:
        return self._rules

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        if not 0.0 <= request.risk <= 1.0:
            raise ValueError("request risk must be between 0 and 1")

        results = tuple(rule.evaluate(request) for rule in self._rules)
        effects = {result.effect for result in results}
        if PolicyEffect.DENY in effects:
            effect = PolicyEffect.DENY
        elif PolicyEffect.REQUIRE_APPROVAL in effects:
            effect = PolicyEffect.REQUIRE_APPROVAL
        else:
            effect = PolicyEffect.ALLOW

        reasons = tuple(result.reason for result in results if result.effect is not PolicyEffect.ALLOW)
        if not reasons:
            reasons = ("All configured policy rules allowed the action.",)
        return PolicyDecision(effect=effect, reasons=reasons, rule_results=results)


@dataclass(frozen=True, slots=True)
class ToolAllowlistRule:
    allowed_tools: frozenset[str]
    name: str = "tool_allowlist"

    def evaluate(self, request: PolicyRequest) -> RuleResult:
        if request.tool_name not in self.allowed_tools:
            return RuleResult(
                rule=self.name,
                effect=PolicyEffect.DENY,
                reason=f"Tool '{request.tool_name}' is not in the configured allowlist.",
            )
        return RuleResult(self.name, PolicyEffect.ALLOW, "Tool is allowlisted.")


@dataclass(frozen=True, slots=True)
class RiskThresholdRule:
    approval_threshold: float = 0.5
    deny_threshold: float = 0.95
    name: str = "risk_threshold"

    def __post_init__(self) -> None:
        if not 0.0 <= self.approval_threshold <= self.deny_threshold <= 1.0:
            raise ValueError("risk thresholds must satisfy 0 <= approval <= deny <= 1")

    def evaluate(self, request: PolicyRequest) -> RuleResult:
        if request.risk >= self.deny_threshold:
            return RuleResult(
                self.name,
                PolicyEffect.DENY,
                f"Risk {request.risk:.2f} meets the deny threshold {self.deny_threshold:.2f}.",
            )
        if request.risk >= self.approval_threshold:
            return RuleResult(
                self.name,
                PolicyEffect.REQUIRE_APPROVAL,
                f"Risk {request.risk:.2f} requires human approval.",
            )
        return RuleResult(self.name, PolicyEffect.ALLOW, "Risk is below approval threshold.")


@dataclass(frozen=True, slots=True)
class EvidenceRequiredRule:
    actions: frozenset[str] = frozenset({"execute_tool"})
    name: str = "evidence_required"

    def evaluate(self, request: PolicyRequest) -> RuleResult:
        if request.action in self.actions and not request.evidence_ids:
            return RuleResult(
                self.name,
                PolicyEffect.DENY,
                f"Action '{request.action}' requires at least one evidence reference.",
            )
        return RuleResult(self.name, PolicyEffect.ALLOW, "Evidence requirement satisfied.")


def default_policy() -> PolicyEngine:
    return PolicyEngine((EvidenceRequiredRule(), RiskThresholdRule()))
