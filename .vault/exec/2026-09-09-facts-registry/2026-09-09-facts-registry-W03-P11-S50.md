---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:2a2f63c71e615b739f221c0d74a7cf3f80ff6f6c1fa73cbba64270744de161fe'
step_id: 'S50'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Rewire Art 20 Art 52 DT12 and SAL calculations

## Scope

- `src/cadrumo/application/modelo and src/cadrumo/domain/modelos`

## Changes

- `M` `src/cadrumo/application/modelo/_art20_advisory.py`
- `M` `src/cadrumo/application/modelo/_art52_advisory.py`
- `M` `src/cadrumo/application/modelo/calculate_input.py`
- `M` `src/cadrumo/application/modelo/tests/test_actions.py`
- `M` `src/cadrumo/application/modelo/verification_actions.py`
- `M` `src/cadrumo/domain/modelos/dt12_reduccion.py`
- `M` `src/cadrumo/domain/modelos/modelo_fact_context.py`
- `M` `src/cadrumo/domain/modelos/sal_reserva_especial.py`
- `M` `src/cadrumo/domain/modelos/tests/test_dt12_window.py`
- `M` `src/cadrumo/domain/modelos/tests/test_fiscal_reductions.py`
- `A` `src/cadrumo/domain/modelos/tests/test_modelo_fact_context.py`
- `verify:` `uv run --no-sync pytest -q -n0 <S50 domain, Art 20/52 advisory, and DT12 window nodeids>` -> pass
- `verify:` `uv run --no-sync ruff check <S50 source and test paths>` -> pass
