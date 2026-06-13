---
step_id: S60
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S60 — test: _pdfplumber and _record_design defer to centralized config

## Outcome

Added `test_pdfplumber_and_record_design_do_not_mutate_pdfminer_logger` to
`src/aeat/core/test_logging.py`. The test calls `configure_logging()`,
imports both `aeat.adapters.inbound.pdf._pdfplumber` and
`aeat.domain.calculations.registry._record_design`, then asserts
`logging.getLogger("pdfminer").level` is still `WARNING` (no re-mutation
from either module). Also asserts `suppress_pdfminer_debug_logging` is no
longer in `_pdfplumber.__all__`.

## Files touched

- `src/aeat/core/test_logging.py`

## Verification

`uv run --no-sync pytest src/aeat/core/test_logging.py -x -q` — 11 passed.
`vault plan step check S60` applied.
