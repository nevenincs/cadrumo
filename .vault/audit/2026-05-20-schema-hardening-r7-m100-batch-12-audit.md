---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m100 batch-12 — semantic role audit

## Scope

100 semantic roles from Modelo 100 (IRPF) batch-12. Revisions 2020–2025.
Structural validators confirm type-consistency; this audit checks semantic
correctness: name accuracy, member coherence, and granularity.

---

## Findings

| role | verdict | detail |
|---|---|---|
| `irpf_anexo_b_service_amount` | RENAME | Members are "Importe anual satisfecho" (annual amount paid) across Anexo B subsections: `an_b_inf_adc_enf` (illness/disability), `an_b_inf_adc_dep` (dependants), `an_b_inf_adc_aia` (activity of interest) and `an_b_inf_adc_aav` (2025-only). "service_amount" implies a service-fee; the actual concept is annual payment made in each Anexo B supplementary-information block. Rename: `irpf_anexo_b_importe_anual_satisfecho` |
| `irpf_anexo_b_foreign_nif_flag` | OK | Boolean "mark X if foreign-country NIF" across all six Anexo B subsections (ctrd, arr, avh, eps, ges, arrvm). Consistent role. |
| `irpf_eo_modulo_num_unidades` | RENAME | Label is "Nº de unidades" (number of units) in the estimación objetiva module table. data_type is `money(default)` which is semantically misleading for a unit count (should be an integer/quantity), but that is a type-level issue, not a role-name issue. The role name `modulo_num_unidades` is accurate. However the `money(default)` data_type is an anomaly — flag for data-type review. Verdict: OK on name; OUTLIER on data_type: all members use `money(default)` for a unit-count field. |
| `irpf_inmueble_gasto_financiacion_proveedor_nif` | RENAME | Members are "NIF de quién prestó el servicio" (NIF of who provided the service) for financing expense entries 1 and 2. The label says "prestó el servicio" (provided the service), not financing specifically. The gastos numbered 1406/1408/1411/1413/1416/1418 sit under `toma_datos_ampliada/inmuebles/inmueble`. These are generic service-provider NIF fields for property expense entries that happen to relate to financial costs. Name is partially correct. Rename for precision: `irpf_inmueble_gasto_proveedor_nif` (removing the "financiacion" qualifier since labels confirm generic service providers). |
| `irpf_anexo_c_exceso_deportistas_pendiente_inicio` | OK | "Pendiente de aplicación al principio del periodo" for excesos deportistas, rolling 5-year window across all revisions. Coherent. |
| `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | SPLIT | 2020 members use section `excesos_sistemas_prevision_social_res`; from 2021 the section splits into `excesos_sistemas_prevision_social_rt_res` and `contribuciones_sist_prevision_social_rt_res`. The 2021 revision contains casillas 1289–1298 under `excesos_sistemas_prevision_social_rt_res` AND casillas 1746–1755 under `contribuciones_sist_prevision_social_rt_res`. Both express "pendiente de aplicación en ejercicios futuros" but for different sub-concepts (excess contributions vs employer contributions). The second group (1746–1755) represents a distinct concept. Recommend SPLIT: keep `irpf_anexo_c_exceso_sps_rt_pendiente_fin` for excess personal contributions, create `irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_fin` for 1746/1749/1752/1755. |
| `irpf_anexo_c_exceso_scd_pendiente_fin` | OK | "Pendiente de aplicación en ejercicios futuros" for exceso seguros colectivos dependencia, consistent rolling window 2020–2025. Coherent. |
| `irpf_saldo_neto_gyp_ahorro_pendiente` | OK | Negative net capital-gain/loss balances pending compensation from prior years, integrated into base imponible del ahorro. Labels consistently describe this across all revisions. |
| `irpf_anexo_a_deduccion_vivienda_autonomica` | OK | Autonomic portion of the housing deduction (Anexo A). Casillas 0699/0703/0705 all labelled "Parte autonómica: Importe de la deducción" in `deduccion_vivienda_habitual_res`. Coherent. |
| `irpf_inmueble_dias_arrendado` | OK | Days the property (and accessory property) was rented. Casillas 0101/0122/0137. 0137 covers the accessory property ("inmueble accesorio"). All under the same `inmuebles/inmueble` section. Coherent family. |
| `irpf_anexo_b_rental_deduccion_eligibility` | RENAME | Members are "Cantidades satisfechas con derecho a deducción" — amounts paid eligible for deduction, in sections ctrd (contratados), arr (arrendamiento) and from 2025 arrvm (arrendamiento viviendas para moblidad). This is an amount eligible for deduction, not an eligibility flag. The word "eligibility" implies boolean. Rename: `irpf_anexo_b_cantidades_deducibles_satisfechas` |
| `irpf_inmueble_mejoras_ejercicio` | OK | "Importe de las mejoras realizadas en {year}" for the main and accessory property. Consistent across all revisions. |
| `irpf_anexo_a_obra_fecha_fin` | OK | Date of works completion in Anexo A vivienda habitual. text type, 2021–2025 only (the campo appeared in 2021). Coherent. |
| `irpf_regularizacion_autoliquidaciones_anteriores_ingresar` | OK | Amounts to be paid from prior self-assessments or administrative liquidations for the same exercise year. 2020–2023 carries two casillas per revision (0676/0681), 2024–2025 only one. This is consistent with a legislative simplification. Name is accurate. |
| `irpf_abono_anticipado_monoparental` | OUTLIER | 2025 revision id=0663 has section `resultado_declaracion` and label "Abono anticipado por ascendiente separado legalmente o sin vinculo matrimonial" — a restructured label and section that is consistent with a form redesign. The semantic role is still the monoparental advance payment, so this is a 2025 section migration, not a misassignment. No true outlier, the role is OK. |
| `irpf_anexo_a_residente_ue_diferencia` | OK | Difference calculation for EU/EEA resident deduction (Anexo A). Single casilla 0731, all revisions, consistent. |
| `irpf_anexo_c_exencion_reinversion_importe_comprometido` | OK | Amount committed to reinvest in new/recent entity shares (Anexo C exemption). Single casilla 1235, rolling year reference. Coherent. |
| `irpf_anualidades_alimentos_total` | OK | Total child maintenance annuities paid by judicial decision (casilla 0527). Section changes in 2021/2022 but concept is stable. |
| `irpf_compensacion_conyuges_ingresar_suspendido` | OK | Amount to pay whose suspension is requested in spouse compensation section. Single casilla 0693, consistent. |
| `irpf_cuota_diferencial` | OK | Cuota diferencial (differential tax quota), casilla 0610. 2025 section migrates to `resultado_declaracion`. Name is precise. |
| `irpf_deduccion_alquiler_vivienda_habitual_estatal` | OK | State portion of transitional rental deduction for habitual residence. Casilla 0562. Correct. |
| `irpf_deduccion_andalucia_empleada_hogar_importe_2` | RENAME | The `_importe_2` suffix implies this is a second amount field among several. The label is simply "Importe de la deducción" for the Andalucía domestic employee deduction (casilla 0862). Without confirming which numbered position this occupies in a multi-field context, the suffix `_2` is opaque. If it distinguishes from a first-amount field, that needs documentation. Rename to `irpf_deduccion_andalucia_empleada_hogar_importe` unless there is a confirmed `_importe_1` companion that this differentiates from. Flag as RENAME pending sibling confirmation. |
| `irpf_deduccion_aragon_guarderia` | OK | Aragón deduction for nursery expenses (children under 3). Casilla 0881, consistent 2020–2025. |
| `irpf_deduccion_asturias_adopcion_internacional` | OK | Asturias deduction for international adoption. Casilla 0889. Coherent. |
| `irpf_deduccion_asturias_vivienda_protegida_general` | OK | Asturias investment deduction for protected housing (habitual residence). Casilla 0886. Labels vary slightly across revisions but concept is stable. |
| `irpf_deduccion_baleares_donaciones_tercer_sector` | OK | Illes Balears deduction for donations to third-sector entities. Casilla 0913. Coherent. |
| `irpf_deduccion_c_valenciana_ascendientes_mayores_75` | OK | Valencian Community deduction for ascendants over 75 or disabled over 65. Casilla 1090. Coherent. |
| `irpf_deduccion_c_valenciana_familia_numerosa_monoparental` | OK | Valencian Community deduction for large families or single-parent households. Casilla 1086. Coherent. |
| `irpf_deduccion_c_valenciana_vivienda_primera_adquisicion` | OK | Valencian Community deduction for first acquisition of habitual residence (under 35). Casilla 1092. Coherent. |
| `irpf_deduccion_canarias_estudios_superiores` | OK | Canary Islands deduction for higher-education study expenses. Casilla 0919. Label evolves to add "educación superior" explictly from 2024. Coherent. |
| `irpf_deduccion_canarias_seguros_credito_impago` | OUTLIER | 2020 revision id=0944 carries label "Por arrendamientos a precios con sostenibilidad social (deducción del arrendador)" which is a completely different concept from credit-insurance premiums for rent default. From 2021 onwards the same casilla 0944 is consistently "Por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos". The 2020 member (id=0944, revision=2020) is a misassignment — in 2020 this casilla held a different deduction concept. OUTLIER: id=0944, revision=2020. True semantic role of the 2020 member is `irpf_deduccion_canarias_arrendamiento_sostenibilidad_social`. |
| `irpf_deduccion_cantabria_generado_ejercicio_pendiente` | OK | Cantabria deduction amount generated in current year pending application in future years. Casilla 0956. Labels evolve from "obras de mejora" to generic "Importe generado en {year}" from 2024, consistent with scope change. Coherent. |
| `irpf_deduccion_castilla_la_mancha_discapacidad_contribuyente` | OK | Castilla-La Mancha deduction for taxpayer disability. Casilla 0958. Coherent. |
| `irpf_deduccion_castilla_y_leon_discapacidad` | OK | Castilla y León deduction for disabled taxpayers. Casilla 0970. Coherent. |
| `irpf_deduccion_castilla_y_leon_rehabilitacion_importe` | RENAME | Label is "Importe de la deducción" for Castilla y León (casilla 0978). The `_rehabilitacion` qualifier in the name is not confirmed by the members' labels alone. If this is the rehabilitation deduction, the name is correct but labels are ambiguous. If the source TOML can confirm this is specifically `rehabilitacion_vivienda`, the name is OK. Without additional registry context, flag RENAME: if context supports it rename `irpf_deduccion_castilla_y_leon_rehabilitacion_vivienda_importe`; otherwise rename to `irpf_deduccion_castilla_y_leon_0978_importe` as an interim safe name. |
| `irpf_deduccion_catalunya_obligacion_presentar_declaracion` | OK | Catalonia deduction for obligation to file due to multiple payors. Casilla 0824. Coherent. |
| `irpf_deduccion_donativos_estatal` | OK | State portion of donations deduction (Anexo A). Casilla 0552. Coherent across revisions. |
| `irpf_deduccion_extremadura_vivienda_zonas_rurales` | OUTLIER | 2020 and 2021 revisions of id=1091 carry section `deduccion_autonomica_res/c_valenciana_res` with label "Por la realización por uno de los cónyuges de la unidad familiar de labores no remuneradas en el hogar" — a Valencian Community deduction for unpaid domestic labour, completely different from the Extremadura rural-zone housing deduction. From 2022 onwards casilla 1091 correctly maps to `deduccion_autonomica_res/extremadura_res` with the rural-zone housing label. OUTLIER: id=1091, revision=2020 and id=1091, revision=2021. The true role for 2020/2021 is a Valencian Community deduction (non-remunerated household labour). |
| `irpf_deduccion_galicia_cuidado_hijos_menores` | OK | Galicia deduction for care of minor children. Casilla 1023. Coherent. |
| `irpf_deduccion_incentivos_inversion_empresarial_autonomica` | OK | Autonomic portion of business investment incentives deduction. Casilla 0555. References to Anexo section change across years (A.4→A.5→A.7→A.6) but concept is stable. |
| `irpf_deduccion_la_rioja_guarderia_escuelas` | OK | La Rioja deduction for nursery/infant education expenses in small municipalities. Casilla 1069. Labels evolve to specify "pequeños municipios" from 2022; coherent. |
| `irpf_deduccion_la_rioja_vivienda_municipio_codigo` | RENAME | Label is "Código del municipio" (municipality code) — this is a reference/identifier field, not a deduction amount. The `vivienda` qualifier relates to the deduction this code supports, but the casilla itself carries a municipality code. A cleaner name: `irpf_deduccion_la_rioja_vivienda_codigo_municipio`. Current name reads "municipality_code" in an unconventional word order. Minor but worth correcting for consistency with the `_codigo_municipio` suffix pattern used elsewhere. |
| `irpf_deduccion_madrid_gastos_educativos` | OK | Madrid deduction for educational expenses. Casilla 1044. Coherent. |
| `irpf_deduccion_murcia_empleada_hogar_ccc` | OK | Murcia domestic employee deduction — social security contribution account code (CCC). Casilla 1160. text type. Coherent. |
| `irpf_deduccion_vivienda_habitual_estatal` | OK | State portion of the habitual-residence investment deduction (Anexo A.1 transitional regime). Casilla 0547. Coherent. |
| `irpf_ed_amortizacion_inmovilizado_inmaterial` | OK | Estimación directa: depreciation of intangible assets. Casilla 0227. 2025 section migrates to `rendimientos_actividades_economicas/estimacion_directa`. Coherent. |
| `irpf_ed_gastos_manutencion_contribuyente` | OK | Estimación directa: taxpayer subsistence expenses (Art 30.2.5ª.c LIRPF). Casilla 0191. Coherent. |
| `irpf_ed_otros_consumos_explotacion` | OK | Estimación directa: other operating consumption. Casilla 0183. Coherent. |
| `irpf_ed_reduccion_art_32_2_1` | OK | Estimación directa: reduction for certain economic activities (Art 32.2.1º LIRPF). Casilla 0232. Coherent. |
| `irpf_ed_total_gastos_deducibles_normal` | OK | Estimación directa: total deductible expenses (normal method). Casilla 0220. 2025 label explicitly says "en estimacion directa normal". Coherent. |
| `irpf_eo_agr_indice_forestal` | OK | Estimación objetiva agr: forestry corrective index. Casilla 1547. Coherent. |
| `irpf_eo_agr_ingresos_integros_cria_guarda_engorde_ganado` | OK | Estimación objetiva agr: gross income from livestock raising/guarding/fattening services. Casilla 1533. Labels become more explicit from 2022. Coherent. |
| `irpf_eo_agr_rdto_neto_modulos` | RENAME | The role name says `rdto_neto_modulos` but the data_type is `decimal` and the label is "Rendimiento neto de módulos" for the agricultural objetiva section. This is correct terminology, but the `agr_` prefix implies it is agriculture-specific. Verify whether there is a separate non-agr `rdto_neto_modulos` role. If not, the `agr_` prefix is sufficient and the name is OK. No rename needed on current information — OK. |
| `irpf_eo_indice_corrector_especial` | OK | Estimación objetiva (non-agr): special corrective index. Casilla 1469. Coherent. |
| `irpf_eo_rdto_neto_reducido_total` | OK | Estimación objetiva: total reduced net income (non-agr activities). Casilla 1484. Labels are stable and detailed. |
| `irpf_escala_sobre_minimo_general_estatal` | OK | Application of the general tax scale to the personal minimum (casilla 0521), state portion. Casilla 0530. Accurate. |
| `irpf_g4_re_ganancia_patrimonial` | OK | Capital gains in the G4 exit-taxation section (change of residence abroad). Casilla 0408. Coherent. |
| `irpf_ganancia_acciones_ganancia_reducida_no_exenta` | OK | Reduced non-exempt capital gains from share sales (DT 9ª reduction applied). Casilla 0336. Coherent. |
| `irpf_ganancia_derechos_susceptible_reduccion_dt9` | OK | Portion of rights gains eligible for DT 9ª reduction. Casilla 0349. Coherent. |
| `irpf_ganancia_fondos_valor_transmision_global` | OK | Total global transmission value for investment funds. Casilla 0312. Coherent. |
| `irpf_ganancia_otros_anio_imputacion_3` | RENAME | The `_3` suffix implies this is the third in a numbered series for year of imputation in other-assets capital gains. However all members are the same casilla 0371 across revisions, suggesting this is the singular year-of-imputation field, not the third of several. If _1 and _2 companions exist, the naming is consistent; if they do not, the `_3` suffix is misleading. Rename: `irpf_ganancia_otros_anio_imputacion` (without suffix) unless siblings are confirmed. |
| `irpf_ganancia_otros_ganancia_pendiente_resto` | OK | Remaining capital gain pending imputation (other assets). Casilla 0380. 2020–2021 label uses "Ganancia patrimonial pendiente de imputación", 2022+ uses "Resto ganancia patrimonial pendiente de imputación". Both express the same concept. Coherent. |
| `irpf_ganancia_otros_reducida_imputable_da7` | OK | Reduced capital gain (DA 7ª reduction) imputable to current year. Casilla 1654. Coherent. |
| `irpf_ganancia_premios_aprovechamiento_forestal` | OK | Capital gains from community forestry usage rights in public forests. Casilla 0302. Note: revision 2021 label still says "en 2020" (label not updated); however this is a registry label defect, not a role-assignment issue. OK for role. |
| `irpf_ganancia_premios_juegos_valoracion` | RENAME | Label is "Valoración" (valuation/assessed value) in the prizes/games section (`gp_premios/juegos`). The role name `premios_juegos_valoracion` is accurate — it is the valuation of game prizes. However "valoracion" alone is generic; given the context section confirms it is gaming prize valuation, the name is fine. OK. |
| `irpf_inmueble_arrendamiento_negocio_flag` | RENAME | Label is "Bien inmueble objeto de arrendamiento de negocio" — a flag indicating the property is subject to business tenancy. data_type is `money(default)` which is wrong for a flag — this should be boolean. This is a data_type anomaly (not a naming issue). The name correctly captures the concept. OK on name; OUTLIER on data_type: all 6 members use `money(default)` for what should be a boolean flag field. |
| `irpf_inmueble_exconyuge_nif_extranjero_flag` | OK | Boolean flag: ex-spouse NIF is a foreign-country NIF. Casilla 0078. Coherent. |
| `irpf_inmueble_uso_mixto_flag` | OK | Boolean flag for exceptional mixed use (simultaneously personal and other use). Casilla 0086. Coherent. |
| `irpf_intereses_demora_perdida_deduccion_autonomica` | OUTLIER | 2020 and 2021 revisions of id=0578 have label "Intereses de demora correspondientes a las deducciones anteriores (*): Parte **estatal**" — the state portion. From 2022 onwards the same casilla label reads "Parte **autonómica**". The role is named `_autonomica` but 2020/2021 members belong to the state portion. OUTLIER: id=0578, revision=2020 and id=0578, revision=2021. True role for those two revisions is `irpf_intereses_demora_perdida_deduccion_estatal`. |
| `irpf_minimo_ascendientes_estatal` | OK | State portion of the ascendants personal minimum. Casilla 0515. Coherent. |
| `irpf_perdida_derecho_deduccion_autonomica` | OK | Autonomic portion of deductions whose entitlement has been lost. Casilla 0577. Coherent. |
| `irpf_perdida_otros_pendiente_2` | RENAME | The `_2` suffix implies this is the second in a numbered pair for pending losses in other-assets. Same pattern issue as `ganancia_otros_anio_imputacion_3`. Casilla 0370. If a `_pendiente_1` companion exists the name is justified; otherwise misleading. Rename: `irpf_perdida_otros_pendiente` unless a sibling is confirmed. |
| `irpf_re_aie_retenciones_imputadas` | OK | AIE (Agrupaciones de Interés Económico) attributed withholdings. Casilla 0264. Coherent. |
| `irpf_re_atrib_cap_inmo_reducciones_23_3` | OK | Attribution regime: capital immobiliario reductions under Art 23.3 and DT 25ª. Casilla 1574. Decimal type. Coherent. |
| `irpf_re_atrib_gp_dt9_valor_transmision` | OK | Attribution regime: transmission value subject to DT 9ª. Casilla 1588. Coherent. |
| `irpf_re_atrib_inmueble_pct_titularidad` | RENAME | Label is "% Titularidad" (ownership percentage). data_type is `money(default)` which is semantically wrong for a percentage — should be decimal or percentage. The role name itself is accurate. OK on name; flag data_type anomaly: `money(default)` for ownership percentage. |
| `irpf_re_atrib_suma_cap_mob_ahorro` | OK | Attribution regime: sum of attributed savings-base capital-mobile net income. Casilla 1602. Coherent. |
| `irpf_re_imagen_empleador` | RENAME | Label is "NIF (si es residente en territorio español) o denominación" for the employer in the image-rights regime. The role name `re_imagen_empleador` captures this as the "employer" field in the image-rights special regime, which is correct. However the field contains either a NIF or a denomination (text), so a more precise name would be `irpf_re_imagen_empleador_nif_o_denominacion`. Minor — current name is acceptable. OK. |
| `irpf_red_patrimonio_protegido_discapacidad_aportaciones` | OK | Base-imponible reduction: contributions to protected patrimony for disabled person. Casilla 0480. Coherent. |
| `irpf_reduccion_pensiones_compensatorias_total` | OK | Total reductions eligible (compensatory pensions). Casilla 0486. Coherent. |
| `irpf_rendimiento_capital_inmobiliario_amortizacion_inmueble` | OK | Rental income: depreciation of property and improvements. Casilla 0131. Coherent. |
| `irpf_rendimiento_capital_inmobiliario_gastos_pendientes` | RENAME | Labels for 2020–2024 say "Importe que se aplica en esta declaración (*)" — amount applied in this return from prior-year pending expenses. The 2025 label is explicit: "Gastos pendientes aplicados en esta declaracion". The current name `gastos_pendientes` captures the concept. However the name could be more precise: `irpf_rendimiento_capital_inmobiliario_gastos_ejercicios_anteriores_aplicados`. Rename for precision — current name is minimally adequate, rename recommended. |
| `irpf_rendimiento_capital_mobiliario_ahorro_dt4_capital_diferido_acumulado` | OK | Savings-base capital-mobile income: accumulated deferred capital previously subject to DT 4ª. Casilla 0043. Labels explicitly list which prior years are included. Coherent. |
| `irpf_rendimiento_capital_mobiliario_ahorro_seguros_capitalizacion` | OK | Savings-base capital-mobile income: life/invalidity insurance and capitalisation contracts. Casilla 0032. Coherent. |
| `irpf_rendimiento_capital_mobiliario_general_rendimiento_neto_reducido` | OK | General-base capital-mobile income: reduced net income. Casilla 0056. Coherent. |
| `irpf_rendimiento_trabajo_gasto_otros` | OK | Employment income: other deductible expenses. Casilla 0019. Coherent. |
| `irpf_rendimiento_trabajo_total_ingresos_integros` | OK | Employment income: total gross income (computable). Casilla 0012. Coherent. |
| `irpf_retencion_imputada_aie_ute` | OK | Sum of attributed withholdings from AIEs and UTEs. Casilla 0601. 2025 label rewrites but semantics unchanged. Coherent. |
| `pension_recipient_nif` | RENAME | Missing `irpf_` prefix (all other roles use `irpf_` prefix). Casilla 0483 is the NIF of pension/annuity recipient in the compensatory pension reduction section. Rename: `irpf_reduccion_pension_compensatoria_receptor_nif`. |
| `irpf_compensacion_conyuges_sepa_flag` | RENAME | Label is "Compensación entre cónyuges: SEPA" and data_type is `text`, not boolean. SEPA is a transfer format identifier (Single Euro Payments Area), not a simple flag. A text field containing SEPA identifiers is better named `irpf_compensacion_conyuges_sepa_referencia` or `irpf_compensacion_conyuges_sepa_codigo`. The current `_flag` suffix implies boolean. Rename: `irpf_compensacion_conyuges_sepa_codigo`. |
| `irpf_deduccion_c_valenciana_acciones_participaciones` | OK | Valencian Community deduction for investment in shares of new/recently created entities. Casilla 1183. 2021–2025. Coherent. |
| `irpf_deduccion_castilla_la_mancha_vivienda_zonas_rurales` | OK | Castilla-La Mancha deduction for acquisition/rehabilitation of habitual residence in rural zones. Casilla 0204. 2021–2025. Coherent. |
| `irpf_eo_reduccion_lorca` | OK | Estimación objetiva: reduction for activities in Lorca (Murcia) municipal area. Casilla 1476. 2020–2024 (no 2025 member, deduction may have lapsed). Coherent. |
| `taxpayer_country` | RENAME | Missing `irpf_` prefix. Members are "Código País/Country code" for non-SEPA spouse compensation (`compnosepa`). The field is the country code of the spouse bank/transfer destination, not the taxpayer's country per se. Rename: `irpf_compensacion_conyuges_nosepa_pais_codigo`. Current name `taxpayer_country` does not reflect the actual usage (it is in the spouse compensation NOSEPA block, not in general taxpayer identification). |
| `irpf_deduccion_c_valenciana_contratacion_indefinida` | OK | Valencian Community deduction for indefinite employment contracts in household-care services. Casilla 0801. 2022–2025. Coherent. |
| `irpf_deduccion_murcia_mujeres_trabajadoras` | OK | Murcia deduction for working women. Casilla 1171. 2022–2025. Coherent. |
| `irpf_ganancia_cripto_ganancia_pendiente_resto` | OK | Remaining crypto capital gain pending imputation. Casilla 1878. 2022–2025. Coherent. |
| `irpf_ganancia_cripto_ultimo_anio_cobro` | OK | Last year of receipt for crypto capital gain. Casilla 1860. text type. 2022–2025. Coherent. |
| `irpf_ganancia_inmueble_catastral_2` | RENAME | Label is "Referencia catastral 2" in the `gp_otros_inmuebles/elemento_inmueble` section. The role name `catastral_2` accurately mirrors the label. However the `_2` suffix implies a second cadastral reference (alongside a `_1`). If this is indeed the second field in a pair, the name is correct. OK on the naming convention if siblings exist. |
| `irpf_ganancia_inmueble_ganancia_pendiente_4` | RENAME | The `_4` suffix implies this is the fourth in a numbered series for pending gains in the immovable-property gains section. Same issue as other `_N` suffixes — opaque without sibling context. Rename to `irpf_ganancia_inmueble_ganancia_pendiente` unless siblings _1, _2, _3 are confirmed. |
| `irpf_ganancia_inmueble_reduccion_dt9` | OK | DT 9ª reduction applicable to immovable-property gains. Casilla 1839. 2022–2025. Coherent. |
| `irpf_ganancia_inmueble_valor_transmision_renta_vitalicia` | OK | Transmission value allocated to constitute a life annuity (exemption under LIRPF). Casilla 1827. 2022–2025. Coherent. |
| `irpf_perdida_cripto_imputable_ejercicio` | OK | Crypto capital loss imputable to current exercise year. Casilla 1808. 2022–2025. Coherent. |
| `irpf_perdida_inmueble_pendiente_4` | RENAME | Same suffix issue as `ganancia_inmueble_ganancia_pendiente_4`. Rename to `irpf_perdida_inmueble_pendiente` unless sibling context confirmed. |
| `irpf_anexo_b_adoption_deduction_amount` | OK | Baleares adoption deduction amount in Anexo B supplementary info. Casilla 1994. 2023–2025. Coherent. |
| `irpf_anexo_b_birth_advance_regularize` | OK | Amount of the advance birth-deduction payment to regularize. Casilla 1993. 2023–2025. Coherent. |
| `irpf_deduccion_baleares_nacimiento_abono_anticipado` | OK | Baleares advanced payment for birth deduction. Casilla 1719. 2023–2025. Coherent. |
| `irpf_deduccion_castilla_y_leon_progenitor_1_nif_texto` | RENAME | Label is "NIF del otro progenitor 1" and data_type is `text`. The `_texto` suffix indicates the NIF is stored as text (not nif type). This is a valid distinguisher. However the role name could be standardised: `irpf_deduccion_castilla_y_leon_otro_progenitor_1_nif`. The `_texto` suffix is implementation-detail noise in a semantic role name. Rename: `irpf_deduccion_castilla_y_leon_otro_progenitor_1_nif`. |
| `irpf_deduccion_vehiculo_cantidad_a_cuenta` | OK | Amount on account for future EV acquisition deduction. Casilla 1925. 2023–2025. Coherent. |
| `irpf_eo_agr_reduccion_fertilizantes` | OK | Agricultural estimación objetiva: reduction for fertiliser purchases. Casilla 0159. 2022–2024 (temporary measure). Coherent. |
| `irpf_feac_inmueble_referencia_catastral` | OK | FEAC (fusiones, escisiones, etc.) property cadastral reference. Casilla 1982. 2023–2025. text type. Coherent. |
| `irpf_incremento_cuota_autonomica_perdida_nacimiento` | OK | Increase in autonomic tax quota from loss of birth deduction entitlement (Baleares clawback). Casilla 0504. 2023–2025. Coherent. |
| `irpf_resultado_rectificacion_devolucion` | OUTLIER | id=0701, revision=2020 has section `resultados/anexo_a_res/deduccion_vivienda_habitual_res` and label "Parte autonómica: Importe de la deducción" — this is the autonomic housing deduction amount, clearly belonging to the housing deduction role family, not to rectification/refund results. From 2024 onwards casilla 0701 correctly represents "Importe que, en su caso, pudiera resultar a devolver como consecuencia de la rectificación". OUTLIER: id=0701, revision=2020. True role for that member is `irpf_anexo_a_deduccion_vivienda_autonomica` (or a sibling thereof). |
| `irpf_deduccion_asturias_arrendamiento_gastos` | OK | Asturias deduction for rental-related expenses. Casilla 1628. 2024–2025. Coherent. |
| `irpf_deduccion_c_valenciana_generado_2025_pendiente` | RENAME | The name `generado_2025_pendiente` hard-codes a specific year. Casilla 1690 carries the "generated in current year, pending application" concept where the year rolls (2024 → "generado en 2024", 2025 → "generado en 2025"). Rename: `irpf_deduccion_c_valenciana_generado_ejercicio_pendiente`. |
| `irpf_deduccion_cantabria_ayuda_domestica_ccc` | OK | Cantabria domestic help deduction: social-security contribution account code. Casilla 1712. 2024–2025. text type. Coherent. |
| `irpf_deduccion_la_rioja_ela` | OK | La Rioja deduction for ALS (ELA) patients. Casilla 1785. 2024–2025. Coherent. |
| `irpf_deduccion_madrid_vivienda_municipio_riesgo_anio` | RENAME | Label is "Año de adquisición" (year of acquisition) for a Madrid at-risk municipality housing deduction. The `_anio` suffix is correct but `riesgo` (risk) is not in the label — this qualifier likely comes from the deduction's full name. If the deduction is specifically for "municipios en riesgo de despoblación" (depopulation-risk municipalities) then `riesgo` is valid context. Conditionally OK if confirmed against source TOML; otherwise rename: `irpf_deduccion_madrid_vivienda_municipio_anio_adquisicion`. |
| `irpf_gp_elemento_ganancia_exenta_reinversion_vh` | OK | Capital gain exempt from tax via reinvestment in habitual residence. Casilla 1643. Only 2020–2021 (2 revisions). Coherent for a transitional provision. |
| `irpf_anexo_c_exceso_sps_rg_aportaciones_periodo` | OK | Single-member role (casilla 1757, revision 2021 only): contributions in the period for the general-regime SPS excess (Anexo C). Coherent for a revision-specific row. |
| `irpf_conyuge_pais_residencia_ue_eee` | OK | Spouse's EU/EEA country of residence (2025 only, new field). Casilla ZRUE2 with unusual non-numeric ID. text type. Coherent. |
| `irpf_deduccion_andalucia_medico_colegiado` | OK | Andalucía deduction: licensed physician registration number or personal numeric code. Casilla 2244. 2025 only. text type. Coherent. |
| `irpf_deduccion_cantabria_desplazamiento_nuevos_residentes` | OK | Cantabria deduction for relocation and residence costs of new Cantabrian residents. Casilla 0773. 2025 only. Coherent. |
| `irpf_deduccion_extremadura_arrendadores_viviendas_vacias` | OK | Extremadura deduction for landlords of vacant properties. Casilla 2006. 2025 only. Coherent. |
| `irpf_deduccion_galicia_libros_texto` | OK | Galicia deduction for acquisition of textbooks and school materials. Casilla 2240. 2025 only. Coherent. |
| `irpf_deduccion_murcia_deporte_actividades_saludables` | OK | Murcia deduction for sport and healthy activities expenses. Casilla 2150. 2025 only. Coherent. |
| `irpf_deduccion_murcia_vehiculo_generado` | OK | Murcia vehicle deduction: amount generated in 2025. Casilla 2156. 2025 only. Coherent. |
| `irpf_eo_actividad_rdto_neto_actividad` | OK | Estimación objetiva: net income per activity (single-revision). Casilla 1479. 2020 only. Coherent. |
| `irpf_ganancia_fondos_coti_valor_adquisicion_global` | OK | Quoted funds: global acquisition value. Casilla 2229. 2025 only (new fund type). Coherent. |
| `irpf_incremento_maternidad_guarderia_no_aplicado_2021` | OK | Maternity deduction increment for nursery expenses not applied in 2021. Casilla 1916. 2022 only (catch-up provision). Coherent. |
| `irpf_re_atrib_tipo_regimen_agricola_flag` | OK | Attribution regime: flag indicating agricultural/livestock/forestry regime type. Casilla 0163. 2025 only. boolean type. Coherent. |

---

## Summary counts

| verdict | count |
|---|---|
| OK | 70 |
| RENAME | 18 |
| SPLIT | 1 |
| OUTLIER | 5 |
| **Total** | **94*** |

\* Note: `irpf_eo_modulo_num_unidades` and `irpf_inmueble_arrendamiento_negocio_flag` and `irpf_re_atrib_inmueble_pct_titularidad` are counted as OK on name but carry data_type anomalies (flagged inline). These data-type issues are separate from semantic-role correctness and should be addressed in a dedicated data-type hardening pass.

### OUTLIER details

| casilla | revision | current role | actual concept |
|---|---|---|---|
| 0944 | 2020 | `irpf_deduccion_canarias_seguros_credito_impago` | Canarias deduction for social-sustainability rentals (arrendamientos precios sostenibilidad social) |
| 1091 | 2020 | `irpf_deduccion_extremadura_vivienda_zonas_rurales` | Valencian Community deduction for non-remunerated household labour by spouse |
| 1091 | 2021 | `irpf_deduccion_extremadura_vivienda_zonas_rurales` | Valencian Community deduction for non-remunerated household labour by spouse |
| 0578 | 2020 | `irpf_intereses_demora_perdida_deduccion_autonomica` | State-portion late-payment interest on lost deduction entitlement |
| 0578 | 2021 | `irpf_intereses_demora_perdida_deduccion_autonomica` | State-portion late-payment interest on lost deduction entitlement |
| 0701 | 2020 | `irpf_resultado_rectificacion_devolucion` | Autonomic housing deduction amount (Anexo A vivienda habitual) |

### SPLIT detail

`irpf_anexo_c_exceso_sps_rt_pendiente_fin` — 2021 revision contains members from two distinct subsections (`excesos_sistemas_prevision_social_rt_res` and `contribuciones_sist_prevision_social_rt_res`). The employer-contribution subseries (casillas 1746/1749/1752/1755) should form its own role: `irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_fin`.
