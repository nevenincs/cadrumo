---
step_id: "S03"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P01.S03

## Summary

Replaced `class _BinaryXlsConversionError(Exception)` with `class _BinaryXlsConversionError(CoreError)` at `src/aeat/domain/calculations/registry/_workbook_parity.py:63`. Added `from ....core.errors import CoreError` import. The pre-staged `ErrorCode` declaration in `src/aeat/core/errors/registry/_core.py` (code `INTEGRITY_REGISTRY_BINARY_XLS_CONVERSION`) was already present; removed a conflicting duplicate entry in `_domain.py`. Removed the stale allowlist entry from `test_exception_base_hygiene.py` since the class is no longer a bare `Exception` subclass.

## Files touched

- `src/aeat/domain/calculations/registry/_workbook_parity.py` — base class changed to `CoreError`, import added
- `src/aeat/core/errors/registry/_domain.py` — conflicting duplicate entry removed
- `src/aeat/core/errors/test_exception_base_hygiene.py` — stale allowlist entry removed

## Outcome

All relevant tests pass. Pre-existing `modelo_210` cadence failure is unrelated.
