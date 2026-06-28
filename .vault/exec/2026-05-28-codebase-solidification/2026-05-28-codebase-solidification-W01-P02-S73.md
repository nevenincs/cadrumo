---
step_id: S73
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P02.S73 — pikepdf._core moved to dictConfig loggers block

## Outcome

Added `pikepdf._core` to the `loggers` block in `configure_logging()` (WARNING,
propagate=True) in `src/aeat/core/logging.py`, matching the established pdfminer
pattern. Removed the bootstrap-time `_logging.getLogger("pikepdf._core").setLevel()`
mutation from `src/aeat/__init__.py` (line 25). Updated the module docstring in
`__init__.py` to reflect that logger-level policy lives in dictConfig.

## Files touched

- `src/aeat/core/logging.py` (loggers block extended)
- `src/aeat/__init__.py` (bootstrap mutation removed, docstring updated)

## Verification

`uv run --no-sync pytest src/aeat/core/test_logging.py -q` — 12 passed.
