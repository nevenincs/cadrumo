---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Expose target-scoped deletion assessment and verify reset operation ownership and fingerprint during deletion

## Scope

- `src/cadrumo/application/bucket_maintenance/_service.py`

## Description

- Add the public `assess_deletion` method: it validates the bucket root against link redirection, returns an absent assessment for a missing directory, refuses a directory without a readable registered manifest, and otherwise returns the label, lifecycle status, retention floor, and deletion fingerprint without any lifecycle mutation.
- Reassess retention and the deletion fingerprint inside `_delete_locked` before any mutation, reusing `assess_deletion` so the assessment path and the delete path cannot drift.
- Verify caller-supplied reset ownership during deletion: when `reset_operation_id` and `expected_deletion_fingerprint` are present, call the durable journal's `verify_deletion_ownership` and refuse the erase when the journal does not own the requested target.
- Refuse before lifecycle mutation when the expected fingerprint diverges from the freshly-observed fingerprint (content changed after assessment).
- Accept an already-absent target only when a matching operation id and expected fingerprint prove ownership through the journal's deleting marker; generic absence remains a `ProfileNotFoundError`.

## Outcome

The service composes the canonical primitives rather than re-implementing any write path: the erase still runs the soft-tombstone `delete_profile_with_lifecycle_span` followed by the hard `remove_profile_bucket_directory`, under the pointer-first `active_profile_pointer_transaction` and the mutation target lock. Reset-owned deletion routes its `BUCKET_DELETED` event only through an explicitly injected repository, leaving the external reset journal as the surviving ownership evidence. Proven by the P01.S05 real-behavior suite (fingerprint-mismatch refusal, matching-ownership erase, journal-proven idempotent absence) and the P01.S04 non-mutating assessment tests. Full bucket_maintenance + config_reset suites green (86 tests); ruff clean; collection clean.

## Notes

Landed in commit `11356b4792`; this record grounds it and re-verifies at HEAD. The composition honours composition-service-no-parallel-write-path: no second pointer writer or second bucket-deletion path is introduced. The journal `verify_deletion_ownership` / `create` surface lives in `_config_reset_repository.py` (P02.S07 territory) and was already present at HEAD, so the service delegates rather than reimplementing ownership checks.
