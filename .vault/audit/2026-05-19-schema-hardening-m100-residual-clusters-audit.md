---
tags:
  - "#audit"
  - "#schema-hardening"
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
  - "[[2026-05-19-schema-hardening-m100-nif-role-assignment-audit]]"
  - "[[2026-05-19-schema-hardening-enrollment-campaign-queue-audit]]"
---

# `schema-hardening` audit: M100 residual clusters role classification

## Scope

Four residual M100 IRPF clusters across all six revisions (2020–2025). Classification
covers casillas not already carrying a `semantic_role`. All proposals follow the
cross-revision hard rule: every id appearing in multiple revisions carries the same
role across all of them; revision-scoped divergences are flagged explicitly.

| cluster | section_path (TOML) | unique_ids | 2025_total | 2025_already_roled | 2025_to_assign |
|---------|---------------------|-----------:|-----------:|-------------------:|---------------:|
| base_imponible_liquidable | resultados.base_imponible_res / base_liquidable_res / red_base_imponible_res | 47 | 47 | 1 | 46 |
| integracion_ganancias | resultados.integracion_res / gp_*_res / saldos_neg_gy_p_*_res | 62 | 61 | 26 | 35 |
| toma_datos_ampliada.anexo_a | toma_datos_ampliada.anexo_a.* | 49 | 49 | 9 | 40 |
| toma_datos_ampliada.otros | toma_datos_ampliada (root section only) | 36 | 36 | 0 | 36 |

> **Note on section-inventory count discrepancy.** The section inventory (M100 section
> inventory audit) lists the `resultados.integracion_ganancias` cluster as 55 casillas
> (all unroled). The actual 2025 revision contains 61 casillas when the full set of
> `gp_*_res`, `saldos_neg_gy_p_*_res`, and `integracion_res` sections is included.
> The 26 already-roled casillas (1245–1270) were assigned `irpf_anexo_c_*` roles in a
> prior audit pass (saldos_neg_gy_p cluster). The remaining 35 are unroled. Similarly,
> `toma_datos_ampliada.otros` has 36 unique ids (not 46); the inventory's count likely
> reflects cross-revision casilla-revision pair counting rather than unique ids.

---

## Cluster 1 — `resultados.base_imponible_liquidable`

**TOML section paths:** `["resultados", "base_imponible_res"]`, `["resultados", "base_liquidable_res"]`,
`["resultados", "red_base_imponible_res"]`.

**Semantic summary.** Three sub-families: (a) saldo-neto aggregation rows feeding the
base imponible general and del ahorro; (b) reducción rows (tributación conjunta,
previsión social, patrimonios protegidos, pensiones compensatorias, deportistas) that
subtract from the base to produce the base liquidable; (c) the four named totals —
base imponible general (0435, already roled `base_imponible_irpf`), base imponible del
ahorro (0460), base liquidable general (0500, 0505), and base liquidable del ahorro
(0510). All monetary values are `decimal` (IRPF intermediate precision, signed).
Where `data_type` is unset the bulk-apply pass should infer `decimal` from context
(the three `input_kind = "computed"` casillas with explicit `decimal` set the pattern).

### Role-assignment table

| id | section | role | label_snippet | data_type | revisions_present | notes |
|----|---------|------|---------------|-----------|-------------------|-------|
| 0428 | red_base_imponible_res | `irpf_reduccion_prevision_social_aportado` | Aportaciones del ejercicio | decimal (infer) | 2022–2025 | Input aportaciones for pension/previsión social general regime. New role. |
| 0429 | base_imponible_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro` | Saldo neto positivo del rdto capital mobiliario (ahorro) | decimal (infer) | 2020–2025 | Net positive CM balance to integrate into ahorro base. New role. |
| 0431 | base_imponible_res | `irpf_saldo_neto_gyp_general_pendiente` | Saldos netos negativos de GyP 2021 a integrar en base general | decimal (infer) | 2020–2025 | Carry-forward negative GyP general balances. New role. |
| 0432 | base_imponible_res | `irpf_saldo_neto_rdtos_base_imponible_general` | Saldo neto de los rendimientos a integrar en base imponible general | decimal | 2020–2025 | Aggregate net of all rendimientos + imputaciones de renta integrating into base general. New role. |
| 0433 | base_imponible_res | `irpf_saldo_neto_gyp_general_limite_25pct` | Saldo neto negativo GyP 2025 a integrar en base general (límite 25%) | decimal (infer) | 2020–2025 | GyP netas negativas del ejercicio bounded at 25% of 0432. New role. |
| 0434 | base_imponible_res | `irpf_saldo_neto_gyp_general_pendiente` | Resto de saldos netos negativos GyP 2021–2024 pendientes | decimal (infer) | 2020–2025 | Carry-forward remainder for years 2021–2024; same concept as 0431. **SAME ROLE** as 0431. |
| 0435 | base_imponible_res | `base_imponible_irpf` *(already roled)* | Base imponible general | decimal | 2020–2025 | Already assigned. Skip. |
| 0436 | base_imponible_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | Saldos netos negativos rdto CM 2025 a integrar ahorro (límite 25% [0424]) | decimal (infer) | 2020–2025 | Negative CM ahorro balances bounded at 25% of [0424]. New role. |
| 0437 | red_base_imponible_res | `irpf_reduccion_prevision_social_excesos_pendientes` | Excesos pendientes de reducir de ejercicios anteriores | decimal (infer) | 2022–2025 | Carry-forward of unused previsión social reduction entitlement. New role. |
| 0439 | base_imponible_res | `irpf_saldo_neto_gyp_ahorro_pendiente` | Saldos netos negativos GyP 2021 pendientes (ahorro) | decimal (infer) | 2020–2025 | Year-2021 negative GyP ahorro carry-forward. New role. |
| 0440 | base_imponible_res | `irpf_saldo_neto_gyp_ahorro_pendiente` | Saldos netos negativos GyP 2022 pendientes (ahorro) | decimal (infer) | 2020–2025 | Same concept, year 2022. **SAME ROLE** as 0439. |
| 0441 | base_imponible_res | `irpf_saldo_neto_gyp_ahorro_pendiente` | Saldos netos negativos GyP 2023 pendientes (ahorro) | decimal (infer) | 2020–2025 | Same concept, year 2023. **SAME ROLE** as 0439. |
| 0442 | base_imponible_res | `irpf_saldo_neto_gyp_ahorro_pendiente` | Saldos netos negativos GyP 2024 pendientes (ahorro) | decimal (infer) | 2020–2025 | Same concept, year 2024. **SAME ROLE** as 0439. |
| 0443 | base_imponible_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | Resto saldos netos negativos rdto CM 2021 (límite 25%) | decimal (infer) | 2020–2025 | Same concept as 0436, year 2021. **SAME ROLE** as 0436. |
| 0444 | base_imponible_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | Resto saldos netos negativos rdto CM 2022 (límite 25%) | decimal (infer) | 2020–2025 | Same concept, year 2022. **SAME ROLE** as 0436. |
| 0445 | base_imponible_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | Resto saldos netos negativos rdto CM 2023 (límite 25%) | decimal (infer) | 2020–2025 | Same concept, year 2023. **SAME ROLE** as 0436. |
| 0446 | base_imponible_res | `irpf_saldo_neto_gyp_ahorro_limite_25pct` | Saldos netos negativos GyP 2025 a integrar ahorro (límite 25% [0429]) | decimal (infer) | 2020–2025 | GyP ahorro negativas del ejercicio bounded at 25% of [0429]. New role. |
| 0447 | base_imponible_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | Resto saldos netos negativos rdto CM 2024 (límite 25%) | decimal (infer) | 2020–2025 | Same concept, year 2024. **SAME ROLE** as 0436. |
| 0448 | base_imponible_res | `irpf_saldo_neto_gyp_ahorro_pendiente_resto` | Resto saldos netos negativos GyP 2024 (límite 25%) | decimal (infer) | 2020–2025 | GyP ahorro remainder bounded at 25%, year 2024. New role. |
| 0449 | base_imponible_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | Saldos netos negativos rdto CM 2021 (ahorro) | decimal (infer) | 2020–2025 | Direct CM negative balances (full year amount, not 25%-bounded). **SAME ROLE** as 0436 — same semantic atom, year field only differs. |
| 0450 | base_imponible_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | Saldos netos negativos rdto CM 2022 | decimal (infer) | 2020–2025 | Same concept, year 2022. |
| 0451 | base_imponible_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | Saldos netos negativos rdto CM 2023 | decimal (infer) | 2020–2025 | Same concept, year 2023. |
| 0452 | base_imponible_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | Saldos netos negativos rdto CM 2024 | decimal (infer) | 2020–2025 | Same concept, year 2024. |
| 0453 | base_imponible_res | `irpf_saldo_neto_gyp_ahorro_pendiente_resto` | Resto saldos netos negativos GyP 2021 (ahorro, límite 25%) | decimal (infer) | 2020–2025 | Same concept as 0448, year 2021. **SAME ROLE**. |
| 0454 | base_imponible_res | `irpf_saldo_neto_gyp_ahorro_pendiente_resto` | Resto saldos netos negativos GyP 2022 | decimal (infer) | 2020–2025 | Same concept, year 2022. |
| 0455 | base_imponible_res | `irpf_saldo_neto_gyp_ahorro_pendiente_resto` | Resto saldos netos negativos GyP 2023 | decimal (infer) | 2020–2025 | Same concept, year 2023. |
| 0460 | base_imponible_res | `base_imponible_irpf` | Base imponible del ahorro | decimal (infer) | 2020–2025 | Reuse existing `base_imponible_irpf` role — parallel to 0435 for the ahorro tranche. Cross-revision stable. |
| 0461 | red_base_imponible_res | `irpf_reduccion_tributacion_conjunta` | Reducción para unidades familiares tributación conjunta. Importe | decimal (infer) | 2020–2025 | New role. |
| 0468 | red_base_imponible_res | `irpf_reduccion_prevision_social_total` | Total con derecho a reducción (previsión social, régimen general) | decimal (infer) | 2020–2025 | Aggregate entitlement before cap application. New role. |
| 0469 | red_base_imponible_res | `irpf_reduccion_prevision_social_conyuge_total` | Total con derecho a reducción (previsión social cónyuge) | decimal (infer) | 2020–2025 | New role. |
| 0476 | red_base_imponible_res | `irpf_reduccion_prevision_social_discapacidad_total` | Total con derecho a reducción (previsión social personas con discapacidad) | decimal (infer) | 2020–2025 | New role. |
| 0481 | red_base_imponible_res | `irpf_reduccion_patrimonio_protegido_total` | Total con derecho a reducción (patrimonios protegidos discapacidad) | decimal (infer) | 2020–2025 | New role. |
| 0486 | red_base_imponible_res | `irpf_reduccion_pensiones_compensatorias_total` | Total con derecho a reducción (pensiones compensatorias y anualidades alimentos) | decimal (infer) | 2020–2025 | New role. |
| 0490 | red_base_imponible_res | `irpf_reduccion_mutualidad_deportistas_total` | Total con derecho a reducción (mutualidad previsión social deportistas profesionales) | decimal (infer) | 2020–2025 | New role. |
| 0491 | base_liquidable_res | `irpf_reduccion_tributacion_conjunta` | Por tributación conjunta. Importe de [0461] que se aplica | decimal (infer) | 2020–2025 | Applied portion of 0461. **SAME ROLE** `irpf_reduccion_tributacion_conjunta` — same semantic atom (applied vs. total in different sub-section). Consider whether applied vs. entitlement warrants a distinct role; proposed: share the role, document the applied/total distinction in aliases. |
| 0492 | base_liquidable_res | `irpf_reduccion_prevision_social_aplicada` | Por aportaciones a sistemas previsión social (régimen general). Importe de [0468] que se aplica | decimal (infer) | 2020–2025 | Applied portion. New role. |
| 0493 | base_liquidable_res | `irpf_reduccion_prevision_social_conyuge_aplicada` | Por aportaciones a sistemas previsión social (cónyuge). Importe de [0469] que se aplica | decimal (infer) | 2020–2025 | New role. |
| 0494 | base_liquidable_res | `irpf_reduccion_prevision_social_discapacidad_aplicada` | Por aportaciones sistemas previsión social (discapacidad). Importe de [0476] | decimal (infer) | 2020–2025 | New role. |
| 0495 | base_liquidable_res | `irpf_reduccion_patrimonio_protegido_aplicada` | Por aportaciones patrimonios protegidos discapacidad. Importe de [0481] | decimal (infer) | 2020–2025 | New role. |
| 0496 | base_liquidable_res | `irpf_reduccion_pensiones_compensatorias_aplicada` | Por pensiones compensatorias y anualidades alimentos. Importe de [0486] | decimal (infer) | 2020–2025 | New role. |
| 0497 | base_liquidable_res | `irpf_reduccion_mutualidad_deportistas_aplicada` | Por aportaciones mutualidad deportistas profesionales. Importe de [0490] | decimal (infer) | 2020–2025 | New role. |
| 0500 | base_liquidable_res | `irpf_base_liquidable_general` | Base liquidable general | decimal | 2020–2025 | Named total. Extends `base_imponible_irpf` family. New role (distinct from `base_imponible_irpf` — post-reduction). |
| 0501 | base_liquidable_res | `irpf_compensacion_bases_negativas_generales` | Compensación: Bases liquidables generales negativas 2021–2024 | decimal (infer) | 2020–2025 | Carry-forward compensation applied against positive 0500. New role. |
| 0505 | base_liquidable_res | `irpf_base_liquidable_general_gravamen` | Base liquidable general sometida a gravamen | decimal | 2020–2025 | Post-compensation base that enters the tax scale. New role. |
| 0506 | base_liquidable_res | `irpf_reduccion_tributacion_conjunta` | Reducción tributación conjunta. Remanente de [0461] que se aplica | decimal (infer) | 2020–2025 | Remanente portion; share role `irpf_reduccion_tributacion_conjunta`. |
| 0507 | base_liquidable_res | `irpf_reduccion_pensiones_compensatorias_aplicada` | Reducción pensiones compensatorias. Remanente de [0486] | decimal (infer) | 2020–2025 | Remanente; share role `irpf_reduccion_pensiones_compensatorias_aplicada`. |
| 0510 | base_liquidable_res | `irpf_base_liquidable_ahorro` | Base liquidable del ahorro | decimal (infer) | 2020–2025 | Named total, ahorro tranche. New role. |

**decimal/money divergence flag (Cluster 1):** All casillas in this cluster should bind
`decimal` (signed IRPF intermediate precision). Casillas 0432, 0435, 0500, 0505 have
explicit `data_type = "decimal"`; the remaining 43 have no `data_type` declared. The
bulk-apply pass must set `decimal` on all unset casillas in this cluster. No `money`
casillas are present; no decimal/money span divergence.

---

## Cluster 2 — `resultados.integracion_ganancias`

**TOML section paths:** `["resultados", "integracion_res", "gp_patrimoniales_res"]`,
`["resultados", "integracion_res", "rendimientos_mobiliario_res"]`, `["resultados", "gp_*_res"]`
(acciones, derechos, fondos, fondos_coti, otros_elementos, otros_inmuebles, otras_ganancias,
otras_ganancias_ejer_ant_res, premios_res, reinversion_res, criptomonedas_res),
`["resultados", "anexo_c_res", "saldos_neg_gy_p_general_res"]`,
`["resultados", "anexo_c_res", "saldos_neg_gy_p_ahorro_res"]`.

**Already-roled (skip):** Casillas 1245–1270 carry `irpf_anexo_c_*` roles from a prior
audit pass. These 26 casillas are excluded from the table below.

**Semantic summary.** Two sub-clusters: (a) 9 integration totals in `integracion_res` and
`rendimientos_mobiliario_res` — aggregate sums and net differences of ganancias/pérdidas
patrimoniales feeding the base general and base ahorro; (b) 26 sub-total rows in `gp_*_res`
— per-asset-class sums of gross gains and gross losses that feed the integration totals.
One special case: 0430 (`integracion_res.rendimientos_mobiliario_res`) is the net negative
CM balance carried from base_imponible into the integration section. All values are
`decimal` (signed).

### Role-assignment table — integracion_res sub-cluster

| id | section | role | label_snippet | data_type | revisions_present | notes |
|----|---------|------|---------------|-----------|-------------------|-------|
| 0418 | integracion_res.gp_patrimoniales_res | `irpf_integracion_gyp_general_suma_ganancias` | Suma de ganancias patrimoniales (base general) | decimal (infer) | 2020–2025 | Gross gains aggregate, general base, from all general-base GyP sub-totals. New role. |
| 0419 | integracion_res.gp_patrimoniales_res | `irpf_integracion_gyp_general_suma_perdidas` | Suma de pérdidas patrimoniales (base general) | decimal (infer) | 2020–2025 | Gross losses aggregate, general base. New role. |
| 0420 | integracion_res.gp_patrimoniales_res | `irpf_integracion_gyp_general_saldo_positivo` | Si la diferencia (0418 − 0419) es positiva | decimal (infer) | 2020–2025 | Net positive balance, general base. New role. |
| 0421 | integracion_res.gp_patrimoniales_res | `irpf_integracion_gyp_general_saldo_negativo` | Si la diferencia (0418 − 0419) es negativa | decimal (infer) | 2020–2025 | Net negative balance, general base. New role. |
| 0422 | integracion_res.gp_patrimoniales_res | `irpf_integracion_gyp_ahorro_suma_ganancias` | Suma de ganancias patrimoniales (base ahorro) | decimal (infer) | 2020–2025 | Gross gains aggregate, ahorro base. New role. |
| 0423 | integracion_res.gp_patrimoniales_res | `irpf_integracion_gyp_ahorro_suma_perdidas` | Suma de pérdidas patrimoniales (base ahorro) | decimal (infer) | 2020–2025 | Gross losses aggregate, ahorro base. New role. |
| 0424 | integracion_res.gp_patrimoniales_res | `irpf_integracion_gyp_ahorro_saldo_positivo` | Si la diferencia (0422 − 0423) es positiva | decimal (infer) | 2020–2025 | Net positive balance, ahorro base. New role. |
| 0425 | integracion_res.gp_patrimoniales_res | `irpf_integracion_gyp_ahorro_saldo_negativo` | Si la diferencia (0422 − 0423) es negativa | decimal (infer) | 2020–2025 | Net negative balance, ahorro base. New role. |
| 0430 | integracion_res.rendimientos_mobiliario_res | `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | Saldo neto negativo rdto CM imputable (ahorro) | decimal (infer) | 2020–2025 | This is the same semantic atom as Cluster 1 / 0436 family. **Reuse** role `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente`. Cross-cluster shared role. |

### Role-assignment table — gp_*_res sub-totals

| id | section | role | label_snippet | data_type | revisions_present | notes |
|----|---------|------|---------------|-----------|-------------------|-------|
| 0288 | gp_premios_res.juegos_res | `irpf_gyp_ganancias_bruto` | Suma de ganancias patrimoniales (juegos) | decimal (infer) | 2020–2025 | Gross gains sub-total. New role. |
| 0289 | gp_premios_res.juegos_res | `irpf_gyp_perdidas_bruto` | Suma de pérdidas patrimoniales (juegos) | decimal (infer) | 2020–2025 | Gross losses sub-total. New role. |
| 0290 | gp_premios_res.juegos_res | `irpf_gyp_saldo_neto_general` | Suma de ganancias netas derivadas de juegos | decimal (infer) | 2020–2025 | Net GyP feeding base general. New role. |
| 0297 | gp_premios_res.juegos_pub_res | `irpf_gyp_ganancias_bruto` | Suma de ganancias (premios) | decimal (infer) | 2020–2025 | Same role as 0288. |
| 0306 | gp_premios_res.otras_res | `irpf_gyp_ganancias_bruto` | Suma de otras ganancias no derivadas de transmisión | decimal (infer) | 2020–2025 | Same role. |
| 0307 | gp_premios_res.otras_res | `irpf_gyp_perdidas_bruto` | Suma de otras pérdidas no derivadas de transmisión | decimal (infer) | 2020–2025 | Same role as 0289. |
| 0324 | gp_fondos_res | `irpf_gyp_ganancias_bruto` | Suma de ganancias (fondos de inversión) | decimal (infer) | 2020–2025 | Same role. |
| 0325 | gp_fondos_res | `irpf_gyp_perdidas_bruto` | Suma de pérdidas (fondos de inversión) | decimal (infer) | 2020–2025 | Same role as 0289. |
| 0339 | gp_acciones_res | `irpf_gyp_ganancias_bruto` | Suma de ganancias (acciones) | decimal (infer) | 2020–2025 | Same role. |
| 0340 | gp_acciones_res | `irpf_gyp_perdidas_bruto` | Suma de pérdidas (acciones) | decimal (infer) | 2020–2025 | Same role as 0289. |
| 0354 | gp_derechos_res | `irpf_gyp_ganancias_bruto` | Suma de ganancias (derechos suscripción) | decimal (infer) | 2020–2025 | Same role. |
| 0355 | gp_derechos_res | `irpf_gyp_perdidas_bruto` | Suma de pérdidas (derechos suscripción) | decimal (infer) | 2020–2025 | Same role. |
| 0385 | gp_otros_elementos_res | `irpf_gyp_perdidas_bruto` | Suma de pérdidas (otros elementos patrimoniales) | decimal (infer) | 2020–2025 | Same role. |
| 0386 | gp_otros_elementos_res | `irpf_gyp_ganancias_bruto` | Suma de ganancias (otros elementos patrimoniales) | decimal (infer) | 2020–2025 | Same role. |
| 0387 | gp_otros_elementos_res | `irpf_gyp_saldo_neto_ahorro` | Suma de ganancias ahorro (otros elementos) | decimal (infer) | 2020–2025 | Feeds base ahorro. New role. |
| 0390 | gp_otras_ganancias_res | `irpf_gyp_ganancias_bruto` | Suma de otras ganancias a integrar en base ahorro | decimal (infer) | 2020–2025 | Same role. |
| 0393 | gp_otras_ganancias_ejer_ant_res.gpimpganant | `irpf_gyp_ganancias_bruto` | Suma de ganancias derivadas de transmisiones (ejercicios anteriores) | decimal (infer) | 2020–2025 | Same role. |
| 0396 | gp_otras_ganancias_ejer_ant_res.gpimpperant | `irpf_gyp_perdidas_bruto` | Suma de pérdidas derivadas de transmisiones (ejercicios anteriores) | decimal (infer) | 2020–2025 | Same role. |
| 0400 | gp_reinversion_res | `irpf_gyp_ganancias_bruto` | Suma de imputación a año en curso de ganancias con diferimiento | decimal (infer) | 2020–2025 | Reinversión deferrals current-year imputación. Same role. |
| 0412 | gp_otros_elementos_res | `irpf_gyp_ganancias_bruto` | Suma de ganancias por cambio de residencia fuera del territorio | decimal (infer) | 2020–2025 | Exit-tax gains. Same role. |
| 1813 | gp_otros_criptomonedas_res | `irpf_gyp_perdidas_bruto` | Suma de pérdidas (monedas virtuales/criptomonedas) | decimal (infer) | 2022–2025 | New casilla from 2022; same role. |
| 1814 | gp_otros_criptomonedas_res | `irpf_gyp_ganancias_bruto` | Suma de ganancias (monedas virtuales/criptomonedas) | decimal (infer) | 2022–2025 | Same role. |
| 1844 | gp_otros_inmuebles_res | `irpf_gyp_perdidas_bruto` | Suma de pérdidas (inmuebles transmitidos) | decimal (infer) | 2022–2025 | New casilla from 2022; same role. |
| 1845 | gp_otros_inmuebles_res | `irpf_gyp_ganancias_bruto` | Suma de ganancias (inmuebles transmitidos) | decimal (infer) | 2022–2025 | Same role. |
| 1846 | gp_otros_inmuebles_res | `irpf_gyp_saldo_neto_ahorro` | Suma de ganancias ahorro (inmuebles) | decimal (infer) | 2022–2025 | Same role as 0387. |
| 2235 | gp_fondos_coti_res | `irpf_gyp_ganancias_bruto` | Suma de ganancias (fondos cotizados — ETF) | decimal (infer) | 2025 only | New casilla in 2025; same role. **SINGLE-REVISION** — typo-twin warning expected. |
| 2236 | gp_fondos_coti_res | `irpf_gyp_perdidas_bruto` | Suma de pérdidas (fondos cotizados — ETF) | decimal (infer) | 2025 only | Same role as 0289. **SINGLE-REVISION**. |

**decimal/money divergence flag (Cluster 2):** All casillas have `data_type` unset. Context
(formulas reference `decimal` 0432/0435) and IRPF signed-amount semantics confirm `decimal`.
No `money` casillas present; no decimal/money span divergence.

---

## Cluster 3 — `toma_datos_ampliada.anexo_a`

**TOML section paths:** `["toma_datos_ampliada", "anexo_a", "mejoras_energeticas_viv"]`
(32 casillas) and `["toma_datos_ampliada", "anexo_a", "vehiculos_elec_y_puntos_carga"]`
(17 casillas).

**Correction to task guidance:** The task description identifies this cluster as
"inversiones empresariales". The actual TOML content is the **deducción por mejoras de
eficiencia energética en la vivienda** (Art. 92 bis LIRPF, DA centésima L31/2022) and
**deducción por adquisición de vehículos eléctricos y puntos de recarga** (Art. 92 ter
LIRPF). There is no inversiones empresariales content at this section path; that cluster
lives at `resultados.anexo_a_res.deducciones_inversion_empresarial_res`. The classification
below reflects the actual content.

**Already-roled (skip):** 1657, 1658, 1665, 1666, 1674, 1675 (`service_provider_nif`);
1918, 1931 (`construction_entity_nif`); 1916 (`irpf_incremento_maternidad_guarderia_no_aplicado_2021`
— note: this role name appears misassigned; `Categoría (*)` in `vehiculos_elec_y_puntos_carga`
context should be an `irpf_deduccion_vehiculo_categoria` role, but an existing role is
already set; flagged as a potential mis-assignment for review, do NOT reclassify without
explicit approval).

### Role-assignment table — mejoras_energeticas_viv sub-cluster

| id | section | role | label_snippet | data_type | revisions_present | notes |
|----|---------|------|---------------|-----------|-------------------|-------|
| 1655 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_situacion_clave` | Situación. Clave | text | 2021–2025 | Situación/clave triplet key (vivienda slot 1, deducción reducción demanda energética). New role. |
| 1656 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_referencia_catastral` | Referencia catastral | text | 2021–2025 | Cadastral reference for the property. New role. |
| 1659 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_fecha_certificado_anterior` | Fecha del certificado de eficiencia energética anterior | text | 2021–2025 | Date of pre-works energy certificate. New role. |
| 1660 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_cantidades_satisfechas` | Cantidades satisfechas en el ejercicio | decimal (infer) | 2021–2025 | Amounts paid for the works. New role. |
| 1663 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_situacion_clave` | Situación. Clave | text | 2021–2025 | Slot 2 (deducción mejora consumo energía primaria). Same role as 1655. |
| 1664 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_referencia_catastral` | Referencia catastral | text | 2021–2025 | Same role as 1656. |
| 1667 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_fecha_certificado_anterior` | Fecha del certificado de eficiencia energética anterior | text | 2021–2025 | Same role as 1659. |
| 1668 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_cantidades_satisfechas` | Cantidades satisfechas en el ejercicio | decimal (infer) | 2021–2025 | Same role as 1660. |
| 1671 | mejoras_energeticas_viv | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular | text | 2021–2025 | Contributor attribution for this toma_datos sub-section. New role. |
| 1672 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_situacion_clave` | Situación. Clave | text | 2021–2025 | Slot 3 (deducción edificio en zona de rehabilitación). Same role as 1655. |
| 1673 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_referencia_catastral` | Referencia catastral | text | 2021–2025 | Same role as 1656. |
| 1676 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_fecha_certificado_anterior` | Fecha del certificado de eficiencia energética anterior | text | 2021–2025 | Same role as 1659. |
| 1677 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_cantidades_satisfechas` | Cantidades satisfechas en el ejercicio | decimal (infer) | 2021–2025 | Same role as 1660. |
| 1764 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_fecha_certificado_posterior` | Fecha del certificado de eficiencia energética posterior | text | 2021–2025 | Date of post-works energy certificate. New role. |
| 1765 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_demanda_anterior` | Demanda energética calefacción/refrigeración anterior | decimal (infer) | 2021–2025 | Pre-works demand metric (kWh/m²). New role. **decimal/money flag**: this is a physical metric, not a monetary amount. Must bind `decimal`, not `money`. |
| 1766 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_demanda_posterior` | Demanda energética calefacción/refrigeración posterior | decimal (infer) | 2021–2025 | Post-works demand metric. New role. Same note as 1765. |
| 1767 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_fecha_certificado_posterior` | Fecha del certificado de eficiencia energética posterior | text | 2021–2025 | Same role as 1764. |
| 1768 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_consumo_anterior` | Consumo de energía primaria no renovable anterior | decimal (infer) | 2021–2025 | Pre-works primary energy consumption (kWh/m²). New role. Physical metric; bind `decimal`. |
| 1769 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_consumo_posterior` | Consumo de energía primaria no renovable posterior | decimal (infer) | 2021–2025 | Post-works. New role. Physical metric. |
| 1770 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_calificacion_anterior` | Letra de calificación energética anterior (consumo) | text | 2021–2025 | A–G letter rating. New role. |
| 1771 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_calificacion_posterior` | Letra de calificación energética posterior (consumo) | text | 2021–2025 | New role. |
| 1772 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_fecha_certificado_posterior` | Fecha del certificado de eficiencia energética posterior | text | 2021–2025 | Same role as 1764. |
| 1773 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_consumo_anterior` | Consumo de energía primaria no renovable anterior | decimal (infer) | 2021–2025 | Same role as 1768. |
| 1774 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_consumo_posterior` | Consumo de energía primaria no renovable posterior | decimal (infer) | 2021–2025 | Same role as 1769. |
| 1775 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_calificacion_anterior` | Letra de calificación energética anterior | text | 2021–2025 | Same role as 1770. |
| 1776 | mejoras_energeticas_viv | `irpf_deduccion_eficiencia_energetica_calificacion_posterior` | Letra de calificación energética posterior | text | 2021–2025 | Same role as 1771. |

### Role-assignment table — vehiculos_elec_y_puntos_carga sub-cluster

| id | section | role | label_snippet | data_type | revisions_present | notes |
|----|---------|------|---------------|-----------|-------------------|-------|
| 1917 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_vehiculo_tipo` | Tipo (**) | text | 2023–2025 | Type code for the vehicle/point-of-charge deduction. New role. |
| 1919 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_vehiculo_valor_adquisicion` | Valor de adquisición del vehículo | decimal (infer) | 2023–2025 | Total acquisition value. New role. **decimal/money flag**: this is a monetary amount that also carries `decimal` (IRPF precision required for deduction base). Confirm `decimal` not `money`. |
| 1920 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_vehiculo_precio_sin_iva` | Precio de venta sin IVA o IGIC | decimal (infer) | 2023–2025 | New role. Same decimal/money note. |
| 1921 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_vehiculo_gastos_tributos` | Importe de gastos y tributos inherentes | decimal (infer) | 2023–2025 | New role. |
| 1922 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_vehiculo_cantidades_subvencionadas` | Cantidades subvencionadas o que fueran a serlo | decimal (infer) | 2023–2025 | New role. |
| 1923 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_vehiculo_matricula` | Matrícula | text | 2023–2025 | Vehicle registration plate. New role. |
| 1924 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_vehiculo_fecha_matriculacion` | Fecha de matriculación | text | 2023–2025 | New role. |
| 1925 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_vehiculo_cantidad_a_cuenta` | Importe cantidad a cuenta futura adquisición | decimal (infer) | 2023–2025 | Down-payment for a future vehicle purchase. New role. |
| 1926 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_vehiculo_fecha_pago_a_cuenta` | Fecha del pago a cuenta | text | 2023–2025 | New role. |
| 1929 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_eficiencia_energetica_situacion_clave` | Situación. Clave. (instalación punto de recarga) | text | 2023–2025 | Situación/clave for the charging point installation. Reuse `irpf_deduccion_eficiencia_energetica_situacion_clave` (same triplet pattern). |
| 1930 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_eficiencia_energetica_referencia_catastral` | Referencia catastral (inmueble donde se instala) | text | 2023–2025 | Reuse `irpf_deduccion_eficiencia_energetica_referencia_catastral`. |
| 1932 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_instalacion_recarga_fecha_fin` | Fecha en la que finaliza la instalación | text | 2023–2025 | New role. |
| 1933 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_eficiencia_energetica_cantidades_satisfechas` | Cantidades satisfechas (instalación punto recarga) | decimal (infer) | 2023–2025 | Reuse `irpf_deduccion_eficiencia_energetica_cantidades_satisfechas`. |
| 1934 | vehiculos_elec_y_puntos_carga | `irpf_deduccion_vehiculo_cantidades_subvencionadas` | Cantidades subvencionadas (punto de recarga) | decimal (infer) | 2023–2025 | Same role as 1922. |

**decimal/money divergence flag (Cluster 3):** Monetary fields 1660, 1668, 1677, 1919–1922,
1925, 1933, 1934 carry monetary amounts (deduction bases). Non-monetary metric fields 1765,
1766, 1768, 1769, 1773, 1774 carry physical energy performance measurements (kWh/m²). All
should bind `decimal` (IRPF precision rules). None should bind `money`. Flag: the validator
must confirm no `money` type is set on any of these before bulk-apply.

---

## Cluster 4 — `toma_datos_ampliada.otros`

**TOML section path:** `["toma_datos_ampliada"]` (root, no sub-key).

**Semantic summary.** All 36 casillas carry `data_type = "text"` and zero existing roles.
Every label follows a single pattern: "Contribuyente que/a quien/titular [verb phrase]".
These are declarant-attribution selectors — they identify which declarant (primer
declarante `D` or cónyuge/segundo declarante `C`) is the subject of the corresponding
toma_datos sub-section. They are not NIF fields; they hold a one-character code ("D", "C",
or similar) that routes the section data to the correct declarant. A single role covers the
entire cluster.

### Role-assignment table

| id | section | role | label_snippet | data_type | revisions_present | notes |
|----|---------|------|---------------|-----------|-------------------|-------|
| 0001 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que obtiene los rendimientos (rdto_trabajo) | text | 2020–2025 | |
| 0026 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que obtiene los rendimientos (rcm_base_ahorro) | text | 2020–2025 | |
| 0042 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente a quien corresponde (rcm_base_general) | text | 2020–2025 | |
| 0045 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que obtiene los rendimientos (rci) | text | 2020–2025 | |
| 0062 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular (imputacion_rentas_inmobiliarias) | text | 2020–2025 | |
| 0165 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que realiza la/s actividad/es | text | 2020–2025 | |
| 0256 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente a quien corresponden las imputaciones | text | 2020–2025 | |
| 0267 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que debe efectuar la imputación (AIE/UTE) | text | 2020–2025 | |
| 0271 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que debe efectuar la imputación (cesión) | text | 2020–2025 | |
| 0276 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que debe efectuar la imputación (regímenes especiales) | text | 2020–2025 | |
| 0281 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que obtiene los premios (juegos) | text | 2020–2025 | |
| 0291 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que obtiene los premios (loterías) | text | 2020–2025 | |
| 0298 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que obtiene otras GyP no derivadas de transmisión | text | 2020–2025 | |
| 0308 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente a quien corresponde (imputación diferida) | text | 2020–2025 | |
| 0310 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular de las acciones o participaciones | text | 2020–2025 | |
| 0326 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular de los valores transmitidos | text | 2020–2025 | |
| 0341 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular de los derechos de suscripción transmitidos | text | 2020–2025 | |
| 0388 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que obtiene estas ganancias patrimoniales | text | 2020–2025 | |
| 0391 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente a quien corresponde la imputación (ganancias ejer. ant.) | text | 2020–2025 | |
| 0394 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente a quien corresponde la imputación (pérdidas ejer. ant.) | text | 2020–2025 | |
| 0398 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente a quien corresponde la imputación diferida (reinversión) | text | 2020–2025 | |
| 0402 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular de los valores (fondos de inversión) | text | 2020–2025 | |
| 0462 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que realiza o a quien se imputan las aportaciones | text | 2020–2025 | |
| 0470 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que realiza las aportaciones (previsión social cónyuge) | text | 2020–2025 | |
| 0477 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que realiza las aportaciones (discapacidad) | text | 2020–2025 | |
| 0482 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que abona las pensiones o anualidades | text | 2020–2025 | |
| 0487 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que realiza las aportaciones (deportistas profesionales) | text | 2020–2025 | |
| 1441 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular de la actividad (estimación directa) | text | 2020–2025 | |
| 1485 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular de la actividad (estimación objetiva) | text | 2020–2025 | |
| 1561 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que es socio/comunero/partícipe (AIE/UTE) | text | 2020–2025 | |
| 1614 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente que es socio/comunero/partícipe (regímenes especiales) | text | 2020–2025 | |
| 1624 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular del elemento patrimonial transmitido (otros elementos) | text | 2020–2025 | |
| 1800 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular de las monedas virtuales transmitidas | text | 2022–2025 | New from 2022. |
| 1815 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular del elemento patrimonial transmitido (inmuebles) | text | 2022–2025 | New from 2022. |
| 1972 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular del elemento patrimonial transmitido (ETF) | text | 2023–2025 | New from 2023. |
| 2224 | toma_datos_ampliada | `irpf_toma_datos_contribuyente_titular` | Contribuyente titular de las acciones o participaciones (fondos cotizados) | text | 2025 only | New in 2025. **SINGLE-REVISION** — typo-twin warning expected until 2026 revision lands. |

**Note:** `irpf_toma_datos_contribuyente_titular` collapses all 36 casillas into one role
because the semantic content is identical across all positions: a text discriminator routing
the surrounding toma_datos block to the correct declarant. This role is also proposed for
casilla 1671 in Cluster 3 (above). Verify that `irpf_anexo_c_contribuyente_titular`
(already assigned to 1245, 1258 in Cluster 2's saldos_neg_gy_p sections) should be
merged with `irpf_toma_datos_contribuyente_titular` or kept distinct. These appear
semantically equivalent; a merge would reduce the role count by one and eliminate a
potential typo-twin.

**decimal/money divergence flag (Cluster 4):** All casillas are `data_type = "text"`.
No monetary fields. No decimal/money divergence.

---

## New roles introduced across all four clusters

These role names are not present in the canonical taxonomy as of 2026-05-19:

**Cluster 1 (base_imponible_liquidable) — 14 new roles:**
- `irpf_saldo_neto_rdtos_base_imponible_general` — aggregate net rendimientos + imputaciones feeding base general
- `irpf_saldo_neto_rdto_capital_mobiliario_ahorro` — net positive CM balance to ahorro base
- `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` — carry-forward negative CM ahorro balances (shared Cluster 1 + 2 / 0430)
- `irpf_saldo_neto_gyp_general_pendiente` — carry-forward negative GyP general balances
- `irpf_saldo_neto_gyp_general_limite_25pct` — GyP general bounded at 25% of base
- `irpf_saldo_neto_gyp_ahorro_pendiente` — carry-forward negative GyP ahorro balances
- `irpf_saldo_neto_gyp_ahorro_limite_25pct` — GyP ahorro bounded at 25% of CM ahorro balance
- `irpf_saldo_neto_gyp_ahorro_pendiente_resto` — remainder of GyP ahorro carry-forward after 25% limit
- `irpf_reduccion_tributacion_conjunta` — reducción for joint filing
- `irpf_reduccion_prevision_social_total` — total previsión social entitlement (régimen general)
- `irpf_reduccion_prevision_social_aportado` — actual aportaciones amount for the exercise
- `irpf_reduccion_prevision_social_excesos_pendientes` — carry-forward of unused entitlement
- `irpf_reduccion_prevision_social_conyuge_total` — previsión social entitlement for cónyuge
- `irpf_reduccion_prevision_social_discapacidad_total` — previsión social entitlement for discapacidad
- `irpf_reduccion_patrimonio_protegido_total` — patrimonio protegido discapacidad entitlement
- `irpf_reduccion_pensiones_compensatorias_total` — pensiones compensatorias + anualidades entitlement
- `irpf_reduccion_mutualidad_deportistas_total` — mutualidad deportistas entitlement
- `irpf_reduccion_prevision_social_aplicada` — applied portion of régimen general entitlement
- `irpf_reduccion_prevision_social_conyuge_aplicada` — applied portion for cónyuge
- `irpf_reduccion_prevision_social_discapacidad_aplicada` — applied portion for discapacidad
- `irpf_reduccion_patrimonio_protegido_aplicada` — applied portion of patrimonio protegido
- `irpf_reduccion_pensiones_compensatorias_aplicada` — applied portion of pensiones compensatorias
- `irpf_reduccion_mutualidad_deportistas_aplicada` — applied portion for deportistas
- `irpf_base_liquidable_general` — named base liquidable general total
- `irpf_compensacion_bases_negativas_generales` — prior-year negative general bases applied
- `irpf_base_liquidable_general_gravamen` — base liquidable general after compensation, entering tax scale
- `irpf_base_liquidable_ahorro` — named base liquidable del ahorro total

Two roles from Cluster 1 extend `base_imponible_irpf`: 0460 reuses that role directly;
0500, 0505, 0510 introduce the base liquidable variants.

**Cluster 2 (integracion_ganancias) — 7 new roles:**
- `irpf_integracion_gyp_general_suma_ganancias`
- `irpf_integracion_gyp_general_suma_perdidas`
- `irpf_integracion_gyp_general_saldo_positivo`
- `irpf_integracion_gyp_general_saldo_negativo`
- `irpf_integracion_gyp_ahorro_suma_ganancias`
- `irpf_integracion_gyp_ahorro_suma_perdidas`
- `irpf_integracion_gyp_ahorro_saldo_positivo`
- `irpf_integracion_gyp_ahorro_saldo_negativo`
- `irpf_gyp_ganancias_bruto` — per-asset-class gross gains sub-total
- `irpf_gyp_perdidas_bruto` — per-asset-class gross losses sub-total
- `irpf_gyp_saldo_neto_general` — net GyP sub-total feeding base general
- `irpf_gyp_saldo_neto_ahorro` — net GyP sub-total feeding base ahorro

**Cluster 3 (toma_datos_ampliada.anexo_a) — 14 new roles:**
- `irpf_deduccion_eficiencia_energetica_situacion_clave`
- `irpf_deduccion_eficiencia_energetica_referencia_catastral`
- `irpf_deduccion_eficiencia_energetica_fecha_certificado_anterior`
- `irpf_deduccion_eficiencia_energetica_fecha_certificado_posterior`
- `irpf_deduccion_eficiencia_energetica_cantidades_satisfechas`
- `irpf_deduccion_eficiencia_energetica_demanda_anterior`
- `irpf_deduccion_eficiencia_energetica_demanda_posterior`
- `irpf_deduccion_eficiencia_energetica_consumo_anterior`
- `irpf_deduccion_eficiencia_energetica_consumo_posterior`
- `irpf_deduccion_eficiencia_energetica_calificacion_anterior`
- `irpf_deduccion_eficiencia_energetica_calificacion_posterior`
- `irpf_deduccion_vehiculo_tipo`
- `irpf_deduccion_vehiculo_valor_adquisicion`
- `irpf_deduccion_vehiculo_precio_sin_iva`
- `irpf_deduccion_vehiculo_gastos_tributos`
- `irpf_deduccion_vehiculo_cantidades_subvencionadas`
- `irpf_deduccion_vehiculo_matricula`
- `irpf_deduccion_vehiculo_fecha_matriculacion`
- `irpf_deduccion_vehiculo_cantidad_a_cuenta`
- `irpf_deduccion_vehiculo_fecha_pago_a_cuenta`
- `irpf_deduccion_instalacion_recarga_fecha_fin`
- `irpf_toma_datos_contribuyente_titular` (also Cluster 4)

**Cluster 4 (toma_datos_ampliada.otros) — 1 new role:**
- `irpf_toma_datos_contribuyente_titular`

**Total new roles across four clusters: ~55** (exact count pending merge decision on
`irpf_toma_datos_contribuyente_titular` vs `irpf_anexo_c_contribuyente_titular`).

---

## Id-reuse hazards

### Hazard 1: 0428 — first_seen revision is 2022 (not 2020)

Casilla 0428 appears from 2022 onwards only. In 2020–2021 the slot was absent or used for a
different concept (no 0428 found in those revisions in the `red_base_imponible_res` section).
The role `irpf_reduccion_prevision_social_aportado` is safe for 2022–2025. Verify in 2020–2021
whether `0428` appears in a different section with a different meaning before allowing the
cross-revision role to apply to those revisions.

### Hazard 2: 0437 — first_seen revision is 2022 (carry-forward pensión social, réforme)

Same as 0428. `0437` appears from 2022 onwards. The label "Excesos pendientes de reducir
procedentes de los ejercicios 2017 a 2021" in 2022 becomes "ejercicios 2020 a 2024" in 2025
(year labels update). The semantic concept is stable; role is safe for 2022–2025.

### Hazard 3: 1800, 1815 — criptomonedas and inmuebles contribuyente rows (first_seen 2022)

These casillas appear from 2022. In 2020–2021 the concepts (criptomoneda, ETF-class inmuebles)
did not exist in the TOML registry. The role `irpf_toma_datos_contribuyente_titular` applies
for 2022–2025 only; no revision conflict.

### Hazard 4: 2224, 2235, 2236 — single-revision casillas (2025 only)

Three casillas appear only in 2025 (fondos cotizados ETF sub-category). Roles assigned for
2025. Typo-twin warning expected at registry load. These will become multi-revision once the
2026 revision lands.

### Hazard 5: 0430 — cross-cluster shared role

Casilla 0430 appears in both the `base_imponible_res` section (via `integracion_res.rendimientos_mobiliario_res`
path) and the conceptual orbit of Cluster 1. The role `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente`
bridges both clusters. Validate that the intra-role consistency check does not produce a
false positive when the same role is applied to a casilla in two conceptually adjacent
clusters with identical semantics.

### Hazard 6: `irpf_toma_datos_contribuyente_titular` vs `irpf_anexo_c_contribuyente_titular`

Casillas 1245 and 1258 already carry `irpf_anexo_c_contribuyente_titular` (assigned in the
saldos_neg_gy_p prior audit pass). Casilla 1671 in Cluster 3 and all 36 ids in Cluster 4
are proposed for `irpf_toma_datos_contribuyente_titular`. These two roles are semantically
equivalent — both are declarant D/C attribution text discriminators. **Decision needed before
bulk-apply:** either merge to a single canonical role (and re-assign 1245, 1258) or keep
two distinct roles with documented aliases. Merging is the cleaner option; the intra-role
consistency check will enforce type consistency automatically.

---

## Decimal/money divergence summary

| cluster | monetary fields | physical/metric fields | both types? | verdict |
|---------|----------------|------------------------|-------------|---------|
| base_imponible_liquidable | all monetary (signed IRPF amounts) | none | no | bind `decimal` throughout |
| integracion_ganancias | all monetary (signed GyP amounts) | none | no | bind `decimal` throughout |
| toma_datos_ampliada.anexo_a | 1660,1668,1677,1919–1922,1925,1933,1934 (monetary deduction bases) | 1765,1766,1768,1769,1773,1774 (kWh/m² metrics) | yes — different semantics, same `decimal` type | both groups bind `decimal`; do NOT bind `money` on any |
| toma_datos_ampliada.otros | none (all text) | none | no | no action needed |

**Critical:** Clusters 1 and 2 contain both `base_imponible_irpf` (decimal, any-sign) and
intermediate signed totals that must remain `decimal`. No `money` types should appear.
The bulk-apply pass should assert zero `money` casillas in any of the four clusters before
writing roles.
