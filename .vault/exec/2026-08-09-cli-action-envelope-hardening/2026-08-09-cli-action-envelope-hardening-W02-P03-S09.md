---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:6f4bdd9c5b76fb43c5cec14bfa964f0e8b23dd715a0e09daa1c3f7c1430a2da5'
step_id: 'S09'
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
     The S09 and 2026-08-09-cli-action-envelope-hardening-plan placeholders are machine-filled by
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
     The Define the canonical action catalogue without duplicating application guard predicates and ## Scope

- `src/cadrumo/application/operator_actions/_catalogue.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Define the canonical action catalogue without duplicating application guard predicates

## Scope

- `src/cadrumo/application/operator_actions/_catalogue.py`

## Description

- Add an immutable canonical action catalogue under `src/cadrumo/application/operator_actions/_catalogue.py`.
- Declare stable action identifiers, canonical result-schema command keys, and non-value-bearing argument source specifications.
- Ground every declared target argument against the live `build_verb_input_schemas` projection while deferring live sufficiency and command resolution to S14.
- Add direct catalogue contract tests under `src/cadrumo/application/operator_actions/tests/test_catalogue.py`.

## Outcome

The catalogue deterministically resolves seven initial profile, overview, and workflow action identities to canonical schema keys. It rejects duplicate action identities and duplicate argument names, requires an exact evidence identity only for evidence-derived sources, and fails closed on unknown action identities. Catalogue declarations contain no runtime values, resolution status, applicability predicate, rendered CLI path, or localized prose.

The explicit `CADRUMO_DATABASE_URL` recovery string is intentionally not represented as an action: it is an external environment change rather than an operator-callable command. Its no-recovery treatment remains owned by the root-policy migration.

## Verification

- `uv run --no-sync pytest -q src/cadrumo/application/operator_actions/tests/test_catalogue.py` — `6 passed in 3.21s`.
- `uv run --no-sync pytest -q src/cadrumo/application/operator_actions/tests/test_models.py src/cadrumo/application/operator_actions/tests/test_catalogue.py` — `19 passed in 3.44s`.
- `uv run --no-sync ruff check src/cadrumo/application/operator_actions/_catalogue.py src/cadrumo/application/operator_actions/tests/test_catalogue.py` — `All checks passed!`.
- `uv run --no-sync ruff format --check src/cadrumo/application/operator_actions/_catalogue.py src/cadrumo/application/operator_actions/tests/test_catalogue.py` — `2 files already formatted`.
- `uv run --no-sync basedpyright src/cadrumo/application/operator_actions/_catalogue.py src/cadrumo/application/operator_actions/tests/test_catalogue.py` — `0 errors, 0 warnings, 0 notes`.
- `uv run --no-sync python -c "from cadrumo.entrypoints.mcp._input_schema import build_verb_input_schemas; ..."` confirmed each declared argument name occurs on its current target input surface.

## Notes

The repository-wide import-hygiene gate ran and reported five unrelated existing or concurrent private-import regressions outside this Step's owned files. This Step adds no cross-package private import. The package facade remains concurrent S08 work and was deliberately not modified here.
