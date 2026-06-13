---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step29`

Completed the live workbook backend setup and removed the remaining no-op risk
from the LibreOffice runner path.

- Modified: `pyproject.toml`
- Modified: `uv.lock`
- Modified: `src/aeat/domain/calculations/registry/_workbook_parity.py`
- Modified: `src/aeat/domain/calculations/registry/test_workbook_parity.py`

## Description

The project environment is now self-contained under `uv sync --all-extras` for
the Python dependencies used by the touched runtime surface. `python-i18n` is a
declared runtime dependency, so syncing the project no longer removes the CLI
localization backend.

LibreOffice discovery is no longer only a future availability flag. The runner
can be discovered through `PATH` or configured explicitly through
`AEAT_LIBREOFFICE_EXECUTABLE`. The local machine uses Scoop shims for `soffice`
and `libreoffice`, so ordinary `uv run` processes detect the recalculation
runner without per-command setup.

The LibreOffice execution path now writes recalculated output to a separate
directory and fails if LibreOffice does not produce a converted workbook. This
prevents a stale source workbook from being read as if recalculation had
occurred.

## Verification

- `scoop install libreoffice`
- `scoop reset libreoffice`
- `scoop shim add soffice C:\Users\hello\scoop\apps\libreoffice\current\LibreOffice\program\soffice.exe`
- `scoop shim add libreoffice C:\Users\hello\scoop\apps\libreoffice\current\LibreOffice\program\soffice.exe`
- `uv lock`
- `uv sync --all-extras`
- Live project API smoke: synthetic XLSX inputs `12` and `30` recalculated to workbook output `42` through `run_workbook_with_libreoffice`.
- Corpus workbook backend gate: 72 workbooks discovered, 47 record-design XLSX workbooks, 25 explicit binary XLS unsupported classifications, zero failed scans, LibreOffice runner available.
- `uv run pytest src/aeat/domain/calculations/registry/test_workbook_parity.py -q`
- `uv run pytest src/aeat/domain/calculations/registry src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/application/filing/test_export.py -q`
- `uv run ruff check pyproject.toml src/aeat/domain/calculations/registry src/aeat/application/filing/_export.py src/aeat/application/filing/runtime.py src/aeat/application/filing/test_export.py src/aeat/application/filing/test_schema_completeness.py`
- `uv run ty check src/aeat/domain/calculations/registry src/aeat/application/filing/_export.py src/aeat/application/filing/runtime.py src/aeat/application/filing/test_export.py src/aeat/application/filing/test_schema_completeness.py`
- `uv lock --check`
