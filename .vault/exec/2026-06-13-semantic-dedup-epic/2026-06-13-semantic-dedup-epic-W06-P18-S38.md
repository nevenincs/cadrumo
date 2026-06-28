---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S38'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# A1b Add a core ISO-datetime parse helper for the Z-suffix fromisoformat sites

## Scope

- `src/aeat/core/time.py`

## Description

- Added `core.time.parse_iso_datetime` (normalises a trailing `Z` to `+00:00`
  before `datetime.fromisoformat`) and exported it.
- Routed the three `datetime.fromisoformat(x.replace("Z","+00:00"))` sites:
  `transactions._parse_datetime`, `attachments._parse_captured_at`, and the
  Drive modified-time parse.

## Outcome

Committed as `db919bc9d`, tagged `relocation:parse_iso_datetime` (5 files).
Ruff clean (dropped the now-unused `datetime` import in `_google_drive`); 86
time/transactions/attachments/storage tests green. Behaviour-identical.

## Notes

All three sites were peer-clean at edit time.
