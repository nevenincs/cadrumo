---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:00b78588e926a7bc86e2dade5e607f8c83c0ba3bb87f770519cf2cdac6e29bc7'
step_id: 'S12'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Wire the built crash-recovery reconciliation into the production publication path so a crashed export's orphan operation journal and its cleartext staged temporary file are cleared by an operator-reachable code path rather than only by the test harness, choosing the trigger from how the journal and staged temp are actually keyed

## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py`
- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`

## Description

- Trace every caller of `reconcile_prepared_exports` and confirm the close review's
  reading: definition, package facade re-export, and two test call sites, with no
  production caller anywhere in `src`.
- Read the journal repository and the staged-temp naming to ground the trigger choice:
  the journal root is one storage-root-wide directory (`repository.list()` returns every
  profile's operations), the operation id is clock-free and derived from profile plus
  resolved target identity plus purpose, and the staged temp is a sibling of the
  operator's own destination.
- Add `_reconcile_crash_orphans_before_publication` and call it from
  `export_profile_bundle` before the destination lock is acquired.
- Guard the sweep so a failure logs and continues rather than failing the new export,
  keeping unfinished work journalled for the next publication.
- Extend the module, function, and recovery-suite docstrings to state that recovery now
  rides the operator's next export rather than an unwritten maintenance verb.
- Add three recovery proofs driven entirely through `export_profile_bundle`, with no
  test-side reconciliation call: an unrelated later export clearing another
  destination's orphan, a re-export to the crashed target itself, and a later export
  settling the owed audit event for a crash-published bundle.

## Outcome

The crash-recovery mechanism is reachable from the operator's own path. Both CLI export
doors compose one application authority, so wiring the sweep at that authority covers
`config profile export` and `config profile subject-access-request` from a single call
site rather than two duplicated CLI-side ones.

Placement before the target lock is load-bearing in two independent ways, both grounded
in how the journal is keyed rather than in convenience. Because the operation id is
clock-free, a repeat export to the same target reuses and overwrites the crashed run's
journal, which holds the only record of where that run staged its cleartext temporary
file; reconciling afterwards would leave those bundle bytes stranded with nothing left
pointing at them. And because reconciliation takes each target lock non-blocking and
treats a held lock as an in-flight export, running it from inside this export's own lock
would make it skip precisely the operation it exists to clear.

Non-tautology is observed, not asserted. With the single call line removed, all three new
proofs fail on the right assertions: two on the surviving cleartext staged temporary
file, one on the missing owed export event. Restored, the two export suites pass
together, twenty-one tests.

## Notes

A sweep failure is logged and swallowed at the call site rather than propagated. The
reconciliation contract itself is unchanged, so its direct callers and existing proofs
still see failures. The reason is availability: an operation whose owed audit event
cannot be emitted, for instance because its profile was deleted after the crash, would
otherwise refuse every future export for every profile.

One residual is left open deliberately and is not a regression, since nothing swept
before this change. A journal that cannot be read or finalised aborts the sweep loop, so
operations ordered after it wait for the next attempt, and an operator who crashes and
never exports again keeps the orphan until they do. Closing that would mean per-operation
isolation inside the reconciler, which is a change to its contract rather than to its
wiring, or an operator-invocable maintenance verb, which is CLI surface another campaign
is live in.

Four repository-wide gates are red at this commit and none is owner surface: three import
hygiene assertions and the core-struct docstring link gate, all four naming
`_login_session.py` or `test_profile_session_root_resume.py` from the concurrent login
campaign. Full-tree collection is clean at 13831 tests.
