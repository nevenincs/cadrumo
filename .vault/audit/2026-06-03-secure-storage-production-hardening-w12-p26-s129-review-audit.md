---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S129]]'
---

# `secure-storage-production-hardening` `W12.P26.S129` Review

## S129-001 | PASS | Calc-sheets apply is a one-way Google Sheets export mirror

The reviewed module materialises a pure `SheetExportPlan` into app-owned Google Drive folders and a Google Sheets workbook. It writes the operator-facing spreadsheet projection through Google Drive v3 and Sheets v4 APIs, stamps app ownership metadata, and returns a typed apply result.

It does not construct secure-object repositories, choose local storage providers, route SQL storage, read or write local files, or pull Google Sheets edits into local state. The paired pull path owns readback validation separately and gates consumed workbooks on Drive ownership plus registry metadata.

The only settings signal in the reviewed module is the Drive vault folder name resolved through `Settings`, not naked environment access. Google API failures are surfaced through typed outbound storage errors via `execute_request`; import failures are mapped to `OutboundStorageNetworkError`.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_calc_sheets_apply.py src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_calc_sheets_row_set_headers.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py` passed with 19 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_calc_sheets_apply.py src/aeat/adapters/outbound/google/test_calc_sheets_apply.py src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_calc_sheets_row_set_headers.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py` passed.
- A source scan found no naked environment reads, DB route setup, secure-object repository constructors, local storage provider constructors, or direct local file read/write calls in `_calc_sheets_apply.py`.

Disposition: close `AFR-027` as `remote-mirror`.

## S129-002 | MEDIUM | RESOLVED | Re-export accumulated duplicate Sheets structural metadata

Manual live inspection of the configured app-owned workbook found that two prior exports left duplicate `aeat_*` developer metadata entries and duplicate protected ranges on the `Cálculos`, `Procedencia`, `Tarifas`, and `Guía` tabs. That made the export mirror structurally non-idempotent and left pull metadata parsing dependent on Google API return order if future duplicate identity stamps diverged.

Resolution: `apply_export_plan()` now fetches existing developer metadata and protected ranges for an existing workbook, deletes only adapter-managed developer metadata and app-generated protected ranges, then recreates the current metadata/range set. Pull-side metadata merge now refuses conflicting duplicate identity metadata instead of collapsing it silently.

Validation:

- Live Drive/Sheets inspection confirmed duplicate metadata/ranges on the app-owned `AEAT 130 1T 2025` workbook before the fix.
- `uv run --no-sync pytest -q` over the focused Google adapter suite passed with 131 tests.
- `uv run --no-sync aeat config google sync calc pull --modelo 130 --period 1T --year 2025 --spreadsheet-id 1zvR8fAvabtWjvTfosTZcflGXWaP-khyLEZbVHCmHAoc --compute` passed against the live workbook.
- Targeted Google adapter Ruff passed.
