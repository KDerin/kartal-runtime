# KARTAL-Bench v0.1 methodology

## Purpose

KARTAL-Bench v0.1 evaluates whether the KARTAL reference runtime exhibits eight specified
governance and provenance behaviours. Each scenario executes public Python code and produces
machine-readable assertions. A scenario passes only when every assertion is true.

## Measurement model

- **Unit of evaluation:** one isolated runtime instance and one scenario.
- **Primary measure:** binary conformance for every assertion.
- **Aggregate pass rate:** passed scenarios divided by total scenarios.
- **Unsafe-action prevention:** three scenarios in which no action may be created.
- **Tamper detection:** independent mutation of a journal event and materialized state.
- **Replay fidelity:** integrity, head hash, node count, and absence of repeated side effects.
- **Duration:** wall-clock time measured with `perf_counter_ns`; reported for transparency only.

The suite uses fixed inputs but generates unique internal node identifiers. Durations may vary
by operating system, Python build, CPU state, and background load.

## Interpretation limits

The v0.1 scorecard measures conformance of the implementation to its own published behaviours.
It does not establish comparative safety, regulatory compliance, production security, or
superiority over other runtimes. A perfect conformance score means that the eight public
scenarios passed—not that all possible failures were covered.

## Reproduction

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e .
kartal bench --output benchmarks/results/reproduction.json
python -m unittest discover -s tests -v
```

Record the commit SHA, Python version, operating system, report JSON, and any local changes.

## Planned comparative phase

The next research phase will define adapters and equivalent task contracts for external agent
frameworks. That phase requires preregistered metrics, repeated trials, public scenario data,
confidence intervals where appropriate, and independent review of whether the comparisons are
functionally equivalent.
