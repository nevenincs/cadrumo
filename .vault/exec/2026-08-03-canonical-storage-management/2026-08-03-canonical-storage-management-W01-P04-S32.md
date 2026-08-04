---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:52f21e9f20464d8f50269ee9e0dbf37dc0281093fa625f917b5d7ef438900090'
step_id: 'S32'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite remove_profile_bucket_directory as a caller of the shared trash-rename primitive passing the ignore policy, gated by the existing profile-deletion suite

## Scope

- `src/cadrumo/application/user_profile/_orchestration.py`

## Description

- Rewrite `remove_profile_bucket_directory` (`_orchestration.py`) as a caller of `trash_rename_and_remove`, passing the `ignore` cleanup policy explicitly (leftover trash litter from an ordinary delete is tolerable), still surfacing a genuine failure as a `UserProfileError` via its own `target.exists()` check rather than a raw `OSError`.

## Outcome

Landed in commit `d5fb3f802f`.

## Notes

Same premature-checkbox history as S31; see that record.
