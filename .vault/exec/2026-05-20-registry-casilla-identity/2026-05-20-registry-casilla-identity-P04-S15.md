---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S15'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P04.S15`

Registered the Modelo 200 Liquidación III cuota íntegra casilla `00562`
under `segmento = "DP200014"` as a new casilla fragment, grounded in the
official AEAT 2024 Diseño de Registros.

- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00562-cuota-integra.toml`

## Description

The corpus AEAT 2024 Diseño workbook sheet `DP200014` row position 646
declares casilla `[00562]` "Liquidación III - Base imponible - Cuota
íntegra" with `Tipo = Num` (numeric money). The bare number `00562` was
already taken by the Estado-de-cambios-patrimonio-neto (II) ECPN casilla
(`id = "00562"`, "(-) Distribución de dividendos - Capital - Escriturado",
`segmento` unset) — the exact `00562` collision the ADR cites as the
motivating defect.

The new fragment declares the Liquidación occurrence with the
segment-qualified `id = "DP200014:00562"`, `number = "00562"`, and
`segmento = "DP200014"`; its identity is `(DP200014, 00562)`, distinct
from the ECPN `(None, 00562)`.

`data_type = "money"` per the Diseño `Num` type. `legal_refs` reuse the
established M200 cuota-chain legal block (Ley 27/2014 LIS art. 30 cuota
íntegra, art. 29 tipo de gravamen, art. 41 deducción de pagos a cuenta,
plus the sibling Liquidación legal set), all catalogued in `is.toml`.
`source_refs` reuse the catalogued M200 ids.
`semantic_role = "is_liquidacion_iii_cuota_integra"` is declared
`intentional_singleton` with a reason.

`export_refs` declares `modelo-200-page-014-casilla-00562`: PDF page 14
is the Liquidación page (`DP200014`), so the page-014 `00562` export
field belongs to this Liquidación casilla. The export field's `casilla`
binding is re-pointed from the ECPN occurrence to this casilla in S19;
between S15 and S19 the field still resolves through the ECPN casilla
`id` and M200 stays valid.

## Tests

`pytest` on `test_modelo_200_registry.py`, `test_referential_integrity.py`,
and `test_modelo_parity_coverage.py` — 48 passed. A `RegistryValidator`
sweep over all 26 modelos confirms every modelo still loads valid
(`fail=0`). The ECPN `00562` casilla is untouched.
