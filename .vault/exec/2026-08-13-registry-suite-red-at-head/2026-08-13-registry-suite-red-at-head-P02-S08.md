---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:c0052f05df91ade006b960ff773f11a1bab4c73d03303ba65ca7e060bb28d650'
step_id: 'S08'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-suite-red-at-head with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-08-13-registry-suite-red-at-head-plan placeholders are machine-filled by
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
     The Supply the renta-2024 maternidad profile binding to the registry-layer M100 harnesses from the production derivation authority, never a hand-picked literal and ## Scope

- `src/cadrumo/domain/calculations/registry/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Supply the renta-2024 maternidad profile binding to the registry-layer M100 harnesses from the production derivation authority, never a hand-picked literal

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Add one M100 2024 test-support mapping that derives the empty-descendant
  maternity binding through the public domain authority.
- Replace all 13 inline binding literals across the 11 registry harness modules.
- Add an AST census that prevents the raw binding key from returning outside the
  shared helper.

## Outcome

Every M100 registry harness now obtains the nuisance maternity binding from one
shared 2024-specific helper. The helper calls
`compute_deduccion_maternidad_0611` and converts its integer zero at the strict
registry-scenario boundary to `Decimal`; it does not duplicate maternity
arithmetic or import the application layer.

## Notes

- Eleven M100 modules, the domain maternity authority tests, and the AST census:
  141 passed in 64.29 seconds.
- Ruff, format, and scoped diff checks passed.
- The raw binding key now occurs exactly once in registry tests, inside the
  shared helper.
- Main implementation and census landed concurrently in `bbabb9a26a`; the
  strict Decimal boundary correction landed in `60f615724c`.
