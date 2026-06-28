---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S129'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s129-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S129`

Closed `AFR-027` for the Google calc-sheets apply adapter.

## Description

- Reviewed `src/aeat/adapters/outbound/google/_calc_sheets_apply.py` against the `remote-provider` scanner signal.
- Classified the adapter as a one-way Google Drive/Sheets export mirror, not local storage or secure-object backend code.
- Verified the reviewed module uses `Settings` for the Drive vault folder name and has no naked environment reads.
- Verified Google API failures stay on typed outbound storage error surfaces.
- Recorded the S129 review and updated the affected-file register row to `closed`.

## Outcome

`AFR-027` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_calc_sheets_apply.py src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_calc_sheets_row_set_headers.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_calc_sheets_apply.py src/aeat/adapters/outbound/google/test_calc_sheets_apply.py src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_calc_sheets_row_set_headers.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py`

## Notes

Continuation live review found duplicate app-managed developer metadata and protected ranges on the configured Google Sheets workbook after repeated exports. `_calc_sheets_apply.py` now deletes only adapter-managed developer metadata and protected ranges before recreating the current structural state on re-apply. The focused Google adapter suite passed with 131 tests after the remediation.
