---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:97ca48c61dd3d67e11d00ba523c8c87deee13beadc0b0d8e607047a6099819bd'
step_id: 'S12'
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
     The S12 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Compare old and proposed resolved values across every supported model, revision, casilla, field, and locale and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Compare old and proposed resolved values across every supported model, revision, casilla, field, and locale

## Scope

- `dev/registry/migration`

## Description

- Reconcile old-versus-proposed parity evidence with the landed shared-catalogue runtime.
- Record the bounded verification boundary for loader, Modelo, export, CLI, and locale behavior.
- Keep concurrent-worktree limitations explicit instead of claiming an unscoped full-suite result.

## Outcome

Resolved by the historical bounded campaign of 424 passing Modelo/loader/
export/CLI tests plus the current source-aware locale gates: 15 focused tests
passed with `-n 0`, the locale audit was healthy, and the equality pass
returned `UNRESOLVED []`.

## Notes

The 424-test result predates later concurrent worktree changes and is retained
as bounded evidence, not as a claim that the full repository suite was rerun.
