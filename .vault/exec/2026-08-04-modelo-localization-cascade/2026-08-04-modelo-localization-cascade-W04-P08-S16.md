---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:4e63371535d3632569c061b2a4a13e43b2b0acf11b0624d77e67388b0e0f832c'
step_id: 'S16'
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
     The S16 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Add real-behavior repeatability, temporary-output, and no-live-write tests for the dry-run boundary and ## Scope

- `tests/cadrumo/domain/calculations/registry` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add real-behavior repeatability, temporary-output, and no-live-write tests for the dry-run boundary

## Scope

- `tests/cadrumo/domain/calculations/registry`

## Description

- Reconcile temporary-output and no-live-write tests with the final no-tool boundary.
- Retain real-behavior evidence for new Modelo enrollment and locale contracts.
- Record the exact bounded test results without introducing fakes or compatibility shims.

## Outcome

Resolved by the real-behavior gates: the new Modelo scaffold suite recorded
18 passing tests, and the focused locale honesty/allow-identical/status suite
recorded 15 passing tests. The historical bounded Modelo/loader/export/CLI
campaign recorded 424 passing tests; no fake or monkeypatched migration path
was introduced.

## Notes

The temporary-output tests themselves were deleted with the disposable app;
the remaining production tests prove the final no-legacy boundary.
