---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:496305b98a092a227cbfc85fae1d5d0cf5380ea1635bd2c567eb8cdc55bee2c0'
step_id: 'S07'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Re-confirm bienes-inversion source coordinates through revision_carry_outcome

## Scope

- `src/cadrumo/application/calculations/bienes_inversion_regularizacion.py`

## Changes

- `M` `src/cadrumo/application/calculations/bienes_inversion_regularizacion.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/calculations/tests/test_carry_gate_parity.py` -> `pass`
