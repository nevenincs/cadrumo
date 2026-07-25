---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S65'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Invoke strong profile logout for the active reset target and reconcile dangling pointers through the core authority

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Add a pointer-reconciliation pass that advances every target not yet past the pointer-reconciled phase, persisting the reconciling phase before the logout and the reconciled phase after it.
- Invoke strong profile logout exactly once, and only when the captured pointer snapshot names a bucket that is itself one of the reset targets, so an unrelated active profile is not logged out.
- Consume strong logout through the owning package's public top-level facade rather than any private module, keeping the dependency on the profile package's published surface.
- Capture the pointer snapshot through the core pointer authority inside the active-profile pointer transaction, correlating presence, bucket identity, and content digest.
- On resume, re-read the current pointer under the transaction and compare it against the recorded snapshot, pausing with the pointer-changed reason when the live pointer no longer matches the journal.
- Treat a dangling pointer, whose bucket is already absent, as an explicit reset target so the stale pointer is reconciled rather than left behind.

## Outcome

- The active session is closed through the canonical strong-logout primitive before the bucket backing it is erased, so no live session outlives its storage.
- Logout is delegated, not re-implemented: the reset module adds no pointer-clearing or session-eviction path of its own, preserving the primitive's atomicity and event emission.
- A pointer that moved between start and resume pauses the operation rather than being overwritten, so a concurrent profile switch cannot be silently clobbered by a resumed reset.
- Dangling pointers are reconciled as first-class targets, so a completed reset leaves no stale active-profile record pointing at an absent bucket.
- Landed in commit `60135859e2`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- A concurrent campaign owns the profile orchestration and login-session modules. This step consumes strong logout only through the profile package's public facade, where the symbol is already exported, so no edit to the peer campaign's files was required and no private module is imported.
