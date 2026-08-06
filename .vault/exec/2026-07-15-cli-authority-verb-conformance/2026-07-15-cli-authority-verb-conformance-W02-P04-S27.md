---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:92cb83835132049e5ebc54b11e6870216d0024cc04c26f3d1fd3cb09a8d84503'
step_id: 'S27'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Route repository pointer reads, selection, rollback, and deletion clear through the same reentrant active-profile pointer transaction, preserve whole-create-span ownership and pointer-first test lock order, and remove the retired text-rollback persistence exemption

## Scope

- `src/cadrumo/application/user_profile/_profile_repository.py`
- `src/cadrumo/application/user_profile/tests/test_profile_repository.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`

## Description

- Enter the repository-root active-profile pointer transaction before repository pointer work.
- Capture exact pointer bytes during create and preserve manifest → pointer → encrypted-record ordering.
- On any `BaseException`, independently attempt public engine disposal, propagating bucket cleanup, and exact pointer restoration; group the original error with every rollback failure.
- Hold delete ownership through pointer read, conditional clear, manifest tombstone, and record tombstone.
- Hold select ownership through validation, language-hint refresh, and pointer write.
- Remove the four retired pointer helpers, their direct pointer imports, and the obsolete persistence exemption.
- Acquire the `repository.root` pointer transaction before test storage sessions.

## Outcome

- Updated the repository, repository tests, and sensitive-persistence policy within the approved S27 scope.
- Author checks passed Ruff and `py_compile`.
- Author test lanes passed 23 repository/policy tests, 20 orchestration/setup/wizard tests, and 11 import-hygiene tests.
- Uncached import-linter analyzed 3,422 files and 16,146 dependencies with five contracts kept and none broken.
- Post-change RAG grounding and exact searches found no retired repository helpers or direct repository pointer writes.
- Independent review passed with no blocker, high, or medium findings; its lanes passed 23, 15, and 11 tests respectively, with identical import-linter counts.

## Notes

- One deliberately short timeout produced no acceptance result; the proper serial reruns passed.
- The peer `_fsync` relocation and string-indentation changes in the sensitive-persistence inventory are excluded from S27.
- The remaining profile-health pointer writer belongs to S28.
- S29 owns comprehensive real-file rollback, mutation-strength, and concurrency proof; S27 does not claim those tests or global single-writer completion.
- No data loss occurred and no runtime scaffolds were left.
