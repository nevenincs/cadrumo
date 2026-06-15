---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-15'
step_id: 'S18'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# Promote canonical normalize_decimal_separators and redirect the eight inline European-decimal separator sites

## Scope

- `src/aeat/core/decimal/_coerce.py`

## Description

- Add canonical `normalize_decimal_separators(text, *, strip_thousands)` to
  `core/decimal/_coerce.py` and export it from `core.decimal`.
- Redirect the eight inline separator sites — `sede/_iva_compensation_wallet_parsing.py`
  (full Spanish), `sede/_censo.py` (×2 comma-only), `registry/_export_parse.py`
  (×2 comma-only), `registry/_renta_web_open_oracle.py` (full Spanish, conditional),
  `inbound/pdf/_label_regex.py` (×2: full-Spanish and comma-only branches) — to the
  helper, preserving each site's own validation, symbol-stripping, locale-detection
  and error handling.

## Outcome

The repeated comma/dot separator idiom is single-sourced; the pdf
comma-as-thousands-strip branch (not the kernel) is left as-is. Helper
unit-verified (`"1.234,56"`->`"1234.56"`); 1080 parsing tests pass; ruff and
collect-only clean. Landed as commit `95cdf474e`.

## Notes

Reclassified from the earlier ruled-out/marginal disposition after the directive
to land every behavior-preserving consolidation. F1 (tax-id) and F2 (fichero
`_formats`) remain genuinely not-actionable without a behavior change.
