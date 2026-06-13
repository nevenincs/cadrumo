---
step_id: S57
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S57 — centralize pdfminer logging in dictConfig

## Outcome

Added `pdfminer` entry (`level: WARNING`, `propagate: true`) to the `loggers`
block of `configure_logging()` dictConfig in `src/aeat/core/logging.py`.

Deleted `suppress_pdfminer_debug_logging` context manager from
`src/aeat/adapters/inbound/pdf/_pdfplumber.py` (the function definition, all
three internal `with suppress_pdfminer_debug_logging(),` call sites, the
`__all__` export, and the now-unused `logging`, `Iterator`, `contextmanager`
imports). Updated module docstring to state dictConfig governs pdfminer level.

Updated `src/aeat/adapters/inbound/declaracion/_parser.py` to remove its
import of `suppress_pdfminer_debug_logging` and the wrapping `with` clause
around its `pdfplumber.open()` call.

## Files touched

- `src/aeat/core/logging.py`
- `src/aeat/adapters/inbound/pdf/_pdfplumber.py`
- `src/aeat/adapters/inbound/declaracion/_parser.py`

## Verification

`uv run --no-sync pytest src/aeat/adapters/inbound/pdf/ -x -q` — 50 passed.
`vault plan step check S57` applied.
