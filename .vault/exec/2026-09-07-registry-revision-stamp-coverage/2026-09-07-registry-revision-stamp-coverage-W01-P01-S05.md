---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:13b4b55e6afe1895286da690bd997743b625f985fdd51a144cbb457fa4983c90'
step_id: 'S05'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Re-confirm prorrata regularizacion source coordinates through revision_carry_outcome

## Scope

- `src/cadrumo/application/calculations/prorrata_regularizacion.py`

## Changes

- `M` `src/cadrumo/application/calculations/prorrata_regularizacion.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/calculations/tests/test_carry_gate_parity.py` -> `pass`
