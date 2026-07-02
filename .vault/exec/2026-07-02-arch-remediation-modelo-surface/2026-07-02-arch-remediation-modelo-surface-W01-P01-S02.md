---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S02'
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
     The S02 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Emit the typed unresolved-outcome for an unresolvable M210 IRNR rate instead of a reserved negative Decimal, preserving CasillaObservation provenance through the typed outcome and ## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
