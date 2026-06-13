---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# schema-hardening m200 conversion-activos-diferidos role assignment

## Scope

Cluster: **conversión de activos por impuesto diferido en crédito exigible frente a la Administración tributaria** (art. 130 LIS / DT 33ª y DA 13ª LIS).

- Source JSON: `.vault-scratch/m200-clusters/conversion-activos-diferidos.json`
- Registry path: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/`
- Total casillas classified: **136**
- Distinct sections: 4
- `data_type` distribution: `money` × 136 (uniform — no divergences)
- Roles used: 4 (all reused from existing `is_conversion_aid_*` family — 0 new roles introduced)

Section-to-role mapping confirmed by reading representative TOML files in the registry:

| section key (abbreviated) | semantic_role | confirmed via TOML |
|---|---|---|
| `activos_impuesto_diferido_aid_art_130_lis` | `is_conversion_aid_art130_importe` | 0245, 0367 |
| `activos_impuesto_diferido_aid_dt_33a_y_da_13a_lis` | `is_conversion_aid_dt33a_importe` | 0503 |
| `exceso_cuota_liquida_positiva` | `is_conversion_aid_exceso_cuota_importe` | 0250, 0991 |
| `rectificativa` | `is_conversion_aid_rectificativa` | 0750, 0924 |

## Role assignments

| id | role | label_snippet | data_type | notes |
|---|---|---|---|---|
| 00879 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused |
| 01117 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01118 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01119 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01120 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01121 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01122 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01132 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01133 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01414 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01415 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01416 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01417 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01418 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01419 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01420 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01421 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01422 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01424 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused |
| 01425 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused |
| 01525 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01526 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01527 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01528 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01529 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01530 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01531 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01532 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01533 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01534 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01535 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01536 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01537 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01538 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01539 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01540 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01541 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused |
| 01543 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01544 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01545 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01546 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01547 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01548 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01549 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01550 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01551 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01552 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01553 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01554 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01555 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01556 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01557 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01558 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01559 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01560 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01561 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01562 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01563 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01564 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01565 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01566 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01567 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01568 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01569 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01570 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01580 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused |
| 01581 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused |
| 01582 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused |
| 01591 | `is_conversion_aid_dt33a_importe` | AID. DT 33ª… (DT 33ª y DA 13ª LIS) | money | reused; confirmed unassigned in registry TOML 0503 |
| 01754 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01755 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01756 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01757 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01758 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01759 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01760 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01761 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 01762 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02101 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02102 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02103 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02104 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02105 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02106 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02107 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02108 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02268 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02269 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02270 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02271 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02272 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02273 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02274 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02275 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02276 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02418 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02419 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02420 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02421 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02422 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02423 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02424 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02425 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02426 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02491 | `is_conversion_aid_rectificativa` | Rectificativa (art. 130 LIS) | money | reused; confirmed unassigned in registry TOML 0750 |
| 02492 | `is_conversion_aid_rectificativa` | Rectificativa (art. 130 LIS) | money | reused; confirmed unassigned in registry TOML 0750 |
| 02493 | `is_conversion_aid_rectificativa` | Rectificativa (art. 130 LIS) | money | reused; confirmed unassigned in registry TOML 0750 |
| 02494 | `is_conversion_aid_rectificativa` | Rectificativa (art. 130 LIS) | money | reused; confirmed unassigned in registry TOML 0750 |
| 02786 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02787 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02788 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02789 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02790 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02793 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02794 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02795 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 02797 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused |
| 02798 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused |
| 02799 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused |
| 03244 | `is_conversion_aid_rectificativa` | Rectificativa (art. 130 LIS) | money | reused; confirmed unassigned in registry TOML 0924 |
| 03245 | `is_conversion_aid_rectificativa` | Rectificativa (art. 130 LIS) | money | reused; confirmed unassigned in registry TOML 0924 |
| 03318 | `is_conversion_aid_rectificativa` | Rectificativa (art. 130 LIS) | money | reused |
| 03319 | `is_conversion_aid_rectificativa` | Rectificativa (art. 130 LIS) | money | reused |
| 03320 | `is_conversion_aid_rectificativa` | Rectificativa (art. 130 LIS) | money | reused |
| 03604 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 03605 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 03606 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 03607 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 03608 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 03609 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 03610 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 03611 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 03612 | `is_conversion_aid_art130_importe` | AID. Art. 13… (Art. 130 LIS) | money | reused |
| 03614 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused; confirmed unassigned in registry TOML 0991 |
| 03615 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused; confirmed unassigned in registry TOML 0991 |
| 03616 | `is_conversion_aid_exceso_cuota_importe` | Exceso cuota líquida positiva - Ejercici… | money | reused; confirmed unassigned in registry TOML 0991 |

## Data_type divergences

None. All 136 casillas carry `data_type = "money"`. No cross-role data_type conflicts exist in this cluster.

## Summary

- **Total classified:** 136
- **New roles introduced:** 0
- **Roles reused (verbatim):**
  - `is_conversion_aid_art130_importe` — 97 casillas (section `activos_impuesto_diferido_aid_art_130_lis`)
  - `is_conversion_aid_dt33a_importe` — 18 casillas (section `activos_impuesto_diferido_aid_dt_33a_y_da_13a_lis`)
  - `is_conversion_aid_exceso_cuota_importe` — 12 casillas (section `exceso_cuota_liquida_positiva`)
  - `is_conversion_aid_rectificativa` — 9 casillas (section `rectificativa`)
- **Data_type divergences:** 0
- **Role-to-data_type consistency:** verified — every role maps exclusively to `money` within and across sections.
