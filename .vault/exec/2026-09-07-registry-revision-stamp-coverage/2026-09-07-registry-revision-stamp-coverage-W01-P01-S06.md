---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f2090e1858334f670698df195d99ee84caf6e471413db44537a3dd9426a67b43'
step_id: 'S06'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Re-confirm IVA annual-partition source coordinates through revision_carry_outcome

## Scope

- `src/cadrumo/application/calculations/iva_compensation_annual_partition.py`

## Changes

- `M` `src/cadrumo/application/calculations/iva_compensation_annual_partition.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/calculations/tests/test_carry_gate_parity.py` -> `pass`
