---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Delete the _rewrite_m210_sentinels rewrite shim and consume the typed unresolved-outcome member to emit the BLOCKING verification finding

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Delete `_rewrite_m210_sentinels` from verification actions.
- Add `_m210_unresolved_outcome_findings` to consume typed M210 outcomes.
- Convert the convenio verification tests from sentinel observations to `RegistryCalculationUnresolvedOutcome`.

## Outcome

The verification layer now emits M210 BLOCKING findings from typed unresolved outcomes.

## Notes

Focused verification for W1 passed: `32 passed in 22.49s` in `_scratch-codex/w1_m210_convenio_pytest.log`.
