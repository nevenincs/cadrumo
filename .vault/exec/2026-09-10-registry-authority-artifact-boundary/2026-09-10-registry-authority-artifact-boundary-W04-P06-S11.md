---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:16952737a1fd104c2a5ea7b50284ca4227730ea1a3255bcbfcab512aa1391a67'
step_id: 'S11'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# Implement syntax-only Modelo and TaxDomain value types and migrate enum-dependent callers

## Scope

- `src/cadrumo/core/modelo.py`
- `src/cadrumo/core/tax_domain.py`
- `src/cadrumo/entrypoints/`
- `src/cadrumo/application/`
- `src/cadrumo/domain/`

## Changes

- `M` `src/cadrumo/core/modelo.py`
- `M` `src/cadrumo/core/tax_domain.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_filed_observation_storage_context.py`
- `M` `dev/registry/tests/test_modelo_applicability.py`
- `verify:` `rg -n "\bModelo\.[A-Z][A-Z0-9_]*\b|\bTaxDomain\.[A-Z][A-Z0-9_]*\b" src dev -g "*.py"` -> `pass`
- `verify:` `uv run pytest -q -n0 -m "" src/cadrumo/core/tests/test_fact_backed_bootstrap_validation.py dev/registry/tests/test_tax_domain.py dev/registry/tests/test_modelo_specific_embed_scan.py` -> `pass`
- `verify:` `uv run pytest -q -n0 -m "" dev/registry/tests/test_modelo_applicability.py` -> `pass`
