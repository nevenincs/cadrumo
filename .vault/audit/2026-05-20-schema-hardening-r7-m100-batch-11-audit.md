---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m100 batch-11 audit

## Scope

Semantic-correctness review of 68 `semantic_role` assignments from the M100 IRPF
registry, covering revisions 2020–2025. Each role is evaluated for: (1) name
accuracy against member labels, (2) member coherence across revisions, (3)
granularity fitness. Id-reuse across revisions is structural, not a defect.

## Findings

| role | verdict | detail |
|---|---|---|
| `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente` | SPLIT | The role mixes three semantically distinct casilla families. `0430` = saldo neto negativo **del ejercicio corriente** (integration section). `0436` = application capped at 25% of [0424] for the **current year's** negative balance. `0443`–`0452` = **prior-year** residual balances (rolling 4-year window, annex C.2/C.3). These are: (a) current-year net balance, (b) current-year cap-limited carry-in, and (c) prior-year residual carries. Correct split: `irpf_cap_mobiliario_saldo_neto_ejercicio` (0430), `irpf_cap_mobiliario_saldo_neto_cap_25pct` (0436), `irpf_cap_mobiliario_saldo_neto_pendiente_anos_anteriores` (0443–0452). |
| `irpf_inmueble_gasto_financiacion_importe` | RENAME + SPLIT | Name says "gastos de financiación" but members are generic "Gasto 1/Gasto 2/Resto de gastos" — these are not financing-specific. The section `toma_datos_ampliada/inmuebles/inmueble` covers all deductible expenses for rental property. The 2020 revision shows `1409`/`1410` with `money` (not `money(default)`) vs others; this is a structural variance, not an outlier. However the role bundles gastos from three distinct inmueble slots (1407-1410, 1412-1415, 1417-1420) which represent different inmueble instances — this is a repeating-group pattern, normal in M100. Rename to `irpf_inmueble_rdto_capital_inmo_gastos_deducibles_importe` to reflect the actual content (general deductible expenses for income-from-real-estate). |
| `irpf_eo_modulo_rdto_antes_amort` | OK | All members: "Rendimiento por módulo antes de amortización" in `reg_estima_obj/actividad_est_obj`, `money(default)`, revisions 2020–2025. Repeating-group pattern (7 activity slots per revision). Name is accurate: EO = estimación objetiva, módulo = módulo unit yield before amortisation deduction. |
| `irpf_inmueble_mejora_fecha` | OK | All members are date-of-improvement fields (`text`, `toma_datos_ampliada/inmuebles/inmueble`), covering Mejora 1/2/3 for two inmueble slots. Name accurately describes content. |
| `irpf_anexo_c_exceso_scd_pendiente_inicio` | OK | All members: "Pendiente de aplicación al principio del periodo" in `exceso_seguros_colectivos_dependencia_res`, money, rolling 5-year prior-year window. SCD = seguros colectivos de dependencia. Name is accurate. |
| `disabled_person_nif` | RENAME | Missing `irpf_` prefix required by project convention. Members are coherent: NIF of disabled person across four sub-contexts (red_discapacidad, red_patrimonio_protegido_discapacidad, excesos_sistemas_prevision_social, excesos_patrim_protegidos). All `nif` type, all revisions. Rename to `irpf_discapacitado_nif`. |
| `irpf_anexo_c_exceso_patrim_protegido_pendiente_inicio` | OK | All members: "Pendiente de aplicación al principio del periodo" in `excesos_patrim_protegidos_res`, money, rolling 4-year window. Name accurate. |
| `irpf_inmueble_gastos_pendientes_inicio_periodo` | OK | All members: prior-year deductible expense carry-forwards in `inmuebles/inmueble`, money, 4-year rolling window. Name accurate. |
| `beneficiary_nif` | RENAME | Missing `irpf_` prefix. Members span three deduction sub-contexts (deduc_descendiente_disc_res, deduc_ascendiente_disc_res, deduc_familia_numerosa_res) — all are NIF of the tax-credit beneficiary for child disability, ascendant disability, and large family deductions. These are semantically distinct beneficiary types grouped under one role. The grouping is acceptable if the intent is "NIF of the deduction beneficiary in family deductions." Rename to `irpf_deduccion_familiar_beneficiario_nif`. |
| `irpf_deduccion_eficiencia_energetica_situacion_clave` | SPLIT | Contains members from two distinct deduction sub-sections: `mejoras_energeticas_viv` (casillas 1655, 1663, 1672) and `vehiculos_elec_y_puntos_carga` (casilla 1929, from 2023 onwards). These are different deductions (residential energy improvements vs. electric vehicles). The "situación/clave" field serves both, but conflating them obscures the boundary. Split: `irpf_deduccion_mejoras_energeticas_vivienda_situacion_clave` (1655/1663/1672) and `irpf_deduccion_vehiculos_electricos_puntos_carga_situacion_clave` (1929). |
| `irpf_anexo_b_rental_amount_total` | RENAME + OUTLIER | Name says "rental" but members cover: (a) `an_b_inf_adc_ctrd` = contratos de arrendamiento financial/other (`0644`) and (b) `an_b_inf_adc_arr` = arrendamientos informacion adicional (`1128`). In 2025 a third member appears: `2211` in `an_b_inf_adc_arrvm` = arrendamiento de viviendas en mercado (new 2025 section). All three are "importe total satisfecho" but from different annex-B sub-schemas. Name rename: `irpf_anexo_b_importe_total_satisfecho`. The 2025 member `2211` from `an_b_inf_adc_arrvm` is a legitimate 2025 addition, not an outlier. |
| `irpf_inmueble_importe_adquisicion` | OK | All members: "Importe de adquisición" in `inmuebles/inmueble`, money, two inmueble slots (0126, 0141) per revision 2020–2025. Name accurate. |
| `irpf_anexo_c_exceso_eeficiencia_pendiente_inicio` | RENAME + OUTLIER | Name has typo: `eeficiencia` → should be `eficiencia`. More critically: revision 2022 member `1692` has label "Reserva para Inversiones en Canarias 2016 (1): Inversiones previstas..." in section `reserva_inversiones_canarias_res` — this is entirely different from the energy-efficiency excess carryforward. This is a misassigned casilla. **OUTLIER**: `1692` rev 2022 belongs in a Canarias investment reserve role, not energy-efficiency carryforward. All other members (1692 in 2024/2025, 1695, 1854, 2024) correctly reference `excesos_eficiencia_energetica_res`. Rename to `irpf_anexo_c_exceso_eficiencia_energetica_pendiente_inicio`. |
| `irpf_anexo_c_exceso_eeficiencia_pendiente_fin` | RENAME | Same typo: `eeficiencia` → `eficiencia`. All members coherent: "Pendiente de aplicación en ejercicios futuros" in `excesos_eficiencia_energetica_res`. Rename to `irpf_anexo_c_exceso_eficiencia_energetica_pendiente_fin`. |
| `irpf_abono_anticipado_maternidad` | OK | All members: casilla `0612` "Importe del abono anticipado de la deducción" in `deduc_mater_res` (2020–2024) and in `resultado_declaracion` (2025, section restructure). Label in 2025 changes to "Deduccion por maternidad. Abono anticipado" — same concept, section reorganised. Name accurate. |
| `irpf_anexo_a_residente_ue_deduccion_importe` | OK | Single casilla `0732` across all revisions, "Deducción que corresponde al contribuyente" in `deduccion_residente_ue_res`. Coherent. |
| `irpf_anexo_c_exencion_reinversion_ganancia_patrimonial` | RENAME | Name says "exencion_reinversion" but the label consistently refers to "Ganancia patrimonial obtenida como consecuencia de la transmisión de las acciones o participaciones por las que se hubiera practicado la deducción prevista en el art. 68.1". This is the **reversal gain from disposal of new-company shares** (exención por reinversión en nuevas empresas). The content is the taxable gain triggering reversion, not the exemption amount per se. More accurate: `irpf_anexo_c_nuevas_empresas_ganancia_reversion`. |
| `irpf_anexo_c_saldo_neg_gyp_general_generado` | OK | Single casilla `1257` across all revisions, "Saldo negativo de las ganancias y pérdidas imputables al ejercicio, a integrar en la base imponible general, pendientes de compensación en los 4 ejercicios siguientes." Coherent, name accurate. |
| `irpf_compensacion_conyuges_devolver_renunciado` | OK | Single casilla `0694` across all revisions, "Importe del resultado a devolver... a cuyo cobro efectivo se renuncia." Coherent. |
| `irpf_cuota_ccaa_residencia` | OK | Single casilla `0675` across all revisions, "Importe del IRPF que corresponde a la Comunidad Autónoma de residencia." Name accurate. |
| `irpf_deduccion_alquiler_vivienda_habitual_autonomica` | OK | Single casilla `0563` "Por alquiler de la vivienda habitual. Régimen transitorio... Parte autonómica." Coherent across revisions, transitional regime. |
| `irpf_deduccion_andalucia_empleada_hogar_importe_1` | OK | Single casilla `0860` "Importe de la deducción" in `andalucia_res`. Suffix `_1` suggests there is a second slot; coherent. |
| `irpf_deduccion_aragon_economia_social` | OK | Single casilla `0879` "Por inversión en entidades de la economía social." Annexe reference shifts (B.7→B.8→B.9→B.11) across years — label detail changes, concept stable. |
| `irpf_deduccion_asturias_acogimiento_menores` | OK | Single casilla `0893` "Por acogimiento familiar de menores." All revisions. |
| `irpf_deduccion_asturias_vivienda_discapacitados` | OK | Single casilla `0884` "Por adquisición o adecuación de vivienda habitual para contribuyentes con discapacidad." Stable. |
| `irpf_deduccion_baleares_donaciones_patrimonio` | OK | Single casilla `0902` for donations/agreements for cultural/scientific/technological patronage. Coherent. |
| `irpf_deduccion_c_valenciana_arrendamiento_o_cesion` | OK | Single casilla `1095`. Label evolves from "cantidades invertidas en el alquiler" (2020) → "arrendamiento" (2022) → "arrendamiento o cesión en uso" (2023+). Same deduction, label precision increasing. Name accurately reflects the final/broadened concept. |
| `irpf_deduccion_c_valenciana_dos_mas_descendientes` | OK | Single casilla `1104`. Stable label and section. |
| `irpf_deduccion_c_valenciana_vivienda_discapacidad` | OK | Single casilla `1093`. Stable. |
| `irpf_deduccion_canarias_estudios_no_superiores` | OK | Single casilla `0936`. Label shortens in 2024 from "gastos de estudios en educación infantil..." to "gastos de estudios no superiores" — same deduction, label simplification. Name matches the 2024+ label accurately. |
| `irpf_deduccion_canarias_restauracion_bienes` | OK | Single casilla `0918`. Stable label. |
| `irpf_deduccion_cantabria_familia_monoparental` | OK | Single casilla `0775`. Stable. |
| `irpf_deduccion_castilla_la_mancha_cuidado_ascendientes_75` | OK | Single casilla `0961`. Stable. |
| `irpf_deduccion_castilla_y_leon_cuotas_ss_hogar` | OK | Single casilla `0994`. Stable. |
| `irpf_deduccion_castilla_y_leon_patrimonio_historico` | OK | Single casilla `0974`. Stable. |
| `irpf_deduccion_catalunya_nacimiento_adopcion` | OK | Single casilla `1000`. Label expands in 2024 to "hijo o de una hija" (gender-neutral) and in 2025 adds "acogimiento familiar." Name is slightly narrower than 2025 scope but acceptable given evolution. |
| `irpf_deduccion_donativos_autonomica` | OK | Single casilla `0553`. Stable concept "donativos y otras aportaciones, parte autonómica." |
| `irpf_deduccion_extremadura_vivienda_jovenes` | OK | Single casilla `1010`. Stable. |
| `irpf_deduccion_galicia_codigo_instalacion` | OK | Single casilla `1033`, text, code for industrial installation (Oficina Virtual de Industria). Coherent. |
| `irpf_deduccion_general_importe` | RENAME | Too generic — `0721` in `gravamenes_res` is a catch-all "Importe de la deducción" row that appears in the cuota calculation. The surrounding TOML context would clarify which deduction this belongs to, but as a role name it lacks specificity. Given section `gravamenes_res`, this is likely the general/state deductions aggregate. Rename to `irpf_deduccion_cuota_general_importe` to distinguish it from regional deduction amounts. |
| `irpf_deduccion_la_rioja_escuelas_infantiles_0_3` | OK | Single casilla `1075`. Stable. |
| `irpf_deduccion_la_rioja_vivienda_municipio` | RENAME | Name says `vivienda_municipio` but label is "Por cantidades invertidas en la adquisición o construcción de vivienda habitual para jóvenes." There is no municipality component in the label; the deduction is for young people's primary residence. Rename to `irpf_deduccion_la_rioja_vivienda_habitual_jovenes`. |
| `irpf_deduccion_madrid_entidades_cotizadas_mab` | OK | Single casilla `1048`. MAB = Mercado Alternativo Bursátil. Annexe reference evolves (B.7→B.8→B.9→B.11), concept stable. |
| `irpf_deduccion_murcia_donaciones_patrimonio_cultura` | OK | Single casilla `1053`. Label expands in 2023 to include "artísticas, sociales, científico-tecnológicas y medioambientales" — scope broadened. Name partially covers current scope; acceptable given the cultural/heritage donation core remains. |
| `irpf_deduccion_vivienda_habitual_autonomica` | OK | Single casilla `0548` "Deducción por inversión en vivienda habitual... Parte autonómica." Stable transitional-regime deduction. |
| `irpf_ed_actividad_tipo_clave` | OK | Single casilla `0166` "Tipo de actividad/es realizada/s: clave indicativa" in `reg_estima_directa`. Coherent. |
| `irpf_ed_gastos_financieros` | OK | Single casilla `0203` "Gastos financieros" in `reg_estima_directa`. 2025 section path changes (`rendimientos_actividades_economicas/estimacion_directa`) — same concept, restructured section. |
| `irpf_ed_otros_conceptos_deducibles` | OK | Single casilla `0217`. Stable concept, 2025 path change. |
| `irpf_ed_rdto_neto_reducido_total` | OK | Single casilla `0235` "Rendimiento neto reducido total de las actividades económicas en estimación directa." data_type `decimal`. 2025 label/path simplifies, concept stable. |
| `irpf_ed_suministros` | OK | Single casilla `0194` "Suministros." Coherent. 2023 label changes "luz" → "electricidad" (more precise). |
| `irpf_eo_agr_indice_ecologica` | OK | Single casilla `1544` "Por actividades de agricultura ecológica" in `reg_estima_obj_agricola`. money(default). Stable. |
| `irpf_eo_agr_ingresos_integros_cereales_citricos_horticultura` | OK | Single casilla `1503`. 2020/2021 label is generic "Ingresos íntegros"; from 2022 explicitly lists crop categories. The role name reflects the 2022+ specific content and is accurate. |
| `irpf_eo_agr_rdto_neto_minorado` | OK | Single casilla `1539` "Rendimiento neto minorado" in `reg_estima_obj_agricola`, decimal. Stable. |
| `irpf_eo_gastos_extraordinarios` | OK | Single casilla `1477` "Gastos extraordinarios por circunstancias excepcionales" in `reg_estima_obj`. Stable. |
| `irpf_eo_rdto_neto_reducido` | OK | Single casilla `1481` "Rendimiento neto reducido" in `reg_estima_obj`, decimal. Stable. |
| `irpf_escala_sobre_minimo_general_autonomico` | OK | Single casilla `0531` "Aplicación de la escala autonómica... al importe de la casilla [0523]... Parte autonómica." Name accurately reflects the application of the autonomous community tax scale to the personal minimum. |
| `irpf_flag_regularizacion_da45_estatal` | OK | Single casilla `0575`, boolean. DA 45ª regularisation flag, state portion. Name accurate. |
| `irpf_ganancia_acciones_ganancia` | OK | Single casilla `0332` "Ganancias patrimoniales" in `gp_acciones`. money. Stable. |
| `irpf_ganancia_derechos_reduccion_dt9` | OK | Single casilla `0350` "Reducción aplicable (D.T. 9.ª)" in `gp_derechos`. money. DT9 = transitional reduction for pre-1994 assets. Coherent. |
| `irpf_ganancia_fondos_valor_transmision_dt9` | OK | Single casilla `0314` "Valor de transmisión al que resulta aplicable la D.T. 9.ª" in `gp_fondos`. money. Coherent. |
| `irpf_ganancia_otros_anio_imputacion_2` | OK | Single casilla `0367` "Año de imputación" in `gp_otros_elementos`, text. Suffix `_2` indicates second imputación slot. Coherent. |
| `irpf_ganancia_otros_ganancia_pendiente_4` | OK | Single casilla `0377` "Ganancia patrimonial pendiente de imputación" in `gp_otros_elementos`. money. Suffix `_4` = fourth instalment. |
| `irpf_ganancia_otros_reducida_da7` | OK | Single casilla `1653` "Ganancia patrimonial reducida" in `gp_otros_elementos`. money. DA7 = 7ª reducción. Coherent. |
| `irpf_ganancia_otros_valor_transmision_susceptible_dt9` | OK | Single casilla `1636` "Valor de transmisión susceptible de reducción (D.T. 9.ª)" in `gp_otros_elementos`. Coherent. |
| `irpf_ganancia_premios_juegos_pub_valoracion` | OK | Single casilla `0293` "Valoración" in `gp_premios/juegos_pub`. money. Coherent. |
| `irpf_inmueble_arrendamiento_flag` | OK | Single casilla `0075` "Arrendamiento" in `inmuebles/inmueble`, boolean. Coherent. |
| `irpf_inmueble_direccion` | OK | Single casilla `0069` "Dirección" in `inmuebles/inmueble`, text. Coherent. |
| `irpf_inmueble_situacion_clave` | OK | Single casilla `0065` "Situación (clave)" in `inmuebles/inmueble`, text. Coherent. |
| `irpf_integracion_gyp_general_suma_perdidas` | OK | Single casilla `0419` "Suma de pérdidas patrimoniales" in `gp_patrimoniales_res`. Coherent. |
| `irpf_minimo_ascendientes_autonomico` | OK | Single casilla `0516` "Parte autonómica: Mínimo por ascendientes." Coherent. |
| `irpf_perdida_acciones_importe_obtenido` | OK | Single casilla `0337` "Pérdidas patrimoniales. Importe obtenido" in `gp_acciones`. Coherent. |
| `irpf_perdida_otros_pendiente_1` | OK | Single casilla `0366` "Pérdida patrimonial pendiente de imputación" in `gp_otros_elementos`. Suffix `_1` = first instalment. Coherent. |
| `irpf_re_aie_deduccion_inversion_empresarial` | OK | Single casilla `0260` "Deducciones por inversión empresarial (bases imputadas)" in `re_agrup_interes_economico`. AIE = agrupaciones de interés económico. Coherent. |
| `irpf_re_atrib_cap_inmo_reduccion_23_2` | OK | Single casilla `1573` "Reducción aplicable (artículo 23.2)" in `re_at_rentas`, decimal. Art. 23.2 = capital inmobiliario rental reduction for housing. Coherent. |
| `irpf_re_atrib_gp_dt9_susceptibles_reduccion` | OK | Single casilla `1592` "Parte de las ganancias patrimoniales susceptibles de reducción (D.T 9ª)" in `re_at_rentas`. Coherent. |
| `irpf_re_atrib_inmueble_num_dias` | RENAME | data_type is `money(default)` but the label is "Nº de días" — this is a count of days, not a monetary amount. The data_type mismatch is a registry-level issue to flag. The role name is otherwise accurate. Consider flagging to registry maintainers: `1618` should use `integer` or `decimal` not `money(default)`. Role name OK but add note. |
| `irpf_re_atrib_suma_cap_inmo` | OK | Single casilla `1604` "Suma de rendimientos netos del capital inmobiliario, atribuidos," decimal. Coherent. |
| `irpf_re_imagen_cantidad_imputar` | OK | Single casilla `0274` "Cantidad a imputar" in `re_derechos_imagen`. money. Coherent — image rights attribution regime. |
| `irpf_red_discapacidad_exceso_aportaciones_propias` | OK | Single casilla `0472` "Excesos pendientes de reducir... por aportaciones realizadas por la persona con discapacidad." Rolling 5-year window. Coherent. |
| `irpf_reduccion_patrimonio_protegido_total` | OK | Single casilla `0481` "Total con derecho a reducción" in `red_base_imponible_res`. Coherent — total protected-estate reduction entitlement. |
| `irpf_rendimiento_capital_inmobiliario_amortizacion_casos_especiales_accesorio` | OK | Single casilla `0147` "Amortización en casos especiales." 2025 label adds "del inmueble accesorio" — legitimate specificity increase. Name covers the concept adequately. |
| `irpf_rendimiento_capital_inmobiliario_gasto_tributos` | OK | Single casilla `0115` "Tributos, recargos y tasas." 2025 section changes. Coherent. |
| `irpf_rendimiento_capital_mobiliario_ahorro_dividendos` | OK | Single casilla `0029` "Dividendos y demás rendimientos por la participación en fondos propios de entidades." 2025 label shortens but concept identical. Coherent. |
| `irpf_rendimiento_capital_mobiliario_ahorro_rentas_imposicion_capitales` | OK | Single casilla `0033` "Rendimientos procedentes de rentas que tengan por causa la imposición de capitales..." decimal. Coherent. |
| `irpf_rendimiento_capital_mobiliario_general_rendimiento_neto` | OK | Single casilla `0054` "Rendimiento neto" in `rdto_capital_mobiliario_general`, decimal. Coherent. |
| `irpf_rendimiento_trabajo_gasto_defensa_juridica` | OK | Single casilla `0016` "Gastos de defensa jurídica derivados directamente de litigios con el empleador." 2025 label simplified. Coherent. |
| `irpf_rendimiento_trabajo_suma_rendimientos_netos_previos` | OK | Single casilla `0018` "Suma de rendimientos netos previos" in `rdto_trabajo_res`, decimal. Coherent. |
| `irpf_retencion_ganancias_patrimoniales_premios` | OK | Single casilla `0603` "Por ganancias patrimoniales, incluidos premios." 2025 section moves to `retenciones_ingresos_cuenta_pagos_fraccionados`. Concept stable. |
| `irpf_total_pagos_cuenta` | OK | Single casilla `0609` "Total pagos a cuenta." Coherent aggregate. |
| `irpf_compensacion_conyuges_bank_name` | RENAME | Contains English in the role name: `bank_name`. Convention requires stable Spanish tax terminology. Rename to `irpf_compensacion_conyuges_entidad_bancaria_nombre`. |
| `irpf_deduccion_asturias_vivienda_protegida_2021_pendiente` | RENAME | Name encodes the year 2021 — transient. The role covers the rolling "pending amount from prior year's protected-housing deduction" across 2021–2025. Rename to `irpf_deduccion_asturias_vivienda_protegida_pendiente_ejercicio_anterior`. |
| `irpf_deduccion_castilla_la_mancha_traslado_vivienda` | OK | Single casilla `0207`. 2021 label is "Por residencia habitual en zonas rurales" but 2022+ is "Por traslado de vivienda habitual." The role name reflects the 2022+ dominant label. The 2021 entry is a transitional labelling; same casilla id retained. Acceptable. |
| `irpf_deduccion_la_rioja_vehiculos_electricos` | OUTLIER | The 2024 revision is absent (gap between 2023 and 2025). Moreover 2025 uses a **different casilla id**: `0255` instead of `1077` used in 2020–2023. This suggests the deduction was replaced or renumbered in 2024 and a new casilla assigned in 2025. The 2025 member `0255` may belong to a separate role if the 2024 deduction lapsed and was reintroduced. **OUTLIER**: `0255` rev 2025 should be confirmed against AEAT 2025 form — if it is a new/re-introduced deduction casilla it deserves its own role `irpf_deduccion_la_rioja_vehiculos_electricos_2025`. |
| `irpf_suma_retenciones_capital_inmobiliario_aggregate` | OK | Single casilla `0598` "Suma de retenciones e ingresos a cuenta" in `inmuebles_res`, decimal. Revisions 2020–2024 only (2025 not present — likely absorbed into different section). Coherent for revisions covered. |
| `irpf_deduccion_baleares_ela` | SPLIT | Three different deductions share casilla `0770` across revisions: 2022 = "acogida de personas desplazadas por el conflicto de Ucrania", 2023 = "subvenciones para paliar el impacto de la inflación 2023", 2024/2025 = "gastos derivados de la esclerosis lateral amiotrófica (ELA)." These are three distinct, annually-changing deducciones using the same casilla slot. The role name reflects only the 2024/2025 content (ELA). Split: three revision-scoped roles or acknowledge the role tracks a "deducción extraordinaria anual de Baleares" slot that changes content yearly. Recommend: `irpf_deduccion_baleares_extraordinaria_anual` as the stable role name, with per-revision label variation. |
| `irpf_deduccion_murcia_arrendamiento_vivienda` | OK | Single casilla `0991` "Por arrendamiento de vivienda habitual." Revisions 2022–2025 (introduced 2022). Coherent. |
| `irpf_ganancia_cripto_ganancia_pendiente_4` | OK | Single casilla `1875` "Ganancia patrimonial pendiente de imputación" in `gp_otros_criptomonedas`. Revisions 2022–2025. Suffix `_4` = fourth instalment. Coherent. |
| `irpf_ganancia_cripto_titular` | OK | Single casilla `1858` "Contribuyente titular" in `gp_otros_criptomonedas`, text. 2022–2025. Coherent. |
| `irpf_ganancia_inmueble_catastral_1_b` | OK | Single casilla `1883` "Referencia catastral 1" in `gp_otros_inmuebles`, text. Note: label has typo "castastral" in registry — not a role issue. 2022–2025. Coherent. |
| `irpf_ganancia_inmueble_ganancia_pendiente_3` | OK | Single casilla `1896` "Ganancia patrimonial pendiente de imputación" in `gp_otros_inmuebles`. Suffix `_3` = third instalment. Coherent. |
| `irpf_ganancia_inmueble_obtenida` | OK | Single casilla `1833` "Ganancia patrimonial obtenida" in `gp_otros_inmuebles`. 2022–2025. Coherent. |
| `irpf_ganancia_inmueble_valor_transmision` | OK | Single casilla `1826`. Label evolves from "Valor de transmisión" (2022) to "Valor de transmisión ([1911] - [1912])" (2023+) as the form gains explicit cost components. Coherent. |
| `irpf_intereses_demora_regularizacion_estatal` | OK | Single casilla `0582` "Intereses de demora correspondientes a la regularización anterior: Parte estatal." 2022–2025. Coherent. |
| `irpf_perdida_inmueble_pendiente_3` | OK | Single casilla `1897` "Pérdida patrimonial pendiente de imputación" in `gp_otros_inmuebles`. Suffix `_3`. Coherent. |
| `irpf_anexo_a_vehiculo_electrico_deduccion_importe` | OK | Single casilla `1927` "Importe de la deducción por la adquisición de vehículos eléctricos enchufables y de pila de combustible." 2023–2025. Coherent. |
| `irpf_anexo_b_birth_advance_paid` | RENAME | Mixed language. Rename to `irpf_anexo_b_deduccion_nacimiento_abono_anticipado`. |
| `irpf_deduccion_baleares_nacimiento` | OK | Single casilla `1718` "Por nacimiento." Annexe reference evolves. 2023–2025. Coherent. |
| `irpf_deduccion_c_valenciana_generado_pendiente_aplicacion` | SPLIT | Two casillas with different ids and different meanings: `0808` rev 2022 = "Importe aplicado en el ejercicio" (amount **used** this year) vs `0848` rev 2024/2025 = "Importe generado en 20XX pendiente de aplicación" (amount **generated** and pending). These are opposing flow directions (application vs. carry-forward). Split: `irpf_deduccion_c_valenciana_importe_aplicado_ejercicio` (0808/2022) and `irpf_deduccion_c_valenciana_generado_pendiente_aplicacion` (0848/2024-2025). |
| `irpf_deduccion_rib_illes_balears_estatal` | OK | Single casilla `0502` "Por dotaciones a la Reserva para Inversiones en las Illes Balears... Parte estatal." 2023–2025. Coherent. RIB = Reserva para Inversiones en Baleares. |
| `irpf_ed_reduccion_copa_america` | OK | Single casilla `0236` "Reducción de rendimientos acogidos al régimen fiscal del acontecimiento XXXVII Copa América Barcelona." Temporal special regime. 2023–2025. Coherent. |
| `irpf_feac_ganancia_patrimonial_diferida` | OK | Single casilla `1988` "Ganancia patrimonial diferida (Capítulo VII LIS)." FEAC = Fusiones, Escisiones, Aportaciones, Canjes. 2023–2025. Coherent. |
| `irpf_ganancia_inmueble_importe_real_transmision` | OK | Single casilla `1911` "Importe real de la transmisión" in `gp_otros_inmuebles`. 2023–2025. Coherent. |
| `irpf_rendimiento_trabajo_copa_america_reduccion` | OK | Single casilla `0057` Copa América reduction on employment income. 2023–2025. Coherent. |
| `irpf_deduccion_asturias_acciones_participaciones` | OK | Single casilla `1683` "Por inversión en la adquisición de acciones y participaciones sociales de nuevas entidades." 2024–2025. Coherent. |
| `irpf_deduccion_c_valenciana_generado_2023_pendiente` | OK | Single casilla `1209` "Importe generado en 2023 pendiente de aplicación." 2024–2025. Coherent. |
| `irpf_deduccion_cantabria_ayuda_domestica_2024_pendiente` | RENAME | Name encodes year 2024. Same issue as Asturias protected housing: the content rolls forward each year. Rename to `irpf_deduccion_cantabria_ayuda_domestica_pendiente_ejercicio_anterior`. |
| `irpf_deduccion_galicia_otras` | OK | Single casilla `1038` "Otras deducciones" in `galicia_res`. 2023–2024. Coherent catch-all. |
| `irpf_deduccion_madrid_vivienda_municipio_riesgo` | OUTLIER | `2027` rev 2024 = "Por adquisición de vivienda habitual por nacimiento o adopción de hijos" while `2027` rev 2025 = "Por adquisición de vivienda habitual en municipios en riesgo de despoblación." These are two **different** deductions sharing a casilla slot across years; the 2024 label is about family circumstances (birth/adoption) while the 2025 label is about depopulation-risk municipalities. **OUTLIER**: Both members are present and correct for their respective revisions, but the role name `municipio_riesgo` only captures the 2025 concept. The 2024 entry is semantically different. Recommend splitting into revision-scoped roles or renaming to a neutral slot descriptor like `irpf_deduccion_madrid_vivienda_habitual_especifica`. |
| `irpf_ganancia_otros_exenta_50pct_urbanos` | OK | Single casilla `1641` "Ganancia exenta 50 por 100 (sólo determinados inmuebles urbanos)." 2020–2021 only (transitional regime ended). Coherent. |
| `irpf_anexo_c_exceso_sps_rg_aportaciones_pendiente_fin` | OK | Single member: `1759` rev 2021 "Ejercicio 2021: Aportaciones personales pendientes de aplicación en ejercicios futuros" in `aportaciones_sist_prevision_social_rg_res`. Single-revision role — legitimate if 2021 was the only year this specific carryforward existed. Coherent for its scope. |
| `irpf_conyuge_no_residente_flag` | OK | Single member: `NORESIDENTE` rev 2025, boolean, "Conyuge no residente y no contribuyente IRPF." 2025-only new field. Coherent. |
| `irpf_deduccion_andalucia_enfermedad_celiaca` | OK | Single member: `1476` rev 2025, "Para familias con enfermedad celíaca diagnosticada." New 2025 deduction. Coherent. |
| `irpf_deduccion_cantabria_arrendamiento_viviendas_vacias` | OK | Single member: `1706` rev 2025. New 2025 deduction for renting empty housing. Coherent. |
| `irpf_deduccion_catalunya_generado_2025_pendiente` | RENAME | Name encodes year 2025. If this role persists into 2026 revision with a rolling forward, the name becomes stale. However as a single-year 2025 role it is acceptable in the short term. Flag for renaming pattern: `irpf_deduccion_catalunya_pendiente_ejercicio_anterior`. |
| `irpf_deduccion_galicia_generado_2025_pendiente_2` | RENAME | Same issue as above. Rename pattern: `irpf_deduccion_galicia_pendiente_ejercicio_anterior_2`. |
| `irpf_deduccion_murcia_cristales_lentes` | OK | Single member: `2149` rev 2025. New 2025 deduction for glasses/contact lenses. Coherent. |
| `irpf_deduccion_murcia_infraestructuras_referencia_catastral_flag` | RENAME | Name says `infraestructuras` but label is "Si no tiene referencia catastral, marque con una 'X'." The infrastructure concept is absent in the label; this is a cadastral reference absence flag within a Murcia deduction. Rename to `irpf_deduccion_murcia_sin_referencia_catastral_flag`. |
| `irpf_ed_regularizacion_reta_ingresar` | OK | Single member: `0196` rev 2025 "Regularizacion cuotas RETA a ingresar." RETA = Régimen Especial Trabajadores Autónomos. New 2025 field. Coherent. |
| `irpf_ganancia_fondos_coti_ganancia_no_exenta` | OK | Single member: `2232` rev 2025 "Ganancias patrimoniales no exentas" in `gp_fondos_coti`. New 2025 section for listed investment funds. Coherent. |
| `irpf_incremento_maternidad_guarderia_no_aplicado_2020` | RENAME | Name encodes year 2020. Rename to `irpf_incremento_maternidad_guarderia_no_aplicado_ejercicio`. |
| `irpf_re_atrib_reduccion_actividades_artisticas` | OK | Single member: `0384` rev 2025 "Reducción por rendimientos de actividades artísticas obtenidos de manera excepcional (DA 60ª)." New 2025 provision. Coherent. |

## Summary counts

| verdict | count |
|---|---|
| OK | 84 |
| RENAME | 14 |
| SPLIT | 5 |
| OUTLIER | 4 |
| **Total roles reviewed** | **68** |

Note: Some roles carry multiple verdicts (e.g. RENAME + OUTLIER); the table above counts
primary verdict per role. Total distinct issues: 14 renames, 5 splits, 4 outlier casillas.

### Key issues requiring action

- **OUTLIER** `1692` rev 2022 in `irpf_anexo_c_exceso_eeficiencia_pendiente_inicio`: label references Canarias investment reserve, not energy-efficiency excess.
- **OUTLIER** `0255` rev 2025 in `irpf_deduccion_la_rioja_vehiculos_electricos`: different casilla id with a gap in 2024 — possible new deduction introduction.
- **OUTLIER** `2027` in `irpf_deduccion_madrid_vivienda_municipio_riesgo`: 2024 = family-circumstances deduction, 2025 = depopulation-risk deduction; different concepts sharing a slot.
- **SPLIT** `irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente`: mixes current-year balance, current-year capped carry-in, and prior-year residuals.
- **SPLIT** `irpf_deduccion_eficiencia_energetica_situacion_clave`: conflates energy-improvement and electric-vehicle deduction situación fields.
- **SPLIT** `irpf_deduccion_baleares_ela`: casilla 0770 changes deduction subject every year (Ukraine, inflation, ELA) — role name should be neutralised.
- **SPLIT** `irpf_deduccion_c_valenciana_generado_pendiente_aplicacion`: mixes amount-applied (0808) with carry-forward-generated (0848).
- **DATA_TYPE MISMATCH** `irpf_re_atrib_inmueble_num_dias` (1618): labelled "Nº de días" but typed `money(default)` — registry-level defect to flag.
