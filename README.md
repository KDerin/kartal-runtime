# KARTAL Runtime

<p align="center">
  <img src="docs/assets/kartal-runtime-hero.jpg" alt="KARTAL Runtime — auditable agentic AI" width="100%">
</p>

[![CI](https://github.com/KDerin/kartal-runtime/actions/workflows/ci.yml/badge.svg)](https://github.com/KDerin/kartal-runtime/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**Knowledge-grounded Auditable Runtime for Traceable Agentic Logic**

KARTAL is an experimental, model-independent governance layer for agentic AI systems. It
records how evidence becomes claims, decisions, tool calls, observations, approvals, and
errors. The resulting typed provenance graph is append-only and tamper-evident, so a run can
be audited, evaluated, and reconstructed without exposing a model's private chain of thought.

> Status: `v0.1.0-alpha`. The public API will evolve while KARTAL-Bench and framework adapters
> are developed.

## Why KARTAL?

Agent frameworks can orchestrate tools and record execution traces. Production deployments
also need process-level accountability:

- Which evidence supported each claim and decision?
- Was a risky action checked before it produced a side effect?
- Which agent, tool, or evidence item introduced a failure?
- Can an auditor verify that the execution record was not modified?
- Can a failed run be reconstructed without re-executing side effects?

KARTAL focuses on those questions. It complements orchestration frameworks rather than
replacing them.

## v0.1 capabilities

- Typed decision provenance graph
- Tamper-evident SHA-256 event journal
- Evidence, claim, decision, action, observation, approval, and error nodes
- Policy evaluation at the action boundary
- Deny-wins and approval-required policy semantics
- Dry reconstruction of recorded runs
- Process-level grounding and completeness metrics
- Zero mandatory runtime dependencies
- Python 3.11+

## Quick start

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate

python -m pip install -e .
kartal demo
```

Minimal Python example:

```python
from kartal_runtime import AgentRuntime, ToolSpec, default_policy

runtime = AgentRuntime(policy=default_policy())
runtime.register_tool(ToolSpec("calculator", lambda a, b: a + b, risk=0.1))

run_id = runtime.start_run("Add two approved values")
evidence_id = runtime.record_evidence(
    run_id,
    content={"a": 20, "b": 22},
    source_uri="urn:example:approved-input",
)
claim_id = runtime.record_claim(
    run_id,
    agent_id="analyst",
    statement="The approved values can be added.",
    evidence_ids=[evidence_id],
    confidence=0.99,
)
result = runtime.execute_tool(
    run_id,
    agent_id="analyst",
    tool_name="calculator",
    arguments={"a": 20, "b": 22},
    evidence_ids=[evidence_id],
    claim_ids=[claim_id],
)

print(result.value)  # 42
print(runtime.snapshot(run_id)["head_hash"])
```

## Architecture

```text
Evidence -> Claim -> Decision -> Policy Gate -> Action -> Observation
                            \-> Approval / Denial / Error
```

Every mutation creates a canonical journal event whose hash includes the previous event hash.
This gives each run a verifiable history. KARTAL stores concise decision artifacts and does not
require or encourage logging hidden chain-of-thought content.

See [Architecture](docs/architecture.md), [Provenance schema](docs/provenance-schema.json),
[Research agenda](docs/research-agenda.md), and [Roadmap](ROADMAP.md).

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests examples
```

## Security and scope

KARTAL is research software. It does not make an unsafe tool safe, and its audit trail is not a
substitute for authorization, sandboxing, independent security review, or regulatory advice.
See [SECURITY.md](SECURITY.md).

## Author

**Kartal Derin** — AI Researcher and Agentic Systems Architect
[ORCID: 0009-0009-7104-5955](https://orcid.org/0009-0009-7104-5955)

## License

Apache License 2.0.
