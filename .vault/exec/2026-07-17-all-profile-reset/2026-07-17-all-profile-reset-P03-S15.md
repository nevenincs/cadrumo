---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S15'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Prove target discovery includes live, tombstoned, and dangling-pointer buckets but excludes cold defaults

## Scope

- `src/cadrumo/application/tests/test_config_reset.py`

## Description

- Prove target discovery includes a live bucket, a tombstoned bucket, and a dangling-pointer bucket, all discovered in sorted UUID order, and that a completed reset deletes all three (buckets gone, pointer cleared, journal persisted).
- Prove the cold bootstrap/default database (`cadrumo.db` at the storage root) is never a target and survives byte-identical after a full reset.
- Prove the operation erases real registered certificate-source secrets (the encrypted blob store is empty afterward) and releases a held real auth acquisition lock.
- Prove the retention preflight pauses (`RETENTION_UNRESOLVED`) before any auth, pointer, or bucket mutation when a target has a blocking filing without an override, leaving the pointer and buckets untouched.
- Prove `config_reset_status` is a read-only journal view, and prove resume pauses exactly once on changed target content then accepts the new snapshot, and adds a changed-pointer target under the same operation.

## Outcome

Real behavior throughout: real profiles, real tombstone, real certificate source + secret blob, real auth acquisition lock, real pointer file — no mocks or monkeypatch. This suite is the executable proof that discovery reconciles a dangling pointer rather than stranding it and excludes cold defaults, closing the campaign's worst operator-safety defect at the orchestration boundary. 6 tests in this file; 19 P03 tests green overall; ruff clean.

## Notes

This step was already checked in the plan when I inherited P03 but carried no execution record (flagged by `vault plan status` as exec-missing). This record grounds the landed test work (commit `60135859e2`) and re-verifies it green at HEAD, satisfying plan-closure-requires-exec-records.
