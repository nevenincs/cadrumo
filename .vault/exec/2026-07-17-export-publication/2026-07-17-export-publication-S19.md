---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S19'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Classify a journal that vanished mid-scan as a skip rather than a failure so a peer process completing normally cannot make the sweep tell an operator that an unencrypted file may remain, gated on a test removing a journal between scan and reconcile

## Scope

- `src/cadrumo/application/user_profile/_bundle_export_operation.py`
- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`

## Description

- Classify a journal that vanished between the directory walk and the load as a skip,
  ahead of the general unreadable-journal handler it was being caught by.
- Add a proof that reconciliation reports no failure for that state while still
  reconciling the healthy operation beside it.

## Outcome

A peer export completing normally no longer looks like a fault. Because the
not-found error subclasses the general journal error, the isolating handler was
catching it and producing a failure row -- telling the operator an unencrypted file may
remain when in fact a peer simply succeeded and cleaned up after itself. That is the
kind of false alarm that trains an operator to ignore the warning that matters.

The classification now matches the lock-held case: healthy concurrent work is a skip,
in neither the reconciled nor the failed bucket.

## Notes

The first version of this proof was vacuous and was caught by its own negative control.
It deleted the journal before the sweep began, so the directory walk never saw it and
the race was never exercised; it passed with the fix removed. It was rewritten around a
repository subclass that pins only the walk, so the real scan classification, the real
load, and the real filesystem all run and the journal genuinely is absent. The rewritten
proof fails with the classification removed, reporting the not-found failure row.

That miss is worth recording plainly: a passing test written for a race is the easiest
kind of false gate to ship, and only the removed-fix control surfaced it.
