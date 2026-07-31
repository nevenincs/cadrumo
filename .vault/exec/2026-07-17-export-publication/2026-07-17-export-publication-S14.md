---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:c089fc6f1f802c9b83b8027e39fa97523c3f59c95d50ed327e6d574fae557c8f'
step_id: 'S14'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Isolate each operation inside the export reconciliation sweep so one unreadable or unfinalisable journal cannot starve every later-ordered operation, returning a typed reconciliation that reports the isolated failures rather than swallowing them, gated on a poisoned-journal test proving a healthy operation still reconciles alongside a failing one

## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py`
- `src/cadrumo/application/user_profile/_bundle_export_operation.py`
- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`

## Description

- Trace the abort path: the repository listing loads every journal strictly, so a
  single corrupt file raised out of the walk before any operation was touched, and a
  per-operation failure propagated straight out of the loop.
- Add `scan` to the journal repository as the isolating counterpart to `list`,
  reporting unreadable journals rather than raising on the first one.
- Extract `_journal_paths` so `list` and `scan` share one directory walk instead of
  growing a second globbing authority.
- Split the per-operation body into `_reconcile_one_operation`, returning `None` for a
  deliberate skip and raising for a genuine failure so the caller can tell them apart.
- Change the reconciliation contract to return a typed reconciliation carrying the
  operations it resolved and the ones it isolated.
- Keep a failed operation's journal so the next sweep retries it.
- Update every existing call site to the new contract, and assert on the lock-held
  test that an in-flight export produces no failure.
- Add two isolation proofs, each ordering the failing record ahead of a healthy one.

## Outcome

A single bad record can no longer starve the operations behind it. Both failure modes
are real rather than hypothesised, and each was observed as the exact exception that
used to abort the walk: an unparseable journal file raising the journal-corrupt
refusal out of the repository listing, and a completed journal naming a bucket that no
longer exists raising the master-key-material refusal from the owed audit event. The
second is the realistic one -- an operator deleting a profile after its export crashed.

Failures are reported rather than swallowed, which is the distinction that makes this
different from a broad catch. A journal left behind may still describe cleartext bundle
bytes on disk, so the sweep hands its caller the list rather than deciding on the
operator's behalf that a partial recovery was good enough.

The three-way split is deliberate. Reconciled means resolved and cleared. Failed means
isolated and kept for a retry. A skip because a live export holds the target lock is
neither: it is healthy in-flight work, and folding it into failures would train an
operator to ignore the warning that matters.

Non-tautology is observed, not asserted. With the sweep restored to its aborting shape,
both new proofs fail on the two errors above. Restored, the two export suites pass
together at twenty-three tests.

## Notes

This is a deliberate contract change to the reconciliation entry point, authorised
because the previous tuple return had nowhere to put a failure. The repository's strict
`list` is unchanged for callers that want a hard refusal.

The pre-flight guard at the export call site is kept even though per-operation
isolation now handles the common cases: a repository-level refusal, such as a journal
root that has become a symlink, still raises before any operation is reached, and a new
export must not fail because of it.
