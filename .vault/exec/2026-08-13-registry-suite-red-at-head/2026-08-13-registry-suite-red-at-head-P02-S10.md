---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:eed7b487d954cb2ee6918cc70bab877dd6fe383bd6888c1d5c069a7ef78b927e'
step_id: 'S10'
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
     The S10 and 2026-08-13-registry-suite-red-at-head-plan placeholders are machine-filled by
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
     The Add one regression driving a real 2024 2T negative settlement credit into the 3T return and asserting the resulting compensacion figure and ## Scope

- `src/cadrumo/application/calculations/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add one regression driving a real 2024 2T negative settlement credit into the 3T return and asserting the resulting compensacion figure

## Scope

- `src/cadrumo/application/calculations/tests/`

## Description

- Calculate and persist a real 2024 2T negative M303 settlement through the
  encrypted observation repository with its law-selected early revision stamp.
- Resolve its previous-quarter relation into the 2024 3T late revision and
  assert source identity, binding materialization, and casilla 110.
- Persist the same source with the wrong late revision stamp and prove the live
  carry gate refuses it.

## Outcome

The early 2T revision calculates `21 - 63 = -42` and exposes EUR 42 available
compensation. The late 3T revision consumes exactly that 2024/2T source and
materializes EUR 42 into its prior-period compensation binding and casilla 110.
A source falsely stamped with the late revision produces no relation value.

## Notes

- Expected arithmetic and carry direction are grounded in LIVA article 99 and
  the official early/late M303 design authorities, not read back from the engine.
- Owned module: 5 passed. Adjacent relation-consistency and mid-year-design
  tests: 5 passed, with eight pre-existing OpenPyXL warnings.
- Ruff, format, and scoped diff checks passed.
- Independent review found no blocking issue, mock, duplicated resolver, or
  tautological oracle.
- Implementation commit: `c2408f0e81`.
