---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step27`

Completed the Modelo 130 registry export reference path and made the workbook
automation dependency explicit in project metadata.

- Modified: `pyproject.toml`
- Modified: `uv.lock`
- Modified: `registry/aeat/modelos/130.toml`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Modified: `src/aeat/application/filing/_export.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/application/filing/test_schema_completeness.py`
- Modified: `src/aeat/application/filing/test_export.py`

## Description

`pyproject.toml` now declares `pywin32` only as an optional Windows extra.
`openpyxl` remains the required XLSX discovery dependency. LibreOffice headless
is the platform-neutral workbook recalculation path when available; Excel COM is
only a local Windows runner. Binary XLS calculation parity remains an explicit
coverage decision unless a supported cross-platform reader or conversion path is
implemented.

Modelo 130 now declares a registry-owned `fichero-boe` export layout sourced
from the official AEAT record-design workbook. The layout includes the envelope
header, page 01 record, envelope footer, fixed offsets, field lengths, literals,
filler fields, draft-derived fields, required header fields, and casilla fields
01 through 19.

The filing runtime now exposes export layout definitions through the validated
registry subview. `export_draft` renders the active registry layout to bytes,
writes the file locally, and returns a digest-bearing receipt. `verify_export`
checks exported casilla payloads against the approved draft and reports drift by
casilla id.

## Tests

- `uv lock --check`
- `uv run python -c "import openpyxl; print('spreadsheet discovery stack ok')"`
- Direct registry validation over committed registry TOML.
- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_export.py -q`
- `uv run pytest src/aeat/domain/calculations/registry src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/application/filing/test_export.py -q`
- `uv run ruff check pyproject.toml src/aeat/domain/calculations/registry src/aeat/application/filing/_export.py src/aeat/application/filing/runtime.py src/aeat/application/filing/test_export.py src/aeat/application/filing/test_schema_completeness.py`
- `uv run ty check src/aeat/domain/calculations/registry src/aeat/application/filing/_export.py src/aeat/application/filing/runtime.py src/aeat/application/filing/test_export.py src/aeat/application/filing/test_schema_completeness.py`
- `git diff --check` over the touched project, registry, runtime, and test files.

Focused verification passed with 100 tests.
