---
step_id: S100
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-P26-S99]]"
---

# cross-domain-continuity W05.P26.S100 — 7 regression tests for iva-wallet balance

## Deliverables

- `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py` (NEW): 7 tests using `isolated_runtime_profile` (real encrypted SQLite, real `IvaCompensationHistoryRepository`).

## Test coverage

- `test_balance_totals_remaining_after_fifo_applications`: Q1-2024 +1200, Q2-2024 -300, Q1-2025 -500 → `total_balance=400`, `next_expiry_year=2028` at `as_of_year=2028`.
- `test_next_expiry_year_is_earliest_active_lot_plus_four`: Two lots; expired one excluded; active 2023 lot → `next_expiry_year=2027`.
- `test_next_expiry_year_none_when_no_active_lots_with_balance`: All lots EXPIRED → `None`.
- `test_empty_history_returns_zero_balance`: Empty repo → zero balance, `lot_count=0`, `next_expiry_year=None`.
- `test_cli_balance_verb_emits_expected_keys`: `--format json` output validates payload fields.
- `test_cli_balance_verb_text_output_lines`: Text-mode output contains tab-delimited metric lines.
- `test_carry_forward_lot_rejects_unbalanced_amounts_anti_tautology`: Mutated `applied_amount + remaining_amount != generated_amount` triggers `model_validator` `ValueError` — proves the roundtrip contract is not tautological.

## Results

All 7 tests pass: `7 passed in 3.04s`.

## Commit

`c9fb9f1f8` — W05.P26.S100: 7 regression tests for iva-wallet balance (real adapters + anti-tautology)
