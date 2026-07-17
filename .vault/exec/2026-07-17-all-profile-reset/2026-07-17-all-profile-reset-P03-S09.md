---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Replace scoped reset with start, status, and resume over all live, tombstoned, and dangling-pointer targets

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Replace the removed scoped reset with three public entry points: `start_config_reset`, `config_reset_status`, and `resume_config_reset`.
- Discover the target set as every registered bucket (`list_profile_buckets(include_tombstoned=True)`) UNION the active-pointer bucket, so live, tombstoned, and dangling-pointer targets are all reconciled; the cold bootstrap/default database is never added as an implicit target.
- Drive execution through a durable roll-forward state machine (`_roll_forward`) composing the auth, pointer, and bucket-deletion authorities, refusing a concurrent start via the journal's incomplete-overlap check.

## Outcome

The single reset intent now addresses the whole target set as one durable operation rather than a per-scope shortcut, closing the ADR's Option E decision (one confirmed all-profile reset as a crash-resumable composition). A dangling pointer is a first-class target reconciled rather than stranded — the core of the safety defect. Proven by the P03.S15 discovery-and-completion test (live A + tombstoned B + dangling target all deleted, cold `cadrumo.db` untouched). 19 P03 tests green; ruff clean; collection clean.

## Notes

Landed in commit `60135859e2` (feat(config): add durable reset orchestration). This record grounds it and re-verifies at HEAD. The orchestration composes the canonical owners (`reset_operator_auth`, `logout_active_profile`, `BucketMaintenanceService.delete`, the pointer transaction) and introduces no parallel writer.
