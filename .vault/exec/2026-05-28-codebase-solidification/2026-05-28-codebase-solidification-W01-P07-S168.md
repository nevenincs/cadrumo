---
step_id: S168
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S168 — IVA-regime enum surface tests

## Outcome

Created `src/aeat/application/modelo/test_actions.py` with four real-behavior tests:

- `test_iva_ledger_exempt_regimes_contains_enum_members` — asserts every element
  of `_IVA_LEDGER_EXEMPT_REGIMES` is an `IVARegime` instance, not a bare string.
- `test_iva_ledger_exempt_regimes_includes_simplificado` — pins SIMPLIFICADO in the set.
- `test_iva_ledger_exempt_regimes_excludes_general` — anti-tautology: GENERAL must
  not be exempt.
- `test_iva_regime_enum_covers_all_wizard_choice_values` — cross-cuts `_IVA_REGIME_CHOICE_VALUES`
  against `IVARegime` members to prevent drift.

All 4 tests pass. No mocks, no xfail, no tautology.

## Pytest result

282 passed across `test_actions.py` + `wizard/` + `test_schema.py`.

## Commit

`8381a5f9a`
