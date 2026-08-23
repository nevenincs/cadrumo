---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:aaad54be97bfb344ee3b69d041129ee3d863ee8d8a56a48a1e0e9ae88902c147'
step_id: 'S155'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S155 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The correct composite-provenance documentation and validation language identified by formal review and ## Scope

- `src/cadrumo/domain/modelos` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# correct composite-provenance documentation and validation language identified by formal review

## Scope

- `src/cadrumo/domain/modelos`

## Description

- Replace retired provenance field names in the persisted carrier documentation.
- Make contributor-axis validation errors name the exact strict schema fields.
- Update the contract assertion for the corrected diagnostic language.

## Outcome

The persisted provenance contract and its failures now describe the same canonical resolved/contributor schema exposed by the model.

## Notes

Corrective work originated from the MEDIUM finding in the formal S135 quality review. The focused domain contract test and Ruff check passed.
