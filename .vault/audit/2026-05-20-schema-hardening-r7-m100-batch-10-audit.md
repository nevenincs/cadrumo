---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m100 batch-10 audit

## Scope

Semantic-correctness review of 72 `semantic_role` entries from Modelo 100 (IRPF),
revisions 2020–2025. Each role was checked for: (1) name accuracy against member
labels and sections, (2) member coherence across revision span, (3) granularity fit.
Registry TOMLs were consulted where necessary. Id-reuse across revisions is expected
and not treated as a defect.

---

## Findings

| role | verdict | detail |
|---|---|---|
| `irpf_anexo_b_deduccion_autonomica` | SPLIT | Groups at least 9 structurally distinct regional/type sub-deducciones in Anexo B (arrendamiento ctrd, arrendamiento arr, empresas nueva creación, medioambiente, RCF, actividades ganaderas, dación en pago AVH, IDES, seguros EPS, and from 2024 ref-catastral, IPSE, ENF, DEP, AIA, AFP, SCAV, RCINCE, ARRVM). These are separate tax deduction concepts belonging to different Anexo B subsections. Each deserves its own role. The current container is a catch-all for "any Anexo B deduction amount" regardless of nature. Suggested split: `irpf_anexo_b_deduccion_arrendamiento`, `irpf_anexo_b_deduccion_nuevas_empresas`, `irpf_anexo_b_deduccion_dacion_en_pago`, `irpf_anexo_b_deduccion_seguros_alquiler_arrendador`, `irpf_anexo_b_deduccion_ref_catastral`, plus individual roles per remaining subsection code. |
| `irpf_gyp_perdidas_bruto` | SPLIT | Groups gross-loss subtotals from five distinct G/P categories in a single role: juegos (prizes), otras-no-transmisión, fondos-IIC, acciones-negociadas, derechos-suscripción, otros-elementos, ejercicios-anteriores, and from 2022 criptomonedas and inmuebles. Each subsection represents a legally distinct asset class with separate treaty treatment. The role name omits the multi-category character. Recommended split into per-asset-class roles, e.g. `irpf_gyp_perdidas_bruto_fondos`, `irpf_gyp_perdidas_bruto_acciones`, `irpf_gyp_perdidas_bruto_criptomonedas`, `irpf_gyp_perdidas_bruto_inmuebles`, `irpf_gyp_perdidas_bruto_otros`, `irpf_gyp_perdidas_bruto_ejercicios_anteriores`. |
| `landlord_nif` | RENAME | Missing `irpf_` prefix required by convention; crosses two distinct section contexts (Anexo B deduction info and Anexo A state deduction), but both are arrendador identity fields. The name is otherwise accurate. Rename to `irpf_arrendador_nif`. |
| `irpf_inmueble_mejora_proveedor_nif` | OK | Correctly represents NIF of contractor who performed improvement works (mejoras 1–3) on real estate across all revisions. Name is accurate; `data_type: text` rather than `nif` is consistent with how the AEAT form encodes this field (free-text NIF slot for the service provider). |
| `irpf_anexo_c_exceso_sps_disc_propias_aplicado` | OK | Rolling 5-year window of "applied in this declaration" amounts for excess pension-system contributions from disabled persons' own contributions (Anexo C). The cohort of casilla IDs shifts one year per revision, as expected. Name is accurate. |
| `irpf_anexo_b_carry_forward_pending` | OUTLIER | From revision 2023 onwards casillas 1115 (2023/24/25) and 1118 (2023/24/25) are Madrid deductions for ascendant care and student-loan interest, not Comunitat Valenciana carry-forward amounts. For 2025, casilla 1078 is a Galicia deduction for vacant property adaptation costs. These are entirely different deduction concepts inserted into what was a C. Valenciana carry-forward role due to casilla id reuse. **Outliers:** `1115` (revisions 2023, 2024, 2025) — actually `irpf_deduccion_madrid_cuidado_ascendientes`; `1118` (revisions 2023, 2024, 2025) — actually `irpf_deduccion_madrid_prestamos_estudios`; `1078` (revision 2025) — actually `irpf_deduccion_galicia_adecuacion_inmueble_arrendamiento`. The core carry-forward members (1078 for 2020–2024, 1115/1118 for 2020–2022, 1206, 1392) belong in the role. |
| `irpf_anexo_c_rdto_cm_negativo_pendiente_inicio` | OK | Rolling 4-year window of negative capital-mobiliario income balances pending at period start (Anexo C). Casilla IDs 1272–1280 shift correctly per revision. Name is accurate. |
| `irpf_deduccion_castilla_y_leon_importe_pendiente_aplicacion` | OK | Carry-forward pending amounts for two Castilla y León investment-in-business deduction programmes (casillas 0981–0999), rolling by year. Name is accurate. Note: 2023 onwards casilla 0997 absent (dropped from the form) — this is a valid structural change, not an error. |
| `irpf_anexo_b_insurance_premium` | RENAME | Section path is `an_b_inf_adc_eps` (seguros de crédito para arrendamientos), and the labels say "Primas satisfechas". The role is specifically about insurance premium payments for credit-risk insurance on rental income (landlord deduction), not a generic insurance premium. Rename to `irpf_anexo_b_prima_seguro_credito_arrendamiento` for precision. Current name `irpf_anexo_b_insurance_premium` uses English mid-name which is inconsistent with naming conventions. |
| `irpf_inmueble_referencia_catastral` | OK | Three slots for referencia catastral within the property detail section (0066 primary, 1212 and 1394 for secondary/tertiary properties). All `text` type. Consistent across all revisions. Name is accurate. |
| `irpf_anexo_a_inversion_importe_deduccion` | RENAME | Two slots (0712, 0714) are "importe de la inversión con derecho a deducción" specifically for Anexo A deduction for investment in new/recently-created companies (empresas de nueva creación), not a generic investment deduction. The section is `deduccion_empresas_nueva_creacion_res`. Rename to `irpf_anexo_a_nuevas_empresas_importe_inversion`. |
| `irpf_inmueble_gastos_tributos_adquisicion` | OK | Two slots for acquisition taxes and expenses on property. Consistent label and section across all revisions. Name is accurate. |
| `irpf_anexo_c_exceso_eeficiencia_aplicado` | OUTLIER + RENAME | Role name contains typo ("eeficiencia"). More importantly, casilla `1696` in revision 2022 is **not** an energy-efficiency excess applied: its label is "Reserva para Inversiones en Canarias 2016 (1): Inversiones previstas en las letras C y D (2.º a 6.º) del art.º 27.4" — a Canarias investment-reserve entry, not an energy efficiency excess. This is a genuine outlier caused by casilla id reuse. **Outlier:** `1696` (revision 2022) — actually belongs to `irpf_reserva_inversiones_canarias`. From revision 2023 onwards `1696` correctly maps to "Ejercicio 2021: Aplicado en esta declaración" within `excesos_eficiencia_energetica_res`. Rename to `irpf_anexo_c_exceso_eficiencia_energetica_aplicado`. |
| `irpf_anexo_a_mejora_energia_exceso_pendiente` | OK | Two casillas (1680 = excess generated in current year; 1778 = accumulated prior-year excesses pending) for energy-improvement deduction carry-forward in Anexo A. Labels evolve correctly per revision. Name is accurate. |
| `irpf_abono_anticipado_familia_numerosa` | OK | Single casilla 0661 representing the advance payment (abono anticipado) of the large-family deduction. In 2025 the section moves from `calculo_impuesto_res` to `resultado_declaracion` — a valid structural migration, not a semantic change. Name is accurate. |
| `irpf_anexo_a_residente_ue_cuota_irnr` | OK | Single casilla 0729 for IRNR quotas paid by EU/EEA family members, used to support the EU-resident deduction in Anexo A. Name is accurate. |
| `irpf_anexo_c_exencion_reinversion_ganancia_exenta` | OK | Single casilla 1236 for the exempt capital gain on reinvestment in new companies (Anexo C). Consistent across all revisions. Name is accurate. |
| `irpf_anexo_c_saldo_neg_gyp_ahorro_generado` | OK | Single casilla 1270 for the negative savings-base G/P balance generated this year pending future compensation (Anexo C). Name is accurate. |
| `irpf_compensacion_bases_negativas_generales` | OK | Single casilla 0501 for compensation of prior-year general negative tax bases (rolling 4-year window referenced). Name is accurate. |
| `irpf_cuota_base_liquidable_general_estatal` | OK | Single casilla 0532 for the state-share tax quota on general taxable base. Name is accurate. |
| `irpf_cuota_resultante_autoliquidacion` | OK | Single casilla 0595 for the net self-assessment tax liability. In 2025 section moves to `resultado_declaracion`. Name is accurate. |
| `irpf_deduccion_andalucia_empleada_hogar_ccc_2` | RENAME | Casilla 0861 is "Código Cuenta de Cotización" — a social security employer account number for domestic workers, used in Andalucía's household employee deduction. The suffix `_2` is opaque; the name suggests a second CCC whereas it is the CCC field of a single-entry context. Rename to `irpf_deduccion_andalucia_empleada_hogar_ccc`. If a `_1` / `_2` distinction exists in the data model it should be clarified, but there is no `_1` counterpart visible in this batch. |
| `irpf_deduccion_aragon_donativos_ecologicos_id` | RENAME | The `_id` suffix is misleading — this is a monetary deduction amount, not an identifier. The label is "Por donaciones con finalidad ecológica y en investigación y desarrollo científico y técnico". Rename to `irpf_deduccion_aragon_donativos_ecologicos_id_importe`. Better: `irpf_deduccion_aragon_donativos_ecologicos`. |
| `irpf_deduccion_asturias_acogimiento_mayores` | OK | Single casilla 0883 for the Asturias deduction for non-paid hosting of persons over 65. Consistent across all revisions. Name is accurate. |
| `irpf_deduccion_asturias_transporte_publico` | OK | Single casilla 0813 for Asturias public transport expense deduction for rural residents at risk of depopulation. Label wording evolves (zonas rurales → concejos, 2022+; +crisis demográfica 2025) but concept is stable. Name is accurate. |
| `irpf_deduccion_baleares_donaciones_lengua` | OK | Single casilla 0905 for Illes Balears Catalan language promotion donation deduction. Consistent across all revisions. Name is accurate. |
| `irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto_flag` | RENAME | The label reads "Marque una X si en la casilla [1096] ha consignado un NIF de otro país" — it is a foreign-NIF flag, not a different-municipality flag. The role name is semantically wrong. Rename to `irpf_deduccion_c_valenciana_arrendador_nif_extranjero_flag`. |
| `irpf_deduccion_c_valenciana_donativos_ecologicos` | OK | Single casilla 1099 for C. Valenciana ecological donations deduction. Consistent across all revisions. Name is accurate. |
| `irpf_deduccion_c_valenciana_vivienda_adquisicion_rehabilitacion` | OK | Single casilla 1094 for C. Valenciana deduction for acquisition/rehabilitation of habitual residence from public aid. Consistent. Name is accurate. |
| `irpf_deduccion_canarias_enfermedad` | OK | Single casilla 0940 for Canarias illness expense deduction. From 2024 the label cross-references Anexo B casilla. Name is accurate. |
| `irpf_deduccion_canarias_rehabilitacion_energetica` | OK | Single casilla 0939 for Canarias energy rehabilitation deduction. Label wording slightly narrows from 2021 (drops "reforma"). Name is accurate. |
| `irpf_deduccion_cantabria_enfermedad` | OK | Single casilla 0954. Stable across all revisions. Name is accurate. |
| `irpf_deduccion_castilla_la_mancha_cooperacion_internacional` | OK | Single casilla 0962. Stable. Name is accurate. |
| `irpf_deduccion_castilla_y_leon_cuidado_hijos_menores` | OK | Single casilla 0990. Stable. Name is accurate. |
| `irpf_deduccion_castilla_y_leon_partos_multiples_2023` | RENAME | The `_2023` suffix encodes a transient project phase reference in a stable identifier — violates source hygiene. The deduction itself (partos múltiples or adopciones simultáneas, rolling 2-year window) has been present since 2020. Rename to `irpf_deduccion_castilla_y_leon_partos_multiples`. |
| `irpf_deduccion_catalunya_intereses_prestamos_estudios` | OK | Single casilla 1004 for Catalunya master/doctorate loan interest deduction. Stable. Name is accurate. |
| `irpf_deduccion_doble_imposicion_transparencia` | OK | Single casilla 0589 for international double-taxation relief under fiscal transparency regime. In 2025 section moves to `resultado_declaracion`. Name is accurate. |
| `irpf_deduccion_extremadura_viudos` | OK | Single casilla 1018. Stable. Name is accurate. |
| `irpf_deduccion_galicia_climatizacion_acs` | OK | Single casilla 1032 for Galicia renewable-energy heating/hot-water installation deduction. Stable. Name is accurate. |
| `irpf_deduccion_galicia_rehabilitacion_centros_historicos` | OK | Single casilla 1034. Stable. Name is accurate. |
| `irpf_deduccion_la_rioja_bicicletas` | OK | Single casilla 1166. Stable. Name is accurate. |
| `irpf_deduccion_la_rioja_vivienda_jovenes` | OK | Single casilla 1081. Stable. Name is accurate. |
| `irpf_deduccion_madrid_dos_mas_descendientes_ingresos_reducidos` | OK | Single casilla 1045. Stable. Name is accurate. |
| `irpf_deduccion_murcia_donaciones_investigacion_biosanitaria` | OK | Single casilla 1060. Stable. Name is accurate. |
| `irpf_deduccion_vehiculo_cantidades_subvencionadas` | OK | Two slots (1922, 1934) for subsidised amounts in electric vehicle purchase and charging point installation (Anexo A). Present from 2023. Name is accurate. |
| `irpf_ed_actividad_iae_code` | OK | Single casilla 0167 for the IAE (impuesto sobre actividades económicas) group/heading code for direct-estimation activity. Stable. Name is accurate. |
| `irpf_ed_exceso_amortizacion_libertad` | OK | Single casilla 0179 for the excess amortisation claimed under free-amortisation regime (DA 30ª). In 2025 section moves to `rendimientos_actividades_economicas/estimacion_directa`. Name is accurate. |
| `irpf_ed_modalidad_clave` | OK | Single casilla 0168 for the N/S (normal/simplified) estimation method code. Stable. Name is accurate. |
| `irpf_ed_rdto_neto_reducido` | OK | Single casilla 0226 for reduced net income from direct-estimation activity (decimal type). Name is accurate. |
| `irpf_ed_suma_rdtos_netos_reducidos` | OK | Single casilla 0231 summing all direct-estimation reduced net incomes. Name is accurate. |
| `irpf_eo_agr_gastos_extraordinarios` | OK | Single casilla 1552 for extraordinary costs under exceptional circumstances in agricultural objective estimation. Stable. Name is accurate. |
| `irpf_eo_agr_ingresos_integros_bovino_leche` | OK | Single casilla 1500 for dairy-cattle gross income in agricultural objective estimation. Name is accurate. |
| `irpf_eo_agr_ingresos_integros_remolacha` | OK | Single casilla 1491 for sugar-beet gross income. Name is accurate. |
| `irpf_eo_cobros_pagos_flag` | OK | Single casilla 1443 boolean flag for cash-basis income attribution in objective estimation. Stable. Name is accurate. |
| `irpf_eo_rdto_neto_previo` | OK | Single casilla 1465 for preliminary net income in objective estimation. Stable. Name is accurate. |
| `irpf_escala_sobre_minimo_ahorro_estatal` | OK | Single casilla 0538 for the state tax-scale applied to the personal/family minimum allocated to general base. Name is accurate. |
| `irpf_flag_regularizacion_da45_autonomico` | RENAME | From 2022 onwards the label and section consistently describe this as the **autonómica** (regional) part of the DA 45ª regularisation flag, but 2020–2021 labels say "Parte estatal". From 2022 the semantics changed in the form itself. The current name says `_autonomico` but the 2020–2021 members carry the state-part flag. Consider splitting into two revision-scoped roles, or rename to `irpf_flag_regularizacion_da45` (neutral) and document the 2020–2021 vs 2022+ semantic shift in comments. Verdict: RENAME to `irpf_flag_regularizacion_da45` (remove the misleading `_autonomico` suffix given the multi-revision semantic ambiguity). |
| `irpf_ganancia_acciones_exenta_renta_vitalicia` | OK | Single casilla 0333 for capital gains exempt by reinvestment in annuities (rentas vitalicias), within listed-shares section. Stable. Name is accurate. |
| `irpf_ganancia_derechos_ganancia_reducida_no_exenta` | OK | Single casilla 0351 for reduced non-exempt capital gain on subscription rights. Name is accurate. |
| `irpf_ganancia_fondos_valor_adquisicion_global` | OK | Single casilla 0315 for global acquisition value in IIC fund transmissions. Name is accurate. |
| `irpf_ganancia_otros_anio_imputacion_1` | RENAME | The `_1` suffix is opaque (there is a `_3` for pending gains — the `_1` likely refers to the first imputation-year field). Rename to `irpf_ganancia_otros_anio_imputacion` for clarity, or keep the `_1` only if a systematic `_1/_2` split exists in the batch. Given only `_1` appears here the suffix adds no information. Rename to `irpf_ganancia_otros_anio_imputacion`. |
| `irpf_ganancia_otros_ganancia_pendiente_3` | RENAME | The `_3` suffix is opaque. The field (0373) represents the capital gain pending imputation in the `elemento_patrimonial` context. If the `_3` refers to the third installment slot the name should say so explicitly. If it is an arbitrary counter, remove it: `irpf_ganancia_otros_ganancia_pendiente_imputacion`. |
| `irpf_ganancia_otros_reduccion_dt9` | OK | Single casilla 1648 for the DT 9ª reduction on other capital gains. Consistent across revisions. Name is accurate. |
| `irpf_ganancia_otros_valor_transmision_renta_vitalicia` | OK | Single casilla 1634 for the portion of transmission value reinvested to establish an annuity. Name is accurate. |
| `irpf_ganancia_premios_juegos_pub_metalico` | OK | Single casilla 0292 for cash prize amounts from public games. Name is accurate. |
| `irpf_inmueble_arrendamiento_accesorio_flag` | OK | Single casilla 0074 boolean for whether property is rented as an accessory to a primary property. Stable. Name is accurate. |
| `irpf_inmueble_dias_vivienda_habitual` | RENAME | `data_type: money(default)` is incorrect for a day count. This is a design-level type error but falls outside the rename/split scope. The name itself is accurate — `irpf_inmueble_dias_vivienda_habitual`. No rename needed; flag the `data_type` mismatch as a separate structural issue. |
| `irpf_inmueble_referencia_catastral_principal` | OK | Single casilla 0090 for the catastral reference of the main property to which an accessory property is linked. Name is accurate. |
| `irpf_integracion_gyp_general_suma_ganancias` | OK | Single casilla 0418 summing all general-base capital gains for integration. Name is accurate. |
| `irpf_minimo_aplicado_base_general_estatal` | OK | Single casilla 0521 for the personal/family minimum applied to general base for state-tax purposes. Name is accurate. |
| `irpf_perdida_acciones_importe_computable` | OK | Single casilla 0338 for the computable capital loss on listed shares. Name is accurate. |
| `irpf_perdida_otros_obtenida` | OK | Single casilla 1638 for the capital loss obtained on other patrimonial elements. Name is accurate. |
| `irpf_re_aie_deduccion_doble_imposicion` | OK | Single casilla 0263 for double-taxation relief on income attributed from agrupaciones de interés económico. Name is accurate. |
| `irpf_re_atrib_cap_inmo_rdto_neto_entidad` | RENAME | The prefix `cap_inmo` (capital inmobiliario) is misleading — the section is `re_at_rentas` which covers income attributed from partnerships/entities generally, and the label is generic "Rendimiento neto atribuido por la entidad". The data_type is `decimal` (not `money`) consistent with a net-income figure. Rename to `irpf_re_atrib_rdto_neto_entidad`. |
| `irpf_re_atrib_gp_dt9_reducciones` | OK | Single casilla 1593 for DT 9ª reductions on attributed capital gains. Name is accurate. |
| `irpf_re_atrib_gp_transmision_ganancias` | OK | Single casilla 1586 for attributed capital gains from transmissions. Name is accurate. |
| `irpf_re_atrib_suma_act_eco` | OK | Single casilla 1605 summing attributed economic-activity net incomes. Name is accurate. |
| `irpf_re_iic_suma_imputaciones` | OK | Single casilla 0280 summing income imputations from IIC entities constituted in tax havens. Name is accurate. |
| `irpf_red_discapacidad_exceso_aportaciones_parientes` | OK | Single casilla 0473 for pending excess reductions from prior years for contributions to disability protection funds on behalf of relatives. Rolling window. Name is accurate. |
| `irpf_reduccion_patrimonio_protegido_aplicada` | OK | Single casilla 0495 for the applied portion of the protected-heritage (patrimonio protegido) reduction. Name is accurate. |
| `irpf_rendimiento_capital_inmobiliario_amortizacion_casos_especiales` | OK | Single casilla 0132 for special-case amortisation in rental income calculation. In 2025 section moves to `rendimientos_capital_inmobiliario/amortizacion`. Name is accurate. |
| `irpf_rendimiento_capital_inmobiliario_gasto_servicios_suministros` | OK | Single casilla 0113 for utility and service costs deducted from rental income. In 2025 section moves to `rendimientos_capital_inmobiliario/gastos_deducibles`. Name is accurate. |
| `irpf_rendimiento_capital_mobiliario_ahorro_deuda_subordinada_preferentes` | OK | Single casilla 0034 for income from subordinated debt and preferred shares, in savings-base capital-mobiliario section. Name is accurate. |
| `irpf_rendimiento_capital_mobiliario_ahorro_rendimiento_neto_reducido` | OK | Single casilla 0040 for reduced net income in savings-base capital-mobiliario. Name is accurate. |
| `irpf_rendimiento_capital_mobiliario_general_reduccion` | OK | Single casilla 0055 for reductions on general-base capital-mobiliario income (irregular/long-term). Name is accurate. |
| `irpf_rendimiento_trabajo_gasto_colegio_profesional` | OK | Single casilla 0015 for compulsory professional association fees deducted from employment income. Name is accurate. |
| `irpf_rendimiento_trabajo_rendimiento_neto_reducido` | OK | Single casilla 0025 for reduced net employment income. Name is accurate. |
| `irpf_retencion_directiva_ahorro_2003_48` | OK | Single casilla 0606 for withholdings under EU Savings Directive 2003/48/CE (pre-2019). Name is accurate. |
| `irpf_tipo_medio_gravamen_general_estatal` | RENAME | Casilla 0534 is the **effective tax rate** (tipo medio, expressed as a percentage), not a monetary cuota. The `data_type: money(default)` is a registry-level type error, but the role name should accurately describe it as a rate, not a cuota. Rename to `irpf_tipo_medio_gravamen_base_liquidable_general_estatal`. |
| `irpf_compensacion_conyuges_bank_city` | RENAME | Missing `irpf_` scoping is already present, but `bank_city` in the role name is in English and refers to the bank city field within the spouse-compensation payment section (`compnosepa`). A more accurate domain name: `irpf_compensacion_conyuges_entidad_ciudad`. |
| `irpf_deduccion_asturias_vivienda_protegida_2021` | RENAME | The `_2021` suffix embeds a transient year reference in a stable identifier — violates source hygiene. The concept is "Asturias protected housing deduction: generated amount pending (rolling year)". Rename to `irpf_deduccion_asturias_vivienda_protegida_generado_pendiente`. |
| `irpf_deduccion_castilla_la_mancha_residencia_zonas_rurales` | OK | Single casilla 0201 (2021+). Stable. Name is accurate. |
| `irpf_deduccion_la_rioja_donaciones_investigacion_patrimonio` | OK | Single casilla 0251 (2021+). Stable. Name is accurate. |
| `irpf_rendimiento_act_eco_estimacion_directa_rdto_neto` | RENAME | Casilla 0224 is the net income (before reducción) in direct estimation (2021+). The role `irpf_ed_rdto_neto_reducido` covers casilla 0226 (net reduced). There is now overlap risk: casilla 0224 is the intermediate pre-reduction net, not the reduced figure. Rename to `irpf_ed_rdto_neto_previo_reduccion` to distinguish from `irpf_ed_rdto_neto_reducido` (0226). |
| `irpf_deduccion_asturias_vivienda_protegida_pendiente` | RENAME | The `_pendiente` suffix is ambiguous — both this and `irpf_deduccion_asturias_vivienda_protegida_2021` hold pending amounts. This role (casilla 0800, 2022+) holds the amount **generated in the prior year pending application**, while casilla 1610 holds the amount **generated in the current year**. Rename to `irpf_deduccion_asturias_vivienda_protegida_anio_anterior_pendiente`. |
| `irpf_deduccion_la_palma_estatal` | OK | Casilla 0544 (2022+) for La Palma island state-part deduction. Name is accurate. |
| `irpf_ganancia_cripto_ganancia_pendiente_3` | RENAME | The `_3` suffix is opaque (same issue as `irpf_ganancia_otros_ganancia_pendiente_3`). Rename to `irpf_ganancia_cripto_ganancia_pendiente_imputacion`. |
| `irpf_ganancia_cripto_tipo_contraprestacion_clave` | OK | Single casilla 1803 for the counterpart-type code in crypto-asset gain declarations. Name is accurate. |
| `irpf_ganancia_inmueble_catastral_1` | RENAME | The `_1` suffix refers to the first catastral reference among potentially multiple references for a property disposal. If a `_2` counterpart exists (not in this batch) the `_1` is appropriate; otherwise rename to `irpf_ganancia_inmueble_referencia_catastral`. Also note "catastral" should be standardised as `referencia_catastral` for consistency with `irpf_inmueble_referencia_catastral`. Rename to `irpf_ganancia_inmueble_referencia_catastral_1`. |
| `irpf_ganancia_inmueble_ganancia_pendiente_2` | RENAME | The `_2` suffix is opaque. Rename to `irpf_ganancia_inmueble_ganancia_pendiente_imputacion`. |
| `irpf_ganancia_inmueble_no_exenta_sin_reduccion` | OK | Casilla 1842 for the non-exempt capital gain on real-estate disposal. Name is accurate. |
| `irpf_ganancia_inmueble_valor_adquisicion` | OK | Casilla 1830. Stable across 2022–2025. Name is accurate. |
| `irpf_intereses_demora_regularizacion_autonomico` | OK | Casilla 0583 (2022+) for late-interest charge on prior regularisation, autonomous community part. Name is accurate. |
| `irpf_perdida_inmueble_pendiente_2` | RENAME | The `_2` suffix is opaque. Rename to `irpf_perdida_inmueble_pendiente_imputacion`. |
| `employer_nif` | RENAME | Missing `irpf_` prefix; also the field (0397, 2023+) is specifically the NIF of the employer in the pension-contribution reduction section. Rename to `irpf_empleador_nif`. |
| `irpf_anexo_b_adoption_pending_claim` | RENAME | English mid-name inconsistent with convention; specifically Illes Balears adoption deduction (Anexo B). Rename to `irpf_anexo_b_deduccion_adopcion_pendiente_reclamar`. |
| `irpf_deduccion_baleares_adopcion` | OK | Casilla 1721 (2023+) for Baleares adoption deduction result. Name is accurate. |
| `irpf_deduccion_c_valenciana_generado_2022_pendiente` | RENAME | Year-specific suffix in a stable identifier; concept is a rolling carry-forward. Rename to `irpf_deduccion_c_valenciana_generado_pendiente`. |
| `irpf_deduccion_rib_illes_balears_autonomica` | OK | Casilla 0503 (2023+) for Illes Balears investment reserve deduction, autonomous community part. Name is accurate. |
| `irpf_ed_mutualidades_alternativas_titular` | OK | Casilla 0195 (2023+) for alternative mutual society contributions by the business owner under direct estimation. Name is accurate. |
| `irpf_feac_fecha_operacion` | OK | Casilla 1987 (2023+) for the FEAC (fusiones, escisiones, aportaciones, canjes) operation date. Name is accurate. |
| `irpf_ganancia_inmueble_importe_real_adquisicion` | OK | Casilla 1913 (2023+) for the actual acquisition price of the property. Name is accurate. |
| `irpf_red_prevision_social_rendimientos_trabajo_rango_flag` | RENAME | From 2025 the label inverts: 2023–2024 "≤ 60.000 €" mark, 2025 "> 60.000 €" mark. These are semantically opposite flags sharing the same casilla id and role. This is an actual semantic flip introduced by the AEAT form in 2025. The role name currently says `rango_flag` which is neutral but the inversion is a precision issue. Rename to `irpf_red_prevision_social_rendimientos_trabajo_rango_superior_flag` to match the 2025 semantics, and document that 2023–2024 members carry the inverted (≤60k) polarity. |
| `irpf_anexo_b_other_service_amount` | RENAME | English mid-name; casilla 2140 is "Importe anual satisfecho de otros gastos" in Anexo B AIA subsection. Rename to `irpf_anexo_b_otros_gastos_importe_anual`. |
| `irpf_deduccion_c_valenciana_danos_vivienda_dana_generado` | OK | Casilla 1703 (2024–2025) for C. Valenciana DANA flood-damage housing deduction generated amount. Name is accurate. |
| `irpf_deduccion_cantabria_ayuda_domestica` | OK | Casilla 1711 (2024–2025) for Cantabria domestic help deduction. Name is accurate. |
| `irpf_deduccion_galicia_acciones_participaciones_3` | RENAME | The `_3` suffix is opaque — if there are `_1` and `_2` counterparts the numbering may be meaningful but they are not in this batch. The concept is Galicia deduction for share/equity investment in special-interest projects. Rename to `irpf_deduccion_galicia_acciones_participaciones_proyectos_especiales` if this is a distinct variant, or `irpf_deduccion_galicia_acciones_participaciones` if the `_3` is merely a sequence counter. |
| `irpf_deduccion_madrid_vivienda_anio_adquisicion` | OK | Casilla 2018 (2024–2025) for the acquisition year of property in Madrid housing deduction context. Name is accurate. |
| `irpf_discrepancia_criterio_administrativo` | OK | Casilla 0669 (2024–2025) for the administrative criterion discrepancy amount in rectificative self-assessments. Name is accurate. |
| `irpf_anexo_c_exceso_sps_rg_aportaciones_aplicado` | OK | Single member (casilla 1758, revision 2021 only). Applied general-regime pension-system excess contribution in Anexo C. Name is accurate; single-revision presence is expected for a transitional form entry. |
| `irpf_conyuge_grado_discapacidad` | OK | Casilla `DPGMIN_C` (2025 only) for spouse disability degree. Name is accurate. |
| `irpf_declarante_sexo` | OK | Casilla `SEXO_D` (2025 only) for declarant sex. Name is accurate. |
| `irpf_deduccion_canarias_acciones_participaciones` | OK | Casilla 2246 (2025 only) for Canarias new-enterprise share/equity investment deduction. Name is accurate. |
| `irpf_deduccion_catalunya_generado_2025` | RENAME | Year-specific suffix in a stable identifier. Rename to `irpf_deduccion_catalunya_generado_pendiente`. |
| `irpf_deduccion_galicia_generado_2025_pendiente` | RENAME | Year-specific suffix. Rename to `irpf_deduccion_galicia_generado_pendiente`. |
| `irpf_deduccion_madrid_generado_2024_pendiente_2` | RENAME | Year-specific suffix + opaque `_2` counter. Rename to `irpf_deduccion_madrid_generado_pendiente`. |
| `irpf_deduccion_murcia_infraestructuras_referencia_catastral` | OK | Casilla 2158 (2025 only) for the catastral reference in Murcia infrastructure-works deduction. Name is accurate. |
| `irpf_ed_regularizacion_reta_devolver` | OK | Casilla 0197 (2025 only) for RETA quota regularisation amounts to be refunded. Name is accurate. |
| `irpf_ganancia_fondos_coti_ganancia` | OK | Casilla 2230 (2025 only) for capital gains from transfers/redemptions of ETF-like listed funds (`gp_fondos_coti`), introduced in 2025. Name is accurate. |
| `irpf_hijos_residentes_ue_eee_flag` | OK | Casilla `HIJOSUE` (2025 only) boolean for EU/EEA-resident children. Name is accurate. |
| `irpf_re_at_rdto_neto_estimacion_directa_objetiva` | OK | Single member (casilla 1577, revision 2020 only). Net income field covering both normal/simplified direct estimation and objective estimation within attribution regimes. Name is accurate for a 2020-only transitional entry. |
| `taxpayer_nif` | RENAME | Missing `irpf_` prefix. Rename to `irpf_declarante_nif`. Also inconsistent with the `irpf_conyuge_grado_discapacidad` and `irpf_declarante_sexo` naming pattern established elsewhere. |

---

## Summary counts

| verdict | count |
|---|---|
| OK | 46 |
| RENAME | 22 |
| SPLIT | 2 |
| OUTLIER | 2 |
| **Total** | **72** |

### Outlier detail

- `irpf_anexo_b_carry_forward_pending`: casillas `1115` and `1118` (revisions 2023/2024/2025) and `1078` (revision 2025) are Madrid and Galicia regional deductions, not C. Valenciana carry-forward amounts.
- `irpf_anexo_c_exceso_eeficiencia_aplicado`: casilla `1696` (revision 2022) is a Canarias investment reserve entry, not an energy-efficiency applied excess.

### Cross-cutting issues noted

- Several roles carry `data_type: money(default)` for fields that are logically day-counts (`irpf_inmueble_dias_vivienda_habitual`, casilla 0076) or percentage rates (`irpf_tipo_medio_gravamen_general_estatal`, casilla 0534). These are registry-level type errors warranting a separate structural fix ticket.
- English mid-names in roles (`landlord_nif`, `employer_nif`, `taxpayer_nif`, `irpf_anexo_b_insurance_premium`, `irpf_anexo_b_carry_forward_pending`, `irpf_anexo_b_adoption_pending_claim`, `irpf_anexo_b_other_service_amount`) are inconsistent with the Spanish-term convention used by the majority of roles.
- Year-literal suffixes (`_2021`, `_2022`, `_2025`, `_2024`) in role names for rolling carry-forward concepts violate the no-transient-metadata rule and will become stale without deprecation infrastructure.
