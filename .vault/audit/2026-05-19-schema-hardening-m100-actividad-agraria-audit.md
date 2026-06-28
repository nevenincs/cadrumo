---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
---

# `schema-hardening` audit: M100 actividad-agraria cluster

## Scope

The `actividad_agr` cluster sits under `toma_datos_ampliada/reg_estima_obj_agricola/actividad_agr` in the M100 (IRPF) form and covers estimación objetiva (módulos) data-entry for individual agricultural, livestock, and forestry activity lines. The cluster spans 57 casilla ids, present across revisions 2020-2025. Each activity sub-type contributes a repeating triplet: gross income input (`ingresos_integros`, money), an objective index or reduction field (type varies by revision — see id-reuse hazards below), and a derived base yield (`rendimiento_base_producto`, money). Six special-purpose casillas (0157-0160, 0162, 1553) sit outside that triplet pattern and require individual analysis. Three of those (0158, 0159, 0160, 0162) carry confirmed id-reuse hazards — the same casilla number was repurposed for a structurally distinct concept between certain revision years.

## Role assignments

| id | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|
| 0157 | `irpf_eo_agr_ingresos_integros_mejillon_batea` | Producción de mejillón en batea: Ingresos íntegros | money | 2025 | New activity line introduced 2025; single-revision |
| 0158 | `irpf_eo_agr_reduccion_gasoleo_agricola` | Reducción por adquisición de gasóleo agrícola | money | 2022-2024 | Concept A: exceptional reduction, money; see id-reuse hazard |
| 0158 | `irpf_eo_agr_indice` | Índice | text | 2025 | Concept B: repurposed in 2025 as the standard activity índice; see id-reuse hazard |
| 0159 | `irpf_eo_agr_reduccion_fertilizantes` | Reducción por adquisición de fertilizantes | money | 2022-2024 | Concept A: exceptional reduction, money; see id-reuse hazard |
| 0159 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2025 | Concept B: repurposed in 2025 as the standard base yield; both money but distinct concept |
| 0160 | `irpf_eo_agr_reduccion_la_palma` | Reducción para actividades económicas desarrolladas en la Isla de La Palma (Canarias) | money | 2022-2024 | Concept A: territorial emergency reduction; see id-reuse hazard |
| 0160 | `irpf_eo_agr_indice_corrector_mejillon_batea` | 9. Índice corrector de producción de mejillón en batea | money | 2025 | Concept B: corrector index for mejillón batea activity introduced 2025; see id-reuse hazard |
| 0162 | `irpf_eo_agr_reduccion_dana` | Reducción para actividades económicas por los daños producidos por la DANA | money | 2024 | Emergency DANA reduction; single revision only in this cluster; id moves to different section in 2025 |
| 1488 | `irpf_eo_agr_ingresos_integros_porcino_carne` | Ganado porcino de carne: Ingresos íntegros | money | 2020-2025 | Full-span activity; label was generic "Ingresos íntegros" in earlier revisions |
| 1489 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for porcino carne activity line |
| 1490 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for porcino carne activity line |
| 1491 | `irpf_eo_agr_ingresos_integros_remolacha` | Remolacha azucarera: Ingresos íntegros | money | 2020-2025 | Label was generic in earlier revisions |
| 1492 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for remolacha line |
| 1493 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for remolacha line |
| 1494 | `irpf_eo_agr_ingresos_integros_bovino_carne_avicultura` | Ganado bovino de carne, ovino de carne, caprino de carne, avicultura y cunicultura: Ingresos | money | 2020-2025 | Label was generic in earlier revisions |
| 1495 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for bovino carne/avicultura line |
| 1496 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for bovino carne/avicultura line |
| 1497 | `irpf_eo_agr_ingresos_integros_forestal_corta_larga` | Actividades forestales con un periodo medio de corta superior a 30 años: Ingresos íntegros | money | 2020-2025 | Forestry >30 year rotation; label was generic in earlier revisions |
| 1498 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for forestal larga rotación line |
| 1499 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for forestal larga rotación line |
| 1500 | `irpf_eo_agr_ingresos_integros_bovino_leche` | Ganado bovino de leche: Ingresos íntegros | money | 2020-2025 | Label was generic in earlier revisions |
| 1501 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for bovino leche line |
| 1502 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for bovino leche line |
| 1503 | `irpf_eo_agr_ingresos_integros_cereales_citricos_horticultura` | Cereales, cítricos, frutos secos, horticultura, patata, leguminosas, uva mesa: Ingresos | money | 2020-2025 | General crop group; label was generic in earlier revisions |
| 1504 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for cereales/citricos/horticultura line |
| 1505 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for cereales/citricos/horticultura line |
| 1506 | `irpf_eo_agr_ingresos_integros_porcino_cria_ovino_leche_apicultura` | Ganado porcino de cría, bovino de cría, ovino de leche, caprino de leche y apicultura | money | 2020-2025 | Breeding/dairy livestock group; label was generic in earlier revisions |
| 1507 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for porcino cría/ovino leche/apicultura line |
| 1508 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for porcino cría/ovino leche/apicultura line |
| 1509 | `irpf_eo_agr_ingresos_integros_forestal_corta_corta` | Actividades forestales con un período medio de corta igual o inferior a 30 años: Ingresos | money | 2020-2025 | Forestry ≤30 year rotation; label was generic in earlier revisions |
| 1510 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for forestal corta rotación line |
| 1511 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for forestal corta rotación line |
| 1512 | `irpf_eo_agr_ingresos_integros_arroz_oleaginosas_flores` | Arroz, uva para vino DO, oleaginosas, flores, plantas ornamentales: Ingresos | money | 2020-2025 | Higher-value crop group; label was generic in earlier revisions |
| 1513 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for arroz/oleaginosas/flores line |
| 1514 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for arroz/oleaginosas/flores line |
| 1515 | `irpf_eo_agr_ingresos_integros_otras_especies_ganaderas` | Otras especies ganaderas no comprendidas expresamente en otros números: Ingresos íntegros | money | 2020-2025 | Residual livestock catch-all; label was generic in earlier revisions |
| 1516 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for otras especies ganaderas line |
| 1517 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for otras especies ganaderas line |
| 1518 | `irpf_eo_agr_ingresos_integros_forestal_resina` | Actividad forestal dedicada a la extracción de resina: Ingresos íntegros | money | 2020-2025 | Resin extraction forestry; label was generic in earlier revisions |
| 1519 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for forestal resina line |
| 1520 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for forestal resina line |
| 1521 | `irpf_eo_agr_ingresos_integros_raices_tuberculos_forrajes` | Raíces (excepto remolacha), tubérculos, forrajes, algodón, frutos no cítricos: Ingresos | money | 2020-2025 | Root/tuber/forage crop group; label was generic in earlier revisions; typo variant in 2020 |
| 1522 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for raices/tuberculos/forrajes line |
| 1523 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for raices/tuberculos/forrajes line |
| 1524 | `irpf_eo_agr_ingresos_integros_plantas_textiles` | Plantas textiles: Ingresos íntegros | money | 2020-2025 | Textile plant crops; label was generic in earlier revisions |
| 1525 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for plantas textiles line |
| 1526 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for plantas textiles line |
| 1527 | `irpf_eo_agr_ingresos_integros_actividades_accesorias` | Actividades accesorias realizadas por agricultores, ganaderos o forestales: Ingresos | money | 2020-2025 | Ancillary economic activities by agr/livestock/forestry holders; label was generic in earlier revisions |
| 1528 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for actividades accesorias line |
| 1529 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for actividades accesorias line |
| 1530 | `irpf_eo_agr_ingresos_integros_otros_trabajos_accesorios` | Otros trabajos y servicios accesorios realizados por agricultores, ganaderos: Ingresos | money | 2020-2025 | Other ancillary services by agr/livestock holders; label was generic in earlier revisions |
| 1531 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for otros trabajos accesorios line |
| 1532 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for otros trabajos accesorios line |
| 1533 | `irpf_eo_agr_ingresos_integros_cria_guarda_engorde_ganado` | Servicios de cría, guarda y engorde de ganado (aves incluidas): Ingresos íntegros | money | 2020-2025 | Contract livestock rearing services; label was generic in earlier revisions |
| 1534 | `irpf_eo_agr_indice` | Índice | text | 2020-2025 | Objective index for cría/guarda/engorde line |
| 1535 | `irpf_eo_agr_rendimiento_base_producto` | Rendimiento base producto | money | 2020-2025 | Base yield for cría/guarda/engorde line |
| 1553 | `irpf_eo_agr_rdto_neto_actividad` | Rendimiento neto de la actividad | decimal | 2020 | Per-activity net yield total within EO agr input section; only present as actividad_agr casilla in 2020; id was reused in later revisions under a different section |

## Id-reuse hazards

- **0158** — In revisions 2022-2024 this id holds "Reducción por adquisición de gasóleo agrícola" (money, exceptional input-cost reduction). In revision 2025 it is completely repurposed as the standard "Índice" (text, objective yield index) for the mejillón batea activity line. Two rows emitted: `irpf_eo_agr_reduccion_gasoleo_agricola` (2022-2024) and `irpf_eo_agr_indice` (2025).

- **0159** — In revisions 2022-2024 this id holds "Reducción por adquisición de fertilizantes" (money, input-cost reduction). In revision 2025 it becomes the standard "Rendimiento base producto" (money) for the mejillón batea triplet. Both data_types are money but the conceptual roles are distinct — an exceptional reduction cannot share an engine role with a base-yield output. Two rows emitted: `irpf_eo_agr_reduccion_fertilizantes` (2022-2024) and `irpf_eo_agr_rendimiento_base_producto` (2025).

- **0160** — In revisions 2022-2024 this id is "Reducción para actividades económicas desarrolladas en la Isla de La Palma (Canarias)" (territorial emergency reduction, money). In revision 2025 it becomes "9. Índice corrector de producción de mejillón en batea" (a corrective yield index, money). Structurally distinct reduction vs. yield-corrector concepts. Two rows emitted: `irpf_eo_agr_reduccion_la_palma` (2022-2024) and `irpf_eo_agr_indice_corrector_mejillon_batea` (2025).

- **1553** — Present in this cluster (section `actividad_agr`) only in revision 2020, where it represents the per-activity net yield ("Rendimiento neto de la actividad", decimal). In later revisions (2021+) the id 1553 is reused in the `rendimientos_actividades_economicas` section as an informational aggregate for the whole EO agr block ("Rendimiento neto de actividades agrícolas ganaderas y forestales en estimacion objetiva"). Those later uses are outside this cluster's scope but confirm the id crossed a section boundary. One row emitted for the in-cluster concept: `irpf_eo_agr_rdto_neto_actividad` (2020 only).

## Data_type divergences

- **0158** — `data_types` in the cluster JSON shows both `money(default)` and `text`. This is entirely explained by the id-reuse: 2022-2024 is money (reduction), 2025 is text (índice). No single-revision type conflict exists. Resolution: split by revision range as documented in the id-reuse section.

- **1553** — `data_type` is `decimal` (not `money(default)`). This is the only casilla in the cluster with decimal type and reflects the per-activity net yield field which holds a signed multiplier-adjusted value rather than a raw currency input. No remediation needed; decimal is correct for this role.
