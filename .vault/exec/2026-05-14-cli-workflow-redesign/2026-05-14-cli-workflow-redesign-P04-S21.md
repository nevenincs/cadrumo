---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S21'
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
     The S21 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Emit communication-specific bucket events without filing or filed-state terminology and ## Scope

- `src/aeat/application/modelo` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit communication-specific bucket events without filing or filed-state terminology

## Scope

- `src/aeat/application/modelo`

## Description

- Add communication-specific Modelo 145 bucket event kinds for create, export, delivery to payer, and local completion.
- Add a `communication_record` bucket event object type for local payer communication records.
- Emit bucket events from the Modelo 145 communication service after successful create, export, delivery, and local completion operations.
- Keep idempotent create and transition retry paths quiet by returning the existing record before emitting another mutation event.
- Cover emitted event kinds, payload metadata, forbidden filing-shaped vocabulary, retry behavior, and invalid-delivery blocking with real secure-runtime tests.

## Outcome

- Focused ruff gate passed for the bucket event taxonomy, Modelo 145 communication implementation, and communication service tests.
- Focused pytest gate passed for the Modelo 145 communication event, transition, export, validation, create, and service-contract tests: 26 passed.
- Required review found no `P04.S21` issues and was recorded in the feature audit.
- Plan status reports 21 completed steps, next open step `P04.S22`, and no missing exec records.
- Plan check and feature check both passed cleanly after the feature index rebuild.

## Notes

- No blockers, skipped work, or scaffolds.
