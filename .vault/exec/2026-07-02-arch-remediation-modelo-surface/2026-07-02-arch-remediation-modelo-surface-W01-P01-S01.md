---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Add a typed unresolved-outcome member to the calculation engine result carrying casilla id, reason, and grounding context, riding beside the Decimal value channels rather than widening them

## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py`

## Description

- Add `RegistryCalculationUnresolvedOutcome` with casilla id, reason, formula id, operand refs, legal refs, source refs, and string context.
- Add `RegistryUnresolvedOutcomeReason` for the M210 baseline-deferred and convenio-missing cases.
- Add `RegistryCalculationResult.unresolved_outcomes` beside `observations`; leave `values` and `entries` derived from Decimal observations only.

## Outcome

The engine result now has a typed unresolved-outcome side channel without widening Decimal value channels.

## Notes

Focused verification for W1 passed: `32 passed in 22.49s` in `_scratch-codex/w1_m210_convenio_pytest.log`.
