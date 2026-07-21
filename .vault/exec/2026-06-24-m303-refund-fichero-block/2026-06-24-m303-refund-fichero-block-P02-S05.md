---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S05'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

# Emit the REDEME byte mapping redeme_enrolled to 1 or 2 in the header composer

## Scope

- `src/aeat/application/modelo/_export.py`

## Description

- Emit the REDEME byte in the M303 fichero header composer at DR303 page-1 position 110, mapping the standing `redeme_enrolled` profile fact to `"1"` (SI) when enrolled and `"2"` (NO) otherwise.
- Source the byte from the workflow profile IVA facts rather than the refund disposition, so the REDEME indicator rides every M303 filing, not only refunds.

## Outcome

- The header composer in `src/aeat/application/modelo/_export.py` sets `headers["redeme"]` from `workflow_profile.iva.redeme_enrolled`.
- The golden-SHA M303 tests assert the resulting byte at page-1 offset 110 is `"1"` for a REDEME refund filer and `"2"` for a non-REDEME filer. Both pass at HEAD.

## Notes

- This record documents the verified landed state at HEAD.
