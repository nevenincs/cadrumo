---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:bdc01d0eab6d23980eec984c1ce8ef6e025f7db722e7cb67fb0f820d27897342'
step_id: 'S47'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-completeness-closure with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S47 and 2026-08-24-registry-completeness-closure-plan placeholders are machine-filled by
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
     The Add revision filing-year and period scope to census destinations and require exact scoped source mapping with Modelo 100 and 193 cross-satisfaction regressions. and ## Scope

- `src/cadrumo/application/registry/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add revision filing-year and period scope to census destinations and require exact scoped source mapping with Modelo 100 and 193 cross-satisfaction regressions.

## Scope

- `src/cadrumo/application/registry/`

## Description

- Require revision id, filing year, and typed period on every census destination.
- Validate destinations against canonical law-selected revisions and exact source mappings.
- Scope closure composition and live-proof identities to the declared revision.
- Migrate the five existing destination families to published revision selectors.
- Add Modelo 100 and Modelo 193 cross-revision regressions.

## Outcome

Ruff passed. Source coverage passed 7/7, exact destination validation passed 6/6,
live proof passed 6/6, and the changed integration identity test passed 1/1.

## Notes

The broader capability discovery test is blocked by concurrent uncommitted CLI
command-spec work outside this Step at `_modelo_work_command_specs.py:208`.

