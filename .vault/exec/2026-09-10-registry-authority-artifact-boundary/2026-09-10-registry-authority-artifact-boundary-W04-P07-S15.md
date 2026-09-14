---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:7df2488d73e885b41ad645d4ae4054694b449b1485566ac098bfa30e53c43147'
step_id: 'S15'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# Centralize supported filing-year admission and runtime cache identity on ValidatedRegistryAuthority

## Scope

- `src/cadrumo/domain/calculations/registry/authority.py`
- `src/cadrumo/application/filing/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py`
- `M` `src/cadrumo/application/filing/draft_construction.py`
- `M` `src/cadrumo/application/filing/runtime.py`
- `M` `src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py`
- `M` `src/cadrumo/application/filing/tests/test_unsupported_filing_year_refusal.py`
- `M` `src/cadrumo/application/filing/tests/test_runtime.py`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/application/filing/tests/test_unsupported_filing_year_refusal.py src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py src/cadrumo/application/filing/tests/test_runtime.py::test_runtime_provider_exposes_no_application_layer_cache` -> `pass`
- `verify:` `uv run --no-sync python -m py_compile src/cadrumo/domain/calculations/registry/authority.py src/cadrumo/application/filing/draft_construction.py src/cadrumo/application/filing/runtime.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/authority.py src/cadrumo/application/filing/runtime.py src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py src/cadrumo/application/filing/tests/test_unsupported_filing_year_refusal.py src/cadrumo/application/filing/tests/test_runtime.py src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py` -> `pass`

## Notes

A later focused pytest rerun was blocked during import by the concurrently authored untracked `src/cadrumo/domain/calculations/registry/keyed_families.py`, before S15 code or tests executed. The earlier focused S15 run passed 11 tests; the concurrent file was left untouched.
