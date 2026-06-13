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

# `schema-hardening` audit: M100 `toma_datos_ampliada.inmuebles` cluster role assignment

## Scope

2025 revision of M100 IRPF: `toma_datos_ampliada.inmuebles` section family,
128 casillas total. 9 already carry `semantic_role` (8 NIF roles assigned by
prior NIF audit pass + 1 OQ-1 boolean companion already roled). 119 unroled
casillas classified in this audit. All 128 ids are present in all 6 revisions
(2020–2025) with no section-path drift.

---

## Per-id role-assignment table

The filename prefix encodes the 2025 sequential slot; the id column is the
canonical casilla id (stable across revisions). Already-roled rows are
included for completeness and marked **roled-prior**.

| id | section (leaf) | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0063 | inmueble | `irpf_inmueble_porcentaje_propiedad` | Propiedad (%) | decimal (absent) | 2020–2025 | Ownership percentage of the property |
| 0064 | inmueble | `irpf_inmueble_porcentaje_usufructo` | Usufructo (%) | decimal (absent) | 2020–2025 | Usufruct percentage |
| 0065 | inmueble | `irpf_inmueble_situacion_clave` | Situación (clave) | text | 2020–2025 | AEAT situación code: 1=own-use, 2=let, 3=other; minor whitespace diff in 2020 label only |
| 0066 | inmueble | `irpf_inmueble_referencia_catastral` | Referencia Catastral | text | 2020–2025 | 20-char cadastral reference |
| 0067 | inmueble | `irpf_inmueble_naturaleza_urbana` | Urbana | boolean | 2020–2025 | Flag: urban property |
| 0068 | inmueble | `irpf_inmueble_naturaleza_rustica` | Rústica | boolean | 2020–2025 | Flag: rustic/agricultural property |
| 0069 | inmueble | `irpf_inmueble_direccion` | Dirección | text | 2020–2025 | Free-text address of the property |
| 0070 | inmueble | `irpf_inmueble_vivienda_habitual_flag` | Vivienda habitual en {ejercicio} | boolean | 2020–2025 | Year-parameterised label (normal rolling); stable role |
| 0071 | inmueble | `irpf_inmueble_uso_residencia_separacion` | Vivienda en que residen hijos y/o excónyuge | boolean | 2020–2025 | Separation/divorce scenario flag |
| 0072 | inmueble | `irpf_inmueble_afecto_actividades_economicas_flag` | Inmueble afecto a actividades económicas | boolean | 2020–2025 | Flag: property linked to economic activity |
| 0073 | inmueble | `irpf_inmueble_a_disposicion_flag` | A disposición de sus titulares | boolean | 2020–2025 | Flag: available to owners (imputed-income trigger) |
| 0074 | inmueble | `irpf_inmueble_arrendamiento_accesorio_flag` | Arrendamiento como inmueble accesorio | boolean | 2020–2025 | Flag: let as accessory to main property |
| 0075 | inmueble | `irpf_inmueble_arrendamiento_flag` | Arrendamiento | boolean | 2020–2025 | Flag: property is let |
| 0076 | inmueble | `irpf_inmueble_dias_vivienda_habitual` | Número de días vivienda habitual | decimal (absent) | 2020–2025 | Year-parameterised label (normal rolling) |
| **0077** | inmueble | **`spouse_or_foreign_id_nif`** | NIF del excónyuge | text | 2020–2025 | **roled-prior** — OQ-1 text NIF |
| 0078 | inmueble | `irpf_inmueble_exconyuge_nif_extranjero_flag` | Marque X si [0077] contiene NIF de otro país | boolean | 2020–2025 | OQ-1 companion boolean for 0077 |
| 0079 | inmueble | `irpf_inmueble_dias_uso_vivienda_habitual_conyuge` | Número de días este uso (vivienda habitual excónyuge) | decimal (absent) | 2020–2025 | Days sub-field for cónyuge use |
| 0080 | inmueble | `irpf_inmueble_dias_afecto_actividades_economicas` | Número de días uso: afecto actividades económicas | decimal (absent) | 2020–2025 | Year-parameterised label 2021 template artefact; stable role |
| 0081 | inmueble | `irpf_inmueble_contribuyente_actividad_economica` | Contribuyente que realiza la actividad económica | text | 2020–2025 | Identifier token (D/C) for which declarant uses the property for economic activity |
| 0082 | inmueble | `irpf_inmueble_arrendamiento_negocio_flag` | Bien inmueble objeto de arrendamiento de negocio | decimal (absent) | 2020–2025 | Flag (binary integer) for business-lease context |
| 0083 | inmueble | `irpf_inmueble_valor_catastral` | Valor catastral | decimal (absent) | 2020–2025 | Cadastral value — main use slot |
| 0084 | inmueble | `irpf_inmueble_valor_catastral_revisado_flag` | Valor catastral revisado/modificado/colectivo | text | 2020–2025 | Código clave: S/N/revision-year indicator |
| 0085 | inmueble | `irpf_inmueble_dias_a_disposicion` | Número de días a disposición del contribuyente | decimal (absent) | 2020–2025 | Days at owner disposal (imputed income basis) |
| 0086 | inmueble | `irpf_inmueble_uso_mixto_flag` | Caso excepcional: inmueble parte a disposición parte otros usos mismo día | boolean | 2020–2025 | Mixed-use same-day exception flag |
| 0087 | inmueble | `irpf_inmueble_pct_a_disposicion` | Porcentaje (%) inmueble a disposición | decimal (absent) | 2020–2025 | Mixed-use split percentage |
| 0088 | inmueble | `irpf_inmueble_dias_otros_usos` | Número de días (otros usos dentro uso mixto) | decimal (absent) | 2020–2025 | Days in other use within mixed-use split |
| 0090 | inmueble | `irpf_inmueble_referencia_catastral_principal` | Referencia catastral inmueble principal vinculado | text | 2020–2025 | Accessory property's link to principal cadastral ref |
| **0091** | inmueble | **`tenant_or_foreign_id_nif`** | NIF del arrendatario 1 (*) | text | 2020–2025 | **roled-prior** — OQ-1 text NIF |
| 0092 | inmueble | `irpf_inmueble_arrendatario1_nif_extranjero_flag` | Marque X si [0091] contiene NIF de otro país | boolean | 2020–2025 | OQ-1 companion boolean for 0091 |
| 0093 | inmueble | `irpf_inmueble_fecha_contrato_arrendamiento` | Fecha del contrato (*) | text | 2020–2025 | Contract date (DD/MM/YYYY text) — 2021 has template artefact in label |
| **0094** | inmueble | **`tenant_or_foreign_id_nif`** | NIF del arrendatario 2 (*) | text | 2020–2025 | **roled-prior** — OQ-1 text NIF |
| 0095 | inmueble | `irpf_inmueble_arrendatario2_nif_extranjero_flag` | Marque X si [0094] contiene NIF de otro país | boolean | 2020–2025 | OQ-1 companion boolean for 0094 |
| **0097** | inmueble | **`tenant_or_foreign_id_nif`** | NIF del arrendatario 3 (*) | text | 2020–2025 | **roled-prior** — OQ-1 text NIF |
| 0098 | inmueble | `irpf_inmueble_arrendatario3_nif_extranjero_flag` | Marque X si [0097] contiene NIF de otro país | boolean | 2020–2025 | OQ-1 companion boolean for 0097 |
| 0100 | inmueble | `irpf_inmueble_arrendamiento_reduccion_flag` | Marque con X — reducción aplicable arrendamiento | boolean | 2020–2025 | Reduction-eligibility flag for residential letting |
| 0101 | inmueble | `irpf_inmueble_dias_arrendado` | Número de días arrendado | decimal (absent) | 2020–2025 | Days let (main arrendamiento sub-block) |
| 0103 | inmueble | `irpf_inmueble_gastos_financiacion_pendientes_previos` | Importe pendiente deducir ejercicios anteriores | decimal (absent) | 2020–2025 | Rolling 4-year carry-forward label; stable role |
| 0105 | inmueble | `irpf_inmueble_gastos_financiacion_ejercicio` | Intereses capitales + gastos financiación ejercicio | decimal (absent) | 2020–2025 | Current-year financing costs |
| 0106 | inmueble | `irpf_inmueble_gastos_reparacion_conservacion` | Gastos reparación y conservación ejercicio | decimal (absent) | 2020–2025 | Year-parameterised label; repair/maintenance costs |
| 0108 | inmueble | `irpf_inmueble_gastos_financiacion_pendientes_futuros` | Importe ejercicio pendiente deducir 4 años siguientes | decimal (absent) | 2020–2025 | Rolling year label; future 4-year carry-forward |
| 0118 | inmueble | `irpf_inmueble_adquisicion_tipo_onerosa` | Onerosa (compraventa, permuta, etc.) | boolean | 2020–2025 | Acquisition type: onerous |
| 0119 | inmueble | `irpf_inmueble_adquisicion_tipo_lucrativa` | Lucrativa (herencia, legado, donación, etc.) | boolean | 2020–2025 | Acquisition type: gratuitous — **see hazard note on 0134** |
| 0120 | inmueble | `irpf_inmueble_fecha_adquisicion` | Fecha de adquisición del inmueble | text | 2020–2025 | Acquisition date (DD/MM/YYYY) |
| 0121 | inmueble | `irpf_inmueble_fecha_transmision` | Fecha de transmisión en el ejercicio | text | 2020–2025 | Year-parameterised label; disposal date |
| 0122 | inmueble | `irpf_inmueble_dias_arrendado` | Número de días arrendado (arrendamiento accesorio block) | decimal (absent) | 2020–2025 | Parallel arrendamiento-accesorio sub-block; reuses same role as 0101 |
| 0123 | inmueble | `irpf_inmueble_valor_catastral` | Valor catastral (arrendamiento accesorio block) | decimal (absent) | 2020–2025 | Parallel cadastral value slot; reuses same role as 0083 |
| 0124 | inmueble | `irpf_inmueble_valor_catastral_construccion` | Valor catastral de la construcción | decimal (absent) | 2020–2025 | Construction-element of cadastral value |
| 0125 | inmueble | `irpf_inmueble_pct_valor_catastral_construccion` | (Valor catastral construcción / valor catastral) × 100 | decimal (absent) | 2020–2025 | Construction ratio % (amortization base input) |
| 0126 | inmueble | `irpf_inmueble_importe_adquisicion` | Importe de adquisición | decimal (absent) | 2020–2025 | Acquisition cost |
| 0127 | inmueble | `irpf_inmueble_gastos_tributos_adquisicion` | Gastos y tributos inherentes a la adquisición | decimal (absent) | 2020–2025 | Acquisition taxes and fees |
| 0128 | inmueble | `irpf_inmueble_mejoras_previas` | Importe mejoras realizadas en años anteriores | decimal (absent) | 2020–2025 | Prior-year improvements (cumulative) |
| 0129 | inmueble | `irpf_inmueble_mejoras_ejercicio` | Importe mejoras realizadas en el ejercicio | decimal (absent) | 2020–2025 | Year-parameterised label; current-year improvements |
| 0130 | inmueble | `irpf_inmueble_base_amortizacion` | Base de la amortización | decimal (absent) | 2020–2025 | Amortization base |
| 0133 | inmueble | `irpf_inmueble_adquisicion_tipo_onerosa` | Onerosa (compraventa, permuta, etc.) | boolean | 2020–2025 | Accessory-block acquisition type: onerous — reuses role from 0118 |
| 0134 | inmueble | `irpf_inmueble_adquisicion_tipo_lucrativa` | Lucrativa (herencia, legado, donación, etc.) | boolean | 2020–2025 | Accessory-block acquisition type: gratuitous — **hazard**: label in 2020 was "Onerosa" (duplicate with 0133); corrected in 2021+ to "Lucrativa". Role reflects 2021–2025 intent; bulk-apply must confirm 2020 label before writing role to 2020 revision file. |
| 0135 | inmueble | `irpf_inmueble_fecha_adquisicion` | Fecha de adquisición del inmueble (accesorio) | text | 2020–2025 | Accessory-block acquisition date; reuses role from 0120 |
| 0136 | inmueble | `irpf_inmueble_fecha_transmision` | Fecha de transmisión en el ejercicio (accesorio) | text | 2020–2025 | Year-parameterised label; accessory-block disposal date |
| 0137 | inmueble | `irpf_inmueble_dias_arrendado` | Número de días arrendado (accesorio) | decimal (absent) | 2020–2025 | Third slot reusing same role as 0101/0122 |
| 0138 | inmueble | `irpf_inmueble_valor_catastral` | Valor catastral (accesorio) | decimal (absent) | 2020–2025 | Third slot reusing same role as 0083/0123 |
| 0139 | inmueble | `irpf_inmueble_valor_catastral_construccion` | Valor catastral de la construcción (accesorio) | decimal (absent) | 2020–2025 | Reuses role from 0124 |
| 0140 | inmueble | `irpf_inmueble_pct_valor_catastral_construccion` | (VC construcción / VC) × 100 (accesorio) | decimal (absent) | 2020–2025 | Reuses role from 0125 |
| 0141 | inmueble | `irpf_inmueble_importe_adquisicion` | Importe de adquisición (accesorio) | decimal (absent) | 2020–2025 | Reuses role from 0126 |
| 0142 | inmueble | `irpf_inmueble_gastos_tributos_adquisicion` | Gastos y tributos adquisición (accesorio) | decimal (absent) | 2020–2025 | Reuses role from 0127 |
| 0143 | inmueble | `irpf_inmueble_mejoras_previas` | Importe mejoras años anteriores (accesorio) | decimal (absent) | 2020–2025 | Reuses role from 0128 |
| 0144 | inmueble | `irpf_inmueble_mejoras_ejercicio` | Importe mejoras en el ejercicio (accesorio) | decimal (absent) | 2020–2025 | Year-parameterised label; reuses role from 0129 |
| 0145 | inmueble | `irpf_inmueble_base_amortizacion` | Base de la amortización (accesorio) | decimal (absent) | 2020–2025 | Reuses role from 0130 |
| 1211 | inmueble | `irpf_inmueble_contribuyente_titular` | Contribuyente titular | text | 2020–2025 | D/C token identifying which declarant; Anexo C.1 header |
| 1212 | inmueble | `irpf_inmueble_referencia_catastral` | Referencia catastral | text | 2020–2025 | Reuses role from 0066 — Anexo C.1 header |
| 1213 | inmueble | `irpf_inmueble_gastos_pendientes_inicio_periodo` | Ejercicio N-4: Pendiente al principio del periodo | decimal (absent) | 2020–2025 | Rolling year label; oldest carry-forward opening balance |
| 1214 | inmueble | `irpf_inmueble_gastos_aplicados_declaracion` | Ejercicio N-4: Aplicado en esta declaración | decimal (absent) | 2020–2025 | Rolling year label; amount applied from oldest bucket |
| 1215 | inmueble | `irpf_inmueble_gastos_pendientes_inicio_periodo` | Ejercicio N-3: Pendiente al principio del periodo | decimal (absent) | 2020–2025 | Same role as 1213 — N-3 slot |
| 1216 | inmueble | `irpf_inmueble_gastos_aplicados_declaracion` | Ejercicio N-3: Aplicado en esta declaración | decimal (absent) | 2020–2025 | Same role as 1214 — N-3 slot |
| 1217 | inmueble | `irpf_inmueble_gastos_pendientes_futuros_periodo` | Ejercicio N-3: Pendiente en ejercicios futuros | decimal (absent) | 2020–2025 | Remaining balance after application — N-3 slot |
| 1218 | inmueble | `irpf_inmueble_gastos_pendientes_inicio_periodo` | Ejercicio N-2: Pendiente al principio del periodo | decimal (absent) | 2020–2025 | N-2 slot |
| 1219 | inmueble | `irpf_inmueble_gastos_aplicados_declaracion` | Ejercicio N-2: Aplicado en esta declaración | decimal (absent) | 2020–2025 | N-2 slot |
| 1220 | inmueble | `irpf_inmueble_gastos_pendientes_futuros_periodo` | Ejercicio N-2: Pendiente en ejercicios futuros | decimal (absent) | 2020–2025 | N-2 slot |
| 1221 | inmueble | `irpf_inmueble_gastos_pendientes_inicio_periodo` | Ejercicio N-1: Pendiente al principio del periodo | decimal (absent) | 2020–2025 | N-1 slot |
| 1222 | inmueble | `irpf_inmueble_gastos_aplicados_declaracion` | Ejercicio N-1: Aplicado en esta declaración | decimal (absent) | 2020–2025 | N-1 slot |
| 1223 | inmueble | `irpf_inmueble_gastos_pendientes_futuros_periodo` | Ejercicio N-1: Pendiente en ejercicios futuros | decimal (absent) | 2020–2025 | N-1 slot |
| 1224 | inmueble | `irpf_inmueble_gastos_financiacion_ejercicio` | Ejercicio N: Intereses + gastos financiación | decimal (absent) | 2020–2025 | Reuses role from 0105 — Anexo C.1 current-year row |
| 1393 | inmueble | `irpf_inmueble_contribuyente_titular` | Contribuyente titular | text | 2020–2025 | Reuses role from 1211 — Anexo D header |
| 1394 | inmueble | `irpf_inmueble_referencia_catastral` | Referencia catastral | text | 2020–2025 | Reuses role from 0066 — Anexo D header |
| **1395** | inmueble | **`service_provider_nif`** | Gasto 1: NIF de quién realizó la obra o servicio | nif | 2020–2025 | **roled-prior** |
| 1396 | inmueble | `irpf_inmueble_gasto_reparacion_importe` | Gasto 1: Importe del gasto (reparación/conservación) | decimal (absent) | 2020–2025 | Expense line-item amount — Anexo D reparación block |
| **1397** | inmueble | **`service_provider_nif`** | Gasto 2: NIF de quién realizó la obra o servicio | nif | 2020–2025 | **roled-prior** |
| 1398 | inmueble | `irpf_inmueble_gasto_reparacion_importe` | Gasto 2: Importe del gasto | decimal | 2020–2025 | Reuses same role as 1396 |
| **1399** | inmueble | **`service_provider_nif`** | Gasto 3: NIF de quién realizó la obra o servicio | nif | 2020–2025 | **roled-prior** |
| 1400 | inmueble | `irpf_inmueble_gasto_reparacion_importe` | Gasto 3: Importe del gasto | decimal | 2020–2025 | Reuses same role |
| **1401** | inmueble | **`service_provider_nif`** | Gasto 4: NIF de quién realizó la obra o servicio | nif | 2020–2025 | **roled-prior** |
| 1402 | inmueble | `irpf_inmueble_gasto_reparacion_importe` | Gasto 4: Importe del gasto | decimal | 2020–2025 | Reuses same role |
| **1403** | inmueble | **`service_provider_nif`** | Gasto 5: NIF de quién realizó la obra o servicio | nif | 2020–2025 | **roled-prior** — 2020 label has duplicate prefix artefact |
| 1404 | inmueble | `irpf_inmueble_gasto_reparacion_importe` | Gasto 5: Importe del gasto | decimal | 2020–2025 | Reuses same role |
| 1405 | inmueble | `irpf_inmueble_gasto_reparacion_importe` | Resto de gastos (reparación block) | decimal | 2020–2025 | Residual bucket |
| 1406 | inmueble | `irpf_inmueble_gasto_financiacion_proveedor_nif` | Gasto 1: NIF de quién prestó el servicio (financiación) | text | 2020–2025 | OQ-1 deferred: data_type = text, may hold foreign fiscal ID |
| 1407 | inmueble | `irpf_inmueble_gasto_financiacion_importe` | Gasto 1: Importe del gasto (financiación) | decimal (absent) | 2020–2025 | Financing-expense line-item amount |
| 1408 | inmueble | `irpf_inmueble_gasto_financiacion_proveedor_nif` | Gasto 2: NIF de quién prestó el servicio (financiación) | text | 2020–2025 | OQ-1 deferred |
| 1409 | inmueble | `irpf_inmueble_gasto_financiacion_importe` | Gasto 2: Importe del gasto (financiación) | decimal | 2020–2025 | Reuses same role |
| 1410 | inmueble | `irpf_inmueble_gasto_financiacion_importe` | Resto de gastos (financiación block) | decimal | 2020–2025 | Residual bucket |
| 1411 | inmueble | `irpf_inmueble_gasto_financiacion_proveedor_nif` | Gasto 1: NIF de quién prestó el servicio (accesorio) | text | 2020–2025 | OQ-1 deferred — accessory-block financing |
| 1412 | inmueble | `irpf_inmueble_gasto_financiacion_importe` | Gasto 1: Importe (accesorio) | decimal (absent) | 2020–2025 | Reuses same role |
| 1413 | inmueble | `irpf_inmueble_gasto_financiacion_proveedor_nif` | Gasto 2: NIF de quién prestó el servicio (accesorio) | text | 2020–2025 | OQ-1 deferred |
| 1414 | inmueble | `irpf_inmueble_gasto_financiacion_importe` | Gasto 2: Importe (accesorio) | decimal (absent) | 2020–2025 | Reuses same role |
| 1415 | inmueble | `irpf_inmueble_gasto_financiacion_importe` | Resto de gastos (accesorio financiación) | decimal (absent) | 2020–2025 | Residual bucket |
| 1416 | inmueble | `irpf_inmueble_gasto_financiacion_proveedor_nif` | Gasto 1: NIF de quién prestó el servicio (block 3) | text | 2020–2025 | OQ-1 deferred |
| 1417 | inmueble | `irpf_inmueble_gasto_financiacion_importe` | Gasto 1: Importe (block 3) | decimal (absent) | 2020–2025 | Reuses same role |
| 1418 | inmueble | `irpf_inmueble_gasto_financiacion_proveedor_nif` | Gasto 2: NIF de quién prestó el servicio (block 3) | text | 2020–2025 | OQ-1 deferred |
| 1419 | inmueble | `irpf_inmueble_gasto_financiacion_importe` | Gasto 2: Importe (block 3) | decimal (absent) | 2020–2025 | Reuses same role |
| 1420 | inmueble | `irpf_inmueble_gasto_financiacion_importe` | Resto de gastos (block 3) | decimal (absent) | 2020–2025 | Residual bucket |
| 1421 | inmueble | `irpf_inmueble_mejora_fecha` | Mejora 1: Fecha de la realización | text | 2020–2025 | Improvement date — Anexo D mejoras block |
| 1422 | inmueble | `irpf_inmueble_mejora_proveedor_nif` | Mejora 1: NIF de quién realizó la obra | text | 2020–2025 | OQ-1 deferred: text NIF for improvement contractor |
| 1423 | inmueble | `irpf_inmueble_mejora_importe` | Mejora 1: Importe | decimal | 2020–2025 | Improvement amount |
| 1424 | inmueble | `irpf_inmueble_mejora_fecha` | Mejora 2: Fecha de la realización | text | 2020–2025 | Reuses role from 1421 |
| 1425 | inmueble | `irpf_inmueble_mejora_proveedor_nif` | Mejora 2: NIF de quién realizó la obra | text | 2020–2025 | OQ-1 deferred |
| 1426 | inmueble | `irpf_inmueble_mejora_importe` | Mejora 2: Importe | decimal | 2020–2025 | Reuses role |
| 1427 | inmueble | `irpf_inmueble_mejora_fecha` | Mejora 3: Fecha de la realización | text | 2020–2025 | Reuses role |
| 1428 | inmueble | `irpf_inmueble_mejora_proveedor_nif` | Mejora 3: NIF de quién realizó la obra | text | 2020–2025 | OQ-1 deferred |
| 1429 | inmueble | `irpf_inmueble_mejora_importe` | Mejora 3: Importe | decimal | 2020–2025 | Reuses role |
| 1430 | inmueble | `irpf_inmueble_mejora_importe` | Resto importes mejoras | decimal | 2020–2025 | Residual bucket; reuses same role |
| 1431 | inmueble | `irpf_inmueble_mejora_fecha` | Mejora 1: Fecha (accesorio block) | text | 2020–2025 | Reuses role |
| 1432 | inmueble | `irpf_inmueble_mejora_proveedor_nif` | Mejora 1: NIF (accesorio block) | text | 2020–2025 | OQ-1 deferred |
| 1433 | inmueble | `irpf_inmueble_mejora_importe` | Mejora 1: Importe (accesorio) | decimal (absent) | 2020–2025 | Reuses role |
| 1434 | inmueble | `irpf_inmueble_mejora_fecha` | Mejora 2: Fecha (accesorio) | text | 2020–2025 | Reuses role |
| 1435 | inmueble | `irpf_inmueble_mejora_proveedor_nif` | Mejora 2: NIF (accesorio) | text | 2020–2025 | OQ-1 deferred |
| 1436 | inmueble | `irpf_inmueble_mejora_importe` | Mejora 2: Importe (accesorio) | decimal (absent) | 2020–2025 | Reuses role |
| 1437 | inmueble | `irpf_inmueble_mejora_fecha` | Mejora 3: Fecha (accesorio) | text | 2020–2025 | Reuses role |
| 1438 | inmueble | `irpf_inmueble_mejora_proveedor_nif` | Mejora 3: NIF (accesorio) | text | 2020–2025 | OQ-1 deferred |
| 1439 | inmueble | `irpf_inmueble_mejora_importe` | Mejora 3: Importe (accesorio) | decimal (absent) | 2020–2025 | Reuses role |
| 1440 | inmueble | `irpf_inmueble_mejora_importe` | Resto importes mejoras (accesorio) | decimal (absent) | 2020–2025 | Reuses role |

---

## New roles introduced

All roles below are new — none appear in the canonical taxonomy reference as of 2026-05-19.
The `irpf_inmueble_*` prefix is the cluster-local namespace; roles that could generalise
across modelos use bare descriptors (the suffix after the prefix is portable).

| role | data_type | definition |
|---|---|---|
| `irpf_inmueble_porcentaje_propiedad` | decimal | Ownership percentage declared for a property in the IRPF inmuebles toma-datos block |
| `irpf_inmueble_porcentaje_usufructo` | decimal | Usufruct percentage for a property in the same block |
| `irpf_inmueble_situacion_clave` | text | AEAT situación code (1/2/3/4) classifying property use for imputed-income vs. let vs. other |
| `irpf_inmueble_referencia_catastral` | text | 20-character cadastral reference of the declared property |
| `irpf_inmueble_naturaleza_urbana` | boolean | Flag: property is classified as urban (urbana) |
| `irpf_inmueble_naturaleza_rustica` | boolean | Flag: property is classified as rustic/agricultural (rústica) |
| `irpf_inmueble_direccion` | text | Free-text postal address of the declared property |
| `irpf_inmueble_vivienda_habitual_flag` | boolean | Flag: property was the taxpayer's primary residence in the filing year |
| `irpf_inmueble_uso_residencia_separacion` | boolean | Flag: property is occupied by ex-spouse/children under separation/divorce ruling |
| `irpf_inmueble_afecto_actividades_economicas_flag` | boolean | Flag: property is linked to economic activity |
| `irpf_inmueble_a_disposicion_flag` | boolean | Flag: property was at the owner's disposal (triggers imputed-income calculation) |
| `irpf_inmueble_arrendamiento_accesorio_flag` | boolean | Flag: property is let as accessory to a main property |
| `irpf_inmueble_arrendamiento_flag` | boolean | Flag: property is let (arrendamiento) |
| `irpf_inmueble_dias_vivienda_habitual` | decimal | Number of days the property served as primary residence in the filing year |
| `irpf_inmueble_exconyuge_nif_extranjero_flag` | boolean | OQ-1 companion: marks that the ex-spouse NIF in [0077] is a foreign fiscal identifier |
| `irpf_inmueble_dias_uso_vivienda_habitual_conyuge` | decimal | Days the property was used as primary residence under ex-spouse occupancy |
| `irpf_inmueble_dias_afecto_actividades_economicas` | decimal | Days the property was devoted to economic activity |
| `irpf_inmueble_contribuyente_actividad_economica` | text | D/C token indicating which declarant carries the economic-activity use |
| `irpf_inmueble_arrendamiento_negocio_flag` | decimal | Binary-integer flag for business-lease (arrendamiento de negocio) scenario |
| `irpf_inmueble_valor_catastral` | decimal | Cadastral value (valor catastral) of the property |
| `irpf_inmueble_valor_catastral_revisado_flag` | text | Code indicating whether cadastral value has been reviewed/revised via collective valuation |
| `irpf_inmueble_dias_a_disposicion` | decimal | Number of days the property was at the owner's disposal (imputed-income basis) |
| `irpf_inmueble_uso_mixto_flag` | boolean | Exceptional mixed-use flag: property part at disposal, part other use, on same days |
| `irpf_inmueble_pct_a_disposicion` | decimal | Percentage of the property at owner disposal (mixed-use split) |
| `irpf_inmueble_dias_otros_usos` | decimal | Days in other use within a mixed-use split |
| `irpf_inmueble_referencia_catastral_principal` | text | Cadastral reference of the principal property to which an accessory is linked |
| `irpf_inmueble_arrendatario1_nif_extranjero_flag` | boolean | OQ-1 companion for arrendatario 1 NIF [0091] |
| `irpf_inmueble_fecha_contrato_arrendamiento` | text | Date of the rental contract (DD/MM/YYYY) |
| `irpf_inmueble_arrendatario2_nif_extranjero_flag` | boolean | OQ-1 companion for arrendatario 2 NIF [0094] |
| `irpf_inmueble_arrendatario3_nif_extranjero_flag` | boolean | OQ-1 companion for arrendatario 3 NIF [0097] |
| `irpf_inmueble_arrendamiento_reduccion_flag` | boolean | Flag marking eligibility for the residential-letting income reduction |
| `irpf_inmueble_dias_arrendado` | decimal | Number of days the property was let during the filing year |
| `irpf_inmueble_gastos_financiacion_pendientes_previos` | decimal | Carry-forward financing expense from prior years still pending deduction |
| `irpf_inmueble_gastos_financiacion_ejercicio` | decimal | Financing costs (interest + other) incurred in the current filing year |
| `irpf_inmueble_gastos_reparacion_conservacion` | decimal | Repair and maintenance costs for the filing year |
| `irpf_inmueble_gastos_financiacion_pendientes_futuros` | decimal | Current-year financing costs pending deduction in next 4 years |
| `irpf_inmueble_adquisicion_tipo_onerosa` | boolean | Acquisition type flag: onerous (purchase, exchange, etc.) |
| `irpf_inmueble_adquisicion_tipo_lucrativa` | boolean | Acquisition type flag: gratuitous (inheritance, legacy, gift, etc.) |
| `irpf_inmueble_fecha_adquisicion` | text | Property acquisition date (DD/MM/YYYY) |
| `irpf_inmueble_fecha_transmision` | text | Property disposal/transfer date in the filing year (DD/MM/YYYY) |
| `irpf_inmueble_valor_catastral_construccion` | decimal | Construction-element portion of cadastral value |
| `irpf_inmueble_pct_valor_catastral_construccion` | decimal | Ratio: (cadastral construction value / total cadastral value) × 100, used as amortization input |
| `irpf_inmueble_importe_adquisicion` | decimal | Total acquisition cost of the property |
| `irpf_inmueble_gastos_tributos_adquisicion` | decimal | Taxes and fees inherent in the acquisition |
| `irpf_inmueble_mejoras_previas` | decimal | Cumulative improvement costs from prior years |
| `irpf_inmueble_mejoras_ejercicio` | decimal | Improvement costs incurred in the filing year |
| `irpf_inmueble_base_amortizacion` | decimal | Amortization base (construction value portion of acquisition cost) |
| `irpf_inmueble_contribuyente_titular` | text | D/C token identifying which declarant is the titular owner (Anexo C.1/D header) |
| `irpf_inmueble_gastos_pendientes_inicio_periodo` | decimal | Carry-forward expense opening balance at start of a rolling prior-year slot |
| `irpf_inmueble_gastos_aplicados_declaracion` | decimal | Amount from a prior-year carry-forward bucket applied in this declaration |
| `irpf_inmueble_gastos_pendientes_futuros_periodo` | decimal | Remaining balance from a prior-year bucket still pending in future years |
| `irpf_inmueble_gasto_reparacion_importe` | decimal | Individual repair/maintenance expense line-item amount (Anexo D) |
| `irpf_inmueble_gasto_financiacion_proveedor_nif` | text | OQ-1 deferred: NIF of financing-service provider (may be foreign fiscal ID; data_type = text) |
| `irpf_inmueble_gasto_financiacion_importe` | decimal | Individual financing-expense line-item amount (Anexo D) |
| `irpf_inmueble_mejora_fecha` | text | Date a specific improvement was carried out |
| `irpf_inmueble_mejora_proveedor_nif` | text | OQ-1 deferred: NIF of improvement contractor (may be foreign fiscal ID; data_type = text) |
| `irpf_inmueble_mejora_importe` | decimal | Individual improvement line-item amount (Anexo D) |

**56 new roles total.**

---

## Cross-revision id-reuse hazards

### Soft hazard: 0134 — label typo in 2020 revision

| revision | label |
|---|---|
| 2020 | "Onerosa (compraventa, permuta, etc.)" |
| 2021–2025 | "Lucrativa (herencia, legado, donación, etc.)" |

In 2020, both `0133` and `0134` carry the label "Onerosa". This appears to be a
data-entry error in the 2020 source (the companion 0133 has always been "Onerosa"
in all revisions). The 2021–2025 label for 0134 is "Lucrativa", which is the
correct complementary type. The semantic content of the field has always been
gratuitous-acquisition (lucrativa) — the 2020 label is a source-file typo rather
than a genuine semantic change. The proposed role `irpf_inmueble_adquisicion_tipo_lucrativa`
is stable across all 6 revisions.

**Resolution:** Assign `irpf_inmueble_adquisicion_tipo_lucrativa` to 0134 in all
revisions. The bulk-apply pass should note the 2020 label mismatch in a comment
or alias entry so the inconsistency is documented at the casilla level.

### Not a hazard: year-rolling labels

The following casillas have labels that change each revision by substituting the
filing year (2020, 2021, … 2025):

`0070`, `0076`, `0080`, `0093`, `0103`, `0106`, `0108`, `0121`, `0129`, `0136`,
`0144`, `1213`–`1224`, `1439`.

These are label parameterisation, not semantic id-reuse. The underlying concept
is identical in every revision; a single role applies across all 6 revisions.

### Not a hazard: role reuse across sub-blocks

Many roles appear on multiple casilla ids within the same form (e.g.
`irpf_inmueble_dias_arrendado` on 0101, 0122, 0137). These ids represent the same
semantic slot repeated across three structural sub-blocks (main arrendamiento,
arrendamiento accesorio, and arrendamiento negocio). The cross-revision constraint
applies per id, not per role; multiple ids sharing a role is correct and expected.

---

## OQ-1 deferred NIF casillas

Eight casilla ids in this cluster carry `data_type = "text"` for NIF-style fields
that may legally hold a foreign fiscal identifier:

`1406`, `1408`, `1411`, `1413`, `1416`, `1418` — financing expense provider NIF  
`1422`, `1425`, `1428`, `1432`, `1435`, `1438` — improvement contractor NIF

These are given the new role `irpf_inmueble_gasto_financiacion_proveedor_nif` and
`irpf_inmueble_mejora_proveedor_nif` respectively. Unlike `service_provider_nif`
(which binds `data_type = "nif"`), these two new roles must bind `data_type = "text"`
to avoid intra-role consistency failures at registry load. The OQ-1 carve-out
decision (Plan C) will determine whether these roles should be collapsed into
a permissive `service_provider_nif_or_foreign_id` variant or kept separate.

---

## Role reuse patterns observed

The inmuebles cluster exhibits strong repeating structural patterns:

- **Ownership triplet:** referencia_catastral + porcentaje_propiedad + porcentaje_usufructo
- **Situación triplet:** situacion_clave + naturaleza_urbana + naturaleza_rustica
- **Use-flag quintet:** vivienda_habitual + a_disposicion + arrendamiento + arrendamiento_accesorio + afecto_actividades
- **Amortization quintuplet:** valor_catastral + valor_catastral_construccion + pct_valor_catastral_construccion + importe_adquisicion + base_amortizacion
- **Acquisition-type pair:** adquisicion_tipo_onerosa + adquisicion_tipo_lucrativa
- **Carry-forward triplet:** gastos_pendientes_inicio_periodo + gastos_aplicados_declaracion + gastos_pendientes_futuros_periodo (repeats for each of 4 prior-year slots, 1213–1223)
- **Annexo D expense line pair:** provider_nif + gasto_importe (repeats 2–5 times per sub-block)
- **Anexo D mejoras line triplet:** mejora_fecha + mejora_proveedor_nif + mejora_importe (repeats 3 times per block)

The same structural patterns repeat across three property sub-blocks (main, accesorio,
and negocio), producing many casilla ids sharing the same role — which is expected
and intentional. The typo-twin validator will NOT fire because the new roles each
appear on at least two casilla ids within the cluster.

---

## Acceptance notes

- 119 casillas classified in this audit (128 total minus 9 already-roled).
- 56 new roles introduced; none overlap existing taxonomy entries.
- 1 soft cross-revision label hazard (0134 in 2020) — not a semantic id-reuse;
  single role assignment is safe.
- 12 OQ-1 deferred text NIFs assigned roles with `data_type = "text"`;
  must not be collapsed into `service_provider_nif` until OQ-1 carve-out lands.
- Zero genuine cross-revision semantic id-reuse hazards (unlike 0598 in the
  retenciones cluster).
- All 128 ids present in all 6 revisions with no section-path drift.
- New roles should be appended to the canonical taxonomy reference after the
  bulk-apply commit lands.
