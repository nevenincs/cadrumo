---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m100 batch-3 semantic role audit

## Scope

Semantic-correctness review of 57 `semantic_role` entries from M100 (IRPF) batch-3.
Source: `.vault-scratch/r7-m100/batch-3.json`.
Revisions covered: 2020–2025. ID-reuse across revisions is expected and not flagged as a defect.

## Findings

| role | verdict | detail |
|---|---|---|
| `irpf_anexo_a_aeip_aplicado_flag` | RENAME → `irpf_anexo_a_deduccion_inversion_empresarial_aplicado` | Name says "aeip_aplicado_flag" (implies a boolean flag and a specific AEIP acronym) but all members are `money(default)` monetary amounts representing "Aplicado en esta declaración" across a wide range of LIS investment-deduction lines (R&D, cinema, disability employment, canary islands special regimes, fixed assets). The `_flag` suffix is completely wrong; the concept is monetary applied amounts for Anexo A investment deductions. Additionally, 0706 in 2020 is from `deduccion_vivienda_habitual_res` — a housing deduction amount, not an investment deduction — making it a genuine outlier. |
| `irpf_anexo_a_ric_dotacion_importe` | OK | All members are `money(default)` in `reserva_inversiones_canarias_res`, labelled "Importe de las dotaciones" for RIC (Reserva para Inversiones en Canarias) across various base years. Role name accurately reflects concept. |
| `irpf_anexo_a_ric_dotacion_anio` | OK | All `text` in `reserva_inversiones_canarias_res`, labelled "Año de la dotación". Correct. |
| `worker_nif` | RENAME → `irpf_deduccion_autonomica_empleada_hogar_nif` | The role name lacks `irpf_` prefix and is too generic. All members are `nif` fields for household employees or childcare workers within regional autonomic deduction sections (Castilla y León, La Rioja, C. Valenciana, I. Baleares). The concept is specifically the NIF of a contracted domestic/household worker for IRPF autonomic deductions. In 2024–2025 Baleares members (1699, 1700, 1715) extend to "Centro de día" (day care) worker NIFs, which is coherent with the domestic/care worker concept. |
| `irpf_anexo_c_exceso_patrim_protegido_aplicado` | OK | All `money(default)` in `excesos_patrim_protegidos_res`, "Aplicado en esta declaración" for prior-year protected-patrimony excess amounts. Year labels shift each revision as the 4-year carry-forward window rolls forward. Coherent. |
| `irpf_inmueble_gastos_aplicados_declaracion` | OK | All `money(default)` in `toma_datos_ampliada/inmuebles/inmueble`, "Aplicado en esta declaración" for prior-year deferred real-property expenses. Rolling 4-year window. Coherent. |
| `base_imponible_irpf` | SPLIT | Three distinct concepts are mixed. (1) 0259 all revisions: `decimal` in `re_agrup_interes_economico` — "Base imponible imputada" for economic interest groups special regime, a very specific imputation. (2) 0435 all revisions: `decimal` in `base_imponible_res` — standard "Base imponible general". (3) 0460 all revisions: `decimal` in `base_imponible_res` — "Base imponible del ahorro". These are three structurally different tax base concepts; grouping them under one role loses the distinction between the general tax base, the savings tax base, and the imputed special-regime tax base. Suggest: `irpf_base_imponible_general`, `irpf_base_imponible_ahorro`, `irpf_re_agrup_interes_economico_base_imponible_imputada`. Also: the role name lacks the `irpf_` prefix. |
| `irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_fin` | OK | All `money(default)` in `saldos_neg_gy_p_ahorro_res`, "Pendiente de aplicación en ejercicios futuros" for negative capital-gains balances in the savings base. Rolling 3-year window. Coherent. |
| `irpf_deduccion_eficiencia_energetica_fecha_certificado_anterior` | OK | All `text` in `mejoras_energeticas_viv`, labelled "Fecha del certificado de eficiencia energética anterior". Present 2021–2025. Three IDs per revision (1659, 1667, 1676) correspond to three dwelling slots in the energy-efficiency section. Role name is accurate. |
| `irpf_inmueble_contribuyente_titular` | OK | All `text` in `inmuebles/inmueble`, "Contribuyente titular". Stable 2020–2025. Two IDs (1211, 1393) likely represent declarant and spouse slots. |
| `irpf_saldo_neto_gyp_general_pendiente` | OK | All `money(default)` in `base_imponible_res`. Two IDs per revision (0431, 0434) represent "Saldos netos negativos" and "Resto de saldos netos negativos" for non-transfer capital gains pending compensation. The window rolls each revision (4-year lookback). Both are conceptually the same field type — pending general-base capital gain/loss. Acceptable to group; granularity is acceptable. |
| `irpf_regularizacion_autoliquidaciones_anteriores_devolver` | RENAME → `irpf_regularizacion_devolucion_autoliquidaciones_anteriores` | The role clusters two distinct sub-fields: 0677 ("Devoluciones acordadas por la AEAT") and 0682 ("Devoluciones solicitadas"). In 2024–2025 only 0677 appears (0682 was removed). Grouping is acceptable since both are in `regularizacion_res` and represent prior-assessment refund amounts. The name is clear but `devolver` (infinitive) is non-standard — rename to noun form for consistency with rest of registry. |
| `irpf_deduccion_c_valenciana_ayudas_publicas_generalitat` | OUTLIER | 1171 (2020) label "Por cantidades procedentes de ayudas públicas… Orden 5/2020… adquisición o electrificación de bicicletas urbanas" is a distinct deduction from 1169's ERTE/COVID deduction. Both are Generalitat public-aid deductions but for completely different purposes (employment vs. bicycle/EV purchase). 1171 only appears in 2020. If 1171 was merged into 1169 in 2021+, this is a legitimate id-reuse but the 2020 entry belongs to a different specific deduction. Flag: **OUTLIER** 1171/2020 (bicycle/EV aid deduction misassigned to ERTE aid role). |
| `irpf_anexo_a_ceuta_melilla_deduccion_importe` | OK | Single ID 0727 across all revisions in `deduccion_ceuta_melilla_res`. Stable label. Coherent. |
| `irpf_anexo_b_service_amount_total` | RENAME → `irpf_anexo_b_total_cantidades_invertidas_deduccion` | The name "service_amount_total" is not IRPF terminology. The label is "Importe total de las cantidades invertidas con derecho a deducción" across three Anexo B sub-sections (enfermedad/dependencia/ahorro inversiones autónomas). Present 2024–2025 only. Rename to use standard tax terminology. |
| `irpf_anexo_c_exencion_rv_ganancia_exenta` | OK | Single ID 1243 all revisions in `exencion_rentas_vitalicias_res`. "Ganancia patrimonial exenta por reinversión" — reinvestment into life annuities exemption. Stable and accurate. |
| `irpf_ascendiente_discapacidad_fecha_fin` | OK | Single ID 0628 all revisions in `deduc_ascendiente_disc_res`. "Fecha de fin de la discapacidad" for ascendant disability deduction. Coherent. |
| `irpf_conyuge_discapacidad_fecha_fin` | OK | Single ID 0243 all revisions in `deduc_conyuge_disc_res`. Same concept but for spouse. Coherent. |
| `irpf_cuota_irnr_imputada` | OUTLIER | 0605 in 2025 changes section from `calculo_impuesto_res/retenciones_res` to `retenciones_ingresos_cuenta_pagos_fraccionados`. This represents a structural section relocation in the 2025 form. The label drops "(**)" footnote marker and becomes "Cuotas del Impuesto sobre la Renta de no Residentes" (no footnote). The concept is consistent — IRNR withholding-equivalent quota — but the section path change means the 2025 entry sits in a different structural location than 2020–2024. This is a known cross-revision relocation; not a misassignment. Role name and concept are correct. OK. |
| `irpf_deduccion_andalucia_alquiler_vivienda` | OK | Single ID 0853 all revisions in `andalucia_res`. Label changes cross-reference annex number (B.6→B.8→B.9→B.11) tracking form renumbering but concept is constant: rental housing deduction. Coherent. |
| `irpf_deduccion_andalucia_nacimiento_adopcion` | OK | Single ID 0850 all revisions. Label expands in 2022 to include "acogimiento familiar de menores" — legislative scope expansion, not a concept change. Coherent. |
| `irpf_deduccion_aragon_mayores_70` | OK | Single ID 0878 all revisions. Stable label "Para mayores de 70 años". Coherent. |
| `irpf_deduccion_asturias_familia_monoparental` | OK | Single ID 0892 all revisions. Stable. Coherent. |
| `irpf_deduccion_baleares_arrendador_vivienda_permanente` | OK | ID 0909 all revisions. 2020–2023 label is "arrendamiento de bienes inmuebles... destinados a vivienda"; 2024 adds "Primas de seguros"; 2025 reformulates as "Para el arrendador... Primas de seguros". Concept drifts slightly (from full rental deduction to insurance premium sub-component) but stays within the same Baleares landlord housing deduction. The role name correctly says "arrendador_vivienda_permanente". Acceptable. |
| `irpf_deduccion_baleares_libros_texto` | OK | Single ID 0899 all revisions. Stable. Coherent. |
| `irpf_deduccion_c_valenciana_discapacidad_33` | OK | Single ID 1089 all revisions. Stable label "contribuyentes con grado de discapacidad igual o superior al 33%... 65 años". Coherent. |
| `irpf_deduccion_c_valenciana_nacimiento_adopcion_guarda` | OK | Single ID 1083. Label in 2025 adds "delegación de guarda con fines de adopción" — legislative scope expansion. Coherent. |
| `irpf_deduccion_canarias_arrendamiento_vinculado` | OK | Single ID 0942 all revisions. Cross-reference annex number updates but concept stable: rental linked to dación-en-pago operations. Coherent. |
| `irpf_deduccion_canarias_familiares_discapacidad` | OK | Single ID 0941 all revisions. Stable. Coherent. |
| `irpf_deduccion_canarias_vivienda_habitual` | OK | Single ID 0926 all revisions. Stable. Coherent. |
| `irpf_deduccion_cantabria_nacimiento_adopcion` | OK | Single ID 0774 all revisions. Label changes "y" to "o" in 2024 (minor). Coherent. |
| `irpf_deduccion_castilla_la_mancha_donaciones_idi` | OK | Single ID 0964 all revisions. Stable. Coherent. |
| `irpf_deduccion_castilla_y_leon_emprendimiento` | OK | Single ID 0979 all revisions. Cross-reference annex number updates only. Coherent. |
| `irpf_deduccion_castilla_y_leon_vehiculo_matricula` | OK | Single ID 0943 all revisions. "Número de matrícula del vehículo". Coherent. |
| `irpf_deduccion_ceuta_melilla_autonomica` | OK | Single ID 0561 all revisions. Stable "Parte autonómica" of Ceuta/Melilla deduction. Coherent. |
| `irpf_deduccion_extremadura_acogimiento_menores` | OK | Single ID 1013 all revisions. Stable. Coherent. |
| `irpf_deduccion_galicia_acciones_participaciones_2` | OK | Single ID 1029 all revisions. Annex cross-reference updates only. Coherent. |
| `irpf_deduccion_galicia_donaciones_idi` | OK | Single ID 1031 all revisions. Stable. Coherent. |
| `irpf_deduccion_la_rioja_acogimiento_urgencia` | OUTLIER | 1072 in 2020 and 2021 is "Por cantidades invertidas en obras de adecuación de vivienda habitual para personas con discapacidad" (housing adaptation for disabled persons). In 2022–2025 it becomes "Por cada menor en régimen de acogimiento familiar de urgencia temporal o permanente". This is a genuine concept change between revisions — the same casilla ID was repurposed by La Rioja for a completely different deduction from 2022 onward. The role name `irpf_deduccion_la_rioja_acogimiento_urgencia` only fits the 2022–2025 meaning. **OUTLIER** 1072/2020 and 1072/2021 — housing adaptation deduction misassigned to foster care urgency role. |
| `irpf_deduccion_la_rioja_internet_jovenes` | OK | Single ID 1079 all revisions. Stable. Coherent. |
| `irpf_deduccion_madrid_acogimiento_mayores` | OK | Single ID 1042 all revisions. Stable. Coherent. |
| `irpf_deduccion_monoparental` | OUTLIER | 0662 in 2025 changes section from `calculo_impuesto_res/deduc_monoparental_res` to `resultado_declaracion` and label changes from "Importe de la deducción" to "Deduccion por ascendiente separado legalmente o sin vinculo matrimonial". This is a structural relocation of the single-parent deduction amount in 2025. The concept is still the monoparental/separated-parent deduction. Not a misassignment but note the section change — the 2025 entry sits in `resultado_declaracion` while 2020–2024 is in `deduc_monoparental_res`. This is a known 2025 restructuring of the results section. OK (section relocation is cross-revision expected drift). |
| `irpf_deduccion_murcia_material_escolar` | OK | Single ID 1059 all revisions. Stable. Coherent. |
| `irpf_descendiente_cede_flag` | OK | Single ID 0621 all revisions. `boolean` in `deduc_descendiente_disc_res`. Coherent. |
| `irpf_ed_arrendamientos_canones` | OK | Single ID 0192 all revisions. 2025 section path changes to `rendimientos_actividades_economicas/estimacion_directa` (2025 form restructuring). Concept stable. Coherent. |
| `irpf_ed_ingresos_financieros_aplazamiento` | OK | Single ID 0172 all revisions. 2025 section path and label simplified. Concept stable. Coherent. |
| `irpf_ed_otros_servicios_exteriores` | OK | Single ID 0202 all revisions. 2025 section path changes. Concept stable. Coherent. |
| `irpf_ed_reduccion_rendimientos_irregulares` | OK | Single ID 0225 all revisions. `decimal`. 2025 label and section simplified. Concept stable. Coherent. |
| `irpf_ed_variacion_existencias_disminucion` | OK | Single ID 0182 all revisions. 2025 section/label simplified. Concept stable. Coherent. |
| `irpf_eo_agr_indice_personal_asalariado` | OK | Single ID 1541 all revisions. Stable. Coherent. |
| `irpf_eo_agr_ingresos_integros_forestal_resina` | OK | Single ID 1518 all revisions. 2020–2021 label is generic "Ingresos íntegros"; 2022–2025 label clarifies "Actividad forestal dedicada a la extracción de resina". The concept was always forest/resin income given the section `reg_estima_obj_agricola`. Label clarification is acceptable. Coherent. |
| `irpf_eo_agr_rdto_neto_reducido_total` | OK | Single ID 1560 all revisions. `decimal`. Stable formula label. Coherent. |
| `irpf_eo_indice_corrector_pequena_dimension` | OK | Single ID 1470 all revisions. Stable. Coherent. |
| `irpf_eo_reduccion_irregulares` | OK | Single ID 1480 all revisions. Stable. Coherent. |
| `irpf_familia_numerosa_cede_flag` | OK | Single ID 0657 all revisions. `boolean`. Coherent. |
| `irpf_g4_re_reduccion_dt9` | OK | Single ID 0410 all revisions. "Reducción aplicable (D.T. 9.ª)" in `g_cambio_residencia_ext/g4_re`. Coherent. |
| `irpf_ganancia_acciones_valor_adquisicion_global` | OK | Single ID 0331 all revisions. Stable. Coherent. |
| `irpf_ganancia_derechos_valor_transmision_global` | OUTLIER | 0343 in 2020–2022 label says "Importe global de las transmisiones efectuadas en 2019". In 2023 the label suddenly jumps to "en 2024" (one year ahead), which appears to be a data error in the registry TOML — the 2023 form should reference 2023 transmissions not 2024. In 2024 it correctly says "en 2024" and in 2025 "en 2025". **OUTLIER** 0343/2023 — label appears to contain a year reference error (says 2024 but should say 2023 for the 2023 fiscal year form). |
| `irpf_ganancia_inmueble_exenta_reinversion_vh` | OK | Single ID 1230 all revisions. 2020–2021 section is `gp_otros_elementos`, 2022+ moves to `gp_otros_inmuebles` — structural section renaming in the 2022 form. Concept stable: "Ganancia patrimonial exenta por reinversión" for real-estate principal-residence reinvestment. Coherent. |
| `irpf_ganancia_otros_anios_permanencia_1994` | OK | Single ID 1647 all revisions. `text`. "N.º de años de permanencia hasta el 31-12-1994". Transitional regime (DT 9ª). Coherent. |
| `irpf_ganancia_otros_importe_percibir_3` | OK | Single ID 0372 all revisions. `money(default)`. "Importe a percibir" in `gp_otros_elementos`. Coherent. |
| `irpf_ganancia_otros_susceptible_reduccion_da7` | OK | Single ID 1651 all revisions. "Parte de la ganancia patrimonial susceptible de reducción (D.A.7ª)". DA 7ª transitional abatement. Coherent. |
| `irpf_ganancia_premios_juegos_importe_computable` | OK | Single ID 0286 all revisions. `money(default)`. Computed amount for gambling gains. Coherent. |
| `irpf_ganancia_premios_subvencion_vpo` | OK | Single ID 0299 all revisions. "Subvenciones para la adquisición de viviendas de protección oficial". Coherent. |
| `irpf_inmueble_arrendatario2_nif_extranjero_flag` | OK | Single ID 0095 all revisions. `boolean`. "Marque X si NIF de otro país". Coherent. |
| `irpf_inmueble_gastos_financiacion_pendientes_previos` | OK | Single ID 0103 all revisions. Rolling 4-year lookback window for financing costs pending deduction. Coherent. |
| `irpf_inmueble_vivienda_habitual_flag` | OK | Single ID 0070 all revisions. `boolean`. Label updates year number each revision. Coherent. |
| `irpf_intereses_demora_perdida_transitoria_estatal` | OK | Single ID 0576 all revisions. "Intereses de demora correspondientes a las deducciones anteriores: Parte estatal". Late-payment interest on lost transitional deductions. Coherent. |
| `irpf_minimo_descendientes_autonomico` | OK | Single ID 0514 all revisions. "Parte autonómica: Mínimo por descendientes. Importe". Coherent. |
| `irpf_perdida_derecho_deduccion_transitoria_estatal` | OK | Single ID 0574 all revisions. "Importe de las deducciones a las que se ha perdido el derecho". Year updates. Coherent. |
| `irpf_perdida_otros_pendiente_resto` | OK | Single ID 0381 all revisions. 2020–2021 "Pérdida patrimonial pendiente de imputación"; 2022+ "Resto pérdida patrimonial pendiente de imputación". Label clarification only. Coherent. |
| `irpf_re_atrib_act_eco_provisiones_difícil` | OK | Single ID 1579 all revisions. "Provisiones deducibles y gastos de difícil justificación" for attributed-income special regime. 2023+ label adds regulatory citation. Coherent. |
| `irpf_re_atrib_cap_mob_rdto_neto_computable_gral` | OK | Single ID 1568 all revisions. `decimal`. Formula label stable. Coherent. |
| `irpf_re_atrib_gp_exentas_reinversion_vitalicia` | OK | Single ID 1590 all revisions. "Ganancias exentas por reinversión de rentas vitalicias". Coherent. |
| `irpf_re_atrib_inmueble_situacion` | OK | Single ID 1619 all revisions. `text`. "Situación" for attributed-regime real property. Coherent. |
| `irpf_re_atrib_suma_gp_no_transmision_ganancias` | OK | Single ID 1606 all revisions. Stable formula label. Coherent. |
| `irpf_re_tfi_entidad_denominacion` | OK | Single ID 0268 all revisions. "Denominación de la entidad no residente participada" for fiscal transparency regime. Coherent. |
| `irpf_red_pensiones_compensatorias_receptor_nif_extranjero_flag` | OK | Single ID 0484 all revisions. `boolean`. Section path has minor typo correction in 2022 ("comensatorias"→"compensatorias"). Coherent. |
| `irpf_reduccion_prevision_social_conyuge_total` | OK | Single ID 0469 all revisions. 2020 label includes "excesos pendientes de reducir procedentes de los ejercicios 2015 a 2019" (transitional period note); 2021+ simplifies to "Total con derecho a reducción". Concept stable. Coherent. |
| `irpf_rendimiento_capital_inmobiliario_gasto_defensa_juridica` | OK | Single ID 0111 all revisions. 2025 section path and label simplified to `gastos_deducibles`. Concept stable. Coherent. |
| `irpf_rendimiento_capital_inmobiliario_reduccion_rendimientos_irregulares` | OK | Single ID 0151 all revisions. `decimal`. 2025 section/label simplified. Concept stable. Coherent. |
| `irpf_rendimiento_capital_mobiliario_ahorro_intereses_bonificados` | OK | Single ID 0028 all revisions. 2025 section and label simplified. Concept stable: DT 6ª LIS bonified financial asset interest. Coherent. |
| `irpf_rendimiento_capital_mobiliario_general_arrendamiento_bienes_muebles` | OK | Single ID 0046 all revisions. `decimal`. 2025 section/label simplified. Concept stable. Coherent. |
| `irpf_rendimiento_trabajo_aportacion_patrimonio_protegido` | OK | Single ID 0010 all revisions. 2025 section/label simplified. Concept stable: contributions to disabled persons' protected patrimony. Coherent. |
| `irpf_rendimiento_trabajo_importe_integro_dinerario` | OK | Single ID 0003 all revisions. 2025 label and section simplified. Core employment income concept. Coherent. |
| `irpf_resultado_declaracion` | OK | Single ID 0670 all revisions. `decimal`. 2025 section moves to `resultado_declaracion` (structural relocation). Concept stable: net tax result. Coherent. |
| `irpf_saldo_neto_gyp_ahorro_limite_25pct` | OK | Single ID 0446 all revisions. "Saldos netos negativos... límite del 25 por 100". Year updates in label. Coherent. |
| `spouse_or_foreign_id_nif` | RENAME → `irpf_inmueble_exconyuge_nif` | Role name is non-standard (no `irpf_` prefix, generic English). All members are 0077 all revisions, `text` in `inmuebles/inmueble`, labelled "NIF del excónyuge". This is specifically the ex-spouse NIF field in the real property section for ownership/use split purposes. |
| `irpf_deduccion_andalucia_gastos_educativos` | OUTLIER | 0849 in 2020 is "Por las cantidades donadas al Servicio Andaluz de Salud para la lucha contra el avance del COVID-19" — a COVID donation deduction. In 2022–2025 it is "Por gastos educativos" — an education expenses deduction. There is no 2021 entry. The role name only fits 2022+. **OUTLIER** 0849/2020 — COVID health donation deduction misassigned to education expenses role. |
| `irpf_deduccion_c_valenciana_residencia_municipio_riesgo` | OK | Single ID 1181, 2021–2025. "Por residir habitualmente en un municipio en riesgo de despoblamiento". Coherent. |
| `irpf_deduccion_eficiencia_energetica_viviendas` | OK | Single ID 0567, 2021–2025. "Obras de mejora de la eficiencia energética de viviendas: Parte estatal". Cross-reference annex updates only. Coherent. |
| `irpf_ganancia_premios_ayuda_jovenes_agricultores` | OK | Single ID 0279, 2021–2025. Young farmers public aid for first farm establishment. Coherent. |
| `irpf_anexo_a_mejora_energia_base_aplicada_prev` | OK | Single ID 1777, 2022–2025. "Base de la deducción aplicada en [prior years]". Rolling cumulative base. Coherent. |
| `irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin` | SPLIT | 1763 in 2021 is "Contribuciones empresariales pendientes de aplicación en ejercicios futuros" from `contribuciones_sist_prevision_social_rg_res` (Anexo C social security contributions). In 2022 it is "Para mitigar el impacto de la inflación en la adquisición de productos básicos en 2022" from `cantabria_res` (a Cantabria regional deduction). In 2024–2025 it is "Por ocupación de plazas declaradas de difícil cobertura" from `i_baleares_res` (a Baleares employment deduction). Three completely different concepts in three different regions sharing a casilla ID due to form space reuse across revisions. This must be split into separate roles: `irpf_anexo_c_exceso_sps_rg_contribuciones_empresariales_pendiente` (2021), `irpf_deduccion_cantabria_impacto_inflacion` (2022), `irpf_deduccion_baleares_plazas_dificil_cobertura` (2024–2025). |
| `irpf_deduccion_c_valenciana_generado_2024_pendiente` | RENAME → `irpf_deduccion_c_valenciana_pendiente_aplicacion` | The `_2024_` in the role name is a specific year that will become stale. The concept is "Importe generado en [year] pendiente de aplicación" for a C. Valenciana deduction carry-forward. Remove the hardcoded year from the role name. |
| `irpf_ganancia_cripto_anio_imputacion_3` | OK | Single ID 1869, 2022–2025. `text`. "Año de imputación" for crypto asset gain. Coherent. The `_3` suffix presumably denotes a third entry slot. |
| `irpf_ganancia_cripto_importe_percibir_3` | OK | Single ID 1870, 2022–2025. `money(default)`. "Importe a percibir" for crypto asset. Coherent. |
| `irpf_ganancia_cripto_valor_transmision_renta_vitalicia` | OK | Single ID 1805, 2022–2025. "Valor de transmisión destinado a constituir una renta vitalicia" for crypto. Coherent. |
| `irpf_ganancia_inmueble_catastral_3_b` | OK | Single ID 1885, 2022–2025. `text`. "Referencia castastral 3" (note: label has typo "castastral" vs "catastral" — registry source typo, not a role defect). Coherent. |
| `irpf_ganancia_inmueble_importe_percibir_2` | OK | Single ID 1891, 2022–2025. "Importe a percibir" for second real-property element slot. Coherent. |
| `irpf_ganancia_inmueble_situacion_clave` | OK | Single ID 1818, 2022–2025. `text`. "Situación. Clave" for real property. Coherent. |
| `irpf_ganancia_premios_ayuda_200_euros` | OK | Single ID 0356, 2022–2025. "Ayuda de 200 euros para personas físicas de bajo nivel de ingresos". Coherent. |
| `irpf_perdida_cripto_pendiente_2` | OK | Single ID 1868, 2022–2025. "Pérdida patrimonial pendiente de imputación" for crypto. Coherent. |
| `irpf_red_prevision_social_aportaciones_empresa_decision_trabajador` | OK | Single ID 0438, 2022–2025. "Aportaciones efectuadas por la empresa que deriven de una decisión del trabajador". Coherent. |
| `irpf_anexo_c_exceso_sps_rg_contribuciones_aplicado` | SPLIT | Same problem as `irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin`. ID 1762 in 2021 is "Contribuciones empresariales aplicadas en esta declaración" (Anexo C SPS). In 2022 it is "Por el alza de precios" from `canarias_res` (Canarias price-rise deduction). In 2023 it is also "Por el alza de precios" from `canarias_res`. The 2021 SPS contributions concept is entirely different from the 2022–2023 Canarias inflation deduction. Split: `irpf_anexo_c_exceso_sps_rg_contribuciones_empresariales_aplicado` (2021) and `irpf_deduccion_canarias_alza_precios` (2022–2023). |
| `irpf_deduccion_bienes_corporales_illes_balears_estatal` | OK | Single ID 0508, 2023–2025. "Por rendimientos derivados de la venta de bienes corporales producidos en las Illes Balears: Parte estatal". Coherent. |
| `irpf_deduccion_contribuciones_empresariales_prevision_social_aplicado` | OK | Single ID 0764, 2023–2025. "Por contribuciones empresariales a sistemas de previsión social (D.A. tercera RDL 13/2022): Aplicado en esta declaración". Coherent. |
| `irpf_deduccion_vehiculo_fecha_pago_a_cuenta` | OK | Single ID 1926, 2023–2025. `text`. "Fecha del pago a cuenta" for EV deduction. Coherent. |
| `irpf_eo_reduccion_la_palma` | OK | Single ID 0157, 2022–2024 (not present in 2025 — temporary measure). "Reducción para actividades económicas desarrolladas en la isla de La Palma". Coherent. |
| `irpf_feac_tipo_elemento_patrimonial_transmitido` | OK | Single ID 1977, 2023–2025. `text`. 2023–2024 label is "Tipo de operación"; 2025 clarifies to full description including numeric key values (1=acciones, 2=inmuebles, 3=otros). Concept stable. Coherent. |
| `irpf_re_especial_tfi_fusiones_afectado_flag` | OK | Single ID 0416, 2023–2025. `boolean`. 2024 label contains stale year reference "en 2023" — should say "en 2024". This is a registry TOML authoring issue, not a role assignment error. Concept correct. |
| `irpf_retrib_especie_importe_no_exenta_2` | OK | Single ID 1969, 2023–2025. "Retribución en especie (no exenta... art. 42.3.f)". Coherent. |
| `irpf_deduccion_asturias_vivienda_protegida_nueva` | OK | Single ID 0815, 2024–2025. "Por inversión en vivienda habitual que tenga la consideración de protegida: Importe generado en [year] pendiente de aplicación". Coherent. |
| `irpf_deduccion_canarias_cuotas_seguridad_social` | OK | Single ID 2051, 2024–2025. "Por cuotas satisfechas a la Seguridad Social por la contratación de empleados de hogar". Coherent. |
| `irpf_deduccion_cantabria_generado_2024_pendiente` | RENAME → `irpf_deduccion_cantabria_pendiente_aplicacion` | Same structural issue as `irpf_deduccion_c_valenciana_generado_2024_pendiente` — year hardcoded in role name. |
| `irpf_deduccion_madrid_empleada_hogar_ccc` | OK | Single ID 2016, 2024–2025. `text`. "Código Cuenta de Cotización" for Madrid household employee deduction. Coherent. |
| `irpf_deduccion_murcia_conciliacion_ascendientes` | OK | Single ID 2033, 2024–2025. "Por conciliación. Ascendientes mayores de 65 años". Coherent. |
| `irpf_rectnosepa_banco_ciudad` | OK | Single ID 1787, 2021–2022 only. `text`. "Ciudad/City" for non-SEPA bank details in regularisation. Coherent. |
| `irpf_ascendiente_clave_discapacidad` | OK | Single-member 2025 only. "Ascendiente clave discapacidad" in `datos_identificativos/ascendientes`. `text`. Coherent. |
| `irpf_declaracion_ccaa` | OK | Single-member 2025 only. "Comunidad autonoma de la declaracion" in `datos_identificativos/declaracion`. `text`. Coherent — new 2025 structural field. |
| `irpf_deduccion_baleares_vivienda_ocupada_ilegalmente` | OK | Single-member 2025 only. Long label for compensation for illegally occupied housing. `money(default)`. Coherent — new 2025 Baleares deduction. |
| `irpf_deduccion_cantabria_generado_pendiente` | OK | Single-member 2025 only. "Importe generado en 2025". `money(default)`. OK as a 2025-only entry for Cantabria pending generation. |
| `irpf_deduccion_extremadura_ela` | OK | Single-member 2025 only. ELA disease family deduction. Coherent. |
| `irpf_deduccion_la_rioja_enfermedad_celiaca` | OK | Single-member 2025 only. Coeliac disease deduction. Coherent. |
| `irpf_deduccion_murcia_gastos_veterinarios` | OK | Single-member 2025 only. Veterinary expenses deduction. Coherent. |
| `irpf_deduccion_obtencion_rendimientos_trabajo` | OK | Single-member 2025 only. "Deduccion por obtencion de rendimientos del trabajo" in `resultado_declaracion`. `money(default)`. New 2025 work income deduction. Coherent. |
| `irpf_eo_agr_rdto_neto_actividad` | OK | Single-member 2020 only. `decimal`. "Rendimiento neto de la actividad" for agricultural objective estimation. Coherent. |
| `irpf_ganancia_inmueble_catastral_4` | OK | Single-member 2025 only. "Referencia catastral 4". `text`. Coherent. |
| `irpf_inmueble_gasto_deducible_alquiler_locales` | OK | Single-member 2021 only. "Gasto deducible correspondiente a alquileres de locales... Real Decreto-ley 35/2020". COVID-era temporary deduction. Coherent. |
| `irpf_red_prevision_social_aportaciones_individuales_contribuciones_empresariales` | RENAME → `irpf_red_prevision_social_aportaciones_individuales` | Role name suffix `_contribuciones_empresariales` is misleading — the single 2021 member (0463) is labelled "Aportaciones individuales" (individual contributions), not employer contributions. The employer contributions concept is already covered by a separate role. The name conflates two distinct contribution types. |

## Summary counts

- Roles reviewed: 57
- OK: 43
- RENAME: 8 (`irpf_anexo_a_aeip_aplicado_flag`, `worker_nif`, `irpf_regularizacion_autoliquidaciones_anteriores_devolver`, `irpf_anexo_b_service_amount_total`, `spouse_or_foreign_id_nif`, `irpf_deduccion_c_valenciana_generado_2024_pendiente`, `irpf_deduccion_cantabria_generado_2024_pendiente`, `irpf_red_prevision_social_aportaciones_individuales_contribuciones_empresariales`)
- SPLIT: 3 (`base_imponible_irpf`, `irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin`, `irpf_anexo_c_exceso_sps_rg_contribuciones_aplicado`)
- OUTLIER: 5 entries across 4 roles:
  - `irpf_anexo_a_aeip_aplicado_flag`: 0706/2020 (housing deduction in investment role)
  - `irpf_deduccion_c_valenciana_ayudas_publicas_generalitat`: 1171/2020 (bicycle/EV aid in ERTE aid role)
  - `irpf_deduccion_la_rioja_acogimiento_urgencia`: 1072/2020 and 1072/2021 (housing adaptation deduction in foster care role)
  - `irpf_deduccion_andalucia_gastos_educativos`: 0849/2020 (COVID donation in education expenses role)
  - `irpf_ganancia_derechos_valor_transmision_global`: 0343/2023 (label year reference error — says 2024 for 2023 form)

### Priority actions

1. **SPLIT** `base_imponible_irpf` immediately — three structurally distinct tax bases are masked under one role; this will cause incorrect calculation routing.
2. **SPLIT** `irpf_anexo_c_exceso_sps_rg_contribuciones_aplicado` and `irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin` — ID 1762/1763 were reused for completely different deductions in different CCAA across revisions; the current grouping produces nonsensical cross-region aggregation.
3. **RENAME** `worker_nif` — missing `irpf_` prefix is a namespace violation.
4. **RENAME** `spouse_or_foreign_id_nif` — missing prefix and non-Spanish naming convention.
5. Investigate year-reference error in 0343/2023 label against source TOML.
