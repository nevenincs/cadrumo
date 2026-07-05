---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S22'
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
     The S22 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Add service-level errors and logs using communication vocabulary only and ## Scope

- `src/aeat/application/modelo` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add service-level errors and logs using communication vocabulary only

## Scope

- `src/aeat/application/modelo`

## Description

- Add typed Modelo 145 communication service errors for lookup, validation, export rendering, and state-transition refusals.
- Register the new service errors with stable error codes while leaving CLI suggestions unset until the thin CLI phase exists.
- Export the typed error classes through the public modelo facade.
- Add structured service logs for successful create/export/delivery/completion operations, idempotent retries, lookup failures, and validation or transition refusals.
- Cover error registration, catch compatibility, structured error context, and communication-only log messages with real secure-runtime tests.

## Outcome

- Focused ruff gate passed for the Modelo 145 communication implementation, facade, error-registry shard, and service tests.
- Focused pytest gate passed for the Modelo 145 communication error/log, event, transition, export, validation, create, and service-contract tests: 31 passed.
- Focused core error-registry pytest gate passed: 13 passed.
- Required review found no `P04.S22` issues and was recorded in the feature audit.
- Plan status reports 22 completed steps, next open step `P05.S23`, and no missing exec records.
- Plan check and feature check both passed cleanly after the feature index rebuild.

## Notes

- No blockers, skipped work, or scaffolds.
