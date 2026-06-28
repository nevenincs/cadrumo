---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S17'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P04.S17`

Registered the Modelo 200 Liquidación IV cuota del ejercicio casilla
`00599` under `segmento = "DP200014B"`, grounded in the official AEAT
2024 Diseño de Registros.

- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0002-liquidacion-cuota-a-ingresar.toml`

## Description

The corpus AEAT 2024 Diseño workbook sheet `DP200014B` row position 575
declares casilla `[00599]` "Liquidación IV - Cuota del ejercicio a
ingresar o a devolver - Cuota del ejercicio a ingresar o a devolver -
Estado".

As with `00592` (S16), the Liquidación occurrence of `00599` is
**already registered**: the existing fragment
`0002-liquidacion-cuota-a-ingresar.toml` (`id = "00599"`, label "Cuota
del ejercicio a ingresar o a devolver", `input_kind = "computed"`,
`formula = "modelo-200-cuota-ejercicio-a-ingresar-devolver"`,
`semantic_role = "is_resultado_ingresar_o_devolver"`) is the
`DP200014B` cuota-del-ejercicio casilla; the ECPN (`DP200011`) and
aseguradoras (`DP200042`) occurrences of `00599` are not registered.

The fragment now carries `segmento = "DP200014B"`. `id` stays the bare
`"00599"`: it is the sole registered `00599` occurrence, so the bare id
stays unique and every existing reference — most importantly the
`modelo-200-cuota-ejercicio-a-ingresar-devolver` formula that *targets*
`00599`, plus the page-011/page-014b/page-042 export bindings — resolves
unchanged. All other fields (the computed `formula` binding, `data_type`,
`legal_refs`, `source_refs`, `export_refs`) are untouched.

## Tests

`pytest` on `test_modelo_200_registry.py`, `test_referential_integrity.py`,
and `test_modelo_parity_coverage.py` — 48 passed. A `RegistryValidator`
sweep over all 26 modelos confirms every modelo still loads valid
(`fail=0`). The computed-casilla formula binding for `00599` resolves
unchanged.
