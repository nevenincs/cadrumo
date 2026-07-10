---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S09'
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
     The S09 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Add non-filing communication validation rules for rejected filing, deadline, live-read, and portal surfaces and ## Scope

- `src/aeat/domain/calculations/registry` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add non-filing communication validation rules for rejected filing, deadline, live-read, and portal surfaces

## Scope

- `src/aeat/domain/calculations/registry`

## Description

- Reconcile the missing per-step exec record for checked row `P02.S09`.
- Use the existing aggregate evidence record `2026-05-14-cli-workflow-redesign-modelo-145-reopen-p02-s07-s10-exec.md` as the implementation authority.
- Confirm the aggregate record covers the non-filing communication validator rules that reject filing, deadline, live-read, portal, and filing-schedule surfaces for Modelo 145.

## Outcome

- No new source work was performed in this reconciliation pass.
- `P02.S09` now has a dedicated per-step exec record, satisfying the plan-closure record-shape requirement while preserving the original aggregate evidence.
- The original aggregate record reports green registry-schema, source-catalogue, ruff, and type-check verification for the P02 communication vocabulary landing.

## Notes

- This record exists to clear a `vault plan status` missing-exec alert for a row already checked before per-step records were enforced.
