---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b6cb8dc6afa9c156e8ef61381f3cbc7ef2ff7578ca56518788436880f680d9ea'
step_id: 'S52'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Rewire treaty and authorization consumers

## Scope

- `src/cadrumo/domain/calculations/registry/_formula_runtime_irnr.py and src/cadrumo/entrypoints/cli/config_payloads.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_formula_runtime_irnr.py`
- `M` `src/cadrumo/domain/calculations/registry/formula_runtime.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_formula_runtime_m210.py`
- `M` `src/cadrumo/entrypoints/cli/config_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/config/tests/test_apoderado_scopes_payload.py`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/_formula_runtime_irnr.py src/cadrumo/domain/calculations/registry/formula_runtime.py src/cadrumo/entrypoints/cli/config_payloads.py src/cadrumo/entrypoints/cli/config/tests/test_apoderado_scopes_payload.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/calculations/registry/_formula_runtime_irnr.py src/cadrumo/domain/calculations/registry/formula_runtime.py src/cadrumo/entrypoints/cli/config_payloads.py src/cadrumo/entrypoints/cli/config/tests/test_apoderado_scopes_payload.py` -> `pass`

## Notes

`uv run --no-sync pytest -q -n 0 src/cadrumo/domain/calculations/registry/tests/test_formula_runtime_m210.py::test_irnr_resolve_tipo_gravamen_retains_selected_treaty_fact_provenance src/cadrumo/entrypoints/cli/config/tests/test_apoderado_scopes_payload.py` did not return within the focused 30-second runner window while concurrent suite workers were active.
