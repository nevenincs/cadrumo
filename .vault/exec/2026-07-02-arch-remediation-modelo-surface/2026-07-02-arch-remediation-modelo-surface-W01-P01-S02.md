---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Emit the typed unresolved-outcome for an unresolvable M210 IRNR rate instead of a reserved negative Decimal, preserving CasillaObservation provenance through the typed outcome

## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py`

## Description

- Replace unresolvable M210 rate returns with `_UnresolvedFormulaOutcomeError`.
- Materialize the caught outcome in `RegistryCalculationResult.unresolved_outcomes`.
- Mark the target casilla unresolved so downstream formula dependencies remain omitted rather than receiving a placeholder value.

## Outcome

Unresolvable M210 IRNR rates are reported as typed outcomes with formula provenance and context.

## Notes

Focused verification for W1 passed: `32 passed in 22.49s` in `_scratch-codex/w1_m210_convenio_pytest.log`.
