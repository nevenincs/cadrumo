---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S13'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P04.S13`

Registered the Modelo 200 Liquidación III base imponible casilla `00552`
under `segmento = "DP200014"` as a new casilla fragment, grounded in the
official AEAT 2024 Diseño de Registros.

- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00552-base-imponible.toml`

## Description

The corpus AEAT 2024 Diseño workbook sheet `DP200014` row position 166
declares casilla `[00552]` "Liquidación III - Base imponible - Base
imponible" with `Tipo = N` (numeric money). The bare number `00552` was
already taken by the Estado-de-cambios-patrimonio-neto (II) ECPN casilla
(`id = "00552"`, `segmento` unset), so the Liquidación occurrence was
previously undeclarable under the old `id == number` model.

The new fragment declares the Liquidación occurrence with the
segment-qualified `id = "DP200014:00552"` (the `CasillaId` pattern admits
the colon separator; the form keeps `id` globally unique within the
revision while the ECPN occurrence keeps its bare-number `id`). `number`
stays the bare `00552` and `segmento = "DP200014"` carries the AEAT
record-segment code, so the casilla's identity is the pair
`(DP200014, 00552)`, distinct from the ECPN `(None, 00552)`.

`data_type = "money"` per the Diseño `N` type. `legal_refs` reuse the
established Modelo 200 cuota-chain legal block (Ley 27/2014 LIS arts. 29
tipo de gravamen, 30 cuota íntegra, 41 deducción de pagos a cuenta, plus
the sibling Liquidación casilla legal set) — every id is present in the
`is.toml` legal catalogue. `source_refs` reuse the catalogued M200
source ids `aeat-dr-200-2025` and `aeat-modelo-200-manual-2024`.
`semantic_role = "is_liquidacion_iii_base_imponible"` is declared
`intentional_singleton` with a reason, since the top-level Liquidación
base imponible has no sibling casilla sharing the role. `export_refs` is
left empty: P04 scopes the export re-point to casilla `00562` only
(S19); the page-014 `00552` export field is untouched here.

## Tests

`pytest` on `test_modelo_200_registry.py`, `test_referential_integrity.py`,
and `test_modelo_parity_coverage.py` — 48 passed. A direct
`RegistryValidator.validate_modelo` sweep over all 26 modelos confirms
every modelo still loads valid (`ok=26 fail=0`). The ECPN `00552`
casilla is untouched and continues to resolve.
