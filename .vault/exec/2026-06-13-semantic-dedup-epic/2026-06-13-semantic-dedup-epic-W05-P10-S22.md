---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S22'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C1-3 Replace the inline euro-cent quantize outlier with round_to_cents

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Re-verified at HEAD: the money-export encoder re-derived euro-cent rounding
  inline (`abs(amount).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)`) while the
  sibling fichero encoder `_record_spec` already used canonical `round_to_cents`.
- Imported `round_to_cents` from `core.money` and replaced the inline quantize.
- Dropped the now-unused `ROUND_HALF_UP` import; retained `_MONEY_QUANT` for the
  constraint-divergent comparison quantize at the verify site (no rounding mode).

## Outcome

Committed as `ae94c2ffe`, tagged `relocation:round_to_cents`. Ruff clean; 41
filing export tests green. Behaviour-identical (CENT=0.01, ROUND_HALF_UP).

## Notes

The comparison-equality quantize at the verify site was intentionally left
untouched (Pass-2 audit constraint-divergent: context-default rounding).
