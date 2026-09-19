---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:332c8a4fce8dc780eb6549a0abf15cc9fd559b861c47282bb03b431ea17c0d74'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---
# `tui-architecture` audit: `S116 public operation boundary code review`

## Scope

Independent review of `W02.P19.S116` against accepted ADR clauses D0, D2, D6, D7, and D10; the canonical plan; the S115 registry contract; the S116 execution record; and commits `66e4a30d48`, `1778e2f728`, and `7b9085e7b3`. The review used Vaultspec RAG before exact declaration searches, then read the complete DTO, registry, model, replay, observation, facade, and focused-test surfaces. Later uncommitted S120 registry work was excluded from S116 attribution.

## Findings

### s116-mixed-preimplementation-record | medium | The checked S116 evidence record cannot reproduce the implementation it claims

Commit `7b9085e7b3` records S116 and marks the plan row complete before the implementation commits: it is an ancestor of `66e4a30d48` and `1778e2f728`, but contains no S116 production or test change. Its same commit also changes unrelated plan and registry-reference documents. The record has no producing-commit tuple or source-tree digest, so its completion and test claims cannot be verified from the committed tree it records. This is a traceability defect rather than a second code authority; it does not itself expose data or frontend authority.

### s116-public-cross-record-invariants | high | Strict public DTOs accept internally impossible observation state

The DTO family validates each nested record but omits relations that S116 explicitly assigns to the public boundary. Direct construction accepts a `caught_up` page at requested cursor 1 with anchor 2 and next cursor 1; a success whose event row revision exceeds its projection revision; a projection whose progress phase differs from the current phase; and an unsupported pending interaction with a stale revision and a kind undeclared by the definition contract. `OperationObservationMaterialization` later rejects the replay/revision forms on the current service path, but that private S117-side validation cannot make the independently exported S116 DTO contract strict. The focused suite passes because it asserts only the shared anchor and selected per-record rules, so it supplies no adversarial witness for these cross-record states.

## Recommendations

- Reopen or correct S116 before allowing S117 to rely on its DTO boundary. Add public-model validation for the caught-up-anchor, event-revision, progress-phase, declared-interaction/current-revision, and cancellation-availability relationships, with direct refusal witnesses that prove each gate bites.
- Replace the S116 completion evidence with an attestation from one clean implementation commit, or an explicit ordered implementation-commit tuple plus source-tree digest and scoped command receipts. Keep unrelated document changes out of that attestation.

## Resolution disposition

### s116-public-cross-record-invariants | resolved | Public DTO boundary now rejects every reported impossible state

`OperationPublicEventPageV1` requires a caught-up response to have matching requested, anchor, and next cursors. `OperationObservationSuccessV1` rejects event revisions beyond its projection revision. `OperationPublicProjectionV1` binds progress phase to the current phase, binds every pending interaction to the waiting lifecycle, current revision, and definition-declared interaction kind, and rejects cancellation availability after a request or during settlement. Direct adversarial witnesses prove each gate bites.

### s116-mixed-preimplementation-record | resolved | Execution evidence now distinguishes the original premature record from producing code

The S116 record now carries the explicit ordered `66e4a30d48a694175b9f8e61b75cf340afd400cb -> 1778e2f7285037d68e6c88bf3367d2c0e660a996 -> 4967ef8220080aa4de32ab753f3b7679f37301ee` implementation/remediation tuple, source-file SHA-256 evidence, scoped command receipts, and the reason `7b9085e7b35beb570c9c7a0119d5c7c7a2e754bf` cannot prove code completion. The finalization change is a semantic-preserving type narrowing of the same validator.

## Final disposition

Accepted after a fresh read-only follow-up review of the remediation. The reviewer found no new finding; current focused Ruff, basedpyright, public DTO, observation/projection/facade/registry, and complete operation-package checks are green. S116 may be re-closed, while S120 and later work remain independently owned.
