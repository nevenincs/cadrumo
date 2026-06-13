---
step_id: S74
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P02.S74 — pikepdf._core level test

## Outcome

Added `test_pikepdf_core_logger_level_governed_by_dictconfig` to
`src/aeat/core/test_logging.py`. The test resets the `_CONFIGURED` guard,
calls `configure_logging()`, and asserts `logging.getLogger("pikepdf._core").level
== logging.WARNING`. Mirrors the pattern used for the pdfminer S57 test.

## Files touched

- `src/aeat/core/test_logging.py`

## Verification

`uv run --no-sync pytest src/aeat/core/test_logging.py::test_pikepdf_core_logger_level_governed_by_dictconfig -q` — 1 passed.
