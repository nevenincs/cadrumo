---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:353af895f9e223f453e36ec925a144b7562c5c8c61c2f2e19e1ed1c2f5cbc52a'
step_id: 'S01'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Define immutable artifact roles, identity, derivation, disposition, and diagnostic records keyed by bundled relative path

## Scope

- `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/artifact_catalogue.py` -> pass
- `verify:` `uv run ruff format --check src/cadrumo/domain/calculations/registry/artifact_catalogue.py` -> pass
- `verify:` `uv run python -m py_compile src/cadrumo/domain/calculations/registry/artifact_catalogue.py` -> pass
