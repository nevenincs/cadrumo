---
step_id: S457
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W05.P25.S457

## Step

Introduce `XLS_EXTENSION: Final[Literal[".xls"]] = ".xls"` in `external_constants` and migrate `_workbook_parity.py` `.xlsx` cluster + `.xls` literal.

## Outcome

- Added `XLS_EXTENSION: Final[Literal[".xls"]] = ".xls"` to `external_constants.py`.
- Upgraded `XLSX_EXTENSION` and `XLSM_EXTENSION` to `Final[Literal[...]]` for type narrowing.
- Added `Literal` to `external_constants.py` imports.
- In `_workbook_parity.py`: added `XLS_EXTENSION as _XLS_EXTENSION` import, migrated 6 literals (lines 64, 291, 306, 323, 335, 609).
- Pyright type errors resolved via `Final[Literal[...]]` narrowing.

## Files touched

- `src/aeat/core/external_constants.py`
- `src/aeat/domain/calculations/registry/_workbook_parity.py`
