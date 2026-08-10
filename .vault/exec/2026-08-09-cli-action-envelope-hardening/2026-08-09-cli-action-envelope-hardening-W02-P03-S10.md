---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:90aa4126a37bcd97b8dcc9eda0499661e4430e48d7e59be146ec944bf26d1919'
step_id: 'S10'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-action-envelope-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-08-09-cli-action-envelope-hardening-plan placeholders are machine-filled by
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
     The Prove strict action-model validation, catalogue uniqueness, binding sufficiency, and terminal outcomes and ## Scope

- `src/cadrumo/application/operator_actions/tests/test_models.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove strict action-model validation, catalogue uniqueness, binding sufficiency, and terminal outcomes

## Scope

- `src/cadrumo/application/operator_actions/tests/test_models.py`

## Description

- Exercise strict action and catalogue identifiers through production Pydantic constructors.
- Exercise duplicate evidence, binding, missing-name, catalogue-action, and catalogue-argument rejection paths.
- Exercise resolved and missing action arguments, all closed no-recovery outcomes, action/no-recovery XOR, and invalid conditionality branches.
- Assert deterministic serialization and that all seven current declarations exclude external, database, and raw-command authority.
- Close the independent S10 review findings with direct production-constructor regressions only; defer live result/input-schema resolution to S14.

## Outcome

The application-only contract suite now protects the complete S10 model and
catalogue invariants. The runtime tests neither import entrypoint schema
builders nor implement a test-side resolver. No production code changed.

## Verification

`uv run --no-sync pytest src/cadrumo/application/operator_actions/tests -n0`

`39 passed in 0.90s`

`uv run --no-sync ruff check src/cadrumo/application/operator_actions/tests/test_models.py src/cadrumo/application/operator_actions/tests/test_catalogue.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/application/operator_actions/tests/test_models.py src/cadrumo/application/operator_actions/tests/test_catalogue.py`

`0 errors, 0 warnings, 0 notes`

## Notes

The S10 audit initially found missing direct regressions for verdict duplicate
members, closed-outcome consistency, and identifier fields. Those findings
were closed before this record. S14 remains the owner of live command/input
schema resolution and catalogue-to-runtime binding resolution.
