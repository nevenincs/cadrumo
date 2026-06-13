---
tags:
  - '#exec'
  - '#core-authority'
step_id: S08
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W02.P03.S08 — CoreNotFoundError base class created

## Decision

CoreNotFoundError(CoreError, KeyError) was created in `core/errors/_not_found.py`.
The plan mentioned "rename NotFoundError to CoreNotFoundError" — the file didn't
exist; we created it fresh. No existing NotFoundError in core/errors/ to rename.

## Files touched

- `src/aeat/core/errors/_not_found.py` — created (27 lines)
- `src/aeat/core/errors/__init__.py` — import and __all__ export
- `src/aeat/core/errors/registry/_core.py` — ERROR_AEAT_CORE_NOT_FOUND entry
- `src/aeat/core/errors/test_core_error_root.py` — S08 assertion tests
- `src/aeat/locales/{es,en,ca,hu}.yml` — error_aeat_core_not_found locale keys

## Verification gate

`pytest src/aeat/core/errors/test_core_error_root.py -x -q` — 6 passed.

## Commit

`8ee53972b` — feat(errors): W02.P03.S08 CoreNotFoundError base in core/errors/_not_found.py
