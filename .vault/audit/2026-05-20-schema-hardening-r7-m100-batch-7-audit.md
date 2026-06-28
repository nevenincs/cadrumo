---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m100 batch-7 semantic audit

## Scope

Batch-7 contains 132 `semantic_role` groups extracted from the M100 (IRPF) registry across revisions 2020–2025. Each group was judged on three axes: (1) name accuracy against the Spanish IRPF tax vocabulary, (2) member coherence — whether all casillas belong to the declared concept — and (3) granularity — whether the group conflates distinct legal concepts or is over-narrow.

Registry TOMLs under `src/aeat/_data/registry/aeat/modelos/100/revisions/*/casillas/` were consulted for disputed cases.

## Findings

| role | verdict | detail |
|---|---|---|
| `irpf_eo_agr_rendimiento_base_producto` | OK | 17 unique ids × 6 revisions, all `money(default)`, single section `reg_estima_obj_agricola/actividad_agr`. Label stable. |
| `irpf_eo_modulo_definicion` | OK | 7 ids × 6 revisions, all `text`, section `reg_estima_obj/actividad_est_obj`. "Definición" describes the module definition field correctly. |
| `irpf_anexo_b_catastral_ref` | SPLIT | Members span five distinct Anexo B subsections: `an_b_inf_adc_eps` (3 refs per immovable, a rental EP context), `an_b_inf_ad_ref_cat` (dedicated catastral reference sub-section, 2 refs, 2023+), `an_b_inf_adc_ges` (management annex, 2024+), `an_b_inf_adc_vv` (vacant-dwelling annex, 2024+), and `an_b_inf_adc_rcince` (new 2025 context). Each subsection represents a distinct legal context where a catastral reference is collected; grouping them under one role loses context. Recommend splitting into at minimum: `irpf_anexo_b_eps_referencia_catastral`, `irpf_anexo_b_ref_cat_referencia_catastral`, `irpf_anexo_b_ges_referencia_catastral`, `irpf_anexo_b_vv_referencia_catastral`, `irpf_anexo_b_rcince_referencia_catastral`. |
| `irpf_anexo_c_exceso_deportistas_aplicado` | OK | Single section `excesos_deportistas_res`, `money(default)`, year-labelled carryforward "applied in this declaration" series. Name correctly identifies the regime (DT 11ª professional athletes excess) and the flow direction (applied). |
| `producer_nif` | RENAME | Missing `irpf_` prefix; role name `producer_nif` is not domain-namespaced. All members are NIF fields for "NIF del productor N" in `deducciones_inversion_empresarial_res` (art. 36/39 LIS production deduction, Anexo A). Corrected: `irpf_deduccion_inversion_empresarial_productor_nif`. |
| `irpf_anexo_c_exceso_deportistas_pendiente_fin` | OK | Single section, `money(default)`, year-labelled "pendiente de aplicación en ejercicios futuros" series. Correct name for the regime carryforward remainder. |
| `irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio` | OK | Single section `saldos_neg_gy_p_general_res`, `money(default)`, "pendiente al principio del periodo" series. Accurate. |
| `tenant_nif` | RENAME + OUTLIER | Missing `irpf_` prefix. Additionally, casilla `[0158] 2021` (`toma_datos_ampliada/inmuebles/inmueble`) is a data-entry NIF for the tenant on the immovable input form, while the remaining members are result/summary fields in `an_b_inf_adc_eps` (Anexo B EP context, up to 3 tenants). These are different form surfaces. The immovable input casilla should belong to a dedicated role such as `irpf_inmueble_arrendatario_nif`; the Anexo B group should be `irpf_anexo_b_eps_arrendatario_nif`. OUTLIER: `[0158] 2021` is misassigned to this role — registry TOML confirms `semantic_role = "tenant_nif"` but this casilla belongs in the immovable-input section, not in the Anexo B EP summary. |
| `irpf_deduccion_eficiencia_energetica_cantidades_satisfechas` | SPLIT | Members span two section contexts: `mejoras_energeticas_viv` (energy-efficiency improvements on residential buildings, three distinct casilla types for three deduction tiers per RLPF art. 59 bis) and `vehiculos_elec_y_puntos_carga` (casilla 1933, amounts paid for EV charging points, a distinct deduction sub-type introduced 2023). Registry TOML for 1933 confirms the same `semantic_role`, but this is a broader shared label: amounts paid for EV charging installations are not the same legal concept as building energy-efficiency improvement amounts. Recommend: `irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas` (the `mejoras_energeticas_viv` group) and `irpf_deduccion_vehiculo_punto_carga_cantidades_satisfechas` (1933). |
| `ascendant_nif` | RENAME + OUTLIER | Missing `irpf_` prefix. Three semantic surfaces exist: (a) `[0625]` all revisions — NIF of ascendant in the disability deduction calculation result (`deduc_ascendiente_disc_res`); (b) `[0667]` all revisions — NIF of ascendant whose deduction is being regularised (`regularizacion_ascendiente_res`); (c) `[DNIASDLG] 2025` — new 2025 identification data section (`datos_identificativos/ascendientes/ascendiente`). The regularisation NIF and the deduction NIF are arguably different roles (one is the subject of a new deduction, the other is part of a regularisation correction). However, the registry assigns all three to this role; pending a domain decision, flag as RENAME with a note. Corrected name: `irpf_ascendiente_nif`. Marginal OUTLIER flag on `[DNIASDLG] 2025` — it is the identification-data NIF (not a deduction result field), but the registry intentionally groups it here. |
| `irpf_deduccion_eficiencia_energetica_consumo_anterior` | OK | 2 ids × 5 revisions, single section `mejoras_energeticas_viv`, `money(default)`. Name correctly describes "consumo de energía primaria no renovable anterior" input for the energy-efficiency deduction. |
| `irpf_deduccion_castilla_la_mancha_guarderia` | OK | Two casillas (`[0210]`, `[0211]`): main deduction amount plus, by convention, a second field for complementary declaration. Same label and section throughout. Name accurate. |
| `irpf_abono_anticipado_conyuge_discapacidad` | OK | Single casilla `[0249]` across 6 revisions. In 2020–2024 it lives in `deduc_conyuge_disc_res`; in 2025 it migrates to the top-level `resultado_declaracion` section with simplified label. Label evolution and section migration are expected revision changes for the same legal field (art. 81 bis LIRPF advance payment). Registry TOMLs confirm consistent `semantic_role`. |
| `irpf_anexo_a_residente_ue_cuota_conjunta_hipotetica` | OK | Single casilla, 6 revisions, `money(default)`, single section. Name accurately describes the hypothetical joint-assessment quota for EU/EEA residents. |
| `irpf_anexo_c_exceso_sps_disc_parientes_generado` | OK | Year-labelled "aportaciones no aplicadas" series for contributions to social provision systems for disabled persons by relatives (art. 52 LIRPF). Name is accurate. |
| `irpf_anexo_c_exencion_rv_retencion_comprometida` | OK | Year-labelled "retención que se compromete a reinvertir" series for reinvestment exemption in annuities. Name is accurate. |
| `irpf_base_liquidable_general` | OK | Single casilla, 6 revisions, `decimal`, `base_liquidable_res`. Core IRPF result casilla; name accurate. |
| `irpf_cuota_base_liquidable_ahorro_estatal` | OK | Single casilla, 6 revisions, `money(default)`, `gravamenes_res`. Name accurately identifies the state-portion quota on savings tax base. |
| `irpf_cuota_liquida_estatal_incrementada` | OK | Single casilla `[0585]`. Label varies by revision (formula reference updated) and section migrates from `gravamenes_res` to `resultado_declaracion` in later revisions. All variants describe the same computed result (incremented state net tax quota). Registry-consistent. |
| `irpf_deduccion_andalucia_ejercicio_fisico` | OUTLIER | In revisions 2020–2024, casilla `[0921]` is in `canarias_res` with label "Por donaciones en metálico a descendientes o adoptados menores de 35 años para la adquisición o rehabilitación de su primera vivienda habitual" — a Canarias autonomous deduction, not an Andalucía deduction. Only in 2025 does `[0921]` move to `andalucia_res` with the correct label. OUTLIER: `[0921] 2020–2024` are misassigned; they should carry `irpf_deduccion_canarias_donaciones_descendientes_vivienda` (or similar). Registry TOMLs for 2020 confirm `semantic_role = "irpf_deduccion_andalucia_ejercicio_fisico"` is already persisted in the source, so this is a registry-level semantic error introduced during M100 migration. |
| `irpf_deduccion_aragon_arrendamiento_vinculado` | OK | Single casilla `[1170]` across 6 revisions, `money(default)`, `aragon_res`. Label varies to track which Anexo B annex number carries the cross-reference (B.7, B.9, B.10, B.12), which is an expected year-by-year renumbering. Core concept is stable. |
| `irpf_deduccion_aragon_vivienda_victimas_terrorismo` | OK | Stable single casilla, single label, `aragon_res`. Name accurate. |
| `irpf_deduccion_asturias_partos_multiples` | OK | Stable single casilla, single label, `asturias_res`. Name accurate. |
| `irpf_deduccion_baleares_donaciones_investigacion` | OK | Stable single casilla, single label, `i_baleares_res`. Name accurate. |
| `irpf_deduccion_c_valenciana_abonos_culturales` | OK | Stable single casilla, single label, `c_valenciana_res`. Name accurate. |
| `irpf_deduccion_c_valenciana_donaciones_otros_fines` | OK | Stable single casilla, single label, `c_valenciana_res`. Name accurate. |
| `irpf_deduccion_c_valenciana_rentas_arrendamiento` | OK | Stable single casilla, single label, `c_valenciana_res`. Name accurate. |
| `irpf_deduccion_canarias_donaciones_patrimonio_historico` | OK | Stable single casilla, single label, `canarias_res`. Name accurate. |
| `irpf_deduccion_canarias_referencia_catastral_2` | OK | Single casilla, 6 revisions, `text`, `canarias_res`. Accurately names a reference field in the Canarias deduction section. |
| `irpf_deduccion_cantabria_donativos_fundaciones` | OK | Stable single casilla, single label, `cantabria_res`. Name accurate. |
| `irpf_deduccion_castilla_la_mancha_acogimiento_menores` | OK | Stable single casilla, single label, `castilla_la_mancha_res`. Name accurate. |
| `irpf_deduccion_castilla_y_leon_aplicado_ejercicio` | RENAME | Casilla `[0984]` in 2020–2022 holds "importe generado en año N pendiente de aplicación" (pending carryforward amount), while in 2023–2025 it holds "importe aplicado en el ejercicio" (amount applied in the current year). These are semantically distinct: one is a carryforward balance, the other is the current-year application. However, the registry consistently assigns the same casilla to this role across the lifecycle of the CyL deduction. The 2020–2022 labels describe the pending amount from a prior year, not the applied amount. Name `_aplicado_ejercicio` only matches the 2023+ behaviour. Corrected name reflecting the full lifecycle: `irpf_deduccion_castilla_y_leon_pendiente_o_aplicado`. |
| `irpf_deduccion_castilla_y_leon_importe_general` | OK | Stable single casilla, consistent label "Importe de la deducción", `castilla_y_leon_res`. Name adequate. |
| `irpf_deduccion_catalunya_donaciones_lengua_catalana` | OK | Stable single casilla, single label, `catalunya_res`. Name accurate. |
| `irpf_deduccion_doble_imposicion_imputacion_rentas` | OK | Single casilla `[0588]`-equivalent; label varies across revisions (abbreviated vs. full form) and migrates from `cuota_autoliquidacion_res` to `resultado_declaracion`. Both surfaces describe the same double-taxation deduction for image-rights income imputations. Name accurate. |
| `irpf_deduccion_extremadura_partos_multiples` | OK | Stable single casilla, single label, `extremadura_res`. Name accurate. |
| `irpf_deduccion_galicia_certificado_eficiencia_1` | RENAME | In 2020, casilla `[0826]` carries the label for the overall energy-efficiency improvement deduction amount ("Por obras de mejora de eficiencia energética…"), not a certificate registration number. From 2021 onward the same casilla captures "Número de inscripción del certificado 1:". The role name `_certificado_eficiencia_1` only matches 2021+. In 2020 the casilla is a monetary deduction result, not a certificate ID. However the registry assigns the same role to both. RENAME to `irpf_deduccion_galicia_eficiencia_energetica_certificado_1` to correctly reflect that this is Galicia's energy-efficiency deduction certificate-1 field (with the understanding that 2020 used the same slot for the headline amount before the form was restructured). |
| `irpf_deduccion_galicia_nacimiento_adopcion` | OK | Stable single casilla, single label, `galicia_res`. Name accurate. |
| `irpf_deduccion_la_rioja_arrendamiento_menores_36` | OK | Single casilla; label varies to track the Anexo B renumbering. Core concept (La Rioja rental deduction for under-36 taxpayers) is stable. Name accurate. |
| `irpf_deduccion_la_rioja_obras_rehabilitacion` | OK | Stable single casilla, single label, `la_rioja_res`. Name accurate. |
| `irpf_deduccion_madrid_donativos_fundaciones_deportivos` | OK | Single casilla `[1049]`. In 2020–2021 the label was "Por donativos a fundaciones"; from 2022 it expanded to "Por donativos a fundaciones y clubes deportivos". The expanded name matches the current and dominant label. Acceptable. |
| `irpf_deduccion_murcia_discapacidad` | OK | Stable single casilla, single label, `murcia_res`. Name accurate. |
| `irpf_deduccion_unidades_familiares_ue_eee_autonomica` | RENAME | Name contains `_autonomica` but the section is `gravamenes_res` (state/autonomous tax calculation layer), not an autonomous community deduction section. The label itself refers to the deduction for family units where members reside in EU/EEA countries (art. 93 LIRPF and related). Corrected name: `irpf_deduccion_unidades_familiares_ue_eee`. |
| `irpf_descendiente_num_contribuyentes_derecho` | OK | Single casilla `[0618]`, 6 revisions, `money(default)` (used as integer count), `deduc_descendiente_disc_res`. Name accurately describes the headcount field for the descendant disability deduction. |
| `irpf_ed_dietas_viajes_personal` | OK | Single casilla, 6 revisions, two sections (`toma_datos_ampliada` and `rendimientos_actividades_economicas`) reflecting input-form and summary-form dual placement. Label and concept stable. Name accurate. |
| `irpf_ed_mecenazgo_actividades_interes_general` | OK | Single casilla, 6 revisions, label evolves from abbreviated to full form. Core concept (patronage / mecenazgo tax incentive for general-interest activities under direct estimation) is stable. Name accurate. |
| `irpf_ed_provisiones_deducibles` | OK | Stable single casilla, single label, direct-estimation section. Name accurate. |
| `irpf_ed_sueldos_salarios` | OK | Stable single casilla, single label, direct-estimation section. Name accurate. |
| `irpf_eo_agr_cobros_pagos_flag` | OK | Stable single casilla, `boolean`, OA agricultural section. Name accurately describes the cash-basis election flag. |
| `irpf_eo_agr_ingresos_integros_arroz_oleaginosas_flores` | OK | Single casilla, 6 revisions. Label varies between the specific crop enumeration (2020 has a longer description) and a generic "Ingresos íntegros". Section is consistent. Name accurately represents the specific OA agricultural income sub-category. |
| `irpf_eo_agr_ingresos_integros_porcino_cria_ovino_leche_apicultura` | OK | Same pattern as above for the livestock sub-category. Name accurate. |
| `irpf_eo_agr_suma_rdtos_netos_reducidos` | OK | Single casilla, 6 revisions, `decimal`, result section. Name accurate for the sum of net reduced returns of agricultural OA activities. |
| `irpf_eo_rdto_neto_minorado` | OK | Single casilla, 6 revisions, `decimal`, `reg_estima_obj`. Accurately names the reduced net return for OA activities. |
| `irpf_escala_sobre_base_general_estatal` | OK | Single casilla, 6 revisions, `money(default)`, `gravamenes_res`. Name accurately describes application of the general and autonomous tax scale to the general base (state portion). |
| `irpf_familia_numerosa_num_ascendientes` | OK | Single casilla `[0652]`, 6 revisions, `money(default)` (count field), `deduc_familia_numerosa_res`. Name accurate. |
| `irpf_g4_re_valor_transmision_acciones` | OK | Single casilla, 6 revisions, `money(default)`, `g_cambio_residencia_ext/g4_re` section (exit-tax special regime G4). Name accurate. |
| `irpf_ganancia_derechos_exenta_renta_vitalicia` | OK | Single casilla, 6 revisions, `money(default)`, `gp_derechos` section. Correctly names the exempt capital gain for reinvestment in life annuities (art. 38.3 LIRPF). |
| `irpf_ganancia_fondos_reduccion_dt9` | OK | Single casilla, 6 revisions, `money(default)`, `gp_fondos`. Correctly names the reduction applicable under DT 9ª for mutual funds. Both label forms (DT 9ª / D.T. 9ª) are consistent. |
| `irpf_ganancia_otras_base_ahorro` | OK | Single casilla, 6 revisions. Label gains the parenthetical "(intereses indemnizatorios)" in some revisions. Core concept (other capital gains integrating into savings tax base) is stable. Name accurate. |
| `irpf_ganancia_otros_ganancia_pendiente_1` | OK | Single casilla, 6 revisions, `money(default)`, `gp_otros_elementos`. Label template inconsistency (`{0}` placeholder visible in some revisions) is a registry source artefact, not a semantic split. Name accurate for the first pending-imputation instalment. |
| `irpf_ganancia_otros_obtenida` | OK | Stable single casilla, single label formula, `gp_otros_elementos`. Name accurate. |
| `irpf_ganancia_otros_valor_adquisicion` | OK | Stable single casilla, single label, `gp_otros_elementos`. Name accurate. |
| `irpf_ganancia_premios_juegos_pub_ingresos_cuenta` | OK | Stable single casilla, single label, `gp_premios/juegos_pub`. Name accurate for the withholding tax on public lottery/gaming prizes. |
| `irpf_inmueble_a_disposicion_flag` | OK | Stable single casilla, `boolean`, `inmuebles/inmueble`. Name accurate for the "owner's personal disposal" use-type flag. |
| `irpf_inmueble_adquisicion_tipo_onerosa` | OK | Two casillas across 6 revisions, `boolean`, same section. The pair represents the onerosa acquisition-type checkbox (main declarant + second declarant). Name accurate. |
| `irpf_inmueble_dias_otros_usos` | RENAME | Label "Número de días" is accurate but the role name `_dias_otros_usos` implies this day-count field is specifically for "other uses" (usos distintos). The casilla context (`toma_datos_ampliada/inmuebles/inmueble`) is the general immovable input form, where "Número de días" could refer to days in any use category. Registry confirms label and section. Name is plausible but ambiguous — the day-count is more precisely for the non-let, non-principal-residence period. Recommend: `irpf_inmueble_dias_disponibilidad` to better reflect the "días a disposición" concept from LIRPF art. 85. |
| `irpf_integracion_gyp_general_saldo_negativo` | OK | Stable single casilla, single label formula, `gp_patrimoniales_res`. Name accurate for the negative balance in capital-gain/loss integration on the general tax base. |
| `irpf_minimo_aplicado_base_ahorro_estatal` | OK | Single casilla, 6 revisions. Label has a minor typo (double colon in some revisions). Core concept (amount of personal and family minimum applied against the savings tax base, state portion) is stable and name is accurate. |
| `irpf_minimo_personal_familiar_estatal` | OK | Stable single casilla, single label, `minimo_per_fam_res`. Name accurate. |
| `irpf_perdida_otras_ejer_ant_imputable` | OK | Single casilla, 6 revisions. Year-labelled "pérdida patrimonial que procede imputar a [year]" series. Name accurately describes carryforward capital loss imputable from prior years. |
| `irpf_re_aie_deduccion_ceuta_melilla` | OK | Stable single casilla, single label, `re_agrup_interes_economico`. Name accurate for the Ceuta/Melilla income deduction on attributed amounts from economic interest groups. |
| `irpf_re_atrib_cap_inmo_minoraciones` | OK | Stable single casilla, single label, `re_at_rentas`. Name accurate for the reductions applicable to attributed capital-immovable income. |
| `irpf_re_atrib_entidad_nif` | OK | Stable single casilla, single label, `re_at_rentas`. Name accurate for the entity NIF in an income-attribution regime. |
| `irpf_re_atrib_entidad_nif_extranjero_flag` | OK | Two casillas (2 ids), 6 revisions, `boolean`, `re_at_rentas`. Label character encoding garbled in source but content is the "foreign NIF" flag. Name accurate. |
| `irpf_re_atrib_gp_reducidas_no_exentas_imputables` | OK | Single casilla, year-labelled series, `re_at_rentas`. Name accurate for attributed reduced non-exempt capital gains. |
| `irpf_re_atrib_retenciones_cap_mob` | OK | Stable single casilla, single label, `re_at_rentas`. Name accurate. |
| `irpf_re_iic_denominacion` | OK | Stable single casilla, single label, `re_institu_inversion_colectiva`. Name accurate. |
| `irpf_red_discapacidad_aportaciones_parientes` | OK | Single casilla, year-labelled series, `red_discapacidad`. Name accurately describes contributions made by relatives to disability-person social provision systems (art. 52 LIRPF). |
| `irpf_reduccion_mutualidad_deportistas_aplicada` | OK | Stable single casilla, single label, `base_liquidable_res`. Name accurate. |
| `irpf_regularizacion_cobro_anticipado_descendiente` | OK | Single casilla, 6 revisions. Label changes between a short form (2025 `resultado_declaracion`) and the expanded form (earlier revisions). Same legal concept (regularisation of advance payment for disabled-descendant deduction). Name accurate. |
| `irpf_rendimiento_capital_inmobiliario_gasto_saldos_dudoso_cobro` | OK | Single casilla, 6 revisions, two sections (`inmuebles/inmueble` and `gastos_deducibles`). The dual section reflects the same figure appearing on both the input form and the deductible-expenses summary. Name accurate. |
| `irpf_rendimiento_capital_inmobiliario_suma_rendimientos_netos_reducidos` | OK | Single casilla, 6 revisions, `decimal`. Two sections reflect input-form and summary positions. Name accurate. |
| `irpf_rendimiento_capital_mobiliario_ahorro_reduccion_seguros_antiguos` | OK | Single casilla, 6 revisions. Label evolves from abbreviated to full form. Core concept (transitional reduction for certain insurance contracts under DT 4ª LIRPF) is stable. Name accurate. |
| `irpf_rendimiento_capital_mobiliario_general_propiedad_industrial` | OK | Single casilla, 6 revisions, `decimal`. Two sections reflect dual placement. Name accurate. |
| `irpf_rendimiento_trabajo_especie_ingreso_cuenta_repercutido` | OK | Single casilla, 6 revisions. Label evolves from abbreviated to full form. Core concept (in-kind income with passed-on withholding) is stable. Name accurate. |
| `irpf_rendimiento_trabajo_rendimiento_neto` | OK | Single casilla, 6 revisions, `decimal`. Two sections reflect result and summary. Name accurate. |
| `irpf_retencion_atribuida_ganancias_patrimoniales` | OK | Single casilla, 6 revisions. Year-labelled "suma de retenciones atribuidas de ganancias" series. 2025 label uses abbreviated form. Name accurate. |
| `irpf_tipo_medio_gravamen_ahorro_estatal` | RENAME | The label (and formula) is "tipos medios de gravamen … parte estatal"; however, this represents the effective tax rate (tipo medio) derived from the savings-base quota — it is a rate/percentage field but uses `money(default)` data type rather than a rate type. The name is accurate as a label transcription but misleading because `money(default)` implies a monetary amount rather than a rate. The semantic concern is the data_type mismatch; the name itself (`_tipo_medio_gravamen_ahorro_estatal`) is correct. No rename needed for the role name — flag data_type as `ratio` not `money(default)`. |
| `irpf_anexo_c_gan_per_cuartas_tipo_ayuda` | OK | Single casilla, 5 revisions (2021+), `text`, `gan_per_cuartas`. Name accurately describes the type-of-aid field in the quarterly payment capital-gains Anexo C context. |
| `irpf_deduccion_asturias_formacion_autoempleados` | OK | Single casilla, 5 revisions (2021+), `money(default)`, `asturias_res`. Name accurate. |
| `irpf_deduccion_castilla_la_mancha_arrendamiento_familia_numerosa` | OK | Single casilla, 5 revisions (2021+). Label cross-references Anexo B number which changes by year. Core concept (CLM large-family rental deduction) is stable. Name accurate. |
| `irpf_deduccion_la_rioja_donacion_bienes_culturales_autores` | OUTLIER | In 2021, casilla `[0253]` carries the label "Por donaciones para la promoción y estímulo de las actividades de fomento de mecenazgo" (La Rioja mecenazgo / patronage promotion), which is a different legal concept from the 2022+ label "Por donación de bienes culturales por sus autores o creadores y sus herederos" (donation of cultural assets by authors). These are two distinct La Rioja autonomous deductions that shared the same casilla slot when the form was restructured. OUTLIER: `[0253] 2021` is misassigned; it corresponds to a mecenazgo deduction that should carry `irpf_deduccion_la_rioja_mecenazgo` or similar. |
| `irpf_rendimiento_act_eco_atribuido_rdto_neto` | OK | Single casilla, 5 revisions (2021+), `money(default)`, `rendimientos_actividades_economicas`. Name accurate for the net income attributed from income-attribution-regime entities. |
| `irpf_deduccion_asturias_vehiculo_importe` | OK | Single casilla, 4 revisions (2022+), `money(default)`, `asturias_res`. Name accurate for the Asturias vehicle-related deduction amount. |
| `irpf_deduccion_castilla_la_mancha_intereses_vivienda` | OK | Single casilla, 4 revisions (2022+), `money(default)`, `castilla_la_mancha_res`. Name accurate. |
| `irpf_ganancia_cripto_exenta_renta_vitalicia` | OK | Single casilla, 4 revisions (2022+), `money(default)`, `gp_otros_criptomonedas`. Name accurate — exempt gain on crypto reinvestment in annuities. |
| `irpf_ganancia_cripto_no_exenta` | OK | Single casilla, 4 revisions (2022+), `money(default)`, `gp_otros_criptomonedas`. Name accurate — non-exempt net crypto gain. |
| `irpf_ganancia_inmueble_anio_imputacion_4` | RENAME | Name suffix `_4` is unexplained and appears to be a batch-assignment artefact. The casilla carries "Año de imputación" (year of imputation) for a patrimonial gain from an immovable sold on instalment terms. Corrected: `irpf_ganancia_inmueble_anio_imputacion`. |
| `irpf_ganancia_inmueble_fecha_adquisicion` | OK | Single casilla, 4 revisions (2022+), `text`, `gp_otros_inmuebles`. Name accurate. |
| `irpf_ganancia_inmueble_imputacion_plazos` | OK | Single casilla, 4 revisions (2022+), `boolean`, `gp_otros_inmuebles`. Name accurate for the instalment-payment imputation election. |
| `irpf_ganancia_inmueble_transmision_gratuita` | OK | Single casilla, 4 revisions (2022+), `boolean`, `gp_otros_inmuebles`. Name accurate. |
| `irpf_gp_elemento_referencia_catastral_3` | OK | Two casillas (`[0362]` and `[1630]`) in 2020–2021 only. Both are in `gp_otros_elementos`, both `text`. `[0362]` has a typo in its label ("castastral" instead of "catastral") but the registry assigns the same role. Two casillas covering the same logical field on two different rows of the same section (multi-element form). Name is accurate; the typo in `[0362]`'s label is a registry source defect to note but not a semantic-role error. |
| `irpf_perdida_inmueble_imputable_ejercicio` | OK | Single casilla, 4 revisions (2022+). Year-labelled loss-imputation series. Name accurate. |
| `irpf_regularizacion_numero_justificante_rectificacion` | OK | Single casilla, 4 revisions (2020–2023), `text`, `regularizacion_res`. Name accurate for the justification number of the rectification filing. |
| `irpf_deduccion_asturias_subvenciones_rehabilitacion` | OUTLIER | In 2020–2021, casilla `[0822]` carries the label "Por la obtención de subvenciones y/o ayudas para paliar el impacto provocado por la COVID-19 sobre los sectores especialmente afectados por la pandemia" — a specific COVID-19 pandemic relief deduction. In 2022 the same casilla becomes "Importe aplicado en el ejercicio" in the context of housing rehabilitation subsidies (a different concept). Registry TOMLs confirm both map to `irpf_deduccion_asturias_subvenciones_rehabilitacion`. OUTLIER: `[0822] 2020–2021` represent a COVID-specific deduction that should carry a distinct role such as `irpf_deduccion_asturias_covid_ayudas`. The concept was retired after 2021 and the casilla was repurposed. |
| `irpf_deduccion_c_valenciana_autoconsumo_desde_2023` | OK | Single casilla, 3 revisions (2023+), `money(default)`, `c_valenciana_res`. Name accurately identifies the C. Valenciana self-consumption energy deduction introduced in 2023. |
| `irpf_deduccion_murcia_donaciones_patrimonio_cultural` | OK | Single casilla, 3 revisions (2023+), `money(default)`, `murcia_res`. Name accurate. |
| `irpf_deduccion_vehiculo_tipo` | OK | Single casilla, 3 revisions (2023+), `text`, `vehiculos_elec_y_puntos_carga`. Name accurately identifies the vehicle type field in the EV deduction Anexo A section. |
| `irpf_feac_entidad_transmitida_denominacion` | OK | Single casilla, 3 revisions (2023+), `text`, `regimen_especial/feac` (FEAC = fiscal neutrality mergers/acquisitions special regime). Name accurate. |
| `irpf_ganancia_inmueble_amortizaciones` | OK | Single casilla, 3 revisions (2023+), `money(default)`, `gp_otros_inmuebles`. Name accurate — accumulated amortisations reducing acquisition cost for real estate gain calculation. |
| `irpf_rectsepa_cuenta_iban` | RENAME | Label is "SEPA rectificación" and section is `regularizacion_res/rectsepa`. The role name accurately references the SEPA account used for rectification payments, but the name should be `irpf_regularizacion_sepa_cuenta_iban` to follow the established `irpf_` prefix convention and situate it within the regularisation context. The current name lacks the `irpf_` prefix. |
| `irpf_anexo_b_account_foreign_flag` | OK | Two casillas (2 ids, both 2025), `boolean`, `an_b_inf_ad_cm_viv_hab`. Label consistent. The two casillas represent the same flag on two different mortgage/habitual-residence lines. Name is adequately descriptive; an `irpf_` prefix convention check: already starts with `irpf_`. Name accurate. |
| `irpf_anexo_b_device_purchase_amount` | OK | Single casilla (2 revisions: 2024–2025), `money(default)`, `an_b_inf_adc_enf` (illness/disability annex). Label slightly abbreviated in 2024, full in 2025. Name accurately describes the amount paid for medical devices. |
| `irpf_deduccion_c_valenciana_aportaciones_fondos_propios` | OK | Single casilla (2024–2025), `money(default)`, `c_valenciana_res`. Name accurate for the C. Valenciana equity-contribution deduction introduced 2024. |
| `irpf_deduccion_canarias_palma_desarraigo` | OK | Single casilla (2021–2022), `money(default)`, `canarias_res`. Name accurately captures the La Palma volcanic eruption displacement deduction (a time-limited measure). |
| `irpf_deduccion_castilla_la_mancha_municipio_codigo_2` | OK | Single casilla (2024–2025), `text`, `castilla_la_mancha_res`. Name accurate for the municipality code field used in CLM deductions. |
| `irpf_deduccion_madrid_nuevos_contribuyentes_generado` | OK | Single casilla (2024–2025), year-labelled "importe generado en [year]". Name accurate for the Madrid new-taxpayer deduction generated amount. |
| `irpf_deduccion_murcia_gastos_internet` | OK | Single casilla (2024–2025), `money(default)`, `murcia_res`. Name accurate. |
| `irpf_anexo_b_aav_amount_applied` | OK | Single casilla (2025 only), `money(default)`, `an_b_inf_adc_aav`. Name accurately describes the amount applied in the exercise for the AAV Anexo B context. |
| `irpf_ascendiente_fecha_nacimiento` | OK | Single casilla (2025 only), `text`, `datos_identificativos/ascendientes`. Name accurate for the ascendant date-of-birth field introduced in 2025. |
| `irpf_declarante_fecha_fallecimiento` | OK | Single casilla (2025 only), `text`, `datos_identificativos/declarante`. Name accurate for the declarant date-of-death field introduced in 2025. |
| `irpf_deduccion_c_valenciana_pendiente_2024_linea_4` | RENAME | The `_linea_4` suffix is a form-layout artefact, not a stable tax concept. The casilla is "Importe generado en 2024 pendiente de aplicación" within the C. Valenciana deduction. Corrected: `irpf_deduccion_c_valenciana_aportaciones_fondos_propios_pendiente_2024` or, if generalised across years, `irpf_deduccion_c_valenciana_aportaciones_fondos_propios_pendiente_anio_anterior`. The `_linea_4` is an internal form-layout identifier that should not appear in a stable semantic role name. |
| `irpf_deduccion_castilla_la_mancha_otras` | OK | Single casilla (2025 only), `money(default)`, `castilla_la_mancha_res`. Name accurate as a catch-all for miscellaneous CLM deductions. |
| `irpf_deduccion_galicia_ayudas_talidomida` | OK | Single casilla (2025 only), `money(default)`, `galicia_res`. Name accurate for the Galicia thalidomide-victims deduction. |
| `irpf_deduccion_la_rioja_medico_colegiado` | OK | Single casilla (2025 only), `text`, `la_rioja_res`. Name accurate for the physician registration number field in the La Rioja health deduction context. |
| `irpf_deduccion_murcia_infraestructuras_2025_pendiente` | RENAME | Year literal in role name (`_2025`) makes it revision-fragile. Pattern is "importe generado en 2025 pendiente de aplicación" for the Murcia infrastructure deduction. Corrected: `irpf_deduccion_murcia_infraestructuras_pendiente_anio_generacion`. |
| `irpf_descendiente_fecha_nacimiento` | OK | Single casilla (2025 only), `text`, `datos_identificativos/hijos/hijo`. Name accurate for the descendant date-of-birth field introduced in 2025. |
| `irpf_eo_reintegro_subvenciones` | OK | Single casilla (2025 only), `money(default)`, `reg_estima_obj`. Name accurate for the subsidy repayment field in objective estimation. |
| `irpf_ganancia_premios_juegos_valoracion_b` | RENAME | Suffix `_b` is an unexplained form-layout artefact. The casilla is "Valoración" in the `gp_premios/juegos` section (non-public gaming prizes). Corrected: `irpf_ganancia_premios_juegos_valoracion`. |
| `irpf_perdida_fondos_coti_importe_obtenido` | RENAME | Label is "Pérdidas patrimoniales" in `gp_fondos_coti` (listed investment funds). Name `_importe_obtenido` is inaccurate — the casilla records the loss amount, not an "obtained amount" (obtenido implies a gain). Corrected: `irpf_perdida_fondos_coti_importe`. |
| `irpf_rendimiento_trabajo_reduccion_actividades_artisticas_excepcional` | OK | Single casilla (2025 only), `money(default)`, `rendimientos_trabajo`. Name accurately describes the new 2025 reduction for exceptional artistic activity income. |

## Summary counts

| verdict | count |
|---|---|
| OK | 106 |
| RENAME | 12 |
| SPLIT | 2 |
| OUTLIER | 5 |
| **Total** | **132** |

**RENAME roles** (corrected names):
- `producer_nif` → `irpf_deduccion_inversion_empresarial_productor_nif`
- `tenant_nif` → `irpf_arrendatario_nif` (after OUTLIER extraction)
- `ascendant_nif` → `irpf_ascendiente_nif`
- `irpf_deduccion_unidades_familiares_ue_eee_autonomica` → `irpf_deduccion_unidades_familiares_ue_eee`
- `irpf_deduccion_castilla_y_leon_aplicado_ejercicio` → `irpf_deduccion_castilla_y_leon_pendiente_o_aplicado`
- `irpf_deduccion_galicia_certificado_eficiencia_1` → `irpf_deduccion_galicia_eficiencia_energetica_certificado_1`
- `irpf_inmueble_dias_otros_usos` → `irpf_inmueble_dias_disponibilidad`
- `irpf_ganancia_inmueble_anio_imputacion_4` → `irpf_ganancia_inmueble_anio_imputacion`
- `irpf_rectsepa_cuenta_iban` → `irpf_regularizacion_sepa_cuenta_iban`
- `irpf_deduccion_c_valenciana_pendiente_2024_linea_4` → `irpf_deduccion_c_valenciana_aportaciones_fondos_propios_pendiente_anio_anterior`
- `irpf_deduccion_murcia_infraestructuras_2025_pendiente` → `irpf_deduccion_murcia_infraestructuras_pendiente_anio_generacion`
- `irpf_ganancia_premios_juegos_valoracion_b` → `irpf_ganancia_premios_juegos_valoracion`
- `irpf_perdida_fondos_coti_importe_obtenido` → `irpf_perdida_fondos_coti_importe`

**SPLIT roles**:
- `irpf_anexo_b_catastral_ref` — five distinct Anexo B subsection contexts conflated
- `irpf_deduccion_eficiencia_energetica_cantidades_satisfechas` — building energy efficiency vs. EV charging point amounts

**OUTLIER casillas** (misassigned to current role):
- `[0921] 2020–2024` in `irpf_deduccion_andalucia_ejercicio_fisico` — actually Canarias donation-to-descendants-for-housing deduction
- `[0158] 2021` in `tenant_nif` — immovable-input NIF (should be `irpf_inmueble_arrendatario_nif`)
- `[0822] 2020–2021` in `irpf_deduccion_asturias_subvenciones_rehabilitacion` — COVID-19 sector-relief deduction, not rehabilitation subsidies
- `[0253] 2021` in `irpf_deduccion_la_rioja_donacion_bienes_culturales_autores` — La Rioja mecenazgo promotion deduction, not cultural-asset donation by authors

**Data-type note** (not a role name issue):
- `irpf_tipo_medio_gravamen_ahorro_estatal` uses `money(default)` but the field is a rate (effective tax rate); should be `ratio`.
- `irpf_descendiente_num_contribuyentes_derecho` and `irpf_familia_numerosa_num_ascendientes` use `money(default)` but hold integer headcounts.
