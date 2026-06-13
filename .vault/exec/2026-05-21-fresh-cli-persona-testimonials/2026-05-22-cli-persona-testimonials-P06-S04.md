---
tags: ["#exec", "#cli-persona-testimonials"]
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'P06.S04'
related:
  - '[[2026-05-21-cli-persona-testimonials-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
---

# P06.S04 - Modelo 200 casilla 00592 registry drift

Closed task #514 as resolved/no defect after local verification.

## Grounding

The cross-campaign hardening audit records BIND-7 as resolved: Modelo
200 casilla `DP200014B:00592` is present in the committed registry and
the cross-dependency calculation test references a real casilla.

The registry TOML confirms `DP200014B:00592` in
`src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0001-liquidacion-cuota-liquida.toml`
with bare number `00592`, segmento `DP200014B`, section
`liquidacion/cuota_liquida`, legal refs, and source refs
`aeat-dr-200-2025` plus `aeat-modelo-200-manual-2024`.

The formula graph uses the segment-qualified id in
`records/formulas.toml` for `modelo-200-cuota-ejercicio-a-ingresar-devolver`.
This preserves the registry-casilla identity decision that Modelo 200
five-digit numbers are segment-scoped, not globally unique.

## Verification

`uv run --no-sync ruff check src\aeat\domain\calculations\registry\test_modelo_200_registry.py src\aeat\domain\calculations\registry\test_cross_dependency_calculations.py` passed.

`uv run --no-sync pytest -x src\aeat\domain\calculations\registry\test_modelo_200_registry.py::test_modelo_200_liquidacion_cuota_chain_casillas_resolve_under_their_segmento src\aeat\domain\calculations\registry\test_cross_dependency_calculations.py -q` passed with 23 tests.
