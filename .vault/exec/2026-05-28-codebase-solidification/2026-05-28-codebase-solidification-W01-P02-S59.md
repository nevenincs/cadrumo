---
step_id: S59
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S59 — delete duplicated pdfminer silencer from _record_design.py

## Outcome

Deleted `_suppress_pdfminer_debug_logging` context manager from
`src/aeat/domain/calculations/registry/_record_design.py` (function
definition and both `with _suppress_pdfminer_debug_logging(),` call sites
at lines 254 and 661). Removed the now-unused `import logging` statement.
`contextmanager` and `Iterator` are retained — they are still used by
`_ignore_openpyxl_header_footer_metadata_warnings`.

The two pdfplumber.open() call sites now open without the wrapping
context manager; pdfminer noise is governed by dictConfig from S57.

## Files touched

- `src/aeat/domain/calculations/registry/_record_design.py`

## Verification

`uv run --no-sync pytest src/aeat/domain/calculations/registry/ --ignore=src/aeat/domain/calculations/registry/test_catalogue_verification.py --ignore=src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -x -q` — passes.
`vault plan step check S59` applied.
