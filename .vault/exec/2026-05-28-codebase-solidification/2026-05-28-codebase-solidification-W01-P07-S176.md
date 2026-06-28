---
tags:
  - "#exec"
  - "#codebase-solidification"
step_id: S176
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P07.S176 — real-behaviour tests for `DEFAULT_CURRENCY`

## Outcome

6 real-behaviour tests appended to `src/aeat/core/test_external_constants.py`:

- `test_default_currency_value` — asserts `DEFAULT_CURRENCY == "EUR"` (ISO 4217)
- `test_default_currency_is_final_str` — asserts `isinstance(DEFAULT_CURRENCY, str)`
- `test_ledger_transaction_command_reads_currency_from_external_constants` —
  verifies `_models` module imports `DEFAULT_CURRENCY` (identity check) and that
  `ManualLedgerTransactionCommand`'s JSON schema carries the constant value as default
- `test_currency_service_reads_native_eur_from_external_constants` —
  verifies `_service` module imports `DEFAULT_CURRENCY`
- `test_aggregation_predicates_read_currency_from_external_constants` —
  verifies `_currency_predicates` imports `DEFAULT_CURRENCY`
- `test_config_financial_base_currency_default_equals_default_currency` —
  verifies `Settings().financial_base_currency == DEFAULT_CURRENCY`

## Test results

```
38 passed in 2.80s
```

All 38 tests in `test_external_constants.py` pass including the 6 new ones.

## Anti-tautology rationale

Tests assert against the known ISO spec value `"EUR"` (derived from the
ISO 4217 standard, not copied from the constant's own definition). Module
identity checks (`mod.DEFAULT_CURRENCY is DEFAULT_CURRENCY`) verify each
migrated consumer actually imports the canonical symbol rather than carrying
a local literal that could silently diverge.

## Commit

`99e2b8070` — `core(external_constants): centralise DEFAULT_CURRENCY constant (S175/S176)`
