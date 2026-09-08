---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:cfe84eb76168fdb1c7b1b780e2e23dfad6907a62375502ba4814b06e1dae1f2e'
step_id: 'S02'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Pass the observation RegistrySnapshotRef through binding prefill without reconstructing coordinate fields

## Scope

- `src/cadrumo/application/calculations/binding_prefill.py`

## Changes

- `M` `src/cadrumo/application/calculations/binding_prefill.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/calculations/tests/test_carry_gate_parity.py` -> `pass`
