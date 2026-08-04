---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:1c19ea8bfa19c89e394bdf14b9b8d5dabb8f1cccd0fb3c135c1d965de48cfde2'
step_id: 'S33'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite the profile repository's bucket-directory removal as a caller of the shared trash-rename primitive passing the raise policy, gated by the existing create-rollback suite

## Scope

- `src/cadrumo/application/user_profile/_profile_repository.py`

## Description

- Rewrite `ProfileRepository._remove_bucket_directory` as a caller of `trash_rename_and_remove`, keeping the default `raise` policy — load-bearing: a create-rollback cleanup failure must reach the operator aggregated with the original create failure via `BaseExceptionGroup`, never silently lost while a residual directory lingers.

## Outcome

Landed in commit `d5fb3f802f`.

## Notes

Same premature-checkbox history as S31; see that record.
