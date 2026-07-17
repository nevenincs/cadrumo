---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-evidence-atomicity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Remove replay-specific fields from every payload and schema projection and ## Scope

- `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove replay-specific fields from every payload and schema projection

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`

## Description

- Verify no replay-specific fields or schema projections remain in `_modelo_aux_payloads.py`.

## Outcome

- The only replay payload was `ModeloAuditReplayResult`, removed with its `@register_schema("modelo.audit.replay")` registration in P03.S08 (the forced consumer sweep of the command removal). A grep confirms zero remaining `replay` references in `_modelo_aux_payloads.py`. No further change required for this step.

## Notes

- This step's substantive removal landed in commit `87f49c5d2f` (S08); S11 is the verification that the payload/schema surface is clean.
