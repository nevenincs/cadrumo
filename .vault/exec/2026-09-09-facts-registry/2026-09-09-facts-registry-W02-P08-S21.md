---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:cda1aa3f5767c1ff3bb4f598eb9e23c2ff43fdcd893fc575771222b019b7d4f1'
step_id: 'S21'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Adapt global legal parameters without duplicating authority

## Scope

- `src/cadrumo/_data/registry/aeat/legal`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/schema.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_legal_parameter_provider.py`
- `verify:` `uv run python -m pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_legal_parameter_provider.py src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_resolution.py -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/facts/legal_parameters.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/schema.py src/cadrumo/domain/calculations/registry/facts/tests/test_legal_parameter_provider.py` -> `pass`

## Notes

- Focused basedpyright is blocked by the concurrent modelo-projection adapter's `_compile_no_direct_facts` parameter-name mismatch in `facts/providers.py`; S21-owned files have no diagnostics.
