---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:16afcecb7af05b1d7ecf96a6b8dfcc9da50cd2a6d8354b5ae856468a669ed72d'
step_id: 'S195'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in test_catalogue_verification.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py`

## Changes

- `D` `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_catalogues.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_coverage.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_record_design.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_renta.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S195.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s195-execution-self-review-audit.md`

## Notes

- Historical implementation is immutable commit `aef15d15109b62177713bd78d3edede5f03b2b5c`: its exact manifest is one deletion plus the four additions above. Agent-supplied raw physical counts are old `1554`; new `124`, `545`, `435`, and `494` in manifest order. No threshold or baseline change is claimed.
- Executor-reported, not independently replayed and without a retained terminal transcript: `uv run --no-sync python -m compileall -q src/cadrumo/domain/calculations/registry/tests` passed; `ruff check` and `ruff format --check` on the four new files passed; `pytest --collect-only -q` on those four files reported `30 collected in 1.34s`.
- Root's independent AST review found `37` top-level definitions before and after, with missing, extra, and duplicate sets empty; `rg` found no direct imports from the deleted old module. No full pytest was run because four pytest PIDs were active. This record makes no global size result claim.
