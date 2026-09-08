---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:d3b0146c83f87ebafe74aea81d339371353b14110479f335a16b5697f69b1ecc'
step_id: 'S10'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Prove all carry callers share full-coordinate matching and fail closed on divergence

## Scope

- `src/cadrumo/application/calculations/tests/test_carry_gate_parity.py`

## Changes

- `M` `src/cadrumo/application/calculations/tests/test_carry_gate_parity.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/calculations/tests/test_carry_gate_parity.py` -> `pass`
