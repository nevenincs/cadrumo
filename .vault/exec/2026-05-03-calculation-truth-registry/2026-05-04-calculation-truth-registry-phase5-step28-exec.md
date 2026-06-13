---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step28`

Hardened workbook verification against platform lock-in and silent degradation.

- Modified: `pyproject.toml`
- Modified: `uv.lock`
- Modified: `.vault/adr/2026-05-03-calculation-truth-registry-pending-adr.md`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/_workbook_parity.py`
- Modified: `src/aeat/domain/calculations/registry/test_workbook_parity.py`
- Modified: `.vault/exec/2026-05-03-calculation-truth-registry/2026-05-04-calculation-truth-registry-phase5-step27.md`

## Description

`pywin32` is now an optional Windows-only workbook extra, not a required project
dependency. The workbook parity backend prefers LibreOffice headless as the
platform-neutral recalculation route when available. Excel COM remains an
optional local Windows runner.

Workbook discovery can still produce audit reports, but verification no longer
silently accepts failed scans. `verify_workbook_backend` raises on failed or
timed-out scans by default. Formula workbook execution readiness is an explicit
gate: formula-bearing workbooks fail if execution is required and no local
runner is available.

LibreOffice runner execution validates the executable path and accepted
executable name before invoking the subprocess.

## Tests

- `uv lock --check`
- `uv run python -c "import openpyxl; print('spreadsheet discovery stack ok')"`
- `uv run pytest src/aeat/domain/calculations/registry/test_workbook_parity.py -q`
- `uv run pytest src/aeat/domain/calculations/registry src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/application/filing/test_export.py -q`
- `uv run ruff check pyproject.toml src/aeat/domain/calculations/registry src/aeat/application/filing/_export.py src/aeat/application/filing/runtime.py src/aeat/application/filing/test_export.py src/aeat/application/filing/test_schema_completeness.py`
- `uv run ty check src/aeat/domain/calculations/registry src/aeat/application/filing/_export.py src/aeat/application/filing/runtime.py src/aeat/application/filing/test_export.py src/aeat/application/filing/test_schema_completeness.py`
- `git diff --check` over the touched project, registry, plan, ADR, and execution files.

Focused verification passed with 103 tests.
