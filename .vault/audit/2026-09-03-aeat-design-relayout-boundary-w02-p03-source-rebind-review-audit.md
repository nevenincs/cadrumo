---
tags:
  - '#audit'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:19005e4e611ec6101d2cab84202918ac3356e00d0ff3a6af341c1da1cdaed5f5'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

# `modelo-200-semantic-crosswalk` audit: `W02.P03 source-rebind review`

## Scope

Independent review of W02.P03 S05 and S06: the source-rebind planner, its
mutation surface, and focused detector tests. The review checked target-map
ownership, source identity, byte preservation, refusal coverage, isolation,
and publication safety.

## Findings

### source-rebind-transaction | high | A multi-file apply can publish a partial rebind

`apply_m200_source_rebind_plan` completes preflight before writing, but then
calls the one-file atomic writer in a loop over 965 paths. An I/O failure after
one replacement leaves the canonical registry partly rebound, with no journal,
rollback tree, recovery protocol, or failure-injection test. The next run
detects partial application, but cannot restore the original declaration
sources. This violates the phase's atomic mutation requirement.

### source-rebind-transaction-remediation | low | The prior partial-publication finding is resolved

The current implementation stages a copied casilla tree, verifies its exact
source bindings and non-source digests, moves the canonical tree to a sibling
backup, and cuts over the staged tree under an exclusive sidecar lock. The
`BaseException` handler restores the backup and leaves a journal when recovery
cannot finish. This resolves the preceding one-file-loop finding; the open
journal validation and detector findings below remain.

### source-rebind-journal-state | high | An unrecognised journal state can discard the only recovery record

`_recover_m200_source_rebind` validates the journal keys, schema version, and
transaction-child paths, but not the `state` value. With both a live casillas
tree and its backup present, any value other than `candidate_live`, `intent`,
or `backup_staged` falls through to journal deletion. It neither validates the
candidate tree nor restores the backup, and subsequent rebind attempts then
refuse the partial tree without a journal from which to recover. The recovery
state must be a closed, typed enum and unknown values must refuse without
cleanup.

### source-rebind-recovery-detectors | medium | The fault detector proves only ordinary OSError rollback

The one transaction detector injects the second directory replacement as an
`OSError` and observes immediate rollback. It does not inject a
`BaseException`, persist a pre-cutover or post-cutover journal state, or invoke
a subsequent application to prove deterministic next-run recovery and cleanup.
Those cases are central to the journal protocol and remain unproven.

### source-rebind-journal-state-remediation | low | Unknown journal states now preserve recovery evidence

The recovery reader now requires a string member of the closed `intent`,
`backup_staged`, and `candidate_live` state set before it creates any cleanup
path. The detector proves an unrecognised state leaves both the live tree and
backup/journal evidence unchanged.

### source-rebind-recovery-detector-remediation | low | BaseException and pre-candidate recovery are now covered

The detector suite now injects a `BaseException` during cutover and proves
rollback, then persists both `intent` and `backup_staged` recovery journals
and invokes the next dry-run application. Each pre-candidate case restores a
casillas tree and removes the stage, backup, and journal in the temporary
registry root.

### source-rebind-candidate-live-detector | medium | The committed-candidate recovery branch remains unproven

`_recover_m200_source_rebind` has a distinct `candidate_live` branch: it must
retain a verified target-bound candidate and remove its backup, or restore the
backup if candidate verification fails. No detector persists that journal
state and exercises either outcome. This is a durable cutover state, not an
inapplicable branch.

## Recommendations

Implement a transactional staged-tree or per-file rollback protocol with a
durable journal, then test a deliberately interrupted cutover to prove that
the canonical tree is either wholly unchanged or wholly rebound.

Validate `state` against the transaction's closed state set before branching,
and retain an invalid journal for operator recovery. Add isolated temporary
tree detectors for `BaseException` rollback and next-run recovery from each
durable cutover state, checking canonical bytes, journal disposition, and
stage/backup cleanup.

Add a temporary-tree detector for persisted `candidate_live` recovery in both
the verified-candidate and failed-verification cases. It must prove the
resulting casillas source bindings, non-source bytes, and cleanup disposition.
