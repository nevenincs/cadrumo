---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-10'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:7c75c8250ec50241c0c4fb8fb0367556b0ee8326cee3d30f6d95f8079a14acdd'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---

# `ledger-input-localization` ledger

## Changes

- `S01` `T` `add _DECIMAL_RE constant and is_finite() guard`
- `S01` `T` `export both helpers via __all__`
- `S02` `T` `use the signed variant for --amount until C1 (ledger-amount-direction) lands`
- `S03` `T` `gate all four invoice_date parameters (lines 180`
- `S03` `T` `281`
- `S03` `T` `398`
- `S03` `T` `503) through _parse_iso_date`
- `S04` `T` `gate both invoice_date parameters (lines 98`
- `S04` `T` `197) through _parse_iso_date`
- `S05` `T`
- `S06` `T`
- `S07` `T`
- `S08` `T` `confirm no surviving local _parse_decimal/_parse_required_decimal definition remains in any of the six migrated files`
- `S08` `T` `src/aeat/entrypoints/cli/`
- `S09` `T` `src/aeat/locales/`
- `S10` `T` `hint must name the accepted form: dot decimal separator`
- `S10` `T` `no thousands grouping`
- `S10` `T` `e.g. 1234.56`
- `S10` `T` `src/aeat/locales/`
- `S11` `T` `add format example to cli.app.ledger.payable_invoice.invoice_date_help`
- `S11` `T` `cli.app.ledger.collectible_invoice.invoice_date_help`
- `S11` `T` `and cli.app.ledger.evidence.invoice_date_help in all four locales`
- `S11` `T` `src/aeat/locales/`
- `S12` `T` `src/aeat/locales/`
- `S13` `T` `assert acceptance of 1000`
- `S13` `T` `1234.56`
- `S13` `T` `0`
- `S13` `T` `assert signed variant accepts -50.00 and non-negative variant rejects -50.00`
- `S14` `T` `assert acceptance of 2026-01-15`
- `S15` `T` `invoke _parse_iso_date with a bad date and assert all four locales carry %{label} and %{raw} in the rendered message`
- `S16` `T` `verify no pre-existing test regression`
- `S16` `T` `src/aeat/entrypoints/cli/`
