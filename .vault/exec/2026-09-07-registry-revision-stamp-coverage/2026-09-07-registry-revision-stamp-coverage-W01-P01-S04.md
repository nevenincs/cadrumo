---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:76c611cdfa5e7a9e7080eae3cb1ee8e6783b0dc5c5e2b89e98c7964cd8462bfa'
step_id: 'S04'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Map full-coordinate gate refusal onto REGISTRY_REVISION_DIVERGENCE in cross-period clean state

## Scope

- `src/cadrumo/application/calculations/cross_period_clean_state.py`

## Changes

- `M` `src/cadrumo/application/calculations/cross_period_clean_state.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/calculations/tests/test_carry_gate_parity.py` -> `pass`
