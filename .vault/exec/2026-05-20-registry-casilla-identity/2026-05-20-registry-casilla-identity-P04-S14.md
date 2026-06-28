---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S14'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P04.S14`

Registered the Modelo 200 Liquidación III tipo de gravamen casilla
`00558` under `segmento = "DP200014"` as a new casilla fragment, grounded
in the official AEAT 2024 Diseño de Registros.

- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00558-tipo-de-gravamen.toml`

## Description

The corpus AEAT 2024 Diseño workbook sheet `DP200014` row position 438
declares casilla `[00558]` "Liquidación III - Base imponible - Tipo de
gravamen" with `Tipo = Num` and `Contenido = "2 enteros y 2 decimales"` —
a percentage rate, not a money amount. The bare number `00558` was
already taken by the Estado-de-cambios-patrimonio-neto (III) ECPN casilla
(`id = "00558"`, `segmento` unset).

The new fragment declares the Liquidación occurrence with the
segment-qualified `id = "DP200014:00558"`, `number = "00558"`, and
`segmento = "DP200014"`, so its identity is `(DP200014, 00558)`, distinct
from the ECPN `(None, 00558)`.

`data_type = "decimal"` — the registry's established type for a tipo de
gravamen casilla: the only other registry tipo-de-gravamen casilla
(`00063`, "Tipo de gravamen reducido para entidades de nueva creación")
is also typed `decimal`. The schema's `data_type` enum has no dedicated
percentage type and no registry casilla uses `ratio`; `decimal` is the
correct established rate type. The Diseño "2 enteros y 2 decimales"
shape is the numeric width of the AEAT record field and is not forced as
a casilla constraint, consistent with `00063`.

`legal_refs` reuse the established M200 cuota-chain legal block (Ley
27/2014 LIS art. 29 tipo de gravamen plus the sibling Liquidación legal
set), all catalogued in `is.toml`. `source_refs` reuse the catalogued
M200 ids. `semantic_role = "is_liquidacion_iii_tipo_de_gravamen"` is
declared `intentional_singleton` with a reason. `export_refs` is empty:
P04 scopes the export re-point to `00562` only (S19).

## Tests

`pytest` on `test_modelo_200_registry.py`, `test_referential_integrity.py`,
and `test_modelo_parity_coverage.py` — 48 passed. A `RegistryValidator`
sweep over all 26 modelos confirms every modelo still loads valid
(`fail=0`). The ECPN `00558` casilla is untouched.
