---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S405'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P30.S405`

Ran the affected Modelo CLI suites through the centralized runtime helper and found no remaining storage-enrollment blocker in the exercised create/calculate paths.

- Modified: plan step state
- Created: this step record

## Description

The verification batch exercises real CLI flows against isolated secure SQL runtime profiles:

- cross-modelo calculation through the CLI
- bare-numeric casilla normalisation
- Modelo compare over stored calculation revisions
- Modelo projection over stored quarterly calculation revisions

The initial batch exposed a second validation-boundary drift in `work calculate`; after the payload projection repair, the same batch passed end to end. No residual non-storage registry blocker was observed in this phase.

## Tests

Passed:

- `uv run pytest -q src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py src/aeat/entrypoints/cli/test_modelo_compare.py src/aeat/entrypoints/cli/test_modelo_projection.py`

Result:

- 10 passed in the affected Modelo CLI batch

Closing gate:

- `uv run ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_payloads.py src/aeat/entrypoints/cli/test_modelo_work_ux.py src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py src/aeat/entrypoints/cli/test_modelo_compare.py src/aeat/entrypoints/cli/test_modelo_projection.py` passed
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_modelo_work_ux.py::test_idempotent_work_create_reports_reuse src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py src/aeat/entrypoints/cli/test_modelo_compare.py src/aeat/entrypoints/cli/test_modelo_projection.py` passed with 11 tests
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed
- `uv run --no-sync vaultspec-core vault check all --feature secure-storage-production-hardening` did not isolate to the feature surface in this worktree; it reported repository-wide pre-existing structure violations plus the pre-existing multi-feature-tag audit file `2026-05-26-active-profile-storage-runtime-discovery-audit.md`
