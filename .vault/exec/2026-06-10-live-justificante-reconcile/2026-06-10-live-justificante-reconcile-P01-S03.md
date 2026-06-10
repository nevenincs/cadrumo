---
tags:
  - '#exec'
  - '#live-justificante-reconcile'
date: '2026-06-10'
step_id: 'S03'
related:
  - "[[2026-06-10-live-justificante-reconcile-plan]]"
---




# Prove the persistence boundary with a strict secure-storage roundtrip (every defaultable field non-default), a supersession lifecycle test, and an anti-tautology mutate-on-disk proof.

## Scope

- `src/aeat/application/live/tests/test_justificante_capture.py`

## Description

- Add a real encrypted secure-object roundtrip over `isolated_runtime_profile`:
  ACTIVE, SUPERSEDED, and DISCARDED states, every defaultable field non-default.
- Witness the captured PDF survives byte-for-byte across the envelope and the
  sha256 still matches the decoded bytes.
- Exercise the service: a re-filed period (different PDF) supersedes the prior
  ACTIVE capture; the identical receipt re-captures idempotently.
- Add the anti-tautology proof: surgically drop `superseded_by_snapshot_id` from
  the on-disk envelope and assert the load path rejects the record.

## Outcome

Six tests pass; full P01 sweep (live capture + namespace + error hygiene) green
at 42 passed. Landed as commit `67beb8d82`.

## Notes

No mocks, skips, or xfail; uses the real `SecureObjectRepository` and a real
SQLite engine per the roundtrip discipline. No incidents.
