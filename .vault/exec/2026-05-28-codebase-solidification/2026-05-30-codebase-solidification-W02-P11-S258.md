---
step_id: S258
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-lambda6
commit: 590e07cc1
status: closed
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S258

Migrated 6 bare raises to `BucketValidationError`:
- `_layout.py:bucket_paths` — 2 ValueError sites (empty bucket_id, path separator)
- `_keystore_paths.py:keystore_path` — 2 ValueError sites (empty bucket_id, path separator)
- `_keystore_paths.py:validate_keystore_separation` — 2 ValueError sites (resolves under buckets parent, resolves under db dir)
