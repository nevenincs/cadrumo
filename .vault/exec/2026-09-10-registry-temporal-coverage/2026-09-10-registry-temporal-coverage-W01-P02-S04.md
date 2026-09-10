---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:bc3e9f439c8f1afa2d576dbc857d45cdf0bc6d5e406265700ef1d0903a34a8c1'
step_id: 'S04'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Exercise accepted, presumptive-exception, and authored-refusal legal-reference cases through the real validator

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py`
- `verify:` `uv run --no-sync pytest -o addopts='' src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py::test_attested_and_reviewed_presumptive_legal_corpus_remain_accepted src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py::test_reviewed_presumptive_exception_set_exactly_covers_committed_legal_corpus src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py::test_authored_or_unreviewed_presumptive_normative_corpus_is_refused -q` -> `pass`
