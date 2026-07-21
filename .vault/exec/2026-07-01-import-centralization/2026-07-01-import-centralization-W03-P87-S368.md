---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S368'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Retarget setup_answers._m() to lazily import the public aeat.domain.deadlines.taxpayer_model bridge instead of the private aeat.domain.deadlines._models submodule

## Scope

- `src/aeat/core/setup_answers.py`
- `src/aeat/domain/deadlines/taxpayer_model.py`

## Description

- Retargeted `_m()`'s deferred `importlib.import_module` call from the private `aeat.domain.deadlines._models` submodule to the public `aeat.domain.deadlines.taxpayer_model` bridge, preserving the lazy-resolution technique that breaks the `setup_answers` <-> `domain.deadlines._profiles` circular import (the retarget only changes the target string; the cycle-break stays deferred to call time, well after both modules finish loading).
- Found `taxpayer_model.py` re-exported only 5 of the 7 symbols `_m()` resolves (`IVARegime`, `LegalEntityForm`, `FiscalResidency` were missing); widened its `__all__`/imports to the full set consumed by `setup_answers` validators, keeping it a Family-2 documented bridge.
- Verified live: `_m()` now resolves `IVARegime`/`LegalEntityForm`/`FiscalResidency`/`EntityType`/`IrpfEstimationRegime`/`IrpfSpecialRegime`/`IrpfIncomeCategory` from the new target with no import-time regression.

## Outcome

Committed alongside S364, S369, and S388 in one commit (`b6aafa707`). `src/aeat/core/tests -k setup_answers`, `src/aeat/domain/deadlines/tests` (153 tests) all green; `pytest --collect-only -q src/aeat` clean.

## Notes

None.
