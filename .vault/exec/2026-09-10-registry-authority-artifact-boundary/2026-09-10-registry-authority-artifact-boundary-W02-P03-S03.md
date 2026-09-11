---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:9805e681135e7c0de9d0659014ddd2209dbecace83a6220820b0c408bf56b48f'
step_id: 'S03'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

# Replace bundled source compilation with artifact loading

## Scope

- `src/cadrumo/domain/calculations/registry/authority.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `D` `src/cadrumo/domain/calculations/registry/loader.py`
- `A` `dev/registry/compiler/authority.py`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py` -> `pass`
