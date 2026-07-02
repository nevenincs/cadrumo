---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S10'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
---

# Delete the now-unnecessary scattered dispose_engine calls from the CLI lifecycle, rename, and navigation tests whose choreography the unified lifecycle makes redundant

## Scope

- `src/aeat/entrypoints/cli/tests`

## Description

- Delete 64 redundant `dispose_engine` imports and calls from `test_profile_lifecycle_navigation.py` and `test_profile_rename_maintenance_events.py`.
- Track the `_evict_engine` -> `_dispose_engine` cleanup-function rename in the hardening convention guard.

## Outcome

The scattered `dispose_engine` choreography is gone; the guard tracks the renamed cleanup function.

Landed in commit `38e62c216`.

## Notes
