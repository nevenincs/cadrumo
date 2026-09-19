---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-10'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6572a1e8e88b42be27373efec971ffac505a875dfb420f3bb9834905148d2733'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---

# `ledger-input-localization` ledger

## Changes

- `S01` `T` `add _DECIMAL_RE constant and is_finite() guard`
- `S01` `T` `export both helpers via __all__`
- `S01` `T` `src/aeat/entrypoints/cli/_common.py`
- `S02` `T` `use the signed variant for --amount until C1 (ledger-amount-direction) lands`
- `S02` `T` `src/aeat/entrypoints/cli/_ledger.py`
- `S03` `T` `gate all four invoice_date parameters (lines 180`
- `S03` `T` `281`
- `S03` `T` `398`
- `S03` `T` `503) through _parse_iso_date`
- `S03` `T` `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`
- `S04` `T` `gate both invoice_date parameters (lines 98`
- `S04` `T` `197) through _parse_iso_date`
- `S04` `T` `src/aeat/entrypoints/cli/_ledger_evidence_cli.py`
- `S05` `T` `src/aeat/entrypoints/cli/_ledger_inventory_cli.py`
- `S06` `T` `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`
- `S07` `T` `src/aeat/entrypoints/cli/_ledger_ratios_cli.py`
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
- `S13` `T` `src/aeat/entrypoints/cli/tests/test_common_decimal_parser.py`
- `S14` `T` `assert acceptance of 2026-01-15`
- `S14` `T` `src/aeat/entrypoints/cli/tests/test_common_date_parser.py`
- `S15` `T` `invoke _parse_iso_date with a bad date and assert all four locales carry %{label} and %{raw} in the rendered message`
- `S15` `T` `src/aeat/entrypoints/cli/tests/test_localised_parser_errors.py`
- `S16` `T` `verify no pre-existing test regression`
- `S16` `T` `src/aeat/entrypoints/cli/`
