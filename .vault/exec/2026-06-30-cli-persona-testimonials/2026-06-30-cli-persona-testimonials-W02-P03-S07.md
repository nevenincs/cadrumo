---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S07'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Add real-behavior M303 first-period and prior-filing regression coverage

## Scope

- `src/aeat/application/modelo/tests/test_local_cross_period_carry.py`

## Description

- Re-run focused M303 first-period and prior-filing regression coverage.
- Confirm existing tests cover true first-period zero and established activity
  without prior filing evidence.
- Preserve the no-change finding for `test_local_cross_period_carry.py`.

## Outcome

No new test row was needed in
`src/aeat/application/modelo/tests/test_local_cross_period_carry.py`; the
existing real-behavior tests cover the risk. Final focused verification passed:
`uv run --no-sync pytest src/aeat/tests/test_parity.py
src/aeat/tests/test_locale_translation_honesty.py
src/aeat/core/i18n/tests/test_placeholder_parity.py
src/aeat/entrypoints/cli/tests/test_iva_wallet_seed_cli.py::test_cli_seed_help_text_contains_liva_art_99_legal_grounding -q`
reported 26 passed and 1 deselected.

## Notes

The broader M303 behavior tests named by the worker remained green in the worker
run; this Step closes on no-change audit plus focused verification.
