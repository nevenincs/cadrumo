---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:452f905817f5502f735c53c00b4964eb92735b4d41cd8d2265b9d6c283f6ece5'
step_id: 'S09'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

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
