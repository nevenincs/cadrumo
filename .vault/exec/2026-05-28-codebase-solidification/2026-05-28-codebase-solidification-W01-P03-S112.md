---
step_id: S112
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P03.S112 — test IVA wallet empty-cell localized envelopes

## Outcome

Three real-behavior tests added to
`src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`:

- `test_parse_spanish_decimal_empty_cell_raises_with_translated_message`: asserts
  `translated_message` is not None, not the raw key, and >10 chars.
- `test_wallet_row_from_cells_empty_period_raises_with_translated_message`: same
  shape for the period cell path.
- `test_parse_spanish_decimal_whitespace_only_cell_raises_with_translated_message`:
  confirms whitespace-only cells normalise to empty and trigger the same path.

Landed in commit `1926f5cc4`. 51 tests pass.

## Files touched

- `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`

## Verification

pytest 51 passed. `vault plan step check S112` applied.
