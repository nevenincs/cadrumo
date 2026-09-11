---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:3e463dd53f51b21751a60ec8ba7f8c1aabca76dff377d9fafdddb7cb8d4f8eeb'
step_id: 'S04'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

# Remove runtime compiler cache and raw loader exposure

## Scope

- `src/cadrumo/domain/calculations/registry/loader.py`

## Changes

- `D` `src/cadrumo/domain/calculations/registry/loader.py`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `A` `dev/registry/compiler/`
- `M` `dev/registry/pipeline/authority_publication.py`
- `M` `dev/registry/pipeline/cli.py`
- `M` `src/cadrumo/domain/iva/_grounding.py`
- `M` `src/cadrumo/domain/iva/catalogue.py`
- `A` `src/cadrumo/domain/iva/tests/test_artifact_backed_grounding.py`
- `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py dev/registry/tests/test_authority_publication.py src/cadrumo/domain/iva/tests/test_artifact_backed_grounding.py -q` -> `pass`
