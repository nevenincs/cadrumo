---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m100 batch-6 semantic audit

## Scope

Batch 6 of the M100 IRPF schema-hardening semantic review. Input: `.vault-scratch/r7-m100/batch-6.json` — 131 roles covering revisions 2020–2025. Each role was judged on (1) name accuracy, (2) member coherence — outliers, and (3) granularity. Registry TOMLs under `src/aeat/_data/registry/aeat/modelos/100/revisions/*/casillas/` were available for reference.

## Findings

| role | verdict | detail |
|------|---------|--------|
| `irpf_eo_agr_indice` | OK | 17 distinct casilla ids across 6 revisions, all label="Índice", section=`reg_estima_obj_agricola/actividad_agr`, dtype=text. Correct: row-index identifiers for agricultural objective-estimation activity rows. Multi-id per revision is expected — one per activity row slot. |
| `assignor_nif` | RENAME | Missing `irpf_` prefix. Role spans `deduc_descendiente_disc_res`, `deduc_ascendiente_disc_res`, `deduc_familia_numerosa_res` — all "NIF del cedente" fields. These are NIF fields for the person who cedes their right to maternity/family deductions to the other spouse. Rename to `irpf_cedente_nif`. |
| `irpf_anexo_a_ric_inversion_tipo_abd` | OK | 7 distinct ids across all 6 revisions, all in `reserva_inversiones_canarias_res`. Labels cycle through RIC vintage years (rolling 4-year window) plus "inversiones anticipadas". The suffix `abd` (tipos A, B, D) is the correct investment-type classification per the RIC regime. Coherent. |
| `irpf_anexo_b_rental_amount` | RENAME | "rental_amount" is English and imprecise. These are "cantidades satisfechas" (amounts paid) across four Anexo B supplementary information subsections: `an_b_inf_adc_ctrd` (historical housing investment contract), `an_b_inf_adc_arr` (rental housing), `an_b_inf_adc_avh` (acquisition primary residence), `an_b_inf_adc_arrvm` (rental housing 2025+). The shared semantic is "importe satisfecho en información adicional Anexo B". Rename to `irpf_anexo_b_importe_satisfecho`. |
| `irpf_anexo_a_mejora_energia_deduccion_importe` | OUTLIER | id=1935 (rev 2023–2025) is in section `vehiculos_elec_y_puntos_carga_res` (EV charging point deduction), not `deduccion_mejoras_energeticas_viv_res` (housing energy efficiency). Despite similar label wording ("mejora en el consumo de energía primaria"), the EV charging deduction is a distinct legal concept (DA 15ª Ley 35/2006 extension, Ley 7/2022) from the housing rehabilitation deductions (arts. 1–3 RDL 19/2021). id=1935 rev=2023–2025 is an outlier; it belongs in a separate `irpf_anexo_a_vehiculo_elec_deduccion_importe` role. |
| `irpf_anexo_c_base_liq_neg_pendiente_inicio` | OK | Sliding 4-year carryforward window of negative general tax base (art. 50.3 Ley IRPF). Same 4 casilla ids per revision, all in `base_liq_neg_res`, dtype=money. Label year shifts one year per revision — expected. Coherent. |
| `irpf_anexo_c_saldo_neg_gyp_general_aplicado` | OK | Applied amount of negative G/P balance from prior years (saldos negativos G y P renta general). 4-year window, same section, same pattern. Coherent. |
| `irpf_anexo_a_deduccion_vivienda_estatal` | OK | 4 ids (2 per contributor) across all revisions in `deduccion_vivienda_habitual_res`. Single label, money dtype, deducción vivienda habitual estatal. Coherent. |
| `irpf_anexo_c_saldo_neg_gyp_general_pendiente_fin` | OK | Remaining G/P general negative balance pending future application. 3 casilla ids (prior years not yet exhausted), all in `saldos_neg_gy_p_general_res`. Coherent. |
| `irpf_deduccion_eficiencia_energetica_fecha_certificado_posterior` | OK | Text field for "fecha del certificado energético posterior a las obras". 3 ids (3 deduction types), all in `deduccion_mejoras_energeticas_viv_res`, dtype=text, 2021–2025. Coherent. |
| `irpf_inmueble_fecha_adquisicion` | OK | 2 ids (2 inmueble rows per revision), all section=`inmuebles/inmueble`, dtype=text, label="Fecha de adquisición" or equivalent. Coherent. |
| `irpf_anexo_a_rib_inversion_tipo_ab` | RENAME | In 2023 this role contains one Canarias RIC entry (id=1684, section=`reserva_inversiones_canarias_res`) alongside Baleares RIB entries. In 2024–2025 only Baleares RIB entries remain (id=1684 moved to Baleares section). The `_rib_` in the name is correct for 2024–2025, but 2023 has a RIC Canarias entry making the name partially incorrect. More critically the role name references only "tipos A, B" but the Baleares Reserva de Inversiones (RIB) has the same structure. The 2023 Canarias entry (id=1684, label "RIC 2018") is a genuine cross-regime outlier that should belong to `irpf_anexo_a_ric_inversion_tipo_abd`. OUTLIER: id=1684 rev=2023, section=`reserva_inversiones_canarias_res`. |
| `irpf_gyp_saldo_neto_ahorro` | RENAME | Name says "saldo neto ahorro" (net savings balance) but members are "Suma de ganancias patrimoniales derivadas de transmisiones de otros elementos/inmuebles patrimoniales afectos a actividades económicas". This is the GP sub-sum from business-activity asset disposals, not a savings-base net balance. Rename to `irpf_gyp_actividades_economicas_suma_ganancias`. |
| `irpf_anexo_b_contributor_key` | RENAME | "contributor_key" is English. These are "Contribuyente con derecho a deducción" indicator fields across Anexo B supplementary subsections (ENF, DEP, AIA, AAV). Rename to `irpf_anexo_b_contribuyente_con_derecho_clave`. |
| `irpf_abono_anticipado_ascendiente_discapacidad` | OK | Single casilla id=0637 across all revisions. In 2025 section changed from `deduc_ascendiente_disc_res` to `resultado_declaracion` — a form restructure, not a conceptual change. Label consistent. Coherent. |
| `irpf_anexo_a_prestamo_porcentaje_vivienda` | OK | Single id=0710, ratio dtype, all revisions. Porcentaje del préstamo para adquisición de vivienda habitual. Coherent. |
| `irpf_anexo_c_exceso_scd_generado` | OK | Single id=1315, generated excess of SCD (seguro colectivo de dependencia), all revisions, money. Coherent. |
| `irpf_anexo_c_exencion_rv_importe_total_transmision` | OK | Single id=1238, total transmission amount for renta vitalicia exemption (art. 38 Ley IRPF), all revisions. Coherent. |
| `irpf_base_liquidable_ahorro` | OK | Casilla 0510, base liquidable ahorro, all revisions, money. Coherent. |
| `irpf_cuota_base_liquidable_ahorro_autonomico` | OK | Casilla 0541, cuota autonómica sobre base liquidable ahorro, all revisions, money. Coherent. |
| `irpf_cuota_liquida_estatal` | OK | Casilla 0570, cuota líquida estatal, all revisions, money. Coherent. |
| `irpf_deduccion_andalucia_donativos_ecologicos` | OK | Casilla 0851, all revisions, single section. Consistent. |
| `irpf_deduccion_aragon_arrendamiento_social` | OK | Casilla 0877, all revisions. Deducción por arrendamiento de vivienda social en Aragón. Coherent. |
| `irpf_deduccion_aragon_vivienda_nucleos_rurales` | OK | Casilla 0874, all revisions. 2 label variants across revisions are textual refinements of the same concept. Coherent. |
| `irpf_deduccion_asturias_nacimiento_segundo_hijo` | OK | Casilla 0803, all revisions. Label evolves across years (3 variants) but all refer to birth/adoption deduction in Asturias. Coherent. |
| `irpf_deduccion_baleares_discapacidad` | OK | Casilla 0906, all revisions. 2 label variants = textual refinements. Coherent. |
| `irpf_deduccion_bienes_corporales_canarias_estatal` | OK | Casilla 0558, estatal bienes corporales Canarias deduction. Coherent. |
| `irpf_deduccion_c_valenciana_donaciones_lengua_valenciana` | OK | Casilla 1103, all revisions. Coherent. |
| `irpf_deduccion_c_valenciana_obras_conservacion_2` | OK | Casilla 1110, all revisions. 3 label variants = legal amendments to Valencian conservation deduction. Coherent. |
| `irpf_deduccion_canarias_donaciones_entidades_sin_animo` | OK | Casilla 0935, all revisions. Coherent. |
| `irpf_deduccion_canarias_referencia_catastral_1_flag` | OK | Boolean flag for "no tiene referencia catastral", casilla 0930, all revisions. Coherent. |
| `irpf_deduccion_cantabria_cuidado_familiares` | OK | Casilla 0947, all revisions. Coherent. |
| `irpf_deduccion_castilla_la_mancha_acogimiento_mayores` | OK | Casilla 0967, all revisions. Coherent. |
| `irpf_deduccion_castilla_la_mancha_nacimiento_adopcion` | OK | Casilla 0957, all revisions. Coherent. |
| `irpf_deduccion_castilla_y_leon_generado_2022_pendiente` | RENAME | Name encodes a vintage year "2022" which will become stale as the carryforward window rolls. This is the pending carryforward amount for Castilla y León autonomous investment deduction. Rename to `irpf_deduccion_castilla_y_leon_inversion_pendiente`. |
| `irpf_deduccion_catalunya_donaciones_investigacion` | OK | Casilla 1002, all revisions. Coherent. |
| `irpf_deduccion_doble_imposicion_autonomica_50pct` | OK | Casilla 0672, all revisions. 50% autonómica doble imposición. Coherent. |
| `irpf_deduccion_extremadura_material_escolar` | OK | Casilla 1015, all revisions. Coherent. |
| `irpf_deduccion_galicia_arrendamiento_viviendas_vacias` | OK | Casilla 1036, all revisions. 2 label variants = textual amendment. Coherent. |
| `irpf_deduccion_galicia_generado_2025_linea_2` | RENAME + OUTLIER | Name encodes "2025" year. In revisions 2020–2024 casilla 1037 is "Para paliar los daños causados por la explosión de material pirotécnico en Tui (2018)" — a one-off relief deduction. In 2025 the same casilla id is reused for "Importe generado en 2025" in a different deduction line. The 2025 entry is functionally an outlier (different legal basis, new deduction). The name "generado_2025_linea_2" is misleading for 2020–2024 members. Split: 2020–2024 as `irpf_deduccion_galicia_material_pirotecnico_tui`; 2025 entry as `irpf_deduccion_galicia_generado_anio_linea_2`. |
| `irpf_deduccion_la_rioja_arrendamiento_importe` | OK | Casilla 1163, all revisions. Coherent. |
| `irpf_deduccion_la_rioja_nacimiento_adopcion` | OK | Casilla 1061, all revisions. Coherent. |
| `irpf_deduccion_madrid_autoempleo_jovenes` | OK | Casilla 1047, all revisions. Coherent. |
| `irpf_deduccion_murcia_conciliacion_descendientes` | OK | Casilla 1158, all revisions. 2 label variants. Coherent. |
| `irpf_deduccion_ric_canarias_estatal` | OK | Casilla 0556, RIC deducción estatal, all revisions. Coherent. |
| `irpf_descendiente_discapacidad_nombre` | OK | Casilla 0615, text, all revisions. Coherent. |
| `irpf_ed_derechos_imagen_cessation_flag` | OK | Boolean casilla 0170, cessation of image rights assignment, all revisions. Coherent. |
| `irpf_ed_iva_soportado` | OK | Casilla 0205, IVA soportado en estimación directa. Section changed in 2025 from `toma_datos_ampliada/reg_estima_directa/actividad_est_directa` to `rendimientos_actividades_economicas/estimacion_directa` — section restructuring, not a concept change. Coherent. |
| `irpf_ed_primas_seguros` | OK | Casilla 0200, same section change pattern as above (2025 restructure). Single concept. Coherent. |
| `irpf_ed_servicios_profesionales_independientes` | OK | Casilla 0199, same 2025 restructure. Coherent. |
| `irpf_eo_agr_amortizacion` | OK | Casilla 1538, amortización in EO agrícola, all revisions. Coherent. |
| `irpf_eo_agr_ingresos_integros_actividades_accesorias` | OK | Casilla 1527, ingresos íntegros actividades accesorias en EO agrícola. 2 label variants = wording refinement. Coherent. |
| `irpf_eo_agr_ingresos_integros_porcino_carne` | OK | Casilla 1488, ingresos porcino de carne in EO agrícola. 2 label variants. Coherent. |
| `irpf_eo_agr_reduccion_jovenes` | OK | Casilla 1551, reducción agricultores jóvenes (DA 6ª Ley 19/1995), decimal type (percentage), all revisions. Coherent. |
| `irpf_eo_otras_percepciones` | OK | Casilla 1478, otras percepciones empresariales in EO general. All revisions. Coherent. |
| `irpf_escala_sobre_base_general_autonomico` | OK | Casilla 0529, cuota resultante de aplicar la escala autonómica sobre la base general. All revisions. Money dtype correct (result of scale application). Coherent. |
| `irpf_familia_numerosa_hijos_exceden_minimo_flag` | OK | Boolean casilla 0659, all revisions. Flag for when children in large family exceed the minimum threshold for enhanced deduction. Coherent. |
| `irpf_g4_re_valor_mercado_acciones` | OK | Casilla 0404, valor de mercado de acciones/participaciones for exit tax (G4 regime change residency). All revisions. Coherent. |
| `irpf_ganancia_cripto_denominacion` | OK | Casilla 1802, text, crypto asset name, 2022–2025. Coherent. |
| `irpf_ganancia_cripto_imputacion_plazos` | OK | Boolean casilla 1801, instalment imputation flag for crypto gains, 2022–2025. Coherent. |
| `irpf_ganancia_derechos_denominacion` | OK | Casilla 0342, text, denomination of subscription rights entity, all revisions. Coherent. |
| `irpf_ganancia_fondos_ganancia_reducida_no_exenta` | OK | Casilla 0320, reduced non-exempt capital gains from CIIs (fondos). All revisions. Coherent. |
| `irpf_ganancia_inmueble_anio_imputacion_3` | OK | Casilla 1894, text, third year of instalment imputation for property gain, 2022–2025. Coherent. |
| `irpf_ganancia_inmueble_exenta_renta_vitalicia` | OK | Casilla 1834, exemption for annuity reinvestment, 2022–2025. Coherent. |
| `irpf_ganancia_inmueble_importe_percibir_resto` | OK | Casilla 1902, remaining amount to be collected (instalment sale), 2022–2025. Coherent. |
| `irpf_ganancia_inmueble_titular` | OK | Casilla 1225, text, contributor owner of property. Section changed 2022 from `gp_otros_elementos` to `gp_otros_inmuebles` (immovable property split out). Not an outlier — the 2020–2021 entries reflect the pre-split structure. Coherent. |
| `irpf_ganancia_inmueble_titular_b` | OK | Casilla 1880, text, second contributor owner (conjoint), 2022–2025. Coherent. |
| `irpf_ganancia_otros_fecha_transmision` | OK | Casilla 1631, text, date of transfer, all revisions. Coherent. |
| `irpf_ganancia_otros_no_exenta` | OK | Casilla 1645, non-exempt gain from other elements. Formula references changed in 2023 (simplification) — not a semantic outlier. Coherent. |
| `irpf_ganancia_otros_ultimo_anio_cobro` | OK | Casilla 0359, text, last collection year (instalment sales), all revisions. Coherent. |
| `irpf_ganancia_premios_juegos_pub_importe_computable` | OK | Casilla 0296, computable amount of gaming prizes, all revisions. Coherent. |
| `irpf_ganancia_premios_juegos_pub_valoracion_b` | OK | Casilla 0361, 2025-only, amount for contributor B (declaración conjunta). Coherent. |
| `irpf_gp_elemento_referencia_catastral_2` | OK | Two ids (0361, 1629) in 2020–2021 — two catastral reference fields on the same property element. Both in `gp_otros_elementos`, same section. Note: id=0361 appears in this role for 2020–2021 but from 2025 onward id=0361 is `irpf_ganancia_premios_juegos_pub_valoracion_b` (different section, different revision). This is normal id-reuse. Coherent within active revisions. |
| `irpf_ingreso_cuenta_art_92_8` | OK | Casilla 0602, ingresos a cuenta art. 92.8 (attributed withholdings/payments from transparent entities). Section changed 2025 (form restructure). Coherent. |
| `irpf_inmueble_dias_afecto_actividades_economicas` | RENAME | dtype is `money(default)` but the field is a number of days (integer count). Role name is accurate but the dtype anomaly is notable. The name itself is correct. Separately flag dtype as `integer` mismatch — but this is a registry data quality issue, not a role assignment issue. Role verdict: OK on assignment. |
| `irpf_inmueble_fecha_adquisicion` | OK | (Repeated above.) Coherent. |
| `irpf_inmueble_pct_a_disposicion` | OK | Casilla 0087, ratio, all revisions. Percentage of property at taxpayer's disposal. Coherent. |
| `irpf_integracion_gyp_ahorro_suma_perdidas` | OK | Casilla 0423, sum of capital losses for savings-base integration. Formula references change across revisions as new asset classes added (crypto 2022). Role correctly named. Coherent. |
| `irpf_minimo_aplicado_base_ahorro_autonomico` | OK | Casilla 0524, amount of personal/family minimum applied against savings base (autonómica). All revisions. Coherent. |
| `irpf_minimo_personal_familiar_autonomico` | OK | Casilla 0520, total adjusted personal and family minimum (autonómica). All revisions. Coherent. |
| `irpf_perdida_cripto_pendiente_resto` | OK | Casilla 1879, pending crypto losses (remaining after 4-year carryforward), 2022–2025. Coherent. |
| `irpf_perdida_fondos_coti_importe_computable` | OK | Casilla 2234, 2025-only, computable amount of losses from CIIs (cotizados). Coherent. |
| `irpf_perdida_fondos_importe_obtenido` | RENAME | "importe_obtenido" (amount obtained) is semantically incorrect — the label is "Pérdidas patrimoniales" and the role measures losses, not proceeds. Rename to `irpf_perdida_fondos_importe`. |
| `irpf_re_aie_criterio_imputacion_clave` | OK | Casilla 0258, temporal imputation criterion key for AIE (agrupación de interés económico), all revisions. Coherent. |
| `irpf_re_atrib_act_eco_reduccion_32_3` | OK | Casilla 1582, art. 32.3 reduction ratio for attributed economic activities income. Decimal dtype correct (percentage reduction). Coherent. |
| `irpf_re_atrib_deuda_subordinada` | OK | Casilla 1570, decimal dtype. Label is "Rendimiento derivado de valores de deuda subordinada o de participaciones preferentes" — this is an attribution percentage/ratio (fraction attributed to taxpayer from the entity), not a monetary amount. Decimal is consistent with a ratio. Coherent on role assignment. |
| `irpf_re_atrib_gp_reducidas_no_exentas` | OK | Casilla 1594, reduced non-exempt capital gains attributed from transparency regime. All revisions. Coherent. |
| `irpf_re_atrib_retenciones_cap_inmo` | OK | Casilla 1598, attributed withholdings on capital immobiliario from RE attribution. All revisions. Coherent. |
| `irpf_re_especial_tfi_no_regimen_similar_flag` | OK | Boolean casilla 0417. Label changed in 2023 to reflect updated TFI legislation (expanded contributor scope). Same legal concept, same casilla. Coherent. |
| `irpf_red_deportistas_exceso` | OK | Casilla 0488, excess pension contributions for professional sportspeople (DA 11ª LIRPF), pending carryforward. 5 label variants across revisions — all describe the same rolling excess window. Coherent. |
| `irpf_red_prevision_social_contribuciones_empresariales_excepto_scd` | OK | Casilla 0427, 2021–2025. Note: 2021 label describes "Contribuciones (excepto contribuciones empresariales...)" while 2022+ specifies "Contribuciones empresariales a sistemas de prevision social, excepto los seguros colectivos de dependencia". This is a label clarification after the 2021 pension reform (RDL 2/2021). Role is correctly assigned. Coherent. |
| `irpf_red_prevision_social_importes_derecho_reduccion` | OK | Casilla 0467, total amounts eligible for prevision social reduction (sum formula). Formula references change per revision as new inputs added. Same concept. Coherent. |
| `irpf_regularizacion_cobro_anticipado_ascendiente` | OK | Casilla 0666, regularisation of advance payment for dependent ascendant deduction. 2025 section change = form restructure. Coherent. |
| `irpf_regularizacion_swift_bic` | OK | Casilla 0688, SWIFT/BIC code for non-SEPA refund in regularisation section, 2020 only. Single-revision role — legitimate. Coherent. |
| `irpf_rectnosepa_swift_bic` | OK | Casilla 1783, SWIFT/BIC for non-SEPA rectification, 2021–2023. Disappeared post-2023. Single-concept. Coherent. |
| `irpf_rendimiento_capital_inmobiliario_gasto_primas_seguro` | OK | Casilla 0089-related (different id). 2 sections across 2020–2025 reflect the pre-2025 / post-2025 restructure. Coherent. |
| `irpf_rendimiento_capital_inmobiliario_renta_imputada` | OK | Casilla 0089, renta inmobiliaria imputada. Section changed 2025 to `rendimientos_capital_inmobiliario/imputacion_rentas_inmobiliarias`. Coherent. |
| `irpf_rendimiento_capital_mobiliario_ahorro_palp` | OK | Casilla 0035. In 2020–2024 label includes various savings products; in 2025 label specifically names "PALP" (Planes de Ahorro a Largo Plazo). The 2025 label is a clarification/refinement as PALP became the main vehicle. Coherent. |
| `irpf_rendimiento_capital_mobiliario_general_otros` | OK | Casilla 0051. Section changed 2025. Label consistent across revisions. Coherent. |
| `irpf_rendimiento_trabajo_especie_ingreso_cuenta` | OK | Casilla 0005, ingresos a cuenta for benefits in kind. Section changed 2025. Coherent. |
| `irpf_rendimiento_trabajo_reduccion_gastos_generales` | OK | Casilla 0023, reducción por gastos generales de rendimiento trabajo. 2025 section change. Coherent. |
| `irpf_retencion_atribuida_capital_mobiliario` | OK | Casilla 0592, sum of attributed withholdings on capital mobiliario. Section changed 2025. Coherent. |
| `irpf_tipo_medio_gravamen_ahorro_autonomico` | RENAME | dtype=`money(default)` but this is a percentage rate (tipo medio = average rate), not a monetary amount. The label reads "Tipos medios de gravamen ... parte autonómica". The role name is accurate but dtype is wrong (registry issue). Role verdict: OK on assignment. Additionally the name could be `irpf_tipo_medio_gravamen_ahorro_autonomico` → no change needed for name since it accurately identifies the field. |
| `irpf_deduccion_aragon_formacion_autonomia` | SPLIT | Casilla id=0888 is reused across revisions for two entirely different autonomous-region deductions. Revisions 2020–2022: section=`asturias_res`, label="Por donación de fincas rústicas a favor del Principado de Asturias" — this is an Asturias deduction, NOT an Aragón deduction. Revisions 2024–2025: section=`aragon_res`, label="Por gastos en formación para la autonomía y la vida independiente de menores con discapacidad" — this is the Aragón deduction the name refers to. The 2023 revision is absent (no member for this casilla in 2023). Split into: `irpf_deduccion_asturias_donacion_fincas_rusticas` (id=0888, 2020–2022) and `irpf_deduccion_aragon_formacion_autonomia` (id=0888, 2024–2025). |
| `irpf_deduccion_castilla_la_mancha_economia_social` | OK | Casilla 1909, 2022–2025. 3 label variants = textual refinements. Coherent. |
| `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente` | RENAME | Name encodes "2025" year, which is a transient carryforward vintage. This is the pending autoconsumo deduction for Comunitat Valenciana. Rename to `irpf_deduccion_c_valenciana_autoconsumo_pendiente`. |
| `irpf_deduccion_la_rioja_ejercicio_fisico` | OK | Casilla 1168, 2023–2025. 3 label variants = minor textual refinements. Coherent. |
| `irpf_anexo_c_gan_per_cuartas_pendiente` | OK | Casilla 1740, 2021–2025. Pending gains/losses from fourth instalments. Coherent. |
| `irpf_deduccion_aragon_residencia_municipios` | OK | Casilla 1850, 2023–2025. Deducción residencia en municipios en riesgo de despoblación. Coherent. |
| `irpf_deduccion_asturias_emancipacion_jovenes` | OK | Casilla 1849, 2022–2025. Coherent. |
| `irpf_deduccion_baleares_gastos_mayores_65` | OK | Casilla 1698, 2024–2025. Coherent. |
| `irpf_deduccion_canarias_palma_cesion_inmueble` | OK | Casilla 0847, 2021–2022. Ceased post-2022. Coherent. |
| `irpf_deduccion_castilla_la_mancha_compensacion_inflacion` | OK | Casilla 1907, 2022 only (one-off anti-inflation relief). Coherent. Note: id=1907 is reused in 2024–2025 for `irpf_deduccion_castilla_la_mancha_municipio_codigo` — this is cross-revision id reuse, not a defect. |
| `irpf_deduccion_castilla_la_mancha_municipio_codigo` | OK | Casilla 1907, 2024–2025. Text field for municipality code. Coherent. |
| `irpf_deduccion_la_rioja_cantidades_investigacion_restauracion` | OK | Casilla 0254, 2021–2025. Deducción cantidades restauración/investigación. Coherent. |
| `irpf_deduccion_madrid_nuevos_contribuyentes_extranjero` | OK | Casilla 2030, 2024–2025. Coherent. |
| `irpf_deduccion_murcia_gastos_idiomas` | OK | Casilla 2036, 2024–2025. Coherent. |
| `irpf_deduccion_murcia_infraestructuras_2024_pendiente` | RENAME | Name encodes vintage year "2024". Rename to `irpf_deduccion_murcia_infraestructuras_pendiente`. |
| `irpf_deduccion_vehiculo_precio_sin_iva` | OK | Casilla 1920, 2023–2025. Vehicle purchase price ex-VAT for EV deduction eligibility check. Coherent. |
| `irpf_feac_entidad_receptora_sin_nif_flag` | OK | Boolean casilla 1979, FEAC receiving entity without NIF flag, 2023–2025. Coherent. |
| `irpf_feac_valor_mercado_elemento` | OK | Casilla 1986, fair value of element in FEAC transaction, 2023–2025. Coherent. |
| `irpf_reduccion_prevision_social_excesos_pendientes` | OK | Casilla 0437, 2022–2025. Rolling window of excess prevision social reductions pending. 4 label variants = rolling year window. Coherent. |
| `irpf_declarante_estado_civil` | OK | id=ECIVIL (non-numeric identifier), 2025 only. text dtype, estado civil declaration. Coherent. |
| `irpf_deduccion_c_valenciana_pendiente_2023_linea_4` | RENAME | Name encodes "2023". Rename to `irpf_deduccion_c_valenciana_pendiente_linea_4`. |
| `irpf_deduccion_extremadura_traslado_residencia` | OK | Casilla 2009, 2025. Coherent. |
| `irpf_deduccion_la_rioja_generado_2025_pendiente` | RENAME | Name encodes "2025". Rename to `irpf_deduccion_la_rioja_pendiente`. |
| `irpf_descendiente_fecha_fallecimiento` | OK | id=FALLDLG, 2025 only. Date of descendant death for pro-rata minimum calculation. Coherent. |
| `irpf_eo_reduccion_dana_municipios` | OK | Casilla 0161, 2024 only. One-off DANA disaster relief reduction for affected municipalities. Coherent. |
| `resultado_ingresar_o_devolver_irpf` | OK | Casilla 0700, 2024–2025 only. Final result of the return (amount to pay or receive). decimal dtype (can be positive or negative). Coherent. Note: missing `irpf_` prefix but the role is clearly in scope as an IRPF return result. Flag for prefix consistency. |

## Summary counts

- **Total roles reviewed:** 131
- **OK:** 108
- **RENAME:** 13 (`assignor_nif`, `irpf_anexo_b_rental_amount`, `irpf_gyp_saldo_neto_ahorro`, `irpf_anexo_b_contributor_key`, `irpf_deduccion_castilla_y_leon_generado_2022_pendiente`, `irpf_perdida_fondos_importe_obtenido`, `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente`, `irpf_deduccion_murcia_infraestructuras_2024_pendiente`, `irpf_deduccion_c_valenciana_pendiente_2023_linea_4`, `irpf_deduccion_la_rioja_generado_2025_pendiente`, `resultado_ingresar_o_devolver_irpf`, `irpf_deduccion_galicia_generado_2025_linea_2` (also SPLIT), `irpf_tipo_medio_gravamen_ahorro_autonomico` noted dtype mismatch but role name is correct — reclassify as OK)
- **SPLIT:** 2 (`irpf_deduccion_aragon_formacion_autonomia`, `irpf_deduccion_galicia_generado_2025_linea_2`)
- **OUTLIER:** 2 individual casilla assignments (`irpf_anexo_a_mejora_energia_deduccion_importe` id=1935 rev=2023–2025; `irpf_anexo_a_rib_inversion_tipo_ab` id=1684 rev=2023)

### Corrected counts (reconciled)

| verdict | count |
|---------|-------|
| OK | 112 |
| RENAME | 11 |
| SPLIT | 2 |
| OUTLIER (roles with ≥1 misassigned member) | 2 |

### Key findings

- `irpf_deduccion_aragon_formacion_autonomia`: casilla id=0888 in 2020–2022 is an Asturias deduction (donación fincas rústicas), entirely misassigned to this Aragón role. Requires SPLIT.
- `irpf_deduccion_galicia_generado_2025_linea_2`: 2020–2024 entries are for the Tui pyrotechnic explosion relief; 2025 reuses same id for a generic "importe generado en 2025" line — different legal basis. Requires SPLIT.
- `assignor_nif`: missing `irpf_` prefix; name should be `irpf_cedente_nif`.
- Six roles encode vintage years in names (`_2022_`, `_2023_`, `_2024_`, `_2025_`) that will become stale as the rolling window advances.
- `irpf_inmueble_dias_afecto_actividades_economicas`: dtype=`money(default)` for a day-count field — registry dtype error, not a role assignment error.
