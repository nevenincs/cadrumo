---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b320649afea6677721944ce0222925757c192ca7f9d43ce146a115c22072aac4'
step_id: 'S33'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Assert every committed legal catalogue entry satisfies its provenance-bound filing-authority contract

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py`
- `verify:` `uv run --no-sync pytest -o addopts='' src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py::test_every_committed_normative_legal_reference_satisfies_provenance_contract -q` -> pass
