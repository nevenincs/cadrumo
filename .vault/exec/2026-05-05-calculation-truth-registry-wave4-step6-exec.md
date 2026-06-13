---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---

# Modelo 123 Extraction And Export Behaviour Step

## Scope

- Harden Modelo 123 current and 2019-2023 declaration extraction coverage.
- Harden Modelo 123 historical export verification coverage.
- Keep tests on public parser/export behaviour and committed registry
  snapshots.

## Changes

- Added declaration parser boundary coverage for Modelo 123 current 2026
  declaration PDFs.
- Added declaration parser boundary coverage for Modelo 123 2019-2023
  declaration PDFs.
- Added `verify_export` round-trip coverage for the Modelo 123 2019-2023
  record design.
- Updated the plan ledger to record the completed extraction and export
  behaviour coverage.

## Verification

- `uv run ruff check src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\application\filing\test_export.py`
- `uv run ty check src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\application\filing\test_export.py`
- `uv run pytest src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\application\filing\test_export.py -q`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
