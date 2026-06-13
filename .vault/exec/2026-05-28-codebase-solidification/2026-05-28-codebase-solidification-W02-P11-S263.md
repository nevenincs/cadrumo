---
step_id: S263
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-30-codebase-solidification-audit]]"
---

# codebase-solidification W02.P11.S263

**Raise site:** `src/aeat/adapters/persistence/storage/runtime.py:320`

**Change:** Replaced `raise ValueError("bucket_id must not be blank")` with `raise StorageValidationError(...)`. `StorageValidationError` was already imported from `.errors`.

**Tests:** `test_runtime.py` — 22 tests pass.

**Commit:** `d76cbf66e`
