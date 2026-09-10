---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:5424c43792700542af18db19b2da69a499f3bd5c68cd80427efc9b2c5d80b6d2'
step_id: 'S06'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Verify validated-authority publication preserves the provenance-bound legal authority contract

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_authority.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_authority.py`
- `verify:` `uv run --no-sync pytest -o addopts='' src/cadrumo/domain/calculations/registry/tests/test_authority.py::test_authority_exposes_validated_legal_corpus_provenance -q` -> `pass`
