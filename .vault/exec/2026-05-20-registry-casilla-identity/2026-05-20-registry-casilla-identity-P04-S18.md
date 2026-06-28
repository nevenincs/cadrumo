---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S18'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P04.S18`

Registered the Modelo 200 Liquidación IV cuota diferencial casilla
`00611` under `segmento = "DP200014B"` as a new casilla fragment,
grounded in the official AEAT 2024 Diseño de Registros.

- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00611-cuota-diferencial.toml`

## Description

The corpus AEAT 2024 Diseño workbook sheet `DP200014B` row position 711
declares casilla `[00611]` "Liquidación IV - Pagos fraccionados/Cuota
diferencial - Cuota diferencial - Estado" (`Tipo = N`, money). The bare
number `00611` was already taken by the Estado-de-cambios-patrimonio-neto
(III) ECPN casilla (`id = "00611"`, "Otras operaciones con socios o
propietarios - Resultado del ejercicio", `segmento` unset).

The new fragment declares the Liquidación occurrence with the
segment-qualified `id = "DP200014B:00611"`, `number = "00611"`, and
`segmento = "DP200014B"`; its identity is `(DP200014B, 00611)`, distinct
from the ECPN `(None, 00611)`.

`data_type = "money"` per the Diseño `N` type. `legal_refs` carry the
M200 cuota-chain legal block plus Ley 27/2014 LIS art. 124
(autoliquidación / cuota diferencial), all catalogued in `is.toml` — the
plan brief's `art-125` is not present in the legal catalogue, so the
catalogued autoliquidación article `art-124` is used, consistent with
grounding every reference in the registry's legal authority.
`source_refs` reuse the catalogued M200 ids.
`semantic_role = "is_liquidacion_iv_cuota_diferencial"` is declared
`intentional_singleton` with a reason. `export_refs` is empty: P04
scopes the export re-point to `00562` only (S19).

## Tests

`pytest` on `test_modelo_200_registry.py`, `test_referential_integrity.py`,
and `test_modelo_parity_coverage.py` — 48 passed. A `RegistryValidator`
sweep over all 26 modelos confirms every modelo still loads valid
(`fail=0`). The ECPN `00611` casilla is untouched.
