---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:10f2a42eee09af377425860ef2dbf7a8e92da6192a536ddfac32adfed7a0ac66'
step_id: 'S03'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Pass the observation RegistrySnapshotRef through relation prefill without reconstructing coordinate fields

## Scope

- `src/cadrumo/application/calculations/relation_prefill.py`

## Changes

- `M` `src/cadrumo/application/calculations/relation_prefill.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/calculations/tests/test_carry_gate_parity.py` -> `pass`
