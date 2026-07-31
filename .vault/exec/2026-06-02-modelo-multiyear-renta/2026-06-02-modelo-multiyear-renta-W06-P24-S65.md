---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:6c42885107177fd7b1bd733814396f892bee7fb2cd0dc85563fd51f482ef0ab3'
step_id: 'S65'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# build the Patrimonio wealth-base engine with the 60% limite conjunto x-ref to M100 per A5-714 (Ley 19/1991) (vaultspec-high-executor)

## Scope

- `src/aeat/domain/calculations/engines/_modelo_714.py`

## Description

- Add Modelo 714 art.31 limite-conjunto calculation coverage through the registry formula runtime.
- Introduce same-year Modelo 100 relation inputs for the IRPF base and cuota components used by Ley 19/1991 art.31.
- Compute the art.31 chain through `patrimonio.cuota-integra`, `patrimonio.irpf-bases-imponibles`, `patrimonio.limite-conjunto`, `patrimonio.suma-cuotas-limite`, `patrimonio.exceso-limite-conjunto`, `patrimonio.reduccion-limite-80`, and `patrimonio.total-cuota-integra`.

## Outcome

- Satisfied in the current registry-formula architecture rather than by adding a standalone `engines/_modelo_714.py` module.
- The supported revision is bounded to the checked-in 2021-2025 same-year Modelo 100 source revisions.
- Verified by `uv run --no-sync pytest -q -n 0 src/aeat/application/calculations/tests/test_modelo_714_patrimonio_joint_limit_calculation.py src/aeat/domain/calculations/registry/tests/test_modelo_714_registry.py`, which passed 26 tests.

## Notes

- The evidence is relation-backed calculation wiring, not an independent AEAT worked-example replay.
- Art.31 exclusion inputs that are not exposed by Modelo 100 remain explicit Modelo 714 inputs.
