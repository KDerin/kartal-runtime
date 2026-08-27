# Architecture

KARTAL Runtime is a model-independent accountability layer. It can sit beneath an agent
application or ingest normalized events from an external orchestration framework.

## Typed provenance

The graph records concise execution artifacts rather than hidden chain-of-thought content.

| Node | Meaning |
| --- | --- |
| Run | Stable root for one task execution |
| Evidence | Source material available to an agent |
| Claim | A concise, externally inspectable assertion |
| Decision | Policy evaluation for a proposed action |
| Approval | Authenticated human authorization artifact |
| Action | A tool call that passed the policy boundary |
| Observation | Result returned by an action |
| Error | Recorded failure and its location |

Typed edges include `supports`, `derived_from`, `informed`, `triggered`, `produced`,
`approved`, and `failed_at`.

## Tamper evidence

Each graph mutation produces a canonical event. An event hash covers:

- sequence number,
- timestamp,
- operation,
- serialized data,
- previous event hash.

The final head hash commits to the complete event order. Snapshot verification checks both the
hash chain and the materialized graph. This is tamper-evident logging, not digital signing;
signed attestations are planned for a later release.

## Action-boundary governance

Policies run after an agent proposes an action but before the tool handler executes. Rule
results use three effects:

1. `allow`
2. `require_approval`
3. `deny`

`deny` always wins. An approval requirement wins over allow. A denied action has a recorded
decision but no action node, making the absence of the side effect observable.

## Replay

The v0.1 replay engine performs a dry reconstruction from an exported snapshot. It verifies
integrity and rebuilds the graph without calling tools. Side-effect-aware partial replay and
recovery will require idempotency metadata and tool-specific compensation contracts.

## Trust boundaries

KARTAL verifies consistency of what was recorded. It does not independently prove that an
evidence item is true, a reviewer identity is authentic, or an external tool behaved correctly.
Those controls belong to the host application and future attestation adapters.
