---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# `schema-hardening` audit: M100 `toma_datos_ampliada.regimenes_especiales` cluster — role classification

## Scope

M100 IRPF, revisions 2020–2025. Cluster: `toma_datos_ampliada.regimenes_especiales` and
its sub-sections (`re_at_rentas`, `re_agrup_interes_economico`, `re_tr_fiscal_inter`,
`re_derechos_imagen`, `re_institu_inversion_colectiva`) plus the adjacent `reg_estima_obj`
(estimación objetiva non-agricultural) and `reg_estima_obj_agricola` (agricultural módulos)
sub-trees, including their `resultados` summary rows. Total: **203 casillas** per the
section inventory (79 regimenes_especiales + 39 reg_estima_obj + 3 reg_estima_obj_res +
74 reg_estima_obj_agricola + 3 reg_estima_obj_agricola_res in 2025; historical presence
varies by revision). Already-roled casillas (`0257 = investment_entity_nif`,
`0259 = base_imponible_irpf`) are skipped per instructions.

---

## Sub-section map (2025)

| sub-section key | AEAT concept | casilla count |
|---|---|---:|
| `re_at_rentas` | Atribución de rentas (communal/partnership income) | 45 |
| `re_agrup_interes_economico` | Agrupaciones de interés económico (AIE) / UTEs | 9 |
| `re_tr_fiscal_inter` | Transparencia fiscal internacional (CFI) | 3 |
| `re_derechos_imagen` | Cesión de derechos de imagen | 4 |
| `re_institu_inversion_colectiva` | Instituciones de inversión colectiva en paraísos | 3 |
| `reg_estima_obj` | Estimación objetiva (módulos) non-agricultural | 42 |
| `reg_estima_obj_agricola` | Estimación objetiva agricultural módulos | 77 |

---

## Role-assignment table

### A. Estimación objetiva — non-agricultural (`reg_estima_obj`)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1442 | reg_estima_obj / actividad_est_obj | `irpf_eo_actividad_iae_code` | Clasificación I.A.E. (grupo o epígrafe) | text | 2020–2025 | IAE activity classification code; stable label across all revisions |
| 1443 | reg_estima_obj / actividad_est_obj | `irpf_eo_cobros_pagos_flag` | Si opta por criterio de cobros y pagos, consigne X | boolean | 2020–2025 | Cash-basis election flag; stable across all revisions |
| 1444 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_definicion` | Definición (módulo row 1) | text | 2020–2025 | Module definition label — repeating row field (7 repetitions: ids 1444, 1447, 1450, 1453, 1456, 1459, 1462) |
| 1445 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_num_unidades` | Nº de unidades (módulo row 1) | (absent — decimal implied) | 2020–2025 | Number of units for the módulo; repeating row field (ids 1445, 1448, 1451, 1454, 1457, 1460, 1463) |
| 1446 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_rdto_antes_amort` | Rendimiento por módulo antes de amortización (row 1) | (absent — decimal implied) | 2020–2025 | Yield-per-unit before amortisation; repeating row field (ids 1446, 1449, 1452, 1455, 1458, 1461, 1464) |
| 1447 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_definicion` | Definición (módulo row 2) | text | 2020–2025 | Same row-field role as 1444 |
| 1448 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_num_unidades` | Nº de unidades (módulo row 2) | (absent) | 2020–2025 | |
| 1449 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_rdto_antes_amort` | Rendimiento por módulo antes de amortización (row 2) | (absent) | 2020–2025 | |
| 1450 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_definicion` | Definición (módulo row 3) | text | 2020–2025 | |
| 1451 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_num_unidades` | Nº de unidades (módulo row 3) | (absent) | 2020–2025 | |
| 1452 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_rdto_antes_amort` | Rendimiento por módulo antes de amortización (row 3) | (absent) | 2020–2025 | |
| 1453 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_definicion` | Definición (módulo row 4) | text | 2020–2025 | |
| 1454 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_num_unidades` | Nº de unidades (módulo row 4) | (absent) | 2020–2025 | |
| 1455 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_rdto_antes_amort` | Rendimiento por módulo antes de amortización (row 4) | (absent) | 2020–2025 | |
| 1456 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_definicion` | Definición (módulo row 5) | text | 2020–2025 | |
| 1457 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_num_unidades` | Nº de unidades (módulo row 5) | (absent) | 2020–2025 | |
| 1458 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_rdto_antes_amort` | Rendimiento por módulo antes de amortización (row 5) | (absent) | 2020–2025 | |
| 1459 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_definicion` | Definición (módulo row 6) | text | 2020–2025 | |
| 1460 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_num_unidades` | Nº de unidades (módulo row 6) | (absent) | 2020–2025 | |
| 1461 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_rdto_antes_amort` | Rendimiento por módulo antes de amortización (row 6) | (absent) | 2020–2025 | |
| 1462 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_definicion` | Definición (módulo row 7) | text | 2020–2025 | |
| 1463 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_num_unidades` | Nº de unidades (módulo row 7) | (absent) | 2020–2025 | |
| 1464 | reg_estima_obj / actividad_est_obj | `irpf_eo_modulo_rdto_antes_amort` | Rendimiento por módulo antes de amortización (row 7) | (absent) | 2020–2025 | |
| 1465 | reg_estima_obj / actividad_est_obj | `irpf_eo_rdto_neto_previo` | Rendimiento neto previo | (absent — decimal implied) | 2020–2025 | Intermediate sum before minoraciones |
| 1466 | reg_estima_obj / actividad_est_obj | `irpf_eo_minoracion_empleo` | Minoración por incentivo al empleo | (absent — decimal implied) | 2020–2025 | Employment incentive reduction |
| 1467 | reg_estima_obj / actividad_est_obj | `irpf_eo_minoracion_inversion` | Minoración por incentivos a la inversión | (absent — decimal implied) | 2020–2025 | Investment incentive reduction |
| 1468 | reg_estima_obj / actividad_est_obj | `irpf_eo_rdto_neto_minorado` | Rendimiento neto minorado | decimal | 2020–2025 | After employment/investment minoraciones |
| 1469 | reg_estima_obj / actividad_est_obj | `irpf_eo_indice_corrector_especial` | 1. Índice corrector especial | (absent — decimal implied) | 2020–2025 | Special corrector index |
| 1470 | reg_estima_obj / actividad_est_obj | `irpf_eo_indice_corrector_pequena_dimension` | 2. Índice corrector para empresas de pequeña dimensión | (absent — decimal implied) | 2020–2025 | Small-enterprise corrector |
| 1471 | reg_estima_obj / actividad_est_obj | `irpf_eo_indice_corrector_temporada` | 3. Índice corrector de temporada | (absent — decimal implied) | 2020–2025 | Seasonal corrector |
| 1472 | reg_estima_obj / actividad_est_obj | `irpf_eo_indice_corrector_exceso` | 4. Índice corrector de exceso | (absent — decimal implied) | 2020–2025 | Excess corrector |
| 1473 | reg_estima_obj / actividad_est_obj | `irpf_eo_indice_corrector_inicio` | 5. Índice corrector por inicio de nueva actividad | (absent — decimal implied) | 2020–2025 | New-activity start corrector |
| 1474 | reg_estima_obj / actividad_est_obj | `irpf_eo_rdto_neto_modulos` | Rendimiento neto de módulos | decimal | 2020–2025 | Net yield after corrector indices |
| 1475 | reg_estima_obj / actividad_est_obj | `irpf_eo_reduccion_general` | Reducción de carácter general | (absent — decimal implied) | 2020–2025 | General reduction (only if 1474 > 0) |
| 1476 | reg_estima_obj / actividad_est_obj | **HAZARD — see below** | Reducción Lorca / DANA / andalucia-celiaca | (absent) | 2020–2024 only in reg_estima_obj | Cross-revision concept change; 2025 id moves to deduccion_autonomica |
| 1477 | reg_estima_obj / actividad_est_obj | `irpf_eo_gastos_extraordinarios` | Gastos extraordinarios por circunstancias excepcionales | (absent — decimal implied) | 2020–2025 | Extraordinary expenses from exceptional circumstances |
| 1478 | reg_estima_obj / actividad_est_obj | `irpf_eo_otras_percepciones` | Otras percepciones empresariales | (absent — decimal implied) | 2020–2025 | Other business income perceptions |
| 1479 | (out of scope) | — | Rendimiento neto EO (summary row) | — | 2021–2025 in rendimientos_actividades_economicas | 2020: in reg_estima_obj; 2021+: moved to rendimientos_actividades_economicas section. Section drift only; outside cluster in 2025. |
| 1480 | reg_estima_obj / actividad_est_obj | `irpf_eo_reduccion_irregulares` | Reducciones de rendimientos generados en más de 2 años (art.32.1 y DT 25ª) | (absent — decimal implied) | 2020–2025 | Irregular-income reduction |
| 1481 | reg_estima_obj / actividad_est_obj | `irpf_eo_rdto_neto_reducido` | Rendimiento neto reducido | decimal | 2020–2025 | Final per-activity net yield after all reductions |
| 0238 | reg_estima_obj / actividad_est_obj | `irpf_eo_reintegro_subvenciones` | Reintegro de subvenciones | (absent — decimal implied) | 2025 only | New in 2025; subsidy reintegration field |

**reg_estima_obj resultados summary rows:**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1482 | reg_estima_obj_res | `irpf_eo_suma_rdtos_netos_reducidos` | Suma de rendimientos netos reducidos EO exc. agrícolas (suma [1481]) | decimal | 2020–2025 | Aggregate sum of per-activity 1481 rows |
| 1483 | reg_estima_obj_res | `irpf_eo_reduccion_art_32_2_3` | Reducción por el ejercicio de determinadas actividades económicas (art.32.2.3º) | (absent — decimal implied) | 2020–2025 | Portfolio reduction for certain activities |
| 1484 | reg_estima_obj_res | `irpf_eo_rdto_neto_reducido_total` | Rendimiento neto reducido total EO exc. agrícolas ([1482] - [1483]) | decimal | 2020–2025 | Final EO non-agricultural aggregate |

---

### B. Estimación objetiva — agricultural (`reg_estima_obj_agricola`)

The agricultural section is a set of repeating crop/livestock-type rows. Each row has three
fields: ingresos íntegros (gross income), índice (index code), and rendimiento base producto
(base product yield). The section inventory shows ~20 named crop/livestock types followed by
activity-level computations.

**Per-type row fields (shared role per field-position):**

| id pattern | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0157 (2025), 1488, 1491, 1494, 1497, 1500, 1503, 1506, 1509, 1512, 1515, 1518, 1521, 1524, 1527, 1530, 1533 | `irpf_eo_agr_ingresos_integros` | {Crop/species}: Ingresos íntegros | (absent — decimal implied) | varies | Gross income for each agricultural product type |
| 0158 (2025), 1489, 1492, 1495, 1498, 1501, 1504, 1507, 1510, 1513, 1516, 1519, 1522, 1525, 1528, 1531, 1534 | `irpf_eo_agr_indice` | Índice | text | varies | Index code per product type |
| 0159 (2025), 1490, 1493, 1496, 1499, 1502, 1505, 1508, 1511, 1514, 1517, 1520, 1523, 1526, 1529, 1532, 1535 | `irpf_eo_agr_rdto_base_producto` | Rendimiento base producto | (absent — decimal implied) | varies | Base yield per product type |

**0157, 0158, 0159, 0160 in 2025 are HAZARDS — see cross-revision section below.**

**Activity-level computation fields:**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1486 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_actividad_clave` | Actividad realizada. Clave | (absent — text implied) | 2020–2025 | Activity type code |
| 1487 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_cobros_pagos_flag` | Si opta por criterio de cobros y pagos, consigne X | boolean | 2020–2025 | Cash-basis election flag (agricultural parallel of 1443) |
| 1536 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_total_ingresos` | Total ingresos | (absent — decimal implied) | 2020–2025 | Sum of all product-type ingresos |
| 1537 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_rdto_neto_previo` | Rendimiento neto previo | (absent — decimal implied) | 2020–2025 | Net yield before amortisation |
| 1538 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_amortizacion` | Amortización del inmovilizado material e intangible | (absent — decimal implied) | 2020–2025 | Amortisation of fixed assets |
| 1539 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_rdto_neto_minorado` | Rendimiento neto minorado | decimal | 2020–2025 | After amortisation |
| 1540 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_indice_medios_ajenos` | 1. Por utilización de medios de producción ajenos en actividades agrícolas | (absent — decimal implied) | 2020–2025 | Corrector: use of external production means |
| 1541 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_indice_personal_asalariado` | 2. Por utilización de personal asalariado | (absent — decimal implied) | 2020–2025 | Corrector: salaried staff |
| 1542 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_indice_tierras_arrendadas` | 3. Por cultivos realizados en tierras arrendadas | (absent — decimal implied) | 2020–2025 | Corrector: crops on leased land |
| 1543 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_indice_piensos_terceros` | 4. Por piensos adquiridos a terceros en más del 50% | text | 2020–2025 | Corrector: feed sourced from 3rd parties >50% (text key) |
| 1544 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_indice_ecologica` | 5. Por actividades de agricultura ecológica | (absent — decimal implied) | 2020–2025 | Corrector: organic farming |
| 1545 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_indice_regadio_electrico` | 6. Por cultivos en tierras de regadío con energía eléctrica | (absent — decimal implied) | 2020–2025 | Corrector: irrigated electric-energy crops |
| 1546 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_indice_pequena_empresa` | 7. Por ser empresa cuyo rdto. neto minorado no supera 9.447,91 euros | (absent — decimal implied) | 2020–2025 | Corrector: small-income enterprise |
| 1547 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_indice_forestal` | 8. Índice corrector en determinadas actividades forestales | (absent — decimal implied) | 2020–2025 | Corrector: forest activities |
| 1548 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_rdto_neto_modulos` | Rendimiento neto de módulos | decimal | 2020–2025 | Net yield after all correctors |
| 1549 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_reduccion_general` | Reducción de carácter general (sólo si [1548] > 0) | (absent — decimal implied) | 2020–2025 | General reduction |
| 1550 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_diferencia_reduccion` | Diferencia ([1548] - [1549]) | decimal | 2020–2025 | Intermediate subtraction |
| 1551 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_reduccion_jovenes` | Reducción agricultores jóvenes (DA sexta de la Ley) | decimal | 2020–2025 | Young-farmer reduction |
| 1552 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_gastos_extraordinarios` | Gastos extraordinarios por circunstancias excepcionales | (absent — decimal implied) | 2020–2025 | Extraordinary expenses |
| 1553 | (out of scope in 2021–2025) | — | Rendimiento neto de la actividad | (absent) | 2020 only in reg_estima_obj_agricola; 2021+ in rendimientos_actividades_economicas | Moved out of cluster from 2021; section drift, not semantic change |
| 1554 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_reduccion_irregulares` | Reducciones de rendimientos generados en más de 2 años (art.32.1 y DT 25ª) | decimal | 2020–2025 | Irregular-income reduction |
| 1555 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_rdto_neto_reducido` | Rendimiento neto reducido | decimal | 2020–2025 | Final per-activity net yield |
| 0239 | reg_estima_obj_agricola / actividad_agr | `irpf_eo_agr_reintegro_subvenciones` | Reintegro de subvenciones (importe declarado por índices) | (absent — decimal implied) | 2025 only | New in 2025; parallel to 0238 in non-agricultural section |

**Special per-type rows unique to 2025 (IDs reused from prior revisions — HAZARDS):**

These IDs carry the `irpf_eo_agr_ingresos_integros`, `irpf_eo_agr_indice`, and
`irpf_eo_agr_rdto_base_producto` roles only in 2025. See cross-revision hazards section.

**reg_estima_obj_agricola resultados summary rows:**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1558 | reg_estima_obj_agricola_res | `irpf_eo_agr_suma_rdtos_netos_reducidos` | Suma de rendimientos netos reducidos EO agrícolas (suma [1555]) | decimal | 2020–2025 | Agricultural aggregate |
| 1559 | reg_estima_obj_agricola_res | `irpf_eo_agr_reduccion_art_32_2_3` | Reducción por el ejercicio de determinadas actividades económicas (art.32.2.3º) | (absent — decimal implied) | 2020–2025 | Portfolio reduction |
| 1560 | reg_estima_obj_agricola_res | `irpf_eo_agr_rdto_neto_reducido_total` | Rendimiento neto reducido total agrícolas ([1558] - [1559]) | decimal | 2020–2025 | Final EO agricultural aggregate |

---

### C. Atribución de rentas (`re_at_rentas`)

**Entity header fields:**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1562 | re_at_rentas | `irpf_re_atrib_entidad_nif` | NIF de la entidad en régimen de atribución de rentas | text | 2020–2025 | OQ-1 deferred: foreign NIF allowed; data_type = text not nif |
| 1563 | re_at_rentas | `irpf_re_atrib_entidad_nif_extranjero_flag` | Marque X si en [1562] ha consignado un NIF de otro país | boolean | 2020–2025 | Companion boolean for 1562 (OQ-1 pattern) |
| 1621 | re_at_rentas | `irpf_re_atrib_entidad_nif_alt` | NIF de la entidad en atribución de rentas, o Nº de Identificación en país residencia | text | 2020–2025 | Alternative/secondary entity NIF slot for non-resident entities |
| 1622 | re_at_rentas | `irpf_re_atrib_entidad_nif_extranjero_flag` | Marque X si en [1562] ha consignado NIF de otro país (duplicate label) | boolean | 2020–2025 | Second companion boolean; shares role with 1563 |
| 1564 | re_at_rentas | `irpf_re_atrib_pct_participacion` | Porcentaje de participación del contribuyente en la entidad | (absent — decimal implied) | 2020–2025 | Taxpayer's ownership percentage |
| 1576 | re_at_rentas | `irpf_re_atrib_cobros_pagos_flag` | Si opta por criterio de cobros y pagos, consigne X | boolean | 2020–2025 | Cash-basis election flag for atribución entity |
| 0161 | re_at_rentas (2025) | **HAZARD — see below** | 2025: Reg. estimación directa normal; 2024: DANA reduction (reg_estima_obj) | boolean / (absent) | 2021–2025 | Severe concept change between revisions |
| 0162 | re_at_rentas (2025) | **HAZARD — see below** | 2025: Reg. estimación directa simplificada; 2024: DANA reduction (agricola) | boolean / (absent) | 2024–2025 | Severe concept change |
| 0163 | re_at_rentas (2025) | `irpf_re_atrib_tipo_regimen_agricola_flag` | Agrícola, ganadera y forestal | boolean | 2025 only | Regime type flag; new in 2025 |
| 0164 | re_at_rentas (2025) | `irpf_re_atrib_tipo_regimen_resto_flag` | Resto | boolean | 2025 only | Other regime type flag; new in 2025 |
| 0384 | re_at_rentas (2025) | `irpf_re_atrib_reduccion_actividades_artisticas` | Reducción por rendimientos actividades artísticas excepcionales (DA 60ª) | (absent — decimal implied) | 2025 only | New in 2025 |

**Capital mobiliario atribuido sub-block (general BI):**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1565 | re_at_rentas | `irpf_re_atrib_cap_mob_rdto_neto_entidad` | Rendimiento neto atribuido por la entidad | decimal | 2020–2025 | Net yield from entity (capital mobiliario) |
| 1566 | re_at_rentas | `irpf_re_atrib_cap_mob_minoraciones` | Minoraciones aplicables | (absent — decimal implied) | 2020–2025 | |
| 1567 | re_at_rentas | `irpf_re_atrib_cap_mob_reducciones_26_2` | Reducciones aplicables (art.26.2 y DT 25ª) | decimal | 2020–2025 | |
| 1568 | re_at_rentas | `irpf_re_atrib_cap_mob_rdto_neto_computable_gral` | Rendimiento neto computable ([1565]-[1566]-[1567]) | decimal | 2020–2025 | To integrate in BI general |

**Capital mobiliario atribuido sub-block (BI del ahorro):**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1569 | re_at_rentas | `irpf_re_atrib_cap_mob_rdto_neto_computable_ahorro` | Rdto. neto atribuido. Importe computable (excepto [1570]) | decimal | 2020–2025 | Savings-base portion |
| 1570 | re_at_rentas | `irpf_re_atrib_deuda_subordinada` | Rendimiento derivado de valores de deuda subordinada o participaciones preferentes | decimal | 2020–2025 | Subordinated debt / preferred shares income |

**Capital inmobiliario atribuido sub-block:**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1571 | re_at_rentas | `irpf_re_atrib_cap_inmo_rdto_neto_entidad` | Rendimiento neto atribuido por la entidad (capital inmobiliario) | decimal | 2020–2025 | |
| 1572 | re_at_rentas | `irpf_re_atrib_cap_inmo_minoraciones` | Minoraciones aplicables | (absent — decimal implied) | 2020–2025 | |
| 1573 | re_at_rentas | `irpf_re_atrib_cap_inmo_reduccion_23_2` | Reducción aplicable (art.23.2) | decimal | 2020–2025 | Rental income reduction |
| 1574 | re_at_rentas | `irpf_re_atrib_cap_inmo_reducciones_23_3` | Reducciones aplicables (arts.23.3 y DT 25ª) | decimal | 2020–2025 | |
| 1575 | re_at_rentas | `irpf_re_atrib_cap_inmo_rdto_neto_computable` | Rendimiento neto computable ([1571]-[1572]-[1573]-[1574]) | decimal | 2020–2025 | |

**Actividades económicas atribuidas sub-block:**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1578 | re_at_rentas | `irpf_re_atrib_act_eco_minoraciones` | Minoraciones aplicables | (absent — decimal implied) | 2020–2025 | |
| 1579 | re_at_rentas | `irpf_re_atrib_act_eco_provisiones_difícil` | Provisiones deducibles y gastos de difícil justificación (solo ED simplificada) | (absent — decimal implied) | 2020–2025 | |
| 1580 | re_at_rentas | `irpf_re_atrib_act_eco_reduccion_32_1` | Reducción aplicable (art.32.1 y DT 25ª) | decimal | 2020–2025 | |
| 1581 | re_at_rentas | `irpf_re_atrib_act_eco_reduccion_32_2_3` | Reducción aplicable (art.32.2.3) | decimal | 2020–2025 | |
| 1582 | re_at_rentas | `irpf_re_atrib_act_eco_reduccion_32_3` | Reducción aplicable (art.32.3) | decimal | 2020–2025 | |
| 1583 | re_at_rentas | `irpf_re_atrib_act_eco_rdto_neto_computable` | Rendimiento neto computable ([1577]-[1578]-[1579]-[1580]-[1581]-[1582]-[0384]) | decimal | 2020–2025 | |

**Ganancias / pérdidas patrimoniales atribuidas:**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1584 | re_at_rentas | `irpf_re_atrib_gp_no_transmision_ganancias` | Ganancias patrimoniales no derivadas de transmisiones, atribuidas | (absent — decimal implied) | 2020–2025 | Non-transmission gains (BI general) |
| 1585 | re_at_rentas | `irpf_re_atrib_gp_no_transmision_perdidas` | Pérdidas patrimoniales no derivadas de transmisiones, atribuidas | (absent — decimal implied) | 2020–2025 | |
| 1586 | re_at_rentas | `irpf_re_atrib_gp_transmision_ganancias` | Ganancias patrimoniales | (absent — decimal implied) | 2020–2025 | |
| 1587 | re_at_rentas | `irpf_re_atrib_gp_renta_vitalicia` | Valor de transmisión destinado a constituir una renta vitalicia | (absent — decimal implied) | 2020–2025 | Exempt reinvestment basis |
| 1588 | re_at_rentas | `irpf_re_atrib_gp_dt9_valor_transmision` | Valor de transmisión aplicable DT 9ª | (absent — decimal implied) | 2020–2025 | Transitional reduction base |
| 1589 | re_at_rentas | `irpf_re_atrib_gp_exentas_50pct` | Ganancias exentas 50 por 100 (determinados inmuebles urbanos) | (absent — decimal implied) | 2020–2025 | |
| 1590 | re_at_rentas | `irpf_re_atrib_gp_exentas_reinversion_vitalicia` | Ganancias exentas por reinversión de rentas vitalicias | (absent — decimal implied) | 2020–2025 | |
| 1591 | re_at_rentas | `irpf_re_atrib_gp_exentas_reinversion_nuevas` | Ganancia exenta por reinversión en entidades de nueva o reciente creación | (absent — decimal implied) | 2020–2025 | |
| 1592 | re_at_rentas | `irpf_re_atrib_gp_dt9_susceptibles_reduccion` | Parte de las ganancias patrimoniales susceptibles de reducción (DT 9ª) | (absent — decimal implied) | 2020–2025 | |
| 1593 | re_at_rentas | `irpf_re_atrib_gp_dt9_reducciones` | Reducciones aplicables (DT 9ª) | (absent — decimal implied) | 2020–2025 | |
| 1594 | re_at_rentas | `irpf_re_atrib_gp_reducidas_no_exentas` | Ganancias patrimoniales reducidas no exentas ([1586]-[1589]-[1590]-[1591]-[1593]) | (absent — decimal implied) | 2020–2025 | |
| 1595 | re_at_rentas | `irpf_re_atrib_gp_reducidas_no_exentas_imputables` | Ganancias patrimoniales reducidas no exentas imputables al ejercicio | (absent — decimal implied) | 2020–2025 | Year-specific portion |
| 1596 | re_at_rentas | `irpf_re_atrib_gp_perdidas_transmision` | Pérdidas patrimoniales atribuidas por la entidad | (absent — decimal implied) | 2020–2025 | Losses from transmissions |

**Retenciones atribuidas:**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1597 | re_at_rentas | `irpf_re_atrib_retenciones_cap_mob` | Atribución de retenciones de rendimientos de capital mobiliario | (absent — decimal implied) | 2020–2025 | |
| 1598 | re_at_rentas | `irpf_re_atrib_retenciones_cap_inmo` | Atribución de retenciones de rendimientos de capital inmobiliario | (absent — decimal implied) | 2020–2025 | |
| 1599 | re_at_rentas | `irpf_re_atrib_retenciones_act_eco` | Atribución de retenciones de rendimientos de actividades económicas | (absent — decimal implied) | 2020–2025 | |
| 1600 | re_at_rentas | `irpf_re_atrib_retenciones_ganancias` | Atribución de retenciones de ganancias y pérdidas patrimoniales imputables | (absent — decimal implied) | 2020–2025 | |

**Inmueble fields (atribución entity property sub-form):**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1615 | re_at_rentas | `irpf_re_atrib_inmueble_pct_titularidad` | % Titularidad | (absent — decimal implied) | 2020–2025 | Ownership percentage of the property |
| 1616 | re_at_rentas | `irpf_re_atrib_inmueble_urbana_flag` | 'UR'.- Urbana | boolean | 2020–2025 | Urban property indicator |
| 1617 | re_at_rentas | `irpf_re_atrib_inmueble_rustica_flag` | 'RU'.- Rústica | boolean | 2020–2025 | Rural property indicator |
| 1618 | re_at_rentas | `irpf_re_atrib_inmueble_num_dias` | Nº de días | (absent — integer implied) | 2020–2025 | Days used during fiscal year |
| 1619 | re_at_rentas | `irpf_re_atrib_inmueble_situacion` | Situación | text | 2020–2025 | Usage situation key |
| 1620 | re_at_rentas | `irpf_re_atrib_inmueble_ref_catastral` | Referencia catastral | text | 2020–2025 | Cadastral reference |

**Atribución summary rows (resultados):**

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1601 | re_at_rentas_res | `irpf_re_atrib_suma_cap_mob_gral` | Suma rdtos. netos cap. mob. (BI general) atribuidos (suma [1568]) | decimal | 2020–2025 | |
| 1602 | re_at_rentas_res | `irpf_re_atrib_suma_cap_mob_ahorro` | Suma rdtos. netos cap. mob. (BI ahorro) atribuidos (suma [1569]) | decimal | 2020–2025 | |
| 1603 | re_at_rentas_res | `irpf_re_atrib_suma_deuda_subordinada` | Suma rdtos. deuda subordinada/participaciones preferentes (suma [1570]) | decimal | 2020–2025 | |
| 1604 | re_at_rentas_res | `irpf_re_atrib_suma_cap_inmo` | Suma rdtos. netos cap. inmobiliario atribuidos (suma [1575]) | decimal | 2020–2025 | |
| 1605 | re_at_rentas_res | `irpf_re_atrib_suma_act_eco` | Suma rdtos. netos actividades económicas atribuidos (suma [1583]) | decimal | 2020–2025 | |
| 1606 | re_at_rentas_res | `irpf_re_atrib_suma_gp_no_transmision_ganancias` | Suma ganancias pat. no transmisiones (BI gral), atribuidas (suma [1584]) | (absent — decimal implied) | 2020–2025 | |
| 1607 | re_at_rentas_res | `irpf_re_atrib_suma_gp_no_transmision_perdidas` | Suma pérdidas pat. no transmisiones (BI gral), atribuidas (suma [1585]) | (absent — decimal implied) | 2020–2025 | |
| 1608 | re_at_rentas_res | `irpf_re_atrib_suma_gp_transmision_ahorro` | Suma ganancias pat. transmisiones (BI ahorro), atribuidas (suma [1595]) | (absent — decimal implied) | 2020–2025 | |
| 1609 | re_at_rentas_res | `irpf_re_atrib_suma_gp_perdidas_ahorro` | Suma pérdidas pat. transmisiones (BI ahorro), atribuidas (suma [1596]) | (absent — decimal implied) | 2020–2025 | |

---

### D. AIE / UTE (`re_agrup_interes_economico`)

Already roled: 0257 (`investment_entity_nif`), 0259 (`base_imponible_irpf`). Remaining:

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0258 | re_agrup_interes_economico | `irpf_re_aie_criterio_imputacion_clave` | Criterio de imputación temporal. Clave | text | 2020–2025 | Temporal accrual criterion code |
| 0260 | re_agrup_interes_economico | `irpf_re_aie_deduccion_inversion_empresarial` | Deducciones por inversión empresarial (bases imputadas) | (absent — decimal implied) | 2020–2025 | |
| 0261 | re_agrup_interes_economico | `irpf_re_aie_deduccion_creacion_empleo` | Deducciones por creación de empleo (importe deducible imputado) | (absent — decimal implied) | 2020–2025 | |
| 0262 | re_agrup_interes_economico | `irpf_re_aie_deduccion_ceuta_melilla` | Deducción por rentas obtenidas en Ceuta o Melilla (base imputada) | (absent — decimal implied) | 2020–2025 | |
| 0263 | re_agrup_interes_economico | `irpf_re_aie_deduccion_doble_imposicion` | Deducción por doble imposición internacional (base imputada) | (absent — decimal implied) | 2020–2025 | |
| 0264 | re_agrup_interes_economico | `irpf_re_aie_retenciones_imputadas` | Retenciones e ingresos a cuenta imputados | (absent — decimal implied) | 2020–2025 | |
| 0265 | re_agrup_interes_economico_res | `irpf_re_aie_suma_bases_imponibles` | Suma de bases imponibles imputadas (suma [0259]) | decimal | 2020–2025 | Aggregate computed total |

---

### E. Transparencia fiscal internacional (`re_tr_fiscal_inter`)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0268 | re_tr_fiscal_inter | `irpf_re_tfi_entidad_denominacion` | Denominación de la entidad no residente participada | text | 2020–2025 | Non-resident entity name |
| 0269 | re_tr_fiscal_inter | `irpf_re_tfi_imputacion_importe` | Importe de la imputación | (absent — decimal implied) | 2020–2025 | |
| 0270 | re_tr_fiscal_inter_res | `irpf_re_tfi_suma_imputaciones` | Suma de imputaciones de rentas en transparencia fiscal internacional (suma [0269]) | (absent — decimal implied) | 2020–2025 | Aggregate computed |

---

### F. Derechos de imagen (`re_derechos_imagen`)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0272 | re_derechos_imagen | `irpf_re_imagen_primera_cesionaria` | Primera cesionaria: NIF (si residente) o denominación | text | 2020–2025 | OQ-1 text; may hold NIF or foreign identifier |
| 0273 | re_derechos_imagen | `irpf_re_imagen_empleador` | Entidad con la que el contribuyente mantiene relación laboral: NIF o denominación | text | 2020–2025 | OQ-1 text; may hold NIF or foreign identifier |
| 0274 | re_derechos_imagen | `irpf_re_imagen_cantidad_imputar` | Cantidad a imputar | (absent — decimal implied) | 2020–2025 | |
| 0275 | re_derechos_imagen_res | `irpf_re_imagen_suma_imputaciones` | Suma de imputaciones de rentas por cesión de derechos de imagen | (absent — decimal implied) | 2020–2025 | Aggregate computed |

---

### G. Instituciones de inversión colectiva — paraísos fiscales (`re_institu_inversion_colectiva`)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0277 | re_institu_inversion_colectiva | `irpf_re_iic_denominacion` | Denominación de la Institución de Inversión Colectiva | text | 2020–2025 | |
| 0278 | re_institu_inversion_colectiva | `irpf_re_iic_imputacion_importe` | Importe de la imputación | (absent — decimal implied) | 2020–2025 | |
| 0280 | re_institu_inversion_colectiva_res | `irpf_re_iic_suma_imputaciones` | Suma de imputaciones IIC paraísos fiscales (suma [0278]) | (absent — decimal implied) | 2020–2025 | Aggregate computed |

---

## New roles introduced

All roles below are new; none currently appear in the taxonomy reference as of 2026-05-19.

### Estimación objetiva — non-agricultural
- `irpf_eo_actividad_iae_code` — IAE activity classification code
- `irpf_eo_cobros_pagos_flag` — cash-basis election flag (boolean)
- `irpf_eo_modulo_definicion` — module definition label (text; shared by 7 slots 1444-1462)
- `irpf_eo_modulo_num_unidades` — module unit count (shared by 7 slots 1445-1463)
- `irpf_eo_modulo_rdto_antes_amort` — module yield before amortisation (shared by 7 slots 1446-1464)
- `irpf_eo_rdto_neto_previo` — intermediate net yield before incentive minoraciones
- `irpf_eo_minoracion_empleo` — employment incentive reduction
- `irpf_eo_minoracion_inversion` — investment incentive reduction
- `irpf_eo_rdto_neto_minorado` — net yield after incentive minoraciones
- `irpf_eo_indice_corrector_especial` — special corrector index
- `irpf_eo_indice_corrector_pequena_dimension` — small-enterprise corrector
- `irpf_eo_indice_corrector_temporada` — seasonal corrector
- `irpf_eo_indice_corrector_exceso` — excess corrector
- `irpf_eo_indice_corrector_inicio` — new-activity start corrector
- `irpf_eo_rdto_neto_modulos` — net yield after all correctors
- `irpf_eo_reduccion_general` — general reduction
- `irpf_eo_gastos_extraordinarios` — extraordinary expenses
- `irpf_eo_otras_percepciones` — other business income perceptions
- `irpf_eo_reduccion_irregulares` — irregular-income / multi-year reduction
- `irpf_eo_rdto_neto_reducido` — final per-activity net yield
- `irpf_eo_reintegro_subvenciones` — subsidy reintegration (2025 only)
- `irpf_eo_suma_rdtos_netos_reducidos` — aggregate of per-activity 1481 rows
- `irpf_eo_reduccion_art_32_2_3` — portfolio reduction for certain activities (resultados)
- `irpf_eo_rdto_neto_reducido_total` — final EO non-agricultural aggregate

### Estimación objetiva — agricultural
- `irpf_eo_agr_ingresos_integros` — gross income per crop/livestock type
- `irpf_eo_agr_indice` — index code per product type (text)
- `irpf_eo_agr_rdto_base_producto` — base product yield per type
- `irpf_eo_agr_actividad_clave` — activity type code
- `irpf_eo_agr_cobros_pagos_flag` — cash-basis election flag (boolean)
- `irpf_eo_agr_total_ingresos` — total gross income aggregate
- `irpf_eo_agr_rdto_neto_previo` — net yield before amortisation
- `irpf_eo_agr_amortizacion` — amortisation of fixed assets
- `irpf_eo_agr_rdto_neto_minorado` — after amortisation
- `irpf_eo_agr_indice_medios_ajenos` — corrector: external production means
- `irpf_eo_agr_indice_personal_asalariado` — corrector: salaried staff
- `irpf_eo_agr_indice_tierras_arrendadas` — corrector: leased land
- `irpf_eo_agr_indice_piensos_terceros` — corrector: third-party feed >50% (text)
- `irpf_eo_agr_indice_ecologica` — corrector: organic farming
- `irpf_eo_agr_indice_regadio_electrico` — corrector: irrigated electric-energy crops
- `irpf_eo_agr_indice_pequena_empresa` — corrector: small-income enterprise
- `irpf_eo_agr_indice_forestal` — corrector: forest activities
- `irpf_eo_agr_rdto_neto_modulos` — net yield after all correctors
- `irpf_eo_agr_reduccion_general` — general reduction
- `irpf_eo_agr_diferencia_reduccion` — post-general-reduction subtraction
- `irpf_eo_agr_reduccion_jovenes` — young-farmer reduction
- `irpf_eo_agr_gastos_extraordinarios` — extraordinary expenses
- `irpf_eo_agr_reduccion_irregulares` — irregular-income / multi-year reduction
- `irpf_eo_agr_rdto_neto_reducido` — final per-activity net yield
- `irpf_eo_agr_reintegro_subvenciones` — subsidy reintegration (2025 only)
- `irpf_eo_agr_suma_rdtos_netos_reducidos` — aggregate of per-activity 1555 rows
- `irpf_eo_agr_reduccion_art_32_2_3` — portfolio reduction for certain activities
- `irpf_eo_agr_rdto_neto_reducido_total` — final EO agricultural aggregate

### Atribución de rentas
- `irpf_re_atrib_entidad_nif` — entity NIF (OQ-1 deferred text type)
- `irpf_re_atrib_entidad_nif_extranjero_flag` — companion boolean for foreign NIF
- `irpf_re_atrib_entidad_nif_alt` — alternative entity NIF slot for non-residents
- `irpf_re_atrib_pct_participacion` — taxpayer participation percentage
- `irpf_re_atrib_cobros_pagos_flag` — cash-basis election flag
- `irpf_re_atrib_tipo_regimen_agricola_flag` — agricultural regime type flag (2025 only)
- `irpf_re_atrib_tipo_regimen_resto_flag` — other regime type flag (2025 only)
- `irpf_re_atrib_reduccion_actividades_artisticas` — artistic activities reduction (2025 only)
- `irpf_re_atrib_cap_mob_rdto_neto_entidad` — capital mobiliario net yield from entity
- `irpf_re_atrib_cap_mob_minoraciones` — capital mobiliario minoraciones
- `irpf_re_atrib_cap_mob_reducciones_26_2` — capital mobiliario art.26.2 reductions
- `irpf_re_atrib_cap_mob_rdto_neto_computable_gral` — capital mobiliario BI-general computable
- `irpf_re_atrib_cap_mob_rdto_neto_computable_ahorro` — capital mobiliario BI-ahorro computable
- `irpf_re_atrib_deuda_subordinada` — subordinated debt / preferred shares income
- `irpf_re_atrib_cap_inmo_rdto_neto_entidad` — capital inmobiliario net yield from entity
- `irpf_re_atrib_cap_inmo_minoraciones` — capital inmobiliario minoraciones
- `irpf_re_atrib_cap_inmo_reduccion_23_2` — capital inmobiliario art.23.2 reduction
- `irpf_re_atrib_cap_inmo_reducciones_23_3` — capital inmobiliario arts.23.3/DT25 reductions
- `irpf_re_atrib_cap_inmo_rdto_neto_computable` — capital inmobiliario net computable
- `irpf_re_atrib_act_eco_minoraciones` — actividades económicas minoraciones
- `irpf_re_atrib_act_eco_provisiones_difícil` — actividades económicas provisions/difícil justificación
- `irpf_re_atrib_act_eco_reduccion_32_1` — actividades económicas art.32.1 reduction
- `irpf_re_atrib_act_eco_reduccion_32_2_3` — actividades económicas art.32.2.3 reduction
- `irpf_re_atrib_act_eco_reduccion_32_3` — actividades económicas art.32.3 reduction
- `irpf_re_atrib_act_eco_rdto_neto_computable` — actividades económicas net computable
- `irpf_re_atrib_gp_no_transmision_ganancias` — non-transmission gains (BI general)
- `irpf_re_atrib_gp_no_transmision_perdidas` — non-transmission losses (BI general)
- `irpf_re_atrib_gp_transmision_ganancias` — transmission gains
- `irpf_re_atrib_gp_renta_vitalicia` — reinvestment-in-annuity exempt base
- `irpf_re_atrib_gp_dt9_valor_transmision` — DT 9ª transitional value
- `irpf_re_atrib_gp_exentas_50pct` — 50% urban property exemption
- `irpf_re_atrib_gp_exentas_reinversion_vitalicia` — annuity-reinvestment exemption
- `irpf_re_atrib_gp_exentas_reinversion_nuevas` — new-entity reinvestment exemption
- `irpf_re_atrib_gp_dt9_susceptibles_reduccion` — DT 9ª reducible portion
- `irpf_re_atrib_gp_dt9_reducciones` — DT 9ª applied reductions
- `irpf_re_atrib_gp_reducidas_no_exentas` — reduced non-exempt gains
- `irpf_re_atrib_gp_reducidas_no_exentas_imputables` — year-specific reduced non-exempt gains
- `irpf_re_atrib_gp_perdidas_transmision` — transmission losses
- `irpf_re_atrib_retenciones_cap_mob` — attributed capital mobiliario withholding
- `irpf_re_atrib_retenciones_cap_inmo` — attributed capital inmobiliario withholding
- `irpf_re_atrib_retenciones_act_eco` — attributed actividades económicas withholding
- `irpf_re_atrib_retenciones_ganancias` — attributed ganancias patrimoniales withholding
- `irpf_re_atrib_inmueble_pct_titularidad` — property ownership percentage
- `irpf_re_atrib_inmueble_urbana_flag` — urban property flag (boolean)
- `irpf_re_atrib_inmueble_rustica_flag` — rural property flag (boolean)
- `irpf_re_atrib_inmueble_num_dias` — days used
- `irpf_re_atrib_inmueble_situacion` — usage situation key (text)
- `irpf_re_atrib_inmueble_ref_catastral` — cadastral reference (text)
- `irpf_re_atrib_suma_cap_mob_gral` — aggregate capital mobiliario BI-general
- `irpf_re_atrib_suma_cap_mob_ahorro` — aggregate capital mobiliario BI-ahorro
- `irpf_re_atrib_suma_deuda_subordinada` — aggregate subordinated debt income
- `irpf_re_atrib_suma_cap_inmo` — aggregate capital inmobiliario
- `irpf_re_atrib_suma_act_eco` — aggregate actividades económicas
- `irpf_re_atrib_suma_gp_no_transmision_ganancias` — aggregate non-transmission gains
- `irpf_re_atrib_suma_gp_no_transmision_perdidas` — aggregate non-transmission losses
- `irpf_re_atrib_suma_gp_transmision_ahorro` — aggregate transmission gains (BI ahorro)
- `irpf_re_atrib_suma_gp_perdidas_ahorro` — aggregate transmission losses (BI ahorro)

### AIE / UTE
- `irpf_re_aie_criterio_imputacion_clave` — temporal accrual criterion code
- `irpf_re_aie_deduccion_inversion_empresarial` — investment deduction base (imputada)
- `irpf_re_aie_deduccion_creacion_empleo` — employment creation deduction (imputada)
- `irpf_re_aie_deduccion_ceuta_melilla` — Ceuta/Melilla deduction (imputada)
- `irpf_re_aie_deduccion_doble_imposicion` — international double taxation deduction (imputada)
- `irpf_re_aie_retenciones_imputadas` — attributed withholding and payments on account
- `irpf_re_aie_suma_bases_imponibles` — aggregate base imponible imputada

### Transparencia fiscal internacional
- `irpf_re_tfi_entidad_denominacion` — non-resident entity name (text)
- `irpf_re_tfi_imputacion_importe` — imputed income amount
- `irpf_re_tfi_suma_imputaciones` — aggregate imputed income (computed)

### Derechos de imagen
- `irpf_re_imagen_primera_cesionaria` — first assignee entity (OQ-1 text; NIF or foreign ID)
- `irpf_re_imagen_empleador` — employer entity (OQ-1 text; NIF or foreign ID)
- `irpf_re_imagen_cantidad_imputar` — amount to impute
- `irpf_re_imagen_suma_imputaciones` — aggregate image-right imputed income (computed)

### Instituciones de inversión colectiva — paraísos fiscales
- `irpf_re_iic_denominacion` — IIC entity name (text)
- `irpf_re_iic_imputacion_importe` — imputed income amount
- `irpf_re_iic_suma_imputaciones` — aggregate IIC paraísos fiscal imputed income (computed)

**Total new roles: 108**

---

## Cross-revision id-reuse hazards

### Critical — IDs 0157, 0158, 0159, 0160: three-way concept collision

| id | revision | section | concept |
|---|---|---|---|
| 0157 | 2021 | toma_datos_ampliada / inmuebles / inmueble | Gasto deducible alquileres locales (COVID Real Decreto-ley 35/2020) — property deduction amount |
| 0157 | 2022–2024 | toma_datos_ampliada / reg_estima_obj / actividad_est_obj | Reducción para actividades económicas Isla de La Palma (Canarias) — módulos reduction |
| 0157 | 2025 | toma_datos_ampliada / reg_estima_obj_agricola / actividad_agr | Producción de mejillón en batea: Ingresos íntegros — agricultural gross income |

| id | revision | section | concept |
|---|---|---|---|
| 0158 | 2021 | toma_datos_ampliada / inmuebles / inmueble | NIF del arrendatario — tenant NIF (nif type) |
| 0158 | 2022–2024 | reg_estima_obj_agricola | Reducción por adquisición de gasóleo agrícola — fuel subsidy reduction |
| 0158 | 2025 | reg_estima_obj_agricola | Índice (product index code — text) |

| id | revision | section | concept |
|---|---|---|---|
| 0159 | 2022–2024 | reg_estima_obj_agricola | Reducción por adquisición de fertilizantes — fertiliser subsidy reduction |
| 0159 | 2025 | reg_estima_obj_agricola | Rendimiento base producto — base product yield |

| id | revision | section | concept |
|---|---|---|---|
| 0160 | 2022–2024 | reg_estima_obj_agricola | Reducción para actividades económicas Isla de La Palma (Canarias) — agricultural reduction |
| 0160 | 2025 | reg_estima_obj_agricola | 9. Índice corrector de producción de mejillón en batea — corrector index |

**Resolution:** Do NOT assign a single cross-revision role to 0157, 0158, 0159, or 0160.
Assign revision-scoped roles:
- 0157 in 2021: `irpf_inmueble_gastos_covid_alquileres` (or defer to the inmuebles cluster audit)
- 0157 in 2022–2024: `irpf_eo_reduccion_la_palma`
- 0157 in 2025: `irpf_eo_agr_ingresos_integros` (mejillón en batea row)
- 0158 in 2021: defer to inmuebles cluster (tenant_nif is already roled)
- 0158 in 2022–2024: `irpf_eo_agr_reduccion_gasoleo`
- 0158 in 2025: `irpf_eo_agr_indice`
- 0159 in 2022–2024: `irpf_eo_agr_reduccion_fertilizantes`
- 0159 in 2025: `irpf_eo_agr_rdto_base_producto`
- 0160 in 2022–2024: `irpf_eo_agr_reduccion_la_palma`
- 0160 in 2025: `irpf_eo_agr_indice_corrector_mejillon`

These four ids require per-revision role application; bulk-apply must NOT write a single
common role across all revisions.

---

### Critical — IDs 0161, 0162: two-way concept collision

| id | revision | section | concept | data_type |
|---|---|---|---|---|
| 0161 | 2024 | reg_estima_obj / actividad_est_obj | Reducción DANA (municipios RD-Ley 6/2024) — módulos reduction | (absent) |
| 0161 | 2025 | regimenes_especiales / re_at_rentas | Régimen estimación directa normal — activity regime flag | boolean |

| id | revision | section | concept | data_type |
|---|---|---|---|---|
| 0162 | 2024 | reg_estima_obj_agricola / actividad_agr | Reducción DANA (municipios RD-Ley 6/2024) — agricultural reduction | (absent) |
| 0162 | 2025 | regimenes_especiales / re_at_rentas | Régimen estimación directa simplificada — activity regime flag | boolean |

**Resolution:**
- 0161 in 2024: `irpf_eo_reduccion_dana`
- 0161 in 2025: `irpf_re_atrib_tipo_regimen_directa_normal_flag`
- 0162 in 2024: `irpf_eo_agr_reduccion_dana`
- 0162 in 2025: `irpf_re_atrib_tipo_regimen_directa_simplificada_flag`

---

### Moderate — ID 1476: section migration to CCAA deduccion in 2025

| revision | section | concept |
|---|---|---|
| 2020–2024 | reg_estima_obj / actividad_est_obj | Reducción Lorca (Murcia) — módulos reduction for earthquake zone |
| 2025 | resultados / deduccion_autonomica_res / andalucia_res | Para familias con enfermedad celíaca — Andalucía autonomous deduction |

This id is **outside our cluster in 2025** (it lives in deduccion_autonomica_res/andalucia_res)
but IS within our cluster in 2020–2024. The 2025 reassignment to an unrelated concept in a
different section is a severe semantic change. The bulk-apply pass must:
- Assign `irpf_eo_reduccion_lorca` to 1476 in revisions 2020–2024 only
- Leave 2025's 1476 for the deduccion_autonomica cluster audit

---

### Moderate — ID 1553: section migration from reg_estima_obj_agricola to rendimientos

| revision | section | concept |
|---|---|---|
| 2020 | reg_estima_obj_agricola / actividad_agr | Rendimiento neto de la actividad (per-activity agricultural summary) |
| 2021–2025 | rendimientos_actividades_economicas | Rendimiento neto actividades agrícolas, ganaderas y forestales (module-level aggregate) |

Labels are closely related (same concept, different aggregation level). Section change is
structural rather than semantic, but the exact granularity differs (per-activity row in 2020
vs. global aggregate in 2021+). Do NOT assign a common cross-revision role. Assign
`irpf_eo_agr_rdto_neto_actividad` to the 2020-only occurrence. The 2021–2025 occurrence in
`rendimientos_actividades_economicas` is outside this cluster's scope.

---

### Informational — IDs 0238, 0239: new in 2025 only

0238 (`irpf_eo_reintegro_subvenciones`) and 0239 (`irpf_eo_agr_reintegro_subvenciones`) are
present only in 2025. Single-occurrence roles. The typo-twin warning will fire at registry
load; this is expected and documented here.

---

### Informational — IDs 0163, 0164, 0384: new in 2025 only

0163, 0164, 0384 are present only in 2025 within this cluster. Their roles are documented
above; single-occurrence typo-twin warnings are expected.

---

## Decimal / money divergences

All monetary fields in this cluster declare `data_type = "decimal"` (where declared) or
have `data_type` absent (which the registry infers as decimal for M100 IRPF fields). There
are **no `data_type = "money"` declarations** in this cluster across any of the 2020–2025
revisions. No decimal/money divergence requiring flag.

The absent-type casillas (majority of this cluster) should be confirmed as `decimal` by the
bulk-apply pass before writing roles, consistent with the M100 IRPF convention documented
in the taxonomy reference.

---

## Already-roled casillas (skip list)

| id | existing_role | reason |
|---|---|---|
| 0257 | `investment_entity_nif` | Roled in prior NIF audit pass |
| 0259 | `base_imponible_irpf` | Roled in prior monetary audit pass |

---

## Bulk-apply acceptance notes

- **108 new roles** proposed.
- **4 hard hazard IDs** (0157, 0158, 0159, 0160): require per-revision application; bulk-apply
  must use revision-scoped selectors.
- **2 moderate hazard IDs** (0161, 0162): require per-revision application (2024 vs. 2025).
- **1 moderate hazard ID** (1476): apply only to revisions 2020–2024; skip 2025.
- **1 informational hazard ID** (1553): apply only to revision 2020; skip 2021–2025.
- Absent-`data_type` casillas in this cluster should be confirmed as `decimal` before
  writing; the registry will reject a mismatch between inferred type and the bulk-applied
  role's canonical type.
- The re_at_rentas casillas 1562/1621/1563/1622 use `data_type = "text"` (not `"nif"`) due
  to the OQ-1 deferred foreign-NIF pattern; their roles use `irpf_re_atrib_entidad_nif*`
  naming but do NOT claim `nif` type. This is consistent with existing OQ-1 handling.
