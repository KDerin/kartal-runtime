# Research agenda

## Central question

Can an agentic system be operationally trustworthy when its final answer is correct but its
decision process is incomplete, policy-violating, or impossible to reconstruct?

KARTAL treats process-level accountability as a measurable property distinct from endpoint
task accuracy.

## Planned research contributions

The following are research targets, not claims of established novelty:

1. A framework-neutral typed schema connecting evidence, claims, decisions, actions,
   observations, approvals, and errors.
2. Metrics for evidence coverage and provenance completeness.
3. Failure localization across agent and tool boundaries.
4. Safe recovery evaluation that distinguishes reconstruction from side-effectful replay.
5. Cross-agent contamination tests using deliberately corrupted evidence and messages.
6. Runtime policy evaluation at the action boundary.

## KARTAL-Bench

The benchmark will report at least:

- endpoint task success,
- evidence coverage,
- provenance completeness,
- policy violation rate,
- error-localization accuracy,
- recovery success,
- cross-agent contamination,
- latency and token/tool cost.

Experiments will hold the underlying model and tool set constant while comparing monolithic,
chain-based, and multi-agent execution architectures. Every public result must include the task
set, prompts or policies, model identifiers, seeds where applicable, raw traces after redaction,
and evaluation code.

## Publication rule

KARTAL will not claim “first,” “state of the art,” or “production safe” without a documented
literature review, reproducible baseline, statistical analysis, and independent review.
