---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:32cbe05404d6cb5d3d4a82b3da39c1d0f4fec85a7736bb07175a58c6984ce7ea'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# `registry-revision-stamp-coverage` `W01.P01` summary

## Changes

- `M` `src/cadrumo/application/calculations/bienes_inversion_regularizacion.py`
- `M` `src/cadrumo/application/calculations/binding_prefill.py`
- `M` `src/cadrumo/application/calculations/cross_period_clean_state.py`
- `M` `src/cadrumo/application/calculations/iva_compensation_annual_partition.py`
- `M` `src/cadrumo/application/calculations/prorrata_regularizacion.py`
- `M` `src/cadrumo/application/calculations/relation_prefill.py`
- `M` `src/cadrumo/application/calculations/revision_carry_gate.py`
- `M` `src/cadrumo/application/calculations/tests/test_carry_gate_parity.py`
- `M` `src/cadrumo/application/modelo/iva_wallet_gate.py`
- `M` `src/cadrumo/application/prorrata_register/seed.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/calculations/tests/test_carry_gate_parity.py src/cadrumo/application/prorrata_register/tests/test_seed.py` -> `pass`
