---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Author the hard-delete crash-injection test proving readiness refuses a half-removed bucket and the repair detects partial-directory removal

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_bucket_crash_windows.py`

## Description

Authored the hard-delete crash-injection test: prove a soft tombstone leaves the bucket off every live surface but resolvable by id for repair, and that a partial directory with a torn manifest is detected by the repair-integrity scan and idempotently reclaimed by the removal verb.

## Outcome

Two tests pass, pinning tombstone off-surface behaviour plus partial-directory detection and idempotent removal.

## Notes

None.
