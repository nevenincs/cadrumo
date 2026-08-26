---
generated: true
tags:
  - '#index'
  - '#ledger-input-localization'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:7f243a306c685b0f30676b130fed13802a6d60ba726aad3e39d2c8778da1c7fe'
related:
  - '[[2026-06-10-ledger-input-localization-adr]]'
  - '[[2026-06-10-ledger-input-localization-plan]]'
  - '[[2026-06-10-ledger-input-localization-research]]'
  - '[[2026-06-12-ledger-input-localization-audit]]'
---

# `ledger-input-localization` feature index

Auto-generated index of all documents tagged with `#ledger-input-localization`.

## Documents

### adr

- `2026-06-10-ledger-input-localization-adr` - `ledger-input-localization` adr: `Enforce canonical amount and date input with localised actionable rejection` | (**status:** `accepted`)

### audit

- `2026-06-12-ledger-input-localization-audit` - `ledger-input-localization` audit: `Ledger input-localization C3 execution closure`

### exec

- `2026-06-10-ledger-input-localization-P01-S01` - Author canonical parse_decimal_amount (signed and non-negative variants) and verify _parse_iso_date is already present in _common.py
- `2026-06-10-ledger-input-localization-P01-S02` - Replace the local _parse_decimal/_parse_required_decimal with imports of parse_decimal_amount from _common.py
- `2026-06-10-ledger-input-localization-P01-S03` - Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py
- `2026-06-10-ledger-input-localization-P01-S04` - Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py
- `2026-06-10-ledger-input-localization-P01-S05` - Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py
- `2026-06-10-ledger-input-localization-P01-S06` - Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py
- `2026-06-10-ledger-input-localization-P01-S07` - Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py
- `2026-06-10-ledger-input-localization-P01-S08` - Run pytest --collect-only -q to verify zero collection errors across all six migrated modules
- `2026-06-10-ledger-input-localization-P02-S09` - Add %{label} and %{raw} interpolations to cli.common.errors.invalid_iso_date for en, ca, and hu locales using python -m aeat.locales set so all four locales carry the same interpolation tokens as the existing es string
- `2026-06-10-ledger-input-localization-P02-S10` - Append expected-format hint to cli.ledger.errors.invalid_decimal in all four locales (en, es, ca, hu) via python -m aeat.locales set
- `2026-06-10-ledger-input-localization-P02-S11` - Add format example to cli.ledger.add.amount_help in all four locales via python -m aeat.locales set, modelled on the correct_amount_help pattern
- `2026-06-10-ledger-input-localization-P02-S12` - Run python -m aeat.locales scaffold --check and python -m aeat.locales audit to confirm zero drift and all four locales remain in key parity with no honesty-ratchet violations
- `2026-06-10-ledger-input-localization-P03-S13` - Write real-behavior unit tests for parse_decimal_amount: assert refusal of 1.000, 1.234,56, NaN, Infinity, -Infinity, 1e3 (InvalidOperation or ValueError)
- `2026-06-10-ledger-input-localization-P03-S14` - Write real-behavior unit tests for _parse_iso_date applied to invoice_date inputs: assert refusal of 15/01/2026, 01-15-2026, 2026/01/15 with ValueError
- `2026-06-10-ledger-input-localization-P03-S15` - Write real-behavior localised error-payload tests: invoke parse_decimal_amount with a bad input in each of en/es/ca/hu locale contexts and assert each error payload carries label, raw value, and expected-format hint
- `2026-06-10-ledger-input-localization-P03-S16` - Run the full test suite for the entrypoints/cli surface (uv run --no-sync pytest src/aeat/entrypoints/cli/ -x -q) and confirm all new tests pass with no skips or xfail

### plan

- `2026-06-10-ledger-input-localization-plan` - `ledger-input-localization` `Ledger CLI canonical input parsing and localised rejection` plan

### research

- `2026-06-10-ledger-input-localization-research` - `ledger-input-localization` research: `Ledger CLI amount and date input format parsing`
