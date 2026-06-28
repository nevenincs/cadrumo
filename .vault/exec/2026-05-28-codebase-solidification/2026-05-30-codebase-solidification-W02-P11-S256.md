---
step_id: S256
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

# codebase-solidification W02.P11.S256

Migrated 5 bare raises in `_export_header.py` to `BucketValidationError`:
- `_ensure_utc` (2 ValueError sites: naive datetime, non-UTC offset)
- `ExportArchiveHeader._check_manifest_digest` (3 ValueError sites: wrong length, non-hex, uppercase)
