---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:b624e69d07c448287fe44e13e309434bdfab4c03b1bd5340cb358a24fec3f18e'
step_id: 'S31'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add trash_rename_and_remove in the bucket package beside the provisioning primitive, taking an explicit trash-cleanup error policy, gated by a test covering both the rename-succeeds and rename-fails branches

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_layout.py`

## Description

- Add `trash_rename_and_remove(target, on_trash_cleanup_error=...)` beside `provision_bucket_directory` in `_layout.py`, taking an explicit trash-cleanup error policy (raise vs. ignore).

## Outcome

Landed in commit `d5fb3f802f`. Gated by a real held-open-file-handle reproduction (not a mock) at the primitive level, covering both the rename-succeeds and rename-fails branches, proven by mutation (flipping either call site's policy argument reddens its dedicated test).

## Notes

This Step's checkbox was set in the prior reconciliation pass (commit `bb18425074`, "33 of 64") before the primitive existed — `d5fb3f802f` is the only commit in this history that ever defines `trash_rename_and_remove`. The exec record was scaffolded but left empty at that time. Recorded here for honesty; the Step is now genuinely satisfied.
