---
tags:
  - '#plan'
  - '#ledger-input-localization'
date: '2026-06-10'
modified: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-ledger-input-localization-adr]]'
  - '[[2026-06-10-ledger-input-localization-research]]'
---


# `ledger-input-localization` `Ledger CLI canonical input parsing and localised rejection` plan

### Phase `P01` - Shared amount/date validator consolidation

Consolidate all six duplicated _parse_decimal/_parse_required_decimal copies and the unguarded invoice_date pass-throughs into single canonical helpers in _common.py, enforcing the decimal regex plus is_finite() guard and routing every date-typed CLI input through _parse_iso_date.

- [x] `P01.S01` - Author canonical parse_decimal_amount (signed and non-negative variants) and verify _parse_iso_date is already present in _common.py; `add _DECIMAL_RE constant and is_finite() guard; export both helpers via __all__; `src/aeat/entrypoints/cli/_common.py`.
- [x] `P01.S02` - Replace the local _parse_decimal/_parse_required_decimal with imports of parse_decimal_amount from _common.py; `use the signed variant for --amount until C1 (ledger-amount-direction) lands; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `P01.S03` - Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py; `gate all four invoice_date parameters (lines 180, 281, 398, 503) through _parse_iso_date; `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`.
- [x] `P01.S04` - Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py; `gate both invoice_date parameters (lines 98, 197) through _parse_iso_date; `src/aeat/entrypoints/cli/_ledger_evidence_cli.py`.
- [x] `P01.S05` - Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py; `src/aeat/entrypoints/cli/_ledger_inventory_cli.py`.
- [x] `P01.S06` - Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `P01.S07` - Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py; `src/aeat/entrypoints/cli/_ledger_ratios_cli.py`.
- [x] `P01.S08` - Run pytest --collect-only -q to verify zero collection errors across all six migrated modules; `confirm no surviving local _parse_decimal/_parse_required_decimal definition remains in any of the six migrated files; `src/aeat/entrypoints/cli/`.

### Phase `P02` - Locale catalogue updates

Add the missing interpolation tokens to invalid_iso_date in EN/CA/HU, append the expected-format hint to invalid_decimal in all four locales, and add format examples to the amount and invoice-date help strings — all via the aeat.locales CLI to preserve four-locale parity.

- [x] `P02.S09` - Add %{label} and %{raw} interpolations to cli.common.errors.invalid_iso_date for en, ca, and hu locales using python -m aeat.locales set so all four locales carry the same interpolation tokens as the existing es string; `src/aeat/locales/`.
- [x] `P02.S10` - Append expected-format hint to cli.ledger.errors.invalid_decimal in all four locales (en, es, ca, hu) via python -m aeat.locales set; `hint must name the accepted form: dot decimal separator, no thousands grouping, e.g. 1234.56; `src/aeat/locales/`.
- [x] `P02.S11` - Add format example to cli.ledger.add.amount_help in all four locales via python -m aeat.locales set, modelled on the correct_amount_help pattern; `add format example to cli.app.ledger.payable_invoice.invoice_date_help, cli.app.ledger.collectible_invoice.invoice_date_help, and cli.app.ledger.evidence.invoice_date_help in all four locales; `src/aeat/locales/`.
- [x] `P02.S12` - Run python -m aeat.locales scaffold --check and python -m aeat.locales audit to confirm zero drift and all four locales remain in key parity with no honesty-ratchet violations; `src/aeat/locales/`.

### Phase `P03` - Real-behavior boundary tests

Write real-behavior tests covering decimal accept/reject cases and ISO date accept/reject cases, plus a localised error-payload test asserting all four locales carry label, raw value, and expected-format hint — no mocks, no skips, no tautology.

- [x] `P03.S13` - Write real-behavior unit tests for parse_decimal_amount: assert refusal of 1.000, 1.234,56, NaN, Infinity, -Infinity, 1e3 (InvalidOperation or ValueError); `assert acceptance of 1000, 1234.56, 0; assert signed variant accepts -50.00 and non-negative variant rejects -50.00; `src/aeat/entrypoints/cli/tests/test_common_decimal_parser.py`.
- [x] `P03.S14` - Write real-behavior unit tests for _parse_iso_date applied to invoice_date inputs: assert refusal of 15/01/2026, 01-15-2026, 2026/01/15 with ValueError; `assert acceptance of 2026-01-15; `src/aeat/entrypoints/cli/tests/test_common_date_parser.py`.
- [x] `P03.S15` - Write real-behavior localised error-payload tests: invoke parse_decimal_amount with a bad input in each of en/es/ca/hu locale contexts and assert each error payload carries label, raw value, and expected-format hint; `invoke _parse_iso_date with a bad date and assert all four locales carry %{label} and %{raw} in the rendered message; `src/aeat/entrypoints/cli/tests/test_localised_parser_errors.py`.
- [x] `P03.S16` - Run the full test suite for the entrypoints/cli surface (uv run --no-sync pytest src/aeat/entrypoints/cli/ -x -q) and confirm all new tests pass with no skips or xfail; `verify no pre-existing test regression; `src/aeat/entrypoints/cli/`.

## Description

This plan executes cluster C3 of the ledger localisation campaign: closing the silent
amount-misparse defect (research F1), the non-finite admission gap (F2), and the
unguarded `invoice_date` pass-through (F5) by consolidating the six duplicated
`_parse_decimal`/`_parse_required_decimal` helpers (F4) into a single canonical helper
in `_common.py` with a decimal-regex + `is_finite()` guard, and by routing all
date-typed CLI inputs through the existing safe `_parse_iso_date` gate. The locale
catalogue is updated via `python -m aeat.locales set` (never by hand-editing `.yml`)
to make refusals instructive: `invalid_iso_date` gains `%{label}` and `%{raw}` tokens
in EN/CA/HU, `invalid_decimal` gains an expected-format hint in all four locales, and
the amount and invoice-date help strings gain a format example. Real-behavior boundary
tests assert every accept/reject case and confirm the localised error payload carries
label, raw value, and expected-format hint in all four locales. Grounded in
`2026-06-10-ledger-input-localization-adr` (accepted) and
`2026-06-10-ledger-input-localization-research`.

**Sequencing note - C1 dependency:** The ledger `--amount` field must use the signed
variant of the decimal regex (`^-?\d+(\.\d+)?$`) until the concurrent C1
(`ledger-amount-direction`) feature lands and makes ledger amounts a non-negative
magnitude. P01.S02 uses the signed variant; a follow-up Step tightens to the
non-negative form (`^\d+(\.\d+)?$`) after C1 lands. If C1 lands first, P01.S02 must
adopt the non-negative form immediately. C4 (invoice command) consumes the shared
validators from `_common.py` and must not re-derive its own copies.

## Parallelization

P01 must complete before P03 (tests target the helpers authored in P01). P02 (locale
catalogue) is independent of P01 and P03 and may run in parallel with P01, but P03's
localised-error-payload tests (P03.S15) require both P01 and P02 to have landed.

Within P01, S01 must land first (authors the shared helper). S02 through S07 are
independent of each other once S01 is done and may be executed in parallel by separate
agents. S08 (collection-clean verification sweep) must run after S02-S07 are all done.

Within P02, S09, S10, and S11 are independent locale-catalogue operations and may run
in parallel (each touches distinct locale keys). S12 (drift gate) must follow S09-S11.

Within P03, S13 and S14 are independent unit test files and may be authored in parallel.
S15 (localised error-payload tests) requires both S09-S11 (locale keys updated) and S01
(helpers in place); it depends on both P01.S01 and P02.S09-S11. S16 (suite gate) must
be the final step in P03, running after S13-S15.

## Verification

The plan is complete when all of the following hold:

- Every Step in P01, P02, and P03 is closed (`[x]`).
- `rg "_parse_decimal|_parse_required_decimal" src/aeat/entrypoints/cli/` finds zero
  surviving definitions outside `_common.py` (only the canonical helper remains).
- `python -m aeat.locales scaffold --check` exits clean (zero drift).
- `python -m aeat.locales audit` reports no honesty-ratchet violations and all four
  locales are in key parity for `cli.common.errors.invalid_iso_date`,
  `cli.ledger.errors.invalid_decimal`, and all four help string keys.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/ -x -q` is green with no skips and
  no xfail markers on any new test.
- The decimal parser rejects `1.000`, `1.234,56`, `NaN`, `Infinity`, `-Infinity`,
  `1e3` and accepts `1000`, `1234.56`, `0` — verified by P03.S13 passing.
- The date parser rejects `15/01/2026`, `01-15-2026`, `2026/01/15` and accepts
  `2026-01-15` — verified by P03.S14 passing.
- The localised error payload in all four locales carries label, raw value, and
  expected-format hint — verified by P03.S15 passing.
- The sequencing note is respected: `--amount` uses the signed variant until C1 lands;
  the `--amount` call site is flagged with a comment citing the follow-up tighten
  step.
