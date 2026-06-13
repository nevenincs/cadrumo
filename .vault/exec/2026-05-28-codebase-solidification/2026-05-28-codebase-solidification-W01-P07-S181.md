---
tags:
  - "#exec"
  - "#codebase-solidification"
date: "2026-05-28"
modified: '2026-05-28'
step_id: "S181"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P07.S181 — shared file-extension constants

## Outcome

Created `src/aeat/adapters/inbound/financial/providers/_constants.py` with three constants:

- `CSV_EXTENSIONS: frozenset[str] = frozenset({".csv", ".txt"})`
- `PDF_EXTENSION: Final[str] = ".pdf"`
- `XLSX_EXTENSION: Final[str] = ".xlsx"`

Migrated all inline string literals across the providers package:

- `_detection.py` lines 41 and 83: two `{".csv", ".txt"}` inline sets → `CSV_EXTENSIONS`; two `== ".xlsx"` → `XLSX_EXTENSION`; one `== ".pdf"` → `PDF_EXTENSION`
- `_csv.py` line 179: `frozenset({".csv", ".txt"})` → `CSV_EXTENSIONS`
- `_xlsx.py` line 71: `frozenset({".xlsx"})` → `frozenset({XLSX_EXTENSION})`
- `_pdf_n26.py` line 97: `frozenset({".pdf"})` → `frozenset({PDF_EXTENSION})`

## Collision signal

Clean — no non-authored WIP on any target file before first edit.

## Commit

`0ed384302`
