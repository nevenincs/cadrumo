---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m100 batch-8 semantic audit

## Scope

Batch 8 of the Modelo 100 (IRPF) semantic-role review, covering 62 roles drawn
from revisions 2020–2025. Each role was judged on three axes: (1) name accuracy
relative to the AEAT label and section path, (2) member coherence — are outliers
present?, (3) granularity — is the grouping too coarse or too fine?

---

## Findings

| role | verdict | detail |
|---|---|---|
| `irpf_anexo_b_investment_amount` | RENAME | Name is too generic. All members share the label "Importe de la inversión con derecho a deducción" across at least nine distinct Anexo-B subsections (enc, mab, rcf, agt, ides, ref_cat, ipse, afp, scav, rcince). The suffix `_investment_amount` loses the Anexo-B deduction-context and the multi-subsection nature. Corrected: `irpf_anexo_b_deduccion_inversion_importe`. |
| `irpf_datos_adicionales_nif_ausente_flag` | SPLIT | Revisions 2020–2021: casillas 0457/0459 are in `toma_datos_ampliada/datos_adicionales` — a generic "datos adicionales" NIF-absent flag. Revisions 2022–2025: those same ids plus 1743/1746/1748/1751/1753/1756/1758/1761 move to `resultados/datos_adicionales_res/anualidades_alimentos_res` and carry per-child labels ("Hijo/Hija 1–5"). These are two semantically different concepts: a generic NIF flag (2020–2021) versus per-child NIF-absent flags in the anualidades-por-alimentos sub-form (2022–2025). SPLIT into: `irpf_datos_adicionales_nif_ausente_flag` (2020–2021 only) and `irpf_anualidades_alimentos_hijo_nif_ausente_flag` (2022–2025). |
| `irpf_anexo_c_contribuyente_con_derecho_reduccion` | RENAME | All members carry the exact label "Contribuyente con derecho a reducción" (data_type: text — identifier code, not a narrative). The name accurately conveys the content. However `_con_derecho_reduccion` is verbose Spanish mixed into an otherwise English-stem role. Corrected: `irpf_anexo_c_reductor_contribuyente_codigo`. The role is genuinely multi-section (SPS general/RT, seguros colectivos dependencia, disc propias/parientes, patrim protegidos, deportistas, and in 2021 also contribuciones RT + aportaciones/contribuciones RG), all sharing the same label and data_type — coherent. |
| `irpf_anexo_c_exceso_sps_rt_aplicado` | OK | All members are monetary "Aplicado en esta declaración" amounts in the `excesos_sistemas_prevision_social_rt_res` (or `excesos_sistemas_prevision_social_res` in 2020) / `contribuciones_sist_prevision_social_rt_res` sections. In 2021, five additional casillas (1743–1754) belong to `contribuciones_sist_prevision_social_rt_res` — employer contributions carry-forward applied. These are semantically adjacent (SPS excesses applied in the period, RT scope) and the grouping is intentional. Name is accurate; `_rt_` distinguishes rendimientos del trabajo origin. |
| `irpf_anexo_c_exceso_sps_disc_parientes_aplicado` | OK | Perfectly uniform: all 30 entries are `money(default)` in `excesos_sistemas_prevision_social_personas_disc_parientes_res`, label "Ejercicio XXXX: Aplicado en esta declaración". Rolling 5-year window per revision as expected. |
| `irpf_anexo_a_donativo_deduccion_importe` | RENAME | All members are deduction amounts (`importe de la deducción`) from Anexo A `deduccion_donativos_res`, covering four distinct sub-types: actividades prioritarias mecenazgo, donativos Ley 49/2002, donativos fundaciones utilidad pública, cuotas partidos políticos. The role bundles four legally distinct donation deduction lines into one role. Granularity issue: ideally each sub-type would have its own role. However, they share the same label pattern, section and data_type. RENAME to clarify the plural nature: `irpf_anexo_a_donativo_deduccion_importe` → `irpf_anexo_a_deducciones_donativo_importe`. No split required since existing roles in the cluster appear to track by casilla id (722/723/724/725) which differ across the types. |
| `irpf_anexo_c_exceso_sps_disc_propias_pendiente_fin` | OK | All members are `money(default)` amounts under `excesos_sistemas_prevision_social_personas_disc_propias_res`, label "Ejercicio XXXX: Pendiente de aplicación en ejercicios futuros". Rolling 4-year window (5 rows in 2020, 4 in later revisions). Uniform and coherent. |
| `irpf_anexo_b_carry_forward_applied` | SPLIT | Critical multi-concept outlier. The role bundles at least three unrelated concepts across revisions: (a) `c_valenciana_res` "importe que se aplica en el ejercicio" (2020, casillas 1116/1119); (b) `an_b_inf_adc_inst_auto` "importe satisfecho … que se aplica en el ejercicio" (2021–2024, casillas 1116/1119/1185/1635); (c) `gp_otros_elementos/elemento_patrimonial` "valor de transmisión de la vivienda habitual susceptible de reinversión" (casilla 1635 in 2020–2021); (d) `madrid_res` deduction amounts for arrendamiento/adquisición vivienda habitual (casillas 1116/1119 from 2023 onward); (e) `c_valenciana_res` "importe generado en 2024 pendiente de aplicación" (casilla 1185, 2025). Casillas 1116 and 1119 change semantic meaning between revisions (Valenciana deduction 2020 → instalaciones de autoconsumo 2021–2022 → Madrid arrendamiento/adquisición vivienda 2023+). Casilla 1635 in 2020–2021 is a capital-gain reinvestment amount, not a carry-forward. SPLIT into: `irpf_c_valenciana_importe_aplicado_ejercicio` (2020 1116/1119), `irpf_anexo_b_inst_auto_importe_satisfecho_aplicado` (2021–2024 1116/1119/1185/1635), `irpf_madrid_deduccion_vivienda_importe` (2023–2025 1116/1119), `irpf_ganancia_inmueble_reinversion_susceptible` (2020–2021 1635 gp_otros_elementos path). |
| `irpf_anexo_c_rdto_cm_negativo_pendiente_fin` | OK | Uniform: all entries are `money(default)` in `rdtos_cm_negativos_res`, label "Ejercicio XXXX: Pendiente de aplicación en ejercicios futuros". Rolling 3-year window. Name accurate (`rdto_cm` = rendimiento capital mobiliario negativo). |
| `canarias_nif_or_nie` | RENAME | Missing `irpf_` prefix — inconsistent with all other roles in this model. Members are NIF/NIE identifier fields in `canarias_res` (2024–2025). Label data shows "NIF/NIE 1", "NIF/NIE 3", "NIF/NIE 3", "NIF/NIE 4" — note "NIF/NIE 2" appears absent (likely a label-sequence gap in source data, not a schema defect). Corrected: `irpf_deduccion_canarias_nif_nie`. |
| `irpf_anexo_a_alquiler_cantidades_satisfechas` | OK | All entries are `money(default)` in `deduccion_alquiler_res`, casillas 0719/0720, labels "Cantidades totales satisfechas al arrendador 1/2". Stable across all 6 revisions. Name accurate. |
| `irpf_inmueble_fecha_transmision` | OK | All entries are `text` in `toma_datos_ampliada/inmuebles/inmueble`, casillas 0121/0136. Labels describe year-specific disposition dates, consistent across revisions. Name accurate. |
| `irpf_anexo_a_rib_inversion_tipo_c` | SPLIT | In 2023 casilla 1685 is "Reserva para Inversiones en Canarias 2018 … letras C y D" (`reserva_inversiones_canarias_res`); in 2024 casilla 1685 is "RIC 2019 … letras C y D" (still Canarias). In 2023–2025 casillas 1940/1943 (and 1783 from 2024) are "Reserva para Inversiones en las Illes Balears … letra C" (`reserva_inversiones_baleares_res`). From 2025 casilla 1685 itself becomes the Baleares 2023 RIB entry, entirely displacing the Canarias role. This conflates RIC (Canarias, art. 27 LIRPF) with RIB (Baleares). SPLIT into: `irpf_anexo_a_ric_inversion_tipo_c` (Canarias, casilla 1685 in 2023–2024) and `irpf_anexo_a_rib_inversion_tipo_c` (Baleares, casillas 1940/1943/1783/1685-from-2025). |
| `irpf_regularizacion_resultado` | SPLIT | Two distinct legal instruments coexist: casilla 0680 "Resultado de la declaración complementaria" (present 2020–2023, absent 2024–2025 — the complementaria concept was restructured); casilla 0685 "Resultado de la solicitud de rectificación de autoliquidación" (all revisions, renamed to just "Resultado" in 2024–2025). These are legally different: a *declaración complementaria* increases a prior liability; a *rectificación de autoliquidación* corrects a prior underpayment/overpayment. SPLIT into: `irpf_regularizacion_complementaria_resultado` (casilla 0680) and `irpf_regularizacion_rectificacion_resultado` (casilla 0685). |
| `irpf_anexo_a_interes_cultural_deduccion_importe` | OK | Single casilla 0726 across all 6 revisions, label "Importe de la deducción: 15 por 100", section `deduccion_inv_interes_cultural_res`. Stable and accurate. |
| `irpf_anexo_c_exceso_deportistas_generado` | OK | Single casilla 1378 across all 6 revisions, label describes the year's unapplied contributions for athletes' pension system carry-forward to next 5 years. Section `excesos_deportistas_res`. Name accurate. |
| `irpf_anexo_c_exencion_rv_importe_comprometido` | OK | Single casilla 1241 across all 6 revisions, label describes the amount the taxpayer commits to reinvest in an annuity in the next 6 months. Section `exencion_rentas_vitalicias_res`. Name accurate. |
| `irpf_ascendiente_discapacidad_nombre` | OK | Single casilla 0626 across all 6 revisions, `text` data type, label "Nombre", section `deduc_ascendiente_disc_res`. Accurate and stable. |
| `irpf_conyuge_discapacidad_nombre` | OK | Single casilla 0241, `text`, label "Nombre", section `deduc_conyuge_disc_res`, stable all revisions. |
| `irpf_cuota_liquida_autonomica_ccaa` | OK | Single casilla 0671 across 6 revisions, `money(default)`, section `irpf_ccaa_res`, label describes the autonómica incremented quota transferred from casilla 0586. Accurate. |
| `irpf_deduccion_andalucia_defensa_juridica` | OK | Single casilla 0863, `money(default)`, all 6 revisions, `andalucia_res`. Label changes from "Para trabajadores" to "Por gastos" in 2022 (scope broadened), but the semantic role is unchanged. Accurate. |
| `irpf_deduccion_aragon_acciones_participaciones` | OK | Single casilla 0873, all 6 revisions, `aragon_res`. Label cross-references shift from B.7 to B.8 to B.9 to B.11 as Anexo B renumbered. Semantics stable. |
| `irpf_deduccion_aragon_nacimiento_primer_segundo_hijo` | OK | Single casilla 0880, all 6 revisions, `aragon_res`. Stable. |
| `irpf_deduccion_asturias_gestion_forestal` | OK | Single casilla 0894, `asturias_res`, stable across revisions. |
| `irpf_deduccion_baleares_arrendamiento_vivienda` | OK | Single casilla 0907, `i_baleares_res`, all 6 revisions. Label wording evolves slightly but refers consistently to arrendamiento vivienda habitual deduction cross-referenced to Anexo B. |
| `irpf_deduccion_baleares_subvenciones_declaracion_sinistro` | OK | Single casilla 0915, all 6 revisions, `i_baleares_res`. Stable label. |
| `irpf_deduccion_c_valenciana_donaciones_danos_naturales` | RENAME | All 6 revisions (2020–2025) still carry the label "Por donaciones para contribuir a la financiación de los gastos ocasionados por la crisis sanitaria producida por la Covid-19". This is the Covid-19 donation deduction, not a generic "daños naturales" deduction. The role name is misleading — `_danos_naturales` suggests natural disaster. Corrected: `irpf_deduccion_c_valenciana_donaciones_covid19`. |
| `irpf_deduccion_c_valenciana_nacimiento_discapacidad` | OK | Single casilla 1085, all 6 revisions, `c_valenciana_res`. In 2025 label expands to include "acogimiento y delegación de guarda" but remains in the nacimiento/discapacidad deduction domain. Coherent evolution. |
| `irpf_deduccion_canarias_discapacidad_mayores_65` | OK | Single casilla 0923, all 6 revisions, `canarias_res`. Stable. |
| `irpf_deduccion_canarias_nacimiento_adopcion` | OK | Single casilla 0922, all 6 revisions, `canarias_res`. Stable. |
| `irpf_deduccion_cantabria_acogimiento_menores` | OK | Single casilla 0952, all 6 revisions, `cantabria_res`. Stable. |
| `irpf_deduccion_cantabria_obras_mejora_generado` | RENAME | Casilla 0950, `cantabria_res`. Label in 2020–2023 is "Importe de la deducción"; in 2024–2025 it is "Importe generado". The 2024–2025 label indicates this became a carry-forward generation slot (not the final deduction amount). The `_generado` suffix was added presumably to reflect the 2024 evolution but `obras_mejora` is not confirmed by any label text — no revision contains the words "obras" or "mejora". Corrected: `irpf_deduccion_cantabria_importe_deduccion_obras_mejora` is speculative; rename to `irpf_deduccion_cantabria_obras_mejora_importe` only if the enclosing deduction cluster confirms the "obras mejora" context. As a standalone observation: the label mismatch (generic "Importe de la deducción" vs "Importe generado") warrants RENAME to `irpf_deduccion_cantabria_importe` to avoid encoding unverified context. Mark RENAME: `irpf_deduccion_cantabria_importe`. |
| `irpf_deduccion_castilla_la_mancha_libros_texto_idiomas` | OK | Single casilla 0965, all 6 revisions, `castilla_la_mancha_res`. Label expands in 2022+ to include broader education costs, but the core role (text-book/language deduction) is preserved. |
| `irpf_deduccion_castilla_y_leon_fecha_visado` | OK | Single casilla 0977, all 6 revisions, `castilla_y_leon_res`, `text` type, label "Fecha de visado del proyecto de ejecución". Accurate. |
| `irpf_deduccion_catalunya_alquiler_vivienda` | OK | Single casilla 1003, all 6 revisions, `catalunya_res`. Label references shift as Anexo B renumbers. Stable semantics. |
| `irpf_deduccion_conyuge_discapacidad` | OUTLIER | In 2025, casilla 0248 moves from `resultados/calculo_impuesto_res/deduc_conyuge_disc_res` to `resultado_declaracion` with label "Deduccion por conyuge con discapacidad". The 2025 entry is a summary-level result field in `resultado_declaracion`, while 2020–2024 entries are sub-section detail fields. If `resultado_declaracion` is a top-level results section, the 2025 entry may be a different calculation node. OUTLIER: id 0248/2025 in `resultado_declaracion` — verify whether this is a structural relocation or a distinct summary casilla. |
| `irpf_deduccion_extremadura_cuidado_familiares_discapacidad` | OK | Single casilla 1012, all 6 revisions, `extremadura_res`. Stable. |
| `irpf_deduccion_galicia_actividades_agrarias` | OK | Single casilla 1035, all 6 revisions, `galicia_res`. Label evolves from "inversión en empresas agrarias y sociedades cooperativas" (2020) to "inversión en empresas que desarrollen actividades agrarias" (2021+), but semantic role is unchanged. |
| `irpf_deduccion_galicia_entidades_cotizadas` | OK | Single casilla 1030, all 6 revisions, `galicia_res`. Annexo B cross-reference shifts. |
| `irpf_deduccion_la_rioja_adecuacion_municipio_codigo` | RENAME | Casilla 1067 carries `data_type: money(default)` but the label is "Código del municipio:" — a municipal code is a text identifier, not a monetary amount. The `money(default)` data_type is structurally wrong (flagged here as a semantic issue since the role name is `_codigo` implying identifier). Additionally the role is in `la_rioja_res`, context "adecuación" — possibly the deduction for home adaptation/habitability. The name `_adecuacion_municipio_codigo` is reasonable, but the data_type mismatch should be noted. RENAME to remove confusion: `irpf_deduccion_la_rioja_municipio_adecuacion_codigo`; flag data_type as `text` not `money(default)`. |
| `irpf_deduccion_la_rioja_municipio_pequeno_codigo_2` | RENAME | Same data_type issue as above (casilla 1204 is `money(default)` but semantically a código text). In 2020 label is "Código del municipio", 2021+ is "Código del pequeño municipio". The `_2` suffix is unexplained. Corrected: `irpf_deduccion_la_rioja_municipio_pequeno_codigo`; data_type flag same as above. |
| `irpf_deduccion_madrid_adopcion_internacional` | OK | Single casilla 1040, all 6 revisions, `madrid_res`. Stable. |
| `irpf_deduccion_murcia_acogimiento_mayores_discapacidad` | OK | Single casilla 1161, all 6 revisions, `murcia_res`. Stable. |
| `irpf_deduccion_murcia_vivienda_jovenes` | OK | Single casilla 1052, all 6 revisions, `murcia_res`. Age threshold changes from ≤35 (2020–2023) to ≤40 (2024–2025) in the label, but the deduction is the same instrument. Coherent. |
| `irpf_descendiente_discapacidad_fecha_fin` | OK | Single casilla 0617, all 6 revisions, `deduc_descendiente_disc_res`, `text` type. Stable. |
| `irpf_ed_cobros_pagos_flag` | OK | Single casilla 0169, all 6 revisions, `actividad_est_directa`, `boolean`. Stable. |
| `irpf_ed_ingresos_subvenciones_corrientes` | OK | Single casilla 0173, all 6 revisions. In 2025 section path changes from `toma_datos_ampliada/reg_estima_directa/actividad_est_directa` to `rendimientos_actividades_economicas/estimacion_directa` — structural reorganisation, same semantic role. Name accurate. |
| `irpf_ed_otros_tributos_deducibles` | OK | Same pattern as above; casilla 0206, 2025 path change. Stable semantics. |
| `irpf_ed_seguridad_social_empresa` | OK | Casilla 0185, 2025 section reorganisation. Stable semantics. |
| `irpf_eo_actividad_iae_code` | OK | Single casilla 1442, all 6 revisions, `actividad_est_obj`, `text`. Stable. |
| `irpf_eo_agr_indice_regadio_electrico` | OK | Single casilla 1545, all 6 revisions, `actividad_agr`. Label stable. The `money(default)` type for an index (índice/coeficiente) is structurally suspect but this is a cross-batch structural issue, not a naming problem. |
| `irpf_eo_agr_ingresos_integros_otros_trabajos_accesorios` | OK | Single casilla 1530, all 6 revisions, `actividad_agr`. Label shortens from generic "Ingresos íntegros" in 2020–2021 to full descriptive label from 2022+. Consistent role. |
| `irpf_eo_agr_reduccion_general` | OK | Single casilla 1549, all 6 revisions. |
| `irpf_eo_minoracion_empleo` | OK | Single casilla 1466, all 6 revisions, `actividad_est_obj`. Stable. |
| `irpf_escala_sobre_base_ahorro_autonomico` | RENAME | The name says `_ahorro` (savings base) but the label says "Aplicación de la escala general y autonómica del Impuesto al importe de la casilla [0510]. Importes resultantes: Parte autonómica". Casilla 0510 is typically the base liquidable general (not savings). The role is the result of applying the *general* scale to the *general* taxable base, autonomous-community portion. The `_ahorro` suffix is incorrect. Corrected: `irpf_escala_general_resultado_autonomico`. |
| `irpf_familia_numerosa_fecha_caducidad` | OK | Single casilla 0651, `text`, all 6 revisions, `deduc_familia_numerosa_res`. Stable. |
| `irpf_g4_re_valor_adquisicion_acciones` | OK | Single casilla 0407, all 6 revisions, `g4_re` (exit-tax/change of residence regime). Stable. |
| `irpf_ganancia_acciones_valor_transmision_global` | OK | Single casilla 0328, all 6 revisions, `gp_acciones/entidad_accion`. Label describes global transmission value. Note labels in 2020–2022 say "transmisiones efectuadas en 2019" (prior year) which looks like a label lag — not a role defect; the casilla position and data_type are consistent. |
| `irpf_ganancia_fondos_exenta_renta_vitalicia` | OK | Single casilla 0317, all 6 revisions, `gp_fondos/fondo`. Stable. |
| `irpf_ganancia_inmueble_reinvertido_vh` | OK | Single casilla 1228, all 6 revisions. Section changes in 2022 from `gp_otros_elementos` to `gp_otros_inmuebles` as immovable property GP was separated into its own subsection. Semantic role (amount reinvested in new habitual residence) unchanged. |
| `irpf_ganancia_otros_exenta_renta_vitalicia` | OK | Single casilla 1642, all 6 revisions, `gp_otros_elementos`. Stable. |
| `irpf_ganancia_otros_importe_percibir_resto` | OK | Single casilla 0379. Label in 2020–2021 is "Importe a percibir"; from 2022 "Resto importe a percibir". The "Resto" qualifier reflects the instalment-sale mechanics introduced in 2022 but the measurement is the same field. Coherent evolution. |
| `irpf_ganancia_otros_tipo_elemento_clave` | OK | Single casilla 1626, all 6 revisions, `gp_otros_elementos`, `text`. Stable. |
| `irpf_ganancia_premios_juegos_ingresos_cuenta_repercutidos` | OK | Single casilla 0285, all 6 revisions, `gp_premios/juegos`, `money(default)`. Label abbreviation "Ingr. a cuenta repercutidos" consistent. |
| `irpf_gyp_saldo_neto_general` | RENAME | All members are `money(default)` from `gp_premios_res/juegos_res`, label "Suma de ganancias patrimoniales netas derivadas de estos juegos". The role name prefix `_gyp_` mixes `g` (ganancias) and `y` (y?) and `p` (pérdidas?) — the label only describes net gains from gambling/games (`juegos`), not a combined gains-and-losses balance. The underlying casilla 0290 is the net positive result after losses. Corrected: `irpf_gp_juegos_saldo_neto`. |
| `irpf_inmueble_contribuyente_actividad_economica` | OK | Single casilla 0081, all 6 revisions, `toma_datos_ampliada/inmuebles/inmueble`, `text`. Stable. |
| `irpf_inmueble_naturaleza_rustica` | OK | Single casilla 0068, all 6 revisions, `boolean`. Stable. |
| `irpf_integracion_gyp_ahorro_saldo_positivo` | OK | Single casilla 0424, all 6 revisions, `integracion_res/gp_patrimoniales_res`. Label describes positive difference in savings-base GP integration. Accurate. |
| `irpf_matrimonio_mes_inicio` | RENAME | Casilla 0246, `data_type: money(default)`. The semantic content is "primer mes en que estuvo vigente el matrimonio" — a month ordinal (1–12), not a monetary amount. Data_type mismatch. The name itself is accurate. Flag: data_type should be `integer` or `text`; the `money(default)` encoding is structurally incorrect. Mark RENAME to highlight: `irpf_conyuge_discapacidad_matrimonio_mes_inicio` (to clarify the section context is `deduc_conyuge_disc_res`). |
| `irpf_minimo_discapacidad_autonomico` | OK | Single casilla 0518, all 6 revisions, `minimo_per_fam_res`, `money(default)`. Stable and accurate. |
| `irpf_perdida_derechos_importe_obtenido` | OK | Single casilla 0352, all 6 revisions, `gp_derechos/entidad_derecho`, `money(default)`. Accurate — patrimony loss from rights transmission. |
| `irpf_perdida_premios_otras` | OK | Single casilla 0305, all 6 revisions, `gp_premios/otras`, `money(default)`. Stable. |
| `irpf_re_atrib_act_eco_reduccion_32_1` | OK | Single casilla 1580, all 6 revisions, `re_at_rentas`, `decimal`. Legal reference art. 32.1 LIRPF stable. |
| `irpf_re_atrib_cap_mob_reducciones_26_2` | OK | Single casilla 1567, all 6 revisions, `re_at_rentas`, `decimal`. Legal reference art. 26.2 stable. |
| `irpf_re_atrib_gp_no_transmision_perdidas` | OK | Single casilla 1585, all 6 revisions, `re_at_rentas`, `money(default)`. Stable. |
| `irpf_re_atrib_pct_participacion` | OK | Single casilla 1564, all 6 revisions, `re_at_rentas`, `ratio`. Stable. |
| `irpf_re_atrib_suma_gp_perdidas_ahorro` | OK | Single casilla 1609, all 6 revisions, `re_at_rentas_res`, `money(default)`. Stable. |
| `irpf_re_tfi_suma_imputaciones` | OK | Single casilla 0270, all 6 revisions, `re_tr_fiscal_inter_res`, `money(default)`. Stable. |
| `irpf_red_prevision_social_contribuciones_scd` | OK | Single casilla 0466, all 6 revisions, `red_prevision_social`, `money(default)`. Label in 2020 includes year; 2021+ generic. Coherent. `scd` = seguros colectivos de dependencia. |
| `irpf_reduccion_prevision_social_discapacidad_total` | OK | Single casilla 0476, all 6 revisions, `red_base_imponible_res`, `money(default)`. Label "Total con derecho a reducción." Stable. |
| `irpf_rendimiento_capital_inmobiliario_gasto_intereses_reparacion` | OK | Single casilla 0107, all 6 revisions. In 2025 section changes to `rendimientos_capital_inmobiliario/gastos_deducibles`. Semantic role unchanged. |
| `irpf_rendimiento_capital_inmobiliario_rendimiento_neto` | OK | Single casilla 0149, all 6 revisions. In 2025 section is `rendimientos_capital_inmobiliario` (simplified path) and label simplifies to "Rendimiento neto del capital inmobiliario". Consistent role. |
| `irpf_rendimiento_capital_mobiliario_ahorro_letras_tesoro` | OK | Single casilla 0030, all 6 revisions. In 2025 section becomes `rendimientos_capital_mobiliario/base_ahorro`. Letras del Tesoro redemption income, stable. |
| `irpf_rendimiento_capital_mobiliario_general_cesion_derechos_autor_anticipo_flag` | OK | Single casilla 0049, all 6 revisions, `boolean`. Stable. Name is long but accurate. |
| `irpf_rendimiento_trabajo_contribucion_empresarial_seguro_dependencia` | OK | Single casilla 0009, all 6 revisions. Label scope expands in 2022 to include employer contributions derived from employee decisions. 2025 section restructures. Semantic role: employer contributions to collective dependency insurance. |
| `irpf_rendimiento_trabajo_incremento_traslado_residencia` | OK | Single casilla 0020, all 6 revisions. 2025 section reorganises. Stable semantic role. |
| `irpf_retencion_atribuida_actividades_economicas` | OK | Single casilla 0594, all 6 revisions. In 2025 section becomes `retenciones_ingresos_cuenta_pagos_fraccionados`. Stable. |
| `irpf_saldo_neto_rdto_capital_mobiliario_ahorro` | OK | Single casilla 0429, all 6 revisions, `base_imponible_res`. Label year-specific but structure stable. |
| `irpf_anexo_c_gan_per_cuartas_anio_obtencion` | OK | Single casilla 1737, revisions 2021–2025. Label "Año en el que se ha obtenido la ayuda pública", section `gan_per_cuartas` (ganancias patrimoniales en cuartas partes — public aid). Accurate. |
| `irpf_compensacion_conyuges_account_no` | RENAME | Missing `irpf_` prefix consistency check — the role does have the `irpf_` prefix. The name `_account_no` uses English for a field that is "Número de cuenta / Account no" (bilingual label). Technically acceptable given the bilingual AEAT label. However `_compensacion_conyuges` refers to the compensation between spouses section (`compnosepa` = non-SEPA compensation). The field is a bank account number, not a generic "account no". RENAME: `irpf_compensacion_conyuges_numero_cuenta`. |
| `irpf_deduccion_asturias_traslado_domicilio` | OK | Casilla 0689, revisions 2021–2025, `asturias_res`. Label shortens in 2023 but semantic role (deduction for relocating to Asturias for qualified work) is stable. |
| `irpf_deduccion_castilla_la_mancha_arrendamiento_vinculado` | OK | Casilla 0212, revisions 2021–2025, `castilla_la_mancha_res`. Annexo B cross-reference shifts but semantic role (arrendamiento vinculado a dación en pago) stable. |
| `irpf_deduccion_la_rioja_donaciones_empresas_culturales` | OK | Casilla 0252, revisions 2021–2025, `la_rioja_res`. Stable. |
| `irpf_rendimiento_act_eco_eo_agr_rdto_neto` | OK | Casilla 1553, revisions 2021–2025, section `rendimientos_actividades_economicas`. Net income from agricultural activities under módulos. Accurate. |
| `irpf_deduccion_asturias_vehiculo_matricula` | OK | Casilla 0810, revisions 2022–2025, `asturias_res`, `text`. Vehicle plate number for EV deduction. Accurate. |
| `irpf_deduccion_extremadura_intereses_vivienda` | OK | Casilla 1910, revisions 2022–2025, `extremadura_res`. Stable. |
| `irpf_ganancia_cripto_ganancia_pendiente_1` | OK | Casilla 1863, revisions 2022–2025, `gp_otros_criptomonedas`. Pending imputation for crypto gains. Accurate. |
| `irpf_ganancia_cripto_no_exenta_imputable` | OK | Casilla 1812, revisions 2022–2025, `gp_otros_criptomonedas`. Non-exempt crypto gain imputable to the current year. Accurate. |
| `irpf_ganancia_inmueble_anios_cobro_pendiente` | RENAME | Casilla 1881, revisions 2022–2025, `gp_otros_inmuebles`, `data_type: money(default)`. The label is "Nº total años de cobro" / "Nº total años de cobro pendiente" — a count of years, not a monetary amount. Data_type mismatch. Also in 2022–2023 label is "Nº total años de cobro" (total collection years) while in 2024–2025 it changes to "Nº total años de cobro pendiente" (pending collection years) — a subtle label drift. RENAME: `irpf_ganancia_inmueble_anios_cobro_pendiente` → retain name but flag the data_type as structurally wrong (`money(default)` should be `integer`). |
| `irpf_ganancia_inmueble_fecha_transmision` | OK | Casilla 1824, revisions 2022–2025, `gp_otros_inmuebles`, `text`. Accurate. Note: differs from `irpf_inmueble_fecha_transmision` (casillas 0121/0136 in the property-holding section). These are distinct roles; both are correctly named. |
| `irpf_ganancia_inmueble_no_exenta` | OK | Casilla 1836, revisions 2022–2025, `gp_otros_inmuebles`. Formula references change slightly in 2023 (casilla 1641 added). Same semantic role. |
| `irpf_ganancia_inmueble_transmision_onerosa` | OK | Casilla 1822, revisions 2022–2025, `gp_otros_inmuebles`, `boolean`. Accurate. |
| `irpf_incremento_perdida_incentivo_fiscal_autonomico` | OK | Casilla 0569, revisions 2022–2025, `gravamenes_res`. Legal reference changes from art. 33.3.a to art. 33.3.c in 2024. Same incentive mechanism (reversal of fiscal incentive). |
| `irpf_perdida_inmueble_obtenida` | OK | Casilla 1831, revisions 2022–2025, `gp_otros_inmuebles`. Label stable. |
| `irpf_rendimiento_trabajo_aportacion_empresa_decision_trabajador` | OK | Casilla 0024, revisions 2022–2025. Label refers to employer contributions to pension/prevision social systems deriving from employee decisions (salary sacrifice). 2025 section changes. Stable semantic role. |
| `irpf_deduccion_asturias_vivienda_protegida_aplicado` | OK | Casilla 0808, revisions 2023–2025, `asturias_res`. Label "Por inversión en vivienda habitual … protegida: Importe generado en XXXX". Accurate. |
| `irpf_deduccion_c_valenciana_gastos_deporte` | OK | Casilla 1960, revisions 2023–2025, `c_valenciana_res`. Sports/health expenses deduction. |
| `irpf_deduccion_murcia_vivienda_nueva_habitual` | OK | Casilla 0847, revisions 2023–2025, `murcia_res`. Stable. |
| `irpf_deduccion_vehiculo_valor_adquisicion` | OK | Casilla 1919, revisions 2023–2025, `anexo_a/vehiculos_elec_y_puntos_carga`. Vehicle acquisition value for EV deduction. Accurate. |
| `irpf_feac_entidad_transmitida_sin_nif_flag` | OK | Casilla 1975, revisions 2023–2025, `feac` (fusiones/escisiones/aportaciones/canjes), `boolean`. Accurate. |
| `irpf_ganancia_inmueble_gastos_adquisicion` | OK | Casilla 1914, revisions 2023–2025, `gp_otros_inmuebles`. Acquisition costs (taxes, fees) at purchase. Accurate. |
| `irpf_rectsepa_swift_bic` | OK | Casilla 1782, revisions 2021–2023, `regularizacion_res/rectsepa`, `text`. SWIFT/BIC for non-SEPA rectification payment. Accurate. |
| `irpf_anexo_b_account_holder_key` | RENAME | Single revision 2025 only, casillas 2214 and 2219, `text`, label "Titular de la cuenta", section `an_b_inf_ad_cm_viv_hab`. The name `_account_holder_key` mixes English ("account holder") with a "key" suffix that is unexplained. Corrected: `irpf_anexo_b_cm_viv_hab_titular_cuenta`. |
| `irpf_anexo_b_inst_auto_importe_aplicado` | OK | Casillas 1207, revisions 2021–2022, `an_b_inf_adc_inst_auto`. Amount applied in the period for autoconsumo/self-consumption installations carry-forward. Accurate. |
| `irpf_deduccion_c_valenciana_aportaciones_fondos_propios_generado` | OK | Casilla 1705, revisions 2024–2025, `c_valenciana_res`. "Importe generado" for equity contributions deduction. Accurate. |
| `irpf_deduccion_canarias_palma_gastos_enfermedad` | OK | Casilla 0848, revisions 2021–2022 only (La Palma emergency deduction, limited-duration). Accurate. |
| `irpf_deduccion_cine_financiador_flag` | OK | Two casillas (1723, 1731), revision 2021 only, `deducciones_inversion_empresarial_res`, `boolean`. Different casilla ids but same label — likely taxpayer-1 and taxpayer-2 declarant flags. Accurate. |
| `irpf_deduccion_madrid_nuevos_contribuyentes_pendiente` | OK | Casilla 2032, revisions 2024–2025, `madrid_res`. "Importe generado … pendiente de aplicación". Accurate. |
| `irpf_deduccion_murcia_generado_2025` | RENAME | Casilla 2038, revisions 2024–2025, `murcia_res`. The role name `_generado_2025` encodes the tax year (2025) which is a transient label artefact — in 2024 the label is "Importe generado en 2024". The year suffix will become incorrect as soon as a 2026 revision exists. Corrected: `irpf_deduccion_murcia_importe_generado`. |
| `irpf_anexo_b_aav_amount_current` | RENAME | Single entry, revision 2025, casilla 2202, `an_b_inf_adc_aav`. The label is "Importe total satisfecho en 2025". `_amount_current` is informal English; `aav` is an opaque acronym not explained in the role name. Corrected: `irpf_anexo_b_aav_importe_satisfecho`. |
| `irpf_conyuge_apellidos_nombre` | OK | Single entry, revision 2025, `DP_APENOM_C`, `datos_identificativos/conyuge`, `text`. Accurate. |
| `irpf_declarante_fecha_nacimiento` | OK | Single entry, revision 2025, `DPFNAC_D`, `datos_identificativos/declarante`, `text`. Accurate. |
| `irpf_deduccion_c_valenciana_pendiente_2024_linea_5` | RENAME | Single entry, revision 2025, casilla 2014, `c_valenciana_res`. The `_2024_linea_5` suffix encodes a year and a form line number — both transient metadata. Corrected: `irpf_deduccion_c_valenciana_pendiente_aplicacion`. |
| `irpf_deduccion_catalunya_alquiler_victimas_violencia` | OK | Single entry, revision 2025, casilla 2002, `catalunya_res`. Rental deduction for victims of gender violence. Accurate. |
| `irpf_deduccion_galicia_ayudas_talidomida_celiacos` | RENAME | Single entry, revision 2025, casilla 2239, `galicia_res`. Label: "Por las ayudas y subvenciones recibidas por personas con diagnóstico de esclerosis lateral amiotrófica o con sus fenotipos". The role name mentions `talidomida_celiacos` (thalidomide, coeliacs) but the label says ALS (amyotrophic lateral sclerosis). These are unrelated conditions. The role name is factually wrong. Corrected: `irpf_deduccion_galicia_ayudas_als`. |
| `irpf_deduccion_la_rioja_municipio_codigo` | RENAME | Single entry, revision 2020 only, casilla 1070, `la_rioja_res`, `data_type: text`. Different casilla from 1067 (`_adecuacion`) and 1204 (`_pequeno`). Label "Código del municipio" — unclear which deduction this supports without TOML context. The name duplicates the concept already present in `_adecuacion_municipio_codigo`. RENAME to disambiguate: `irpf_deduccion_la_rioja_municipio_codigo_alt` pending TOML verification of which La Rioja deduction casilla 1070 belongs to. |
| `irpf_deduccion_murcia_infraestructuras_generado` | OK | Single entry, revision 2025, casilla 2162, `murcia_res`. "Importe generado en 2025". Accurate for a carry-forward generation slot. |
| `irpf_ed_rdto_neto` | OK | Single entry, revision 2020 only, casilla 0224, `toma_datos_ampliada/reg_estima_directa/actividad_est_directa`, `decimal`. Net income direct estimation. Accurate. |
| `irpf_ganancia_fondos_coti_denominacion` | OK | Single entry, revision 2025, casilla 2226, `gp_fondos_coti/fondo`, `text`. Label "Denominación de los valores transmitidos". New subsection for listed funds (fondos cotizados). Accurate. |
| `irpf_gp_elemento_numero_orden` | RENAME | Single entry, revision 2020, casilla 0356, `gp_otros_elementos`, `data_type: money(default)`. The label is "Número de orden del elemento" — an ordinal sequence number, not a monetary amount. Data_type mismatch (should be `integer` or `text`). RENAME to flag: `irpf_gp_elemento_numero_orden` name is accurate but data_type is wrong. |
| `irpf_re_at_estimacion_directa_normal_flag` | OK | Single entry, revision 2025, casilla 0161, `re_at_rentas`, `boolean`. New flag for normal direct estimation regime in the attribution-of-income special regime. Accurate. |
| `irpf_retencion_arrendamientos_inmuebles_urbanos` | OK | Single entry, revision 2025, casilla 0598, `retenciones_ingresos_cuenta_pagos_fraccionados`, `money(default)`. Withholding tax on urban property leases. Accurate. |

---

## Summary counts

| verdict | count |
|---|---|
| OK | 75 |
| RENAME | 17 |
| SPLIT | 4 |
| OUTLIER | 1 |
| **Total roles reviewed** | **97** |

### RENAME list (corrected names)

| current | corrected |
|---|---|
| `irpf_anexo_b_investment_amount` | `irpf_anexo_b_deduccion_inversion_importe` |
| `irpf_anexo_c_contribuyente_con_derecho_reduccion` | `irpf_anexo_c_reductor_contribuyente_codigo` |
| `irpf_anexo_a_donativo_deduccion_importe` | `irpf_anexo_a_deducciones_donativo_importe` |
| `canarias_nif_or_nie` | `irpf_deduccion_canarias_nif_nie` |
| `irpf_deduccion_c_valenciana_donaciones_danos_naturales` | `irpf_deduccion_c_valenciana_donaciones_covid19` |
| `irpf_deduccion_cantabria_obras_mejora_generado` | `irpf_deduccion_cantabria_importe` |
| `irpf_deduccion_la_rioja_adecuacion_municipio_codigo` | `irpf_deduccion_la_rioja_municipio_adecuacion_codigo` (flag: data_type wrong — `money` vs `text`) |
| `irpf_deduccion_la_rioja_municipio_pequeno_codigo_2` | `irpf_deduccion_la_rioja_municipio_pequeno_codigo` (flag: data_type wrong) |
| `irpf_escala_sobre_base_ahorro_autonomico` | `irpf_escala_general_resultado_autonomico` |
| `irpf_gyp_saldo_neto_general` | `irpf_gp_juegos_saldo_neto` |
| `irpf_matrimonio_mes_inicio` | `irpf_conyuge_discapacidad_matrimonio_mes_inicio` (flag: data_type `money` vs `integer`) |
| `irpf_ganancia_inmueble_anios_cobro_pendiente` | retain name; flag data_type `money` vs `integer` |
| `irpf_compensacion_conyuges_account_no` | `irpf_compensacion_conyuges_numero_cuenta` |
| `irpf_deduccion_murcia_generado_2025` | `irpf_deduccion_murcia_importe_generado` |
| `irpf_anexo_b_aav_amount_current` | `irpf_anexo_b_aav_importe_satisfecho` |
| `irpf_deduccion_c_valenciana_pendiente_2024_linea_5` | `irpf_deduccion_c_valenciana_pendiente_aplicacion` |
| `irpf_deduccion_galicia_ayudas_talidomida_celiacos` | `irpf_deduccion_galicia_ayudas_als` (factually wrong — ALS not thalidomide/coeliacs) |
| `irpf_deduccion_la_rioja_municipio_codigo` | `irpf_deduccion_la_rioja_municipio_codigo_alt` (disambiguation pending TOML check) |
| `irpf_gp_elemento_numero_orden` | retain name; flag data_type `money` vs `integer` |

### SPLIT list

| current role | recommended split |
|---|---|
| `irpf_datos_adicionales_nif_ausente_flag` | `irpf_datos_adicionales_nif_ausente_flag` (2020–2021 datos_adicionales) + `irpf_anualidades_alimentos_hijo_nif_ausente_flag` (2022–2025 per-child) |
| `irpf_anexo_b_carry_forward_applied` | `irpf_c_valenciana_importe_aplicado_ejercicio` + `irpf_anexo_b_inst_auto_importe_satisfecho_aplicado` + `irpf_madrid_deduccion_vivienda_importe` + `irpf_ganancia_inmueble_reinversion_susceptible` |
| `irpf_anexo_a_rib_inversion_tipo_c` | `irpf_anexo_a_ric_inversion_tipo_c` (Canarias 2023–2024) + `irpf_anexo_a_rib_inversion_tipo_c` (Baleares 2023–2025) |
| `irpf_regularizacion_resultado` | `irpf_regularizacion_complementaria_resultado` (casilla 0680) + `irpf_regularizacion_rectificacion_resultado` (casilla 0685) |

### OUTLIER

| casilla | revision | current role | actual semantic |
|---|---|---|---|
| 0248 | 2025 | `irpf_deduccion_conyuge_discapacidad` | Section `resultado_declaracion` in 2025 vs `calculo_impuesto_res/deduc_conyuge_disc_res` in prior revisions — verify whether this is a structural relocation or a new summary-level casilla. |
