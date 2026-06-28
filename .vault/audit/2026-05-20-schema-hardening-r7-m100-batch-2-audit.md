---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m100 batch-2 semantic audit

## Scope

126 semantic roles from `.vault-scratch/r7-m100/batch-2.json`. All six
revisions (2020-2025) covered. Registry TOMLs under
`src/aeat/_data/registry/aeat/modelos/100/revisions/*/casillas/` consulted
for disputed roles. Focus: name accuracy, member coherence, granularity.

## Findings

| role | verdict | detail |
|---|---|---|
| `irpf_contribuyente_titular` | RENAME → `irpf_toma_datos_declarante_selector` | 253 members, 45 unique casilla IDs across all sections. These are "which declarante (1/2) applies to this block" selector fields — not a single "titular" concept but a structural navigation field repeated across every income-type block. Current name implies a single titular concept; actual role is "declarante attribution selector". Acceptable to keep as single role given the structural uniformity, but name is misleading. |
| `irpf_anexo_c_saldo_neg_gyp_ahorro_aplicado` | OK | 4 casilla IDs (one per year subset), all `money(default)`, section `resultados/anexo_c_res/saldos_neg_gy_p_ahorro_res`. Coherent: negative capital-gain/loss balance (ahorro base) applied from prior years. |
| `irpf_anualidades_alimentos_hijo_importe` | OK | 5 casilla IDs (child 1-5), revs 2022-2025, all same section and dtype. Coherent: per-child alimony annuity amounts. |
| `irpf_anexo_c_base_liq_neg_pendiente_fin` | OK | 3 casilla IDs, all revisions, `money(default)`. Coherent: pending negative liquidable base (Anexo C carry-forward). |
| `irpf_reduccion_tributacion_conjunta` | SPLIT → `irpf_reduccion_tributacion_conjunta_importe` + `irpf_reduccion_tributacion_conjunta_aplicada` | 3 casilla IDs that represent two distinct computations: casilla 0461 = reduction entitlement amount (red_base_imponible), casillas 0491 and 0506 = first and second tranche applications against base_liquidable. Different computation stages, different sections. |
| `irpf_anexo_a_nif_extranjero_flag` | RENAME → `irpf_deduccion_alquiler_arrendador_nif_extranjero_flag` | Boolean, 2 IDs (0716/0718), section `deduccion_alquiler_res`. These mark foreign NIF for landlord slots in the housing-rental deduction annexe. The current name `anexo_a_nif_extranjero_flag` is too vague; the "alquiler arrendador" context is essential. |
| `irpf_inmueble_pct_valor_catastral_construccion` | RENAME → `irpf_inmueble_ratio_construccion_catastral` | 2 IDs (0125/0140), all revisions, `money(default)`. The label is "(valor catastral construcción / valor catastral) × 100" — a percentage ratio, not a money amount. The role name is accurate conceptually but the `_pct_` prefix is correct; `money(default)` dtype is a registry encoding artifact. Name is acceptable; however "pct" better expressed as `_ratio_` for non-monetary semantics. Minor rename. |
| `irpf_deduccion_eficiencia_energetica_calificacion_anterior` | OK | 2 IDs, revs 2021-2025, `text`. Coherent: prior energy-efficiency rating code for the dwelling before works. |
| `irpf_anexo_a_rib_dotacion_importe` | OK | 3 IDs (one per year pair), revs 2023-2025, `money(default)`. Coherent: RIB (Reserve for Investment in the Balearic Islands) endowment amount. |
| `irpf_deduccion_incentivos_inversion_empresarial_estatal` | OUTLIER | Member `[2020] id=0814` label starts with "Vigésimo quinta sesión de la Conferencia de las Partes… (COP25)" — this is a specific one-off event-related deduction for COP25 in Madrid, under `deducciones_inversion_empresarial_res`. All other members (0554 across all revisions) are the aggregate state-share of the general investment incentives deduction under `gravamenes_res`. Casilla 0814 (2020 only) should be assigned its own role for the COP25 event deduction. It is structurally and legally distinct from the generic incentivos basket sum. |
| `irpf_anexo_b_insurance_premium_total` | RENAME → `irpf_eps_primas_seguro_deducibles_total` | 1 ID (1202), all revisions, `money(default)`, section `an_b_inf_adc_eps`. "eps" = Entidad de Previsión Social (health insurance entity). Label in 2020/2021 is "Primas satisfechas"; from 2022 onwards is explicit about deductibility. The role name uses English ("insurance_premium") in an otherwise Spanish-terminology codebase — rename to consistent Spanish convention. |
| `irpf_anexo_c_exencion_reinversion_importe_total_transmision` | OK | 1 ID, all revisions, `money(default)`. Coherent: total transfer value for reinvestment exemption (Anexo C). |
| `irpf_ascendiente_cedido_flag` | OK | 1 ID, all revisions, `boolean`. Coherent: flag indicating a dependent ascendant was "cedido" (shared between declarants). |
| `irpf_compensacion_conyuges_swift_flag` | RENAME → `irpf_compensacion_conyuges_swift_bic` | 2 IDs (0697 in 2020, 1792 in 2021-2025), `text` dtype. Label is "Compensación entre cónyuges: SWIFT" — this is a BIC/SWIFT code field (bank identifier), not a boolean flag. The `_flag` suffix is incorrect; this holds a text BIC value. |
| `irpf_cuota_integra_estatal` | OK | 1 ID, all revisions, `money(default)`. Coherent: state gross tax liability (cuota íntegra estatal). |
| `irpf_deduccion_andalucia_adopcion_internacional` | OK | 1 ID, all revisions. Coherent: Andalucía autonomous deduction for international adoption. |
| `irpf_deduccion_andalucia_general` | OK | 1 ID, all revisions. Coherent: Andalucía general autonomous deduction. |
| `irpf_deduccion_aragon_libros_texto` | OK | 1 ID, all revisions. Coherent: Aragón deduction for textbooks. |
| `irpf_deduccion_asturias_centros_0_3` | OK | 1 ID, all revisions. Coherent: Asturias deduction for nursery/0-3 centres. |
| `irpf_deduccion_baleares_arrendador_nif_extranjero_flag` | OK | 1 ID, all revisions, `boolean`. Coherent: Illes Balears deduction — foreign NIF flag for the landlord slot. |
| `irpf_deduccion_baleares_idiomas` | OK | 1 ID, all revisions. Coherent: Illes Balears language learning deduction. |
| `irpf_deduccion_c_valenciana_conciliacion` | OK | 1 ID, all revisions. Coherent: Comunitat Valenciana work-life reconciliation deduction. |
| `irpf_deduccion_c_valenciana_material_escolar` | OK | 1 ID, all revisions. Coherent: Comunitat Valenciana school materials deduction. |
| `irpf_deduccion_canarias_alquiler_vivienda` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_canarias_familia_numerosa` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_canarias_vivienda_discapacidad` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_cantabria_guarderia_municipio_riesgo` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_castilla_la_mancha_donaciones_bienes_culturales` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_castilla_y_leon_donaciones_idi` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_castilla_y_leon_rehabilitacion_subvencionada` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_catalunya_viudedad` | OK | 1 ID, all revisions. Coherent: Catalunya deduction for widowhood. |
| `irpf_deduccion_extremadura_acciones_participaciones` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_galicia_acciones_participaciones` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_galicia_discapacidad_mayores_65` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_interes_cultural_estatal` | OK | 1 ID, all revisions, `money(default)`. Coherent: state deduction for cultural interest. |
| `irpf_deduccion_la_rioja_intereses_hipotecarios` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_madrid_acciones_participaciones` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deduccion_maternidad` | OK | 1 ID (0611), all revisions, `money(default)`. Section varies in 2025 (`resultado_declaracion` vs `calculo_impuesto_res/deduc_mater_res`) but this is a 2025 schema restructure, not a conceptual change. Coherent. |
| `irpf_deduccion_murcia_guarderia` | OK | 1 ID, all revisions. Coherent. |
| `irpf_deducciones_incentivos_inversion_total` | OK | 1 ID (0845), all revisions, `money(default)`. Coherent: total investment-incentive deductions aggregate. Label formula references change by revision as new casillas are added, but the concept is stable. |
| `irpf_ed_aportaciones_prevision_social_personal` | OK | 1 ID, all revisions, `money(default)`. Coherent: personal social-security contributions under estimación directa. |
| `irpf_ed_ingresos_explotacion` | OK | 1 ID, all revisions. Coherent: operating income under direct estimation. |
| `irpf_ed_otros_ingresos` | OK | 1 ID, all revisions. Coherent: other income under direct estimation. |
| `irpf_ed_reduccion_inicio_actividad` | OK | 1 ID (0234), all revisions, `money(default)`. Coherent: reduction for starting a new economic activity (art. 32.3 LIRPF). |
| `irpf_ed_total_ingresos_computables` | OK | 1 ID, all revisions. Coherent: total computable income under direct estimation. |
| `irpf_eo_agr_indice_pequena_empresa` | OK | 1 ID, all revisions. Coherent: small-enterprise index correction in agricultural objective estimation. |
| `irpf_eo_agr_ingresos_integros_forestal_corta_larga` | OK | 1 ID, all revisions. Coherent: gross forestry income (short/long rotation). |
| `irpf_eo_agr_rdto_neto_reducido` | RENAME → `irpf_eo_agr_rdto_neto_reducido_actividad` | 1 ID (1555), all revisions, `decimal`. Section is `actividad_agr` under `reg_estima_obj_agricola`. Role name is technically correct but could specify "por actividad" to distinguish from aggregate results. Minor rename for clarity. |
| `irpf_eo_indice_corrector_inicio` | OK | 1 ID, all revisions. Coherent: start-of-activity corrector index for objective estimation. |
| `irpf_eo_reduccion_general` | OK | 1 ID, all revisions. Coherent: general reduction in objective estimation. |
| `irpf_familia_numerosa_categoria_general_flag` | OK | 1 ID, all revisions, `boolean`. Coherent: large family (familia numerosa) general category flag. |
| `irpf_g4_re_ganancia_susceptible_reduccion_dt9` | OK | 1 ID, all revisions, `money(default)`. Coherent: G4 regime — capital gain susceptible to DT9 reduction. |
| `irpf_ganancia_acciones_susceptible_reduccion_dt9` | OK | 1 ID, all revisions. Coherent: gain on shares susceptible to DT9 reduction. |
| `irpf_ganancia_derechos_valor_transmision_dt9` | OK | 1 ID, all revisions. Coherent: transfer value of subscription rights under DT9. |
| `irpf_ganancia_inmueble_comprometido_reinvertir_vh` | OK | 1 ID, all revisions. Coherent: real estate gain committed to reinvestment (habitual residence exemption). |
| `irpf_ganancia_otros_anios_cobro_pendiente` | OK | 1 ID, all revisions. Coherent: capital gains with deferred collection (split-year receipts). |
| `irpf_ganancia_otros_importe_percibir_2` | OK | 1 ID, all revisions. Coherent: second instalment of other capital gain receipts. |
| `irpf_ganancia_otros_reducida_no_exenta_imputable_dt9` | OK | 1 ID, all revisions. Coherent: reduced but non-exempt capital gain imputable under DT9. |
| `irpf_ganancia_premios_ayuda_publica_otras` | OK | 1 ID, all revisions. Coherent: prizes / public subsidies gains (other category). |
| `irpf_ganancia_premios_subvencion_vivienda_otras` | OK | 1 ID, all revisions. Coherent: housing subsidy gains (other category). |
| `irpf_inmueble_arrendatario1_nif_extranjero_flag` | OK | 1 ID, all revisions, `boolean`. Coherent: foreign NIF flag for first tenant in a rental property block. |
| `irpf_inmueble_gastos_financiacion_pendientes_futuros` | OK | 1 ID, all revisions. Coherent: future financing costs pending deduction for rental property. |
| `irpf_inmueble_valor_catastral_revisado_flag` | RENAME → `irpf_inmueble_valor_catastral_revisado_selector` | 1 ID (0084), all revisions, `text` dtype (not `boolean`). The label asks the taxpayer to indicate whether the cadastral value was revised in the last 10 years — the answer is a coded text selector (S/N or similar), not a boolean. The `_flag` suffix implies boolean; `_selector` or `_indicador` better reflects the `text` dtype. |
| `irpf_intereses_demora_perdida_deduccion_estatal` | OK | 1 ID, all revisions. Coherent: late-payment interest from loss of housing deduction (state portion). |
| `irpf_minimo_contribuyente_estatal` | OK | 1 ID, all revisions. Coherent: taxpayer personal minimum (mínimo del contribuyente) — state tranche. |
| `irpf_perdida_derecho_deduccion_estatal` | OK | 1 ID, all revisions. Coherent: amount of lost housing deduction entitlement (state portion). |
| `irpf_perdida_otros_pendiente_4` | OK | 1 ID, all revisions. Coherent: capital loss — other assets — fourth year pending offset. |
| `irpf_re_atrib_act_eco_minoraciones` | OK | 1 ID, all revisions. Coherent: reductions applied to economic-activity income under attribution regime. |
| `irpf_re_atrib_cap_mob_rdto_neto_computable_ahorro` | RENAME → `irpf_re_atrib_cap_mob_rdto_neto_computable_excl_subordinada` | 1 ID (1569), `decimal`. Label explicitly states "excepto el consignado en la casilla [1570]" — i.e., this is capital-mobile attributed income for savings base, *excluding* subordinated debt/preferred shares (those are in 1570). The current role name does not convey the exclusion. |
| `irpf_re_atrib_gp_exentas_reinversion_nuevas` | OK | 1 ID, all revisions. Coherent: attributed capital gains exempt due to reinvestment in new companies. |
| `irpf_re_atrib_inmueble_rustica_flag` | OK | 1 ID, all revisions, `boolean`. Coherent: rustic property flag in the attribution regime block. |
| `irpf_re_atrib_suma_deuda_subordinada` | OK | 1 ID (1603), all revisions, `decimal`. Coherent: sum of attributed income from subordinated debt / preferred shares (savings base). |
| `irpf_re_imagen_suma_imputaciones` | OK | 1 ID, all revisions. Coherent: total income imputations from image-rights regime. |
| `irpf_red_pensiones_compensatorias_importe` | OK | 1 ID, all revisions. Coherent: compensatory pension / alimony reduction amount (not child alimony). |
| `irpf_reduccion_prevision_social_conyuge_aplicada` | OK | 1 ID, all revisions. Coherent: social-security contribution reduction applied for non-earning spouse. |
| `irpf_rendimiento_capital_inmobiliario_gasto_comunidad` | OK | 1 ID, all revisions. Coherent: community of owners expenses deducted in rental income. |
| `irpf_rendimiento_capital_inmobiliario_reduccion_arrendamiento_vivienda` | OK | 1 ID, all revisions. Coherent: rental income reduction for residential letting. |
| `irpf_rendimiento_capital_mobiliario_ahorro_gastos_deducibles` | OK | 1 ID, all revisions. Coherent: deductible expenses for savings-base capital income. |
| `irpf_rendimiento_capital_mobiliario_ahorro_total_ingresos_integros` | RENAME → `irpf_rendimiento_capital_mobiliario_ahorro_total_ingresos_integros_ratio` | 1 ID, `decimal` dtype (not `money`). The role name ends in a term that implies a monetary total but dtype is `decimal` and the label confirms a ratio/proportion concept rather than an absolute amount. Rename to clarify the decimal nature. |
| `irpf_rendimiento_capital_mobiliario_general_total_ingresos_integros` | RENAME → `irpf_rendimiento_capital_mobiliario_general_total_ingresos_integros_ratio` | Same issue as the ahorro variant — `decimal` dtype on a "total ingresos" concept. The field is a computable decimal ratio, not a money sum. |
| `irpf_rendimiento_trabajo_gasto_ss_mutualidad` | OK | 1 ID, all revisions. Coherent: social-security / mutualidad expense deduction in employment income. |
| `irpf_rentas_exentas_base_general` | OK | 1 ID (0525), all revisions, `money(default)`. Section path changed in 2021/2022 restructure but concept is stable: exempt income corresponding to the general liquidable base. |
| `irpf_retenciones_consideradas_practicadas` | OK | 1 ID (0591), all revisions, `money(default)`. Coherent: withholdings deemed made but not actually collected, still deductible from the tax liability. |
| `spouse_compensation_iban` | RENAME → `irpf_compensacion_conyuges_iban` | 2 IDs (0696 in 2020, 1790 in 2021-2025), `iban` dtype. Role name lacks `irpf_` prefix and uses English "spouse_compensation" — inconsistent with the rest of the schema. Corrected: `irpf_compensacion_conyuges_iban`. |
| `irpf_deduccion_andalucia_familia_numerosa` | OK | 1 ID, revs 2021-2025. Coherent (introduced 2021). |
| `irpf_deduccion_c_valenciana_generado_2025_aplicado` | OK | 1 ID, revs 2021-2025. Coherent: Comunitat Valenciana deduction generated (labelled as 2025 tranche) applied in year. |
| `irpf_deduccion_eficiencia_energetica_demanda_posterior` | OK | 1 ID, revs 2021-2025. Coherent: energy efficiency deduction — demand rating after works. |
| `irpf_ganancia_otros_transmision_onerosa` | OK | 1 ID (1612), revs 2021-2025, `boolean`. Coherent: flag for whether the "other asset" disposal was an inter-vivos onerous transfer (vs. donation/inheritance). |
| `irpf_anexo_a_la_palma_deduccion_importe` | OK | 1 ID, revs 2022-2025. Coherent: La Palma volcanic emergency deduction amount. |
| `irpf_anexo_c_exceso_eeficiencia_generado` | RENAME → `irpf_anexo_c_exceso_eficiencia_energetica_generado` | 1 ID, revs 2022-2025. Typo in role name (`eeficiencia` has double-e). Correct spelling: `eficiencia_energetica`. |
| `irpf_deduccion_c_valenciana_generado_2023_pendiente_2` | OK | 1 ID, revs 2022-2025. Coherent: CV deduction 2023-tranche second pending amount. |
| `irpf_ganancia_cripto_anio_imputacion_2` | OK | 1 ID, revs 2022-2025, `text`. Coherent: year of second-instalment imputation for cryptocurrency gain. |
| `irpf_ganancia_cripto_importe_percibir_2` | OK | 1 ID, revs 2022-2025. Coherent: second-instalment receipt for cryptocurrency gain. |
| `irpf_ganancia_cripto_valor_transmision` | OK | 1 ID, revs 2022-2025. Coherent: transmission value of cryptocurrency (virtual currency) gain. |
| `irpf_ganancia_inmueble_catastral_3` | OK | 1 ID, revs 2022-2025, `text`. Coherent: cadastral reference for third real-estate gain block. |
| `irpf_ganancia_inmueble_importe_percibir_1` | OK | 1 ID, revs 2022-2025. Coherent: first deferred receipt amount for real estate gain. |
| `irpf_ganancia_inmueble_reducida_no_exenta_imputable` | OK | 1 ID, revs 2022-2025. Coherent: reduced non-exempt real estate gain imputable in the year. |
| `irpf_ganancia_inmueble_valor_transmision_susceptible_vh` | OK | 1 ID, revs 2022-2025. Coherent: transfer value susceptible to habitual-residence reinvestment exemption. |
| `irpf_perdida_cripto_pendiente_1` | OK | 1 ID, revs 2022-2025. Coherent: first pending cryptocurrency capital loss (offset carryforward). |
| `irpf_red_prevision_social_aportaciones_autonomos_empresarios` | OK | 1 ID (0499), revs 2022-2025. Label changed in 2023 from describing employer promoter plans to self-employed workers broadly — concept converged and is stable from 2023. Acceptable evolution within a single role. |
| `irpf_anexo_b_birth_pending_claim` | RENAME → `irpf_baleares_deduccion_nacimiento_importe_pendiente` | 1 ID (1992), revs 2023-2025, `money(default)`, section `an_b_inf_ad_i_baleares`. Label: "Deducción por nacimiento: Importe pendiente a solicitar". Role name uses English ("birth_pending_claim") — inconsistent. Corrected Spanish name including the autonomous community scope. |
| `irpf_deduccion_bienes_corporales_illes_balears_autonomica` | OK | 1 ID, revs 2023-2025. Coherent: Illes Balears autonomous deduction for tangible assets. |
| `irpf_deduccion_catalunya_viudedad_anio` | OK | 1 ID, revs 2023-2025, `text`. Coherent: year field for Catalunya widowhood deduction. |
| `irpf_deduccion_vehiculo_fecha_matriculacion` | OK | 1 ID, revs 2023-2025, `text`. Coherent: vehicle registration date for EV/efficient vehicle deduction. |
| `irpf_eo_agr_reduccion_la_palma` | OK | 1 ID, revs 2022-2024 only (La Palma emergency measure, expired). Coherent. |
| `irpf_feac_perdida_patrimonial_diferida` | OK | 1 ID, revs 2023-2025. Coherent: deferred capital loss under FEAC (merger/split-off special regime). |
| `irpf_re_especial_tfi_declarante_num_operaciones` | RENAME → `irpf_re_especial_tfi_declarante_num_operaciones_count` | 1 ID (0414), revs 2020-2022, `money(default)` dtype. The field holds a count of operations (N.º de operaciones) under the special tax-fraud investigation (TFI) regime. The `money(default)` dtype is a registry encoding artifact — semantically it is an integer count. The role name is correct in spirit but `_count` suffix clarifies it is not a monetary amount. |
| `irpf_retrib_especie_importe_no_exenta_1` | OK | 1 ID, revs 2023-2025. Coherent: non-exempt benefit-in-kind amount (first slot). |
| `irpf_deduccion_asturias_gastos_vitales_jovenes` | OK | 1 ID, revs 2024-2025. Coherent: Asturias youth living-cost deduction. |
| `irpf_deduccion_canarias_adecuacion_inmueble_arrendamiento` | OK | 1 ID, revs 2024-2025. Coherent: Canarias property adaptation for rental. |
| `irpf_deduccion_cantabria_generado_2023_pendiente` | OK | 1 ID, revs 2024-2025. Coherent: Cantabria 2023-tranche pending deduction. |
| `irpf_deduccion_madrid_arrendamiento_viviendas_vacias` | OK | 1 ID, revs 2024-2025. Coherent: Madrid vacant housing rental deduction. |
| `irpf_deduccion_madrid_vivienda_precio_adquisicion` | OK | 1 ID, revs 2024-2025. Coherent: Madrid housing deduction — acquisition price field. |
| `irpf_inmueble_numero_orden` | OK | 2 IDs (1210/1392 both in 2020 only), `integer`, both same label/section. Two parallel property-entry slots in 2020 carrying the same role. Not an outlier — structural duplication within a single revision for multi-property declaration. |
| `irpf_ascendiente_apellidos_nombre` | OK | 1 member (2025 only), `text`, `datos_identificativos`. Coherent: dependent ascendant name field (new 2025 requirement). |
| `irpf_conyuge_sexo` | OK | 1 member (2025 only), `text`, `datos_identificativos`. Coherent: spouse gender field (new 2025 requirement). |
| `irpf_deduccion_asturias_medico_colegiado` | OK | 1 member (2025 only), `text`. Coherent: Asturias physician registration number field (new 2025). |
| `irpf_deduccion_cantabria_generado_2025_pendiente_2` | OK | 1 member (2025 only). Coherent: Cantabria 2025-tranche second pending amount. |
| `irpf_deduccion_extremadura_donaciones_culturales` | OK | 1 member (2025 only). Coherent: Extremadura cultural donation deduction. |
| `irpf_deduccion_la_rioja_cuotas_organizaciones_agrarias` | OK | 1 member (2025 only). Coherent: La Rioja deduction for agricultural organisation dues. |
| `irpf_deduccion_murcia_enfermedades_raras` | OK | 1 member (2025 only). Coherent: Murcia rare-disease deduction. |
| `irpf_deduccion_murcia_vehiculo_matricula` | OK | 1 member (2025 only), `text`. Coherent: Murcia vehicle plate/registration field for EV deduction. |
| `irpf_eo_agr_ingresos_integros_mejillon_batea` | OK | 1 member (2025 only). Coherent: Galician mussel-raft (batea) gross income under agricultural objective estimation. |
| `irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia` | OK | 1 member (2025 only). Coherent: transfer value of quoted fund units converted to life annuity (2025 new regime). |
| `irpf_incremento_maternidad_no_aplicado_2021` | OK | 1 member (2022 only). Coherent: one-off transitional casilla carrying 2021 maternity-deduction increment unused in 2021 and applicable in 2022. Revision-scoped transitional field is expected. |
| `irpf_red_prevision_social_aportaciones_ejercicio_2021` | OK | 1 member (2021 only), `money(default)`. Coherent: within-year 2021 contributions field under the pension contribution reduction block. |

## Summary counts

| verdict | count |
|---|---|
| OK | 103 |
| RENAME | 12 |
| SPLIT | 1 |
| OUTLIER | 1 |
| **Total** | **126** |

### RENAME targets (corrected names)

| original | corrected |
|---|---|
| `irpf_contribuyente_titular` | `irpf_toma_datos_declarante_selector` |
| `irpf_anexo_a_nif_extranjero_flag` | `irpf_deduccion_alquiler_arrendador_nif_extranjero_flag` |
| `irpf_inmueble_pct_valor_catastral_construccion` | `irpf_inmueble_ratio_construccion_catastral` |
| `irpf_anexo_b_insurance_premium_total` | `irpf_eps_primas_seguro_deducibles_total` |
| `irpf_compensacion_conyuges_swift_flag` | `irpf_compensacion_conyuges_swift_bic` |
| `irpf_inmueble_valor_catastral_revisado_flag` | `irpf_inmueble_valor_catastral_revisado_selector` |
| `irpf_re_atrib_cap_mob_rdto_neto_computable_ahorro` | `irpf_re_atrib_cap_mob_rdto_neto_computable_excl_subordinada` |
| `irpf_rendimiento_capital_mobiliario_ahorro_total_ingresos_integros` | `irpf_rendimiento_capital_mobiliario_ahorro_total_ingresos_integros_ratio` |
| `irpf_rendimiento_capital_mobiliario_general_total_ingresos_integros` | `irpf_rendimiento_capital_mobiliario_general_total_ingresos_integros_ratio` |
| `spouse_compensation_iban` | `irpf_compensacion_conyuges_iban` |
| `irpf_anexo_c_exceso_eeficiencia_generado` | `irpf_anexo_c_exceso_eficiencia_energetica_generado` |
| `irpf_anexo_b_birth_pending_claim` | `irpf_baleares_deduccion_nacimiento_importe_pendiente` |
| `irpf_re_especial_tfi_declarante_num_operaciones` | `irpf_re_especial_tfi_declarante_num_operaciones_count` |
| `irpf_eo_agr_rdto_neto_reducido` | `irpf_eo_agr_rdto_neto_reducido_actividad` |

### SPLIT target

`irpf_reduccion_tributacion_conjunta` → split into:
- `irpf_reduccion_tributacion_conjunta_importe` (casilla 0461 — entitlement amount, `red_base_imponible`)
- `irpf_reduccion_tributacion_conjunta_aplicada` (casillas 0491 + 0506 — first/second tranche application, `base_liquidable`)

### OUTLIER

`[2020] id=0814` in `irpf_deduccion_incentivos_inversion_empresarial_estatal`:
COP25 one-time event deduction under `deducciones_inversion_empresarial_res`.
All other members are the aggregate state-share sum under `gravamenes_res`.
This casilla requires its own role, e.g. `irpf_deduccion_cop25_importe`.
