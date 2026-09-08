---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:b7f769a0cb45eae755ec1bbad60c0261e849e1dc5ebd1e74d8f345875616413f'
step_id: 'S09'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Re-confirm IVA wallet source coordinates through revision_carry_outcome

## Scope

- `src/cadrumo/application/modelo/iva_wallet_gate.py`

## Changes

- `M` `src/cadrumo/application/modelo/iva_wallet_gate.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/calculations/tests/test_carry_gate_parity.py` -> `pass`
