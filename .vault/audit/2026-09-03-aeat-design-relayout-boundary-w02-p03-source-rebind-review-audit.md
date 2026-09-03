---
tags:
  - '#audit'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:6b7135ce4ecc55533f81b543985b7c3672416a94f82347305f8d5ef26fd99929'
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

## Recommendations

Implement a transactional staged-tree or per-file rollback protocol with a
durable journal, then test a deliberately interrupted cutover to prove that
the canonical tree is either wholly unchanged or wholly rebound.

Validate `state` against the transaction's closed state set before branching,
and retain an invalid journal for operator recovery. Add isolated temporary
tree detectors for `BaseException` rollback and next-run recovery from each
durable cutover state, checking canonical bytes, journal disposition, and
stage/backup cleanup.
