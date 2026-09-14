---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:2634feb8ec4a15ad4114933dd352127795ca86cbeec673f3ee9957a9cf6e394c'
step_id: 'S14'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# Route regulated runtime consumers through published typed authority providers and remove default raw authoring loaders

## Scope

- `src/cadrumo/domain/iva/`
- `src/cadrumo/domain/deadlines/`
- `src/cadrumo/domain/auth/apoderamientos/`
- `src/cadrumo/domain/resources/`

## Changes

- `M` `src/cadrumo/domain/resources/_repos/iva_catalogues.py`
- `M` `src/cadrumo/domain/deadlines/models.py`
- `M` `src/cadrumo/domain/deadlines/tests/test_recargo.py`
- `M` `src/cadrumo/domain/resources/_repos/tests/test_year_keyed.py`
- `M` `src/cadrumo/domain/resources/_repos/tests/test_singletons.py`
- `M` `src/cadrumo/domain/resources/tests/test_registry.py`
- `M` `src/cadrumo/domain/iva/tests/test_catalogue_period_keyed.py`
- `M` `src/cadrumo/domain/iva/tests/test_artifact_backed_grounding.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/deadlines/tests/test_recargo.py src/cadrumo/domain/auth/apoderamientos/tests/test_catalogue.py src/cadrumo/domain/resources/_repos/tests/test_year_keyed.py src/cadrumo/domain/resources/_repos/tests/test_singletons.py src/cadrumo/domain/resources/tests/test_registry.py src/cadrumo/domain/iva/tests/test_catalogue_period_keyed.py src/cadrumo/domain/iva/tests/test_artifact_backed_grounding.py --deselect src/cadrumo/domain/resources/tests/test_registry.py::test_resources_factory_composes_every_repository` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/resources/_repos/iva_catalogues.py src/cadrumo/domain/deadlines/tests/test_recargo.py src/cadrumo/domain/resources/_repos/tests/test_year_keyed.py src/cadrumo/domain/resources/_repos/tests/test_singletons.py src/cadrumo/domain/resources/tests/test_registry.py src/cadrumo/domain/iva/tests/test_catalogue_period_keyed.py src/cadrumo/domain/iva/tests/test_artifact_backed_grounding.py` -> `pass`
