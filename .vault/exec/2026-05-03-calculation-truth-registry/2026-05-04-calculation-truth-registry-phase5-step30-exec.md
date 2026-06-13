---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step30`

Implemented registry-to-workbook parity execution and corrected workbook
classification so record-design spreadsheets are not treated as tax calculation
oracles.

- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/_workbook_parity.py`
- Modified: `src/aeat/domain/calculations/registry/test_workbook_parity.py`
- Modified: `.vault/exec/2026-05-03-calculation-truth-registry/2026-05-04-calculation-truth-registry-phase5-step29.md`

## Description

The workbook parity backend now has an execution path that feeds one
`SyntheticInputSet` into both a validated registry snapshot and a recalculated
workbook, then emits a normal `WorkbookParityRunReport` with workbook outputs,
registry outputs, legal references, source references, and mismatch status.
Inputs must bind both a registry target and a workbook cell for executable
parity. A workbook must be classified as `formula_form`; record designs,
unsupported binary XLS files, static layouts, and validation sheets are rejected
as executable calculation oracles.

The XLSX classifier now treats committed `disenos_registro` files as
`record_design_layout` even when they contain spreadsheet formulas. Inspection
of committed AEAT record-design XLSX files showed formulas such as row counters
and positional accumulators, not filing calculation formulas. The corpus-wide
gate therefore reports the current official workbook set honestly: 72 workbook
artefacts, 47 record-design XLSX files, 25 unsupported binary XLS files, and no
currently committed official formula-form tax calculation workbooks.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_workbook_parity.py -q`
- `uv run pytest src/aeat/domain/calculations/registry src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/application/filing/test_export.py -q`
- `uv run ruff check pyproject.toml src/aeat/domain/calculations/registry src/aeat/application/filing/_export.py src/aeat/application/filing/runtime.py src/aeat/application/filing/test_export.py src/aeat/application/filing/test_schema_completeness.py`
- `uv run ty check src/aeat/domain/calculations/registry src/aeat/application/filing/_export.py src/aeat/application/filing/runtime.py src/aeat/application/filing/test_export.py src/aeat/application/filing/test_schema_completeness.py`
- `uv lock --check`
- Corpus workbook backend gate with LibreOffice available: 72 discovered, 47 record-design XLSX, 25 unsupported binary XLS, zero failed scans.

Focused workbook parity tests passed with 15 tests. Focused registry and filing
verification passed with 107 tests.
