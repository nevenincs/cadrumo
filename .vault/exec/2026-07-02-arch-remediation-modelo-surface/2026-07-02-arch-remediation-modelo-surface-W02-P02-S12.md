---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S12'
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
     The S12 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Consume the same declaration from the calculate orchestrator and delete the function-local MODELO_303_IVA_COMPENSATION_BINDING_ID import and the previous-filing exclusion shim and ## Scope

- `src/aeat/application/modelo/_calculation_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Consume the same declaration from the calculate orchestrator and delete the function-local MODELO_303_IVA_COMPENSATION_BINDING_ID import and the previous-filing exclusion shim

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Import the canonical id + set at the orchestrator module top; delete the three function-local `MODELO_303_IVA_COMPENSATION_BINDING_ID` imports.
- Return the canonical set from `_iva_compensation_previous_filing_exclusions` instead of rebuilding it.
- Drop the redundant application re-export; its one consumer reads the domain facade.

## Outcome

The calculate orchestrator consumes the same declaration as the validator; no function-local import or rebuilt exclusion set remains. Commit `e353111d8`.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
