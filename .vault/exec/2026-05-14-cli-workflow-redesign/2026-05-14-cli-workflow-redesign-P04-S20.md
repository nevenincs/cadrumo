---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S20'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-workflow-redesign with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Add local delivered-to-payer and completed communication state transitions and ## Scope

- `src/aeat/application/modelo` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add local delivered-to-payer and completed communication state transitions

## Scope

- `src/aeat/application/modelo`

## Description

- Add local `delivered_to_payer` and `locally_completed` states to the Modelo 145 communication record.
- Persist delivery and completion timestamps with model-level ordering invariants.
- Add idempotent backend transitions for delivery retries, completion retries, and delivery calls after completion.
- Refuse local completion until delivery has occurred, and refuse delivery for records that do not pass registry-backed validation.
- Cover the transition path with real secure-runtime tests.

## Outcome

- Focused ruff gate passed for the Modelo 145 communication implementation, facade, and service tests.
- Focused pytest gate passed for the Modelo 145 communication create, validate, export, transition, and service-contract tests: 23 passed.
- Required review found no `P04.S20` issues and was recorded in the feature audit.
- Plan status now reports 20 completed steps, next open step `P04.S21`, and no missing exec records.
- Plan check and feature check both passed cleanly after the feature index rebuild.

## Notes

- Bucket-event emission remains deliberately untouched for `P04.S21`.
