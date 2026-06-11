---
tags:
  - '#exec'
  - '#period-grammar-standardisation'
date: '2026-06-11'
step_id: 'S08'
related:
  - '[[2026-06-11-period-grammar-standardisation-plan]]'
---

# W01.P03.S08 Combined Parser Regex Removal

Scope: `src/aeat/domain/period.py`.

## Description

- Remove the combined year-plus-period regexes from `parse_canonical_period`.
- Keep only the raw AEAT quarterly `nT` plus `ejercicio` adapter still needed by live declaration ingestion.
- Rewrite the module and function docstrings so they no longer describe combined strings as canonical backend storage.
- Add domain tests proving raw declaration tokens resolve with `ejercicio` and combined forms refuse.

## Outcome

`parse_canonical_period` no longer accepts combined strings such as quarterly, dashed quarterly, month, annual shorthand, bare year, or pago-fraccionado year-token forms.

## Notes

The plan CLI saved this step as closed, then failed in its cache-invalidation hook with a missing workspace context. The plan file was inspected afterward and the checkbox mutation was correct.
