---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:b57cdfbccc69a725d0a3325ab6abffd9ed4dc08f13f40a2fcaa1214e295f1c9d'
step_id: 'S13'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Define the component/codec contract and public typed query, generation-pin and profile create/decode context signatures, with representative fake behavior for the consumer lanes

## Scope

- `src/cadrumo/domain/calculations/registry/authority_artifact.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/authority_fakes.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_authority_component_contract.py`
- `verify:` `uv run --no-sync pytest -n 0 -m unit src/cadrumo/domain/calculations/registry/tests/test_authority_component_contract.py -q` -> `pass`
- `verify:` `uv run --no-sync ruff check ...` -> `pass`
- `verify:` `uv run --no-sync ty check ...` -> `pass`
