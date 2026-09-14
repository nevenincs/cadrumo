---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:d7acbd032fdba387de8b9c8ae843ba7b7d182a0b5ab7d5f869f47183cdf24844'
step_id: 'S20'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Implement accounted LRU retention and concurrent-load coalescing with oversize, failure, cycle and lease-retirement behavior

## Scope

- `src/cadrumo/domain/calculations/registry/authority_cache.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/authority_cache.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_authority_cache.py`
- `verify:` `uv run --no-sync pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_authority_cache.py -q` -> `pass`
