---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:2a8273aa0de4aa4e5c1d1ba79a88430923d4e0a0a59b6fcf864f6d9bc652c4c0'
step_id: 'S24'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# Replace whole-catalogue validation and snapshot construction in governed_fact_scope.py and snapshot.py with declared same-generation dependencies; refuse recursive bundled loading

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `M` `src/cadrumo/domain/calculations/registry/governed_fact_scope.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/temporal.py`
- `M` `dev/registry/compiler/authority_database.py`
- `M` `dev/registry/tests/test_authority_database.py`
- `verify:` `uv run --no-sync pytest -n 0 dev/registry/tests/test_authority_database.py::test_revision_context_selects_directory_before_one_complete_revision -q` -> `pass`
- `verify:` `uv run --no-sync ruff check ... && uv run --no-sync ty check ...` -> `pass`
