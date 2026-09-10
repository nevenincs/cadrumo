---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:464e673d914ebaddde82d862dfb47a93d97fcea5f68f6187e260658308e00421'
step_id: 'S01'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

# Introduce the typed Sociedades annual-manual coverage catalogue and validate its exact-year dispositions

## Scope

- `src/cadrumo/_data/registry/aeat/legal`

## Changes
- `A` `src/cadrumo/_data/registry/aeat/legal/sociedades-annual-manual-coverage.toml`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/_loader_internals.py`
- `M` `src/cadrumo/domain/calculations/registry/loader.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_supported_filing_years_catalogue.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_authority.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_coverage.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_applicability_registry_cutover.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_loader_directory_mode.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_loader_cache_isolation.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_mutable_tree_fingerprint_invalidation.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_read_parameter_authority_invalidation.py`
- `M` `src/cadrumo/application/modelo/tests/test_binding_readiness.py`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_supported_filing_years_catalogue.py -q --disable-warnings --maxfail=1` -> `pass`
