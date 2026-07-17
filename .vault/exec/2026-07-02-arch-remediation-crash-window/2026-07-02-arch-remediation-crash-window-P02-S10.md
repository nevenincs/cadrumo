---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Author the rename-profile crash-injection test proving the diagnostics detect label drift and the repair re-syncs the manifest from the authoritative SQLite record

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_bucket_crash_windows.py`

## Description

Authored the rename crash-injection test: drive only the record-side write of the real rename to simulate a crash before the manifest label projection, and prove the load-time integrity gate refuses the drifted profile naming the label-drift stores; the anti-tautology partner proves a synced rename loads cleanly.

## Outcome

Two tests pass, pinning fail-closed label-drift detection.

## Notes

The manifest-from-record re-sync is a documented non-goal (no repair verb); the test asserts detection only.
