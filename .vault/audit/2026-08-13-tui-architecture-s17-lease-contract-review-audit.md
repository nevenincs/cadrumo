---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:85595b21bb0bd6abdb5a29bac9bce02c12d9990031a2b3116220cc3aa92b7b1f'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-research]]"
  - "[[2026-08-13-tui-architecture-s17-review-audit]]"
---

# `tui-architecture` audit: `S17 lease contract review`

## Scope

Independent reopened review of `W02.P04.S17` against the complete live plan,
accepted architecture decision, research, execution record, prior rolling audit,
current diff, and whole changed operation-contract files. The review covered the
deterministic lease observation and transition models, exact lease repository
signatures, journal and replay extraction, public facade, safe evidence identity,
and focused real production-model tests. Adapter implementation, plan state, and
unrelated shared-worktree changes were excluded.

## Findings

### lease-signature-mutation-gate | medium | Most public lease parameter and result annotations can drift without a red test

`test_public_port_signatures_pin_explicit_lease_evidence_inputs` pins all four
parameter-name lists, keyword-only `observed_at`, and only the predecessor and
successor annotations of `compare_and_swap`. It does not pin the annotation of
`inspect.operation_id`, `acquire.candidate`, `release.predecessor`, any
`observed_at`, or any of the four return types. A coherent mutation such as
changing `acquire.candidate` from `OperationOwnerLease` to `OperationId`, or
changing a transition return from `OperationLeaseResult`, remains valid Python,
passes the current inspection assertions, and need not produce a basedpyright
error because no concrete adapter is assigned against the protocol in this Step.
The live signatures are correct, but the required mutation-sensitive signature
proof is incomplete at the S19 adapter boundary.

### lease-contract | low | Caller-clocked observation and exact transition evidence satisfy the adjudicated contract

`OperationLeaseObservation` closes state to `ABSENT`, `ACTIVE`, or `EXPIRED`,
binds the exact operation and optional witness at a supplied UTC `observed_at`,
and derives its `ContentDigest` from a versioned canonical payload. Acquisition
accepts a complete caller-created candidate and forbids predecessor evidence;
compare-and-swap requires non-optional exact predecessor and successor leases;
release requires the exact predecessor. Renewal preserves operation, owner,
token, and acquisition identity and extends a live predecessor. Takeover proves
expiry, changes owner and token, begins at the supplied observation time, and
returns a live successor. All result evidence is derived from the complete
versioned transition payload and rejects a noncanonical supplied digest.

No contract calls a clock, token generator, concrete adapter, frontend, storage
implementation, or private sibling from outside the owning application package.
`OperationLeaseObservation`, its disposition, lease results, replay types, and
ports are exposed through the sole operations facade. The lease and replay
extractions preserve their application ownership, while journal commit still
binds the persisted snapshot, expected revision, and exact current lease.

### verification-routes | low | Focused and ordinary pytest routes both pass on the current tree

The exact focused run with `--noconftest` passed 15 tests. The ordinary focused
pytest route also collected and passed the same 15 tests, so the execution
record's earlier unrelated `ApplicationLinkDefinition` collection failure is
not reproducible and is not attributable to S17. Ruff check passed, Ruff format
reported all six scoped files already formatted, and basedpyright reported zero
errors, warnings, or notes.

Final verdict: PASS with one MEDIUM follow-up. No CRITICAL or HIGH finding is
open.

## Recommendations

- Close `lease-signature-mutation-gate` by asserting the evaluated annotation of
  every public lease-port parameter and return, using the production protocol and
  production models directly. Plant at least one wrong-candidate and one
  wrong-result annotation mutation and prove the focused test fails.
- Retain the current caller-supplied time and identity inputs, deterministic
  evidence payloads, exact predecessor/successor vocabulary, facade exports, and
  separate lease/replay modules when S19 implements adapter atomicity.
## Final annotation re-review

### lease-signature-mutation-gate-closure | low | Exact evaluated annotations close the remaining MEDIUM

The remediated test retains exact parameter-name and keyword-only checks and now
compares the complete `inspect.get_annotations(..., eval_str=True)` dictionary
for `inspect`, `acquire`, `compare_and_swap`, and `release`. Every declared
parameter and all four return annotations are covered: operation identity,
candidate, predecessor, successor, caller-supplied observation time,
`OperationLeaseObservation`, and `OperationLeaseResult`. A wrong candidate,
predecessor, successor, observation-time, operation-id, or result type now makes
the focused production-protocol test fail.

The expectation table contains only public type identities and does not
reimplement observation, acquisition, renewal, takeover, release, evidence, or
adapter behavior. The production protocol remains the object inspected, so this
is a mutation-sensitive signature assertion rather than a shadow implementation.
The reported normal pytest, Ruff, format, basedpyright, and VaultSpec gates are
green; the 1,372 VaultSpec warnings are unrelated shared-corpus advisories.

Final verdict: PASS. No CRITICAL, HIGH, or MEDIUM finding remains open.
