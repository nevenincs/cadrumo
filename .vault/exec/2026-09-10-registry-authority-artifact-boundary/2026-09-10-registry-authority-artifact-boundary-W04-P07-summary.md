---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:46ed27f9d0e0fa4672f13afa7a12195d198e0176c3965bd8732da14bc137f5c6'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# `registry-authority-artifact-boundary` `W04.P07` summary

## Changes

- `M` `dev/registry/compiler/runtime_catalogues.py`
- `M` `dev/registry/compiler/tests/test_iva_runtime_catalogues.py`
- `M` `dev/registry/compiler/validator.py`
- `M` `src/cadrumo/application/filing/draft_construction.py`
- `M` `src/cadrumo/application/filing/runtime.py`
- `M` `src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py`
- `M` `src/cadrumo/application/filing/tests/test_runtime.py`
- `M` `src/cadrumo/application/filing/tests/test_unsupported_filing_year_refusal.py`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/runtime_catalogues.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py`
- `M` `src/cadrumo/domain/deadlines/models.py`
- `M` `src/cadrumo/domain/deadlines/tests/test_recargo.py`
- `M` `src/cadrumo/domain/iva/tests/test_artifact_backed_grounding.py`
- `M` `src/cadrumo/domain/iva/tests/test_catalogue_period_keyed.py`
- `M` `src/cadrumo/domain/resources/_repos/iva_catalogues.py`
- `M` `src/cadrumo/domain/resources/_repos/tests/test_singletons.py`
- `M` `src/cadrumo/domain/resources/_repos/tests/test_year_keyed.py`
- `M` `src/cadrumo/domain/resources/tests/test_registry.py`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/application/filing/tests/test_unsupported_filing_year_refusal.py src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py src/cadrumo/application/filing/tests/test_runtime.py::test_runtime_provider_exposes_no_application_layer_cache` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/authority.py src/cadrumo/application/filing/runtime.py src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py src/cadrumo/application/filing/tests/test_unsupported_filing_year_refusal.py src/cadrumo/application/filing/tests/test_runtime.py src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py` -> `pass`
