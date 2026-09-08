---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:5fa66dd1cd60fee4c4992ccd0b69db00ed4c01cb64817ce1c8a4f8a5b6f04dc5'
step_id: 'S01'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Evolve revision_carry_outcome to require RegistrySnapshotRef and compare its complete coordinate through the law-selected registry authority

## Scope

- `src/cadrumo/application/calculations/revision_carry_gate.py`

## Changes

- `M` `src/cadrumo/application/calculations/revision_carry_gate.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/calculations/tests/test_carry_gate_parity.py` -> `pass`
