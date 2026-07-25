---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S67'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Reacquire locks and recheck fingerprints and retention during roll-forward resume without mutating on status

## Scope

- `src/cadrumo/application/config_reset.py`
- `src/cadrumo/application/tests/test_config_reset.py`

## Description

- Take the operation lock, load the journal, and return immediately when the operation is already complete, so a resume of a finished operation is a no-op.
- Reopen the active-profile pointer transaction, re-read the live pointer, and rebuild the lock set from the not-yet-deleted targets unioned with the current pointer bucket, sorted, then reacquire those locks through the shared bucket-maintenance authority.
- Reconcile the recorded pointer snapshot against the live pointer and pause with the pointer-changed reason when they diverge, saving the paused journal and returning without mutating any target.
- Re-assess each unfinished target under the reacquired lock, comparing the freshly computed deletion fingerprint against the value recorded in the journal.
- Pause with the target-state-changed reason and the affected target ids when a fingerprint diverges, so a bucket modified since the snapshot is never erased on the strength of a stale digest.
- Recompute the retention decision for each unfinished target and pause with the retention-unresolved reason when it blocks erase without an approved override, carrying a caller-supplied override through the recheck.
- Clear the pause reason and paused target ids and persist the incomplete status only after both preflights pass, then roll forward through the auth, pointer, deletion, and completion passes.
- Keep `config_reset_status` a pure read that loads a journal by identifier or returns the latest, with no save, repair, or phase advance on any path.
- Re-snapshot a target that vanished out of band below the deleting phase as absent, clearing its fingerprint, label, and lifecycle status, so the operation pauses once on the state change and the next resume converges.
- Leave a target already recorded absent, and a target absent at the deleting phase, unchanged and unblocked, preserving the crash-resume path whose absence is proven by its ownership marker.
- Add a regression proof that a reset paused on retention, whose blocked target is then removed through the canonical bucket-removal primitive, pauses exactly once with the target-state-changed reason and then completes.

## Outcome

- Resume is roll-forward only: it re-derives every precondition under freshly reacquired locks rather than trusting the journal's recorded state, so a bucket, pointer, or retention floor that changed while the operation was interrupted pauses the operation instead of being overrun.
- Lock reacquisition uses the same sorted, de-duplicated authority as the start path, so no divergent ordering exists between the two entry points.
- Status is structurally non-mutating, so an operator may inspect an interrupted destructive operation without advancing it.
- Pause reasons are specific, naming whether the pointer moved, a target changed, or retention blocked, and carry the affected target ids.
- A resume-convergence defect found by an independent audit of this destructive surface is closed: a target removed out of band below the deleting phase was previously returned unmodified, so the change flag was recomputed on every resume and the operation paused forever while start stayed refused by the incomplete-journal guard, leaving the feature permanently unusable with no supported escape.
- The re-snapshot is deliberately one-directional toward absence, and an absent target is never erased, so the correction cannot widen what the operation destroys.
- Landed in commit `60135859e2`, with the resume loop decomposed into named outcome helpers in `9851e08ae8` and the convergence correction plus its regression proof landed by this step.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- Resume identity is the operation identifier, which is randomly minted and clock-free, so a retried resume addresses the same operation rather than creating a new one.
