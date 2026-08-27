# KARTAL-Bench

KARTAL-Bench v0.1 is an executable conformance suite for the KARTAL Runtime reference
implementation. It tests whether required governance and provenance behaviours are present;
it is not yet a comparative benchmark of external frameworks.

## Current suite

| ID | Capability | Expected outcome |
| --- | --- | --- |
| KBT-001 | Evidence-grounded tool execution | Allowed and fully linked |
| KBT-002 | Missing evidence boundary | Denied before action |
| KBT-003 | High-risk action | Denied before handler call |
| KBT-004 | Human approval gate | Executed with approval artifact |
| KBT-005 | Missing required approval | Paused before action |
| KBT-006 | Event and materialized-state tampering | Both detected |
| KBT-007 | Tool failure | Error localized to action |
| KBT-008 | Dry replay | Reconstructed without repeated side effects |

## Run

```bash
python -m pip install -e .
kartal bench
kartal bench --output benchmarks/results/my-run.json
```

The command exits with status `0` only when all scenarios pass. Reports use the
`kartal.benchmark.v0.1` JSON schema identifier and include the environment, measured duration,
journal-event count, assertions, and aggregate scorecard.

## Reference result

The repository includes
[`results/kartal-bench-v0.1.0.json`](results/kartal-bench-v0.1.0.json), generated from the
public suite. Timing values describe one local reference run and are not performance claims.

Read the [methodology](../docs/benchmark-methodology.md) for scope, validity limits, and the
planned comparative phase.
