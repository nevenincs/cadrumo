---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S112'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S112 Modelo Natural-Key Cross-Period Coverage Reconciliation

Scope: `W02.P05.S112` reconciles modelo natural-key CLI verification coverage with the cross-period clean-state contract.

## Description

- Add the residual plan row after the S54 CLI verification lane exposed stale M130 expectations.
- Move the green no-ID calculate/verify/export natural-key workflow to Modelo 111, which does not require upstream clean-state proof.
- Add explicit Modelo 130 natural-key verification coverage proving clean-state refusal without previous-filing evidence.
- Preserve the CLI abstraction contract: both success and refusal paths are addressed by modelo/year/period rather than copied internal IDs.

## Outcome

Natural-key CLI tests now align with the current domain contract. The generic no-ID workflow still proves successful create/calculate/verify/export by natural key, while M130 coverage proves the operator receives the cross-period dependency refusal and next action instead of a false verified-complete result.

## Notes

Verification passed for `src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py` and `src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py` with 23 integration tests passing. Plan validation still reports only the known `PLAN022` non-monotonic identifier warning.
