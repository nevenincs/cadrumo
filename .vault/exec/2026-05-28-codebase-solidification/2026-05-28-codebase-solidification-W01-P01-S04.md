---
step_id: "S04"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P01.S04

## Summary

Added `test_binary_xls_conversion_error_is_registered_in_error_registry` to `src/aeat/domain/calculations/registry/test_workbook_parity.py`. The test calls `get_registered_error_code(_BinaryXlsConversionError)`, asserts the returned code is `INTEGRITY_REGISTRY_BINARY_XLS_CONVERSION`, and verifies that code string appears in `ERROR_REGISTRY`. This confirms `__init_subclass__` binding via `CoreError` inheritance succeeded. Also imported `_BinaryXlsConversionError` in the test module's import block.

## Files touched

- `src/aeat/domain/calculations/registry/test_workbook_parity.py` — new test + imports added

## Outcome

Test passes. 19/20 tests in the module pass; 1 deselected due to pre-existing `modelo_210` cadence registry schema failure unrelated to this step.
