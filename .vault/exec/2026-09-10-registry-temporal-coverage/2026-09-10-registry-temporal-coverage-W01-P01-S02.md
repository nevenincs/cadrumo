---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:285c5fba0a90f4422239ab7e8dc0549672d5386d60e2d727c8a74e19d59435ed'
step_id: 'S02'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Prove attested, presumptive, authored, and out-of-scope provenance classifications with isolated corpus fixtures

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance.py`
- `verify:` `uv run --no-sync pytest -o addopts='' src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance.py -q` -> `pass`
