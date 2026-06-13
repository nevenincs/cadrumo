---
step_id: S487
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P29.S487

**Step**: migrate .xls bare sites + Literal annotations in _workbook_parity.py:109,364,646,1129 to XLS_EXTENSION/XLSX_EXTENSION.

## Outcome

Migrated all bare `.xls`/`.xlsx` string literals in `_workbook_parity.py` to `_XLS_EXTENSION`/`_XLSX_EXTENSION` constants:
- `extension: Literal[".xlsx", ".xls"]` → `Literal[_XLSX_EXTENSION, _XLS_EXTENSION]` (line 103)
- `converted_extension: Literal[".xlsx"]` → `Literal[_XLSX_EXTENSION]` (line 133)
- `extension=".xls"` → `extension=_XLS_EXTENSION` (line 358)
- `suffix.lower() != ".xls"` → `!= _XLS_EXTENSION` (line 640)
- `suffix: Literal[".xlsx", ".xls"]` → `Literal[_XLSX_EXTENSION, _XLS_EXTENSION]` (line 1123)
- Sibling discovery: `_record_design.py:98` had bare `".xls"` — migrated to `_XLS_EXTENSION`

## Files

- `src/aeat/domain/calculations/registry/_workbook_parity.py`
- `src/aeat/domain/calculations/registry/_record_design.py` (sibling)

## Commit

5b45dd58c
