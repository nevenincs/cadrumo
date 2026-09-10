---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:f1c4efc075488d40889e74b784f57e3f92483c2c17b2e8ddc7e3597d1338e262'
step_id: 'S01'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Define the derived normative-corpus provenance classifier and its file-resolution contract

## Scope

- `src/cadrumo/domain/calculations/registry/corpus_provenance.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/corpus_provenance.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/corpus_provenance.py src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance.py` -> `pass`
