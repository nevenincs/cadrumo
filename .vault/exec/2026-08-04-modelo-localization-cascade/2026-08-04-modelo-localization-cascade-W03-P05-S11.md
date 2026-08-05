---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:5f532fe78a6180fc93d8c5247417a5668357fe6c4169b7e15a7f59b63244c6d8'
step_id: 'S11'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-localization-cascade with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Implement the staged root-catalogue resolver with locale fallback rules isolated from production and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the staged root-catalogue resolver with locale fallback rules isolated from production

## Scope

- `dev/registry/migration`

## Description

- Verify the production canonical Modelo identity functions for model, revision, occurrence, continuidad, and alias keys.
- Verify the production fallback order across requested locale and Spanish source.
- Reconcile the historical isolated-resolver row with the live resolver contract.

## Outcome

Resolved in production by `src/cadrumo/domain/calculations/registry/_modelo_localization.py:19-119` and loader enrollment in
`src/cadrumo/domain/calculations/registry/_loader.py:250-329`. The runtime
resolves the requested locale through ordered exact-to-continuidad identities,
then retries the chain in Spanish; no second staged resolver exists.

## Notes

The historical migration resolver was deleted with the disposable application;
this is a reconciliation to the accepted production contract.
