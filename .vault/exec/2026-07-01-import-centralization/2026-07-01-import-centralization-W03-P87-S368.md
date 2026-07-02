---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S368'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace import-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S368 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Retarget setup_answers._m() to lazily import the public aeat.domain.deadlines.taxpayer_model bridge instead of the private aeat.domain.deadlines._models submodule and ## Scope

- `src/aeat/core/setup_answers.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
