---
step_id: S199
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P08.S199

Narrowed `-> Any` returns in `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`:

- Added `from typing import TYPE_CHECKING` + `_GoogleResource` import guard.
- Added `_ValueRange = dict[str, Any]` type alias.
- `_drive_service` / `_sheets_service` return type: `Any` → `"_GoogleResource"`.
- `_verify_ownership` / `_read_developer_metadata` / `_read_row_set_edits` / `_batch_get_values_for_row_sets` param narrowed from `Any` to `"_GoogleResource"`.
- `_batch_get_values` / `_batch_get_values_for_row_sets` return: `list[Any]` → `list[_ValueRange]`.
- `_raw_cell_value` / `_decode_*_edits` param: `list[Any]` → `list[_ValueRange]`.
- `_decode_row_set_block` rows param: `list[Any]` → `list[list[object]]`.

Commit: `491d6af66`
