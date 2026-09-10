---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:549943b2d32783c18e5f21723b07a0cd513054001aa24a0da0e6eb64f2a81803'
step_id: 'S03'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Bind derived provenance to legal-reference evidence-tier validation and correct the stale corpus-tier coverage statement

## Scope

- `src/cadrumo/domain/calculations/registry/legal.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/legal.py`
- `verify:` `uv run --no-sync pytest -o addopts='' src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py::test_committed_registry_legal_and_construct_references_validate_through_loader -q` -> `pass`
