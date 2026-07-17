---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Add target deletion assessment and reset ownership fields to bucket-maintenance contracts

## Scope

- `src/cadrumo/application/bucket_maintenance/_contracts.py`

## Description

- Add `AssessBucketDeletionCommand`, a read-only deletion-assessment intent addressing one explicit bucket by `BucketId`.
- Add `BucketDeletionAssessment` carrying `exists`, and for an existing target the label, lifecycle status, structured `BucketDeletionFingerprint`, and `RetentionFloorAssessment`; a model validator enforces the mutually-exclusive existing/absent shapes so an absent assessment cannot carry bucket metadata.
- Extend `DeleteBucketCommand` with the caller-owned reset context pair `reset_operation_id` and `expected_deletion_fingerprint`, each a 64-char lowercase SHA-256 hex, with a validator requiring the two to appear together (reset deletion ownership needs operation id and expected fingerprint as a unit).
- Extend `DeleteBucketResult` with `deletion_fingerprint`, optional `reset_operation_id`, and the `already_absent` flag distinguishing an actual erase from an accepted journal-proven-absent target.

## Outcome

Closed-value axes stay typed as their core enums (`UserProfileStatus`) and every selector is a `BucketId`, per the architecture-boundaries discipline. The contracts give a programmatic caller the same typed input/output shape the service consumes and provide the operation-ownership fields P01.S02 verifies during deletion. Ruff clean; the contract shapes are exercised end to end by the P01.S04 and P01.S05 real-behavior suites (15 tests green).

## Notes

The implementation landed in commit `11356b4792` (feat(config): establish durable reset deletion foundation). This record grounds that landed work against the plan step under the plan-closure-requires-exec-records discipline; verification was re-run at HEAD before the step was checked. `BucketDeletionFingerprint` is the shared structured fingerprint defined alongside the deletion contracts and re-exported through the package facade.
