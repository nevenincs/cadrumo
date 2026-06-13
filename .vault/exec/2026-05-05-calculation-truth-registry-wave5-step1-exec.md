---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---

# Modelo 131 Source Grounding Step

## Scope

- Start Modelo 131 from official AEAT source closure before registry authoring.
- Catalogue current and historical record-design workbooks from the local AEAT
  corpus.
- Pull the current AEAT Modelo 131 instructions into the official corpus for
  readable calculation citations.

## Changes

- Added source catalogue entries for Modelo 131 record designs covering
  2019-2023, 2024, 2025, and 2026.
- Added a source catalogue entry for current AEAT Modelo 131 instructions.
- Added workbook scanner coverage proving the committed Modelo 131 workbooks
  are layout authority and not executable calculation parity evidence.
- Added generalized committed-registry integrity coverage for legal catalogue
  text, source catalogue hashes, modelo reference closure, and AEAT
  record-design manifest consistency.
- Updated the plan ledger for Modelo 131 source guidance and workbook coverage.

## Verification

- `uv run ruff check src\aeat\domain\calculations\registry\test_workbook_parity.py`
- `uv run ty check src\aeat\domain\calculations\registry\test_workbook_parity.py`
- `uv run pytest src\aeat\domain\calculations\registry\test_workbook_parity.py -q`
- `uv run pytest src\aeat\domain\calculations\registry\test_catalogue_verification.py -q`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
