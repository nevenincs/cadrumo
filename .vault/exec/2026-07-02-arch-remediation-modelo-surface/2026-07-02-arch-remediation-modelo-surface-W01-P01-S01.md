---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S01'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-modelo-surface with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Add a typed unresolved-outcome member to the calculation engine result carrying casilla id, reason, and grounding context, riding beside the Decimal value channels rather than widening them and ## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
