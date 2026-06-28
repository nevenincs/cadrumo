---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S16'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P04.S16`

Registered the Modelo 200 Liquidación IV cuota líquida casilla `00592`
under `segmento = "DP200014B"`, grounded in the official AEAT 2024 Diseño
de Registros.

- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0001-liquidacion-cuota-liquida.toml`

## Description

The corpus AEAT 2024 Diseño workbook sheet `DP200014B` row position 251
declares casilla `[00592]` "Liquidación IV - Otras deducciones - Cuota
líquida" (`Tipo = Num`, money).

Unlike casillas `00552`/`00558`/`00562`/`00611`, the Liquidación
occurrence of `00592` is **already registered** — the existing fragment
`0001-liquidacion-cuota-liquida.toml` (`id = "00592"`,
`section = ["liquidacion", "cuota_liquida"]`,
`semantic_role = "is_cuota_liquida"`) is the `DP200014B` cuota líquida
casilla; the ECPN (`DP200010`) and aseguradoras (`DP200043`) occurrences
of `00592` are not registered. Authoring a *new* fragment, as the Step
text literally suggests, would either collide on `id = "00592"` (a hard
duplicate-id failure) or fabricate a spurious second `00592` casilla.
The correct, corpus-grounded action — and the only one that satisfies
the plan's Verification criterion "registered under their DP200014B
segmento codes" — is to add the `segmento` field to the existing
fragment.

The fragment now carries `segmento = "DP200014B"`. `id` stays the bare
`"00592"`: it is the sole registered `00592` occurrence, so the bare id
remains unique within the revision, and every existing reference (the
`modelo-200-cuota-ejercicio-a-ingresar-devolver` formula reading
`00592`, the page-010/page-014b/page-043 export field bindings, and the
bidirectional export-ref symmetry check keyed on `casilla_by_id`)
resolves unchanged. The ADR's segment-qualified `id` form is required
only when a number has two registered occurrences (the
`00552`/`00558`/`00562` case); a single-occurrence casilla keeps its
bare `id`. All other fields (`label`, `data_type = "money"`,
`semantic_role`, `legal_refs`, `source_refs`, `export_refs`) are
unchanged.

## Tests

`pytest` on `test_modelo_200_registry.py`, `test_referential_integrity.py`,
and `test_modelo_parity_coverage.py` — 48 passed. A `RegistryValidator`
sweep over all 26 modelos confirms every modelo still loads valid
(`fail=0`).
