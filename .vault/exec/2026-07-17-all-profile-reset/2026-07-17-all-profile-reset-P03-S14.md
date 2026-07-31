---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:1e8f7bb715ebdf96166a21e7b26a40717040461738797b891939e8184ec744d7'
step_id: 'S14'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Reacquire locks and recheck fingerprints and retention during roll-forward resume without mutating on status

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Reacquire every remaining target's lock in sorted UUID order on resume (`resume_config_reset`), including the current-pointer bucket, before touching any state.
- Recheck fingerprints during resume (`_resume_preflight`): re-assess each not-yet-deleted target and pause `TARGET_STATE_CHANGED` when a target's content fingerprint diverged from the snapshot, rather than proceeding on a stale assessment.
- Recheck retention during resume: re-derive each target's retention decision and pause `RETENTION_UNRESOLVED` when a blocking record now lacks an approved override; a changed content fingerprint requires renewed `--yes` plus any retention override before continuing.
- Keep status non-mutating: `config_reset_status` loads and returns the journal (by id or latest) without acquiring target locks, changing phases, or writing.

## Outcome

Resume rolls forward against reality rather than its earlier assessment: it re-locks, re-fingerprints, and re-checks retention, pausing for renewed confirmation when the world changed under it, while status stays a pure read. This prevents a resume from erasing a bucket whose content changed since the crash. Proven by the P03.S16 `auth_clearing_after_effect` boundary (resume pauses `TARGET_STATE_CHANGED`, a second resume completes), the P03.S15 resume-pauses-on-changed-content test, and the P03.S17 retention-recheck test. Status non-mutation proven by the read-only-journal-view test. 19 P03 tests green.

## Notes

Landed in commit `60135859e2`; re-verified at HEAD. The pointer reconciliation on resume (`_reconcile_pointer_snapshot_for_resume`) is the pointer-drift counterpart to the fingerprint recheck: both pause rather than mutate when the snapshot no longer holds.
