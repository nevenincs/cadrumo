---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:3c46987973aed67feb0ed088992855bc176f6183c6641a31e9aa29d7ad9204ea'
step_id: 'S04'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Prove deletion assessment reports real retention blockers without mutating the bucket

## Scope

- `src/cadrumo/application/bucket_maintenance/tests/test_service_retention_floor.py`

## Description

- Prove the target-scoped preflight reports a real retention blocker: persist a real `ModeloRecord` filing inside the four-year LGT window through the encrypted `ModeloRecordCatalogueRepository`, then assert `assess_deletion` returns a fingerprint plus a `blocks_erase` retention floor.
- Prove the assessment does not mutate the durable bucket: three repeated assessments return an identical fingerprint, the bucket directory still exists, and the filing catalogue still holds its records afterward.
- Prove the fingerprint tracks authoritative content: adding a second real filing changes the assessment digest and the retention set.
- Prove the pure enforcement path: a blocking assessment refuses without an override (naming count and safe-erase date), erases only with an acknowledged override plus a non-empty reason, refuses acknowledgement without a reason, and reports no override used when nothing is retained.

## Outcome

Real-behavior throughout: real encrypted secure storage via `isolated_runtime_profile`, real registered profiles, real persisted filings, and the real retention floor assessment — no mocks, stubs, or monkeypatch. The suite is the executable proof that deletion assessment reports real retention blockers without touching the bucket. 15 tests green across this file and the P01.S05 delete suite; ruff clean; collection clean.

## Notes

Landed in commit `11356b4792`; re-verified at HEAD (both P01 test files pass, 42s). The full non-active-bucket hard-erase happy path carries a cross-bucket master-key-session coupling documented as deferred; the retention gate itself is exercised here against the active bucket's real filing catalogue and through the pure enforcement path, and the operation-owned hard erase is proven in the two-bucket runtime of the P01.S05 suite.
