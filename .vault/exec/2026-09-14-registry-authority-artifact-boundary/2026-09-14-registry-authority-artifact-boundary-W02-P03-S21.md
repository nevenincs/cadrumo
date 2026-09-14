---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:1af1a15b9862b7910b542d2be1b06f0b891f1f3be294f40b8675b8e336151d6f'
step_id: 'S21'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Expose generation-pinned typed access and replace eager public graph fields while preserving incarnation and stale-capture semantics

## Scope

- `src/cadrumo/domain/calculations/registry/authority.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_authority_database.py`
- `verify:` `checkpoint A focused source/enrollment and component selection` -> `pass`
