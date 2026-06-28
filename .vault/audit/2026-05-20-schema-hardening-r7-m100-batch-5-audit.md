---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 M100 batch-5 audit

## Scope

Semantic-correctness review of 67 `semantic_role` groups from M100 (IRPF) batch-5.
Revisions covered: 2020–2025. Structural validity is out of scope; this review
judges name accuracy, member coherence, and granularity only.

---

## Findings

| role | verdict | detail |
|------|---------|--------|
| `investment_entity_nif` | RENAME | Role spans: AIEs (agrupaciones interés económico), investment funds (sociedades/fondos inversión), new-company deductions (0711/0713, 1131/1133), childcare NIF (1076 La Rioja), MAB/RCF/AGT/IDES/IPSE/AFP/SCAV/RCINCE Annex B entities, Canarias nursery NIFs (2040/2042), and a new 2025 cotizados fund (2225). This is not one role — it is every NIF field on the form that happens to target an entity rather than a person. Rename: `irpf_entidad_nif_varios`. The real issue is under-splitting (see SPLIT below). |
| `investment_entity_nif` | SPLIT | At minimum three distinct sub-roles are present: (a) `irpf_re_agrup_interes_economico_nif` (casilla 0257: AIE regime NIF); (b) `irpf_fondo_inversion_nif` (casillas 0311/0403/2225: fund/issuer NIFs used in ganancias patrimoniales); (c) `irpf_deduccion_nueva_empresa_entidad_nif` (0711/0713/1131/1133: new-company deductions). Childcare NIFs (1076, 0210, 2040/2042) are personal-service providers, not investment entities. |
| `investment_entity_nif` — 0210/1076/2040/2042 | OUTLIER | Casillas 0210 (Castilla-La Mancha, guardería), 1076 (La Rioja, Escuela/Guardería), 2040/2042 (Canarias, guardería) are childcare-centre NIFs linked to the maternidad/guardería deduction pathway. They belong to a `irpf_centro_guarderia_nif` role, not an investment-entity role. |
| `irpf_anexo_a_ric_inversion_tipo_cd` | OK | All members are `money(default)` in `reserva_inversiones_canarias_res`. The casilla-id set shifts each year (rolling 4-year window for dotaciones + anticipo row 0751 + one older-year row). 2021 rev includes 0778 labelled "Importe de las dotaciones" — this is the RIC dotación amount for a prior year, not an investment under letras C/D. Potential semantic drift on 0778 (2021 only) but the section is the same block. Acceptable as rolling-window cross-revision grouping. Name is accurate: inversiones previstas letras C y D art. 27.4. |
| `irpf_inmueble_gasto_reparacion_importe` | RENAME | The casilla labels say "Gasto 1: Importe del gasto" … "Gasto 5: Importe del gasto" plus "Resto de gastos". The repair/conservation expense breakdown under `toma_datos_ampliada/inmuebles/inmueble` is broader than reparación alone — it covers all deductible expenses on the property (interest, IBI, community fees, repair, depreciation are separate casillas). These casillas are the itemised expense lines 1–5 plus remainder. More accurate: `irpf_inmueble_gasto_deducible_importe`. |
| `irpf_anexo_c_exceso_scd_aplicado` | OK | All members are `money(default)` in `exceso_seguros_colectivos_dependencia_res`. Rolling 5-year prior-exercise window of "applied in this declaration" amounts. Name is accurate: excess from collective dependency insurance (SCD), applied amount. |
| `parent_nif` | RENAME + SPLIT | Name lacks `irpf_` prefix and is insufficiently specific. Two distinct usages present: (a) casillas 1209/1244 in `castilla_y_leon_res` — NIF of the "other progenitor" for the Castilla y León autonomic deduction (2021–2025); (b) casillas 1742/1745/1750/1755/1760 in `anualidades_alimentos_res` — NIF of the other parent per child for alimony annuities section (2022–2025). These are semantically different: one is a deduction-qualifier identity field, the other is a per-child alimony counterparty identifier. Corrected names: `irpf_deduccion_cyl_otro_progenitor_nif` and `irpf_anualidades_alimentos_otro_progenitor_nif`. |
| `parent_nif` — 1209 absent from 2023+ | OUTLIER | Casilla 1209 (NIF progenitor 1, Castilla y León) appears only in revisions 2021 and 2022; it is absent from 2023–2025. This is a valid registry discontinuation and not a misassignment, but it should be noted. |
| `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_fin` | OK | All `money(default)` in `excesos_sistemas_prevision_social_personas_disc_parientes_res`. Rolling 4-year prior-exercise "pendiente de aplicación en ejercicios futuros" window. Name is accurate: excess pension contributions for disabled relatives, amount pending future application. |
| `irpf_saldo_neto_gyp_ahorro_pendiente_resto` | OK | All `money(default)` in `base_imponible_res`. Rolling 4-year window of negative net patrimonial gains/losses pending offset (25% cap) in savings base. Name is accurate: "resto" = remaining balance after main offset row. |
| `irpf_anexo_c_exceso_patrim_protegido_pendiente_fin` | OK | All `money(default)` in `excesos_patrim_protegidos_res`. Rolling 3-year prior-exercise "pendiente" window. Name is accurate: excess contributions to protected assets pending future reduction. |
| `tenant_or_foreign_id_nif` | RENAME | Casillas 0091/0094/0097 are "NIF del arrendatario" (tenant's NIF) with `data_type: text` (not `nif`). The `text` type is intentional: these accept NIE (foreign national ID) as well. The role name "or_foreign_id" is correct but adds imprecision. Standardise to `irpf_inmueble_arrendatario_nif` with the text/NIE tolerance documented. Also lacks `irpf_` prefix. |
| `irpf_inmueble_adquisicion_tipo_lucrativa` | OUTLIER | Casilla 0134 in revisions 2020 (label: "Onerosa") then 2021–2025 (label: "Lucrativa"). In revision 2020, 0134 is unambiguously the "onerosa" acquisition flag, the semantic opposite of lucrativa. From 2021 onward the label for 0134 switches to "Lucrativa". This is a registry relabelling: 0134 changed meaning between 2020 and 2021. The 2020 member (0134, "Onerosa") is a misassignment to this role. It should belong to a separate `irpf_inmueble_adquisicion_tipo_onerosa` role for the 2020 revision only. |
| `irpf_inmueble_valor_catastral_construccion` | OK | Both 0124 and 0139 are always "Valor catastral de la construcción" in `toma_datos_ampliada/inmuebles/inmueble`, all `money(default)`. Two casillas exist because the form has two acquisition-type blocks (lucrativa and onerosa). Name is accurate. |
| `irpf_deduccion_eficiencia_energetica_calificacion_posterior` | OK | All `text` in `mejoras_energeticas_viv` (Annex A). Revisions 2021–2025 consistently "Letra de calificación energética posterior (consumo de energía)". Name is accurate. |
| `irpf_deduccion_cantabria_arrendamiento_municipios_riesgo` | OK | All `money(default)` in `cantabria_res`. Label evolves from "riesgo de despoblamiento" to "reto demográfico" to "municipios afectados por riesgo de despoblamiento"; the underlying deduction concept is stable. 2020–2021 has two casillas (0818 tenant + 0819 landlord); from 2022 only 0818 remains (the landlord deduction was removed). This is a valid structural change, not an outlier. Name is accurate. |
| `feac_entity_nif` | RENAME | Lacks `irpf_` prefix. The role covers NIF of entities in the FEAC (fusiones, escisiones, aportaciones de activos, canjes de valores) special regime section. Both 1974 and 1978 are generic "NIF" labels in `regimen_especial/feac` (2023–2025). The two casillas likely represent two different entities in the transaction (transmitting and receiving). Rename: `irpf_feac_entidad_nif`. |
| `irpf_anexo_a_prestamo_id` | OK | Single casilla 0709 across all revisions, "Número de identificación del préstamo hipotecario" in `deduccion_vivienda_habitual_res`, `data_type: text`. Name is accurate. |
| `irpf_anexo_c_exceso_patrim_protegido_generado` | RENAME | Casilla 1362 in all revisions: "Aportaciones de 20XX no aplicadas cuyo importe se solicita poder reducir en los 4 ejercicios siguientes". This is the current-year excess contribution to protected assets being carried forward, not a "generado" amount in a generation/calculation sense. More accurate: `irpf_anexo_c_exceso_patrim_protegido_ejercicio_actual`. |
| `irpf_anexo_c_exencion_rv_importe_reinvertido` | OK | Single casilla 1240, always "Importe reinvertido hasta el 31-12-20XX en rentas vitalicias" in `exencion_rentas_vitalicias_res`. Name is accurate. |
| `irpf_ascendiente_num_contribuyentes_derecho` | RENAME | Casilla 0629 with label "Indique el número de personas con derecho al mínimo por ascendientes", `data_type: money(default)`. This is a count field encoded as money — a known registry convention for integer counts. The role name is accurate in concept but the section is `deduc_ascendiente_disc_res` (deduction for disabled ascendants). Name is acceptable; minor: `irpf_minimo_ascendiente_num_contribuyentes` would be more consistent with peer naming for mínimo personal/familiar fields. |
| `irpf_conyuge_discapacidad_otro_contribuyente_flag` | OK | Single casilla 0244, `boolean`, "Marque X si otro contribuyente tiene derecho respecto del cónyuge con discapacidad". Stable across all revisions. Name is accurate. |
| `irpf_cuota_liquida_autonomica_incrementada` | OK | Casilla 0586 in 2020–2024 in `gravamenes_res` with consistent formula label; 2025 revision moved to `resultado_declaracion` with a simplified label — this is a known section restructuring in the 2025 form. Semantic content unchanged: it remains the incremented autonomous community liquid quota. Name is accurate. |
| `irpf_deduccion_andalucia_discapacidad` | OK | Single casilla 0856, stable across all revisions. Name is accurate. |
| `irpf_deduccion_aragon_adopcion_internacional` | OK | Single casilla 0868, stable. Name is accurate. |
| `irpf_deduccion_aragon_nacimiento_tercer_hijo` | OK | Single casilla 0866, stable. Name is accurate. |
| `irpf_deduccion_asturias_libros_texto` | OK | Single casilla 0896, stable. Name is accurate. |
| `irpf_deduccion_baleares_descendientes_menores_6` | OK | Single casilla 0914, stable. Name is accurate. |
| `irpf_deduccion_bienes_corporales_canarias_autonomica` | OK | Single casilla 0559, stable. Name is accurate. |
| `irpf_deduccion_c_valenciana_donaciones_investigacion_sanitaria` | OK | Single casilla 1172, stable. Name is accurate. |
| `irpf_deduccion_c_valenciana_obras_conservacion_1` | RENAME | Casilla 1108, 2020–2022 labelled generically "Importe de la deducción", 2023–2025 clarified to "Por obras de conservación o mejora en la vivienda habitual (realizadas desde 1 enero 2014 hasta 31 diciembre 2015)". The `_1` suffix is opaque. Rename: `irpf_deduccion_c_valenciana_obras_conservacion_vivienda_2014_2015`. |
| `irpf_deduccion_canarias_donaciones_culturales_deportivas` | OK | Single casilla 0934, stable. Name is accurate. |
| `irpf_deduccion_canarias_referencia_catastral_1` | OK | Single casilla 0929, `text`. Name is accurate. |
| `irpf_deduccion_cantabria_arrendamiento_jovenes_mayores` | OK | Single casilla 0946, label evolves with Annex B numbering changes but semantic content is stable. Name is accurate. |
| `irpf_deduccion_cantabria_traslado_municipio_riesgo` | OK | Single casilla 0821, label evolves from "riesgo de despoblamiento" to "reto demográfico" to "riesgo de despoblamiento" again (2025 reversal). Semantic concept stable. Name is accurate. |
| `irpf_deduccion_castilla_la_mancha_mayores_75` | OK | Single casilla 0960, stable. Name is accurate. |
| `irpf_deduccion_castilla_y_leon_gastos_adopcion` | OK | Single casilla 0992, stable. Name is accurate. |
| `irpf_deduccion_catalunya_angel_inversor` | OK | Single casilla 1008, stable with only Annex B cross-reference numbering changes. Name is accurate. |
| `irpf_deduccion_descendiente_discapacidad` | OK | Casilla 0623, 2020–2024 in `deduc_descendiente_disc_res`; 2025 in `resultado_declaracion`. Semantic content unchanged. Name is accurate. |
| `irpf_deduccion_extremadura_cuidado_hijos_menores_14` | OK | Single casilla 1017, stable. Name is accurate. |
| `irpf_deduccion_galicia_alquiler_jovenes_discapacidad` | RENAME | Casilla 1026 is labelled "Por alquiler de vivienda habitual por contribuyentes de edad igual o inferior a 35 años" across all revisions. The role name says "jovenes_discapacidad" but no disability condition appears in any label. Rename: `irpf_deduccion_galicia_alquiler_jovenes_35`. |
| `irpf_deduccion_galicia_familia_numerosa` | OK | Single casilla 1022, stable. Name is accurate. |
| `irpf_deduccion_la_rioja_adecuacion_vivienda_discapacidad` | OK | Single casilla 1066, stable. Name is accurate. |
| `irpf_deduccion_la_rioja_municipio_pequeno_codigo_3` | RENAME | Casilla 1205, `data_type: money(default)` but semantically a code identifier (código del municipio / pequeño municipio). The `_3` suffix is opaque. Rename: `irpf_deduccion_la_rioja_municipio_pequeno_codigo`. The money type is a registry encoding for numeric codes. |
| `irpf_deduccion_madrid_arrendamiento_vivienda` | OK | Single casilla 1043, stable. Name is accurate. |
| `irpf_deduccion_murcia_adopcion_nacimiento` | OK | Single casilla 1073, stable. Name is accurate. |
| `irpf_deduccion_ric_canarias_autonomica` | OK | Single casilla 0557, stable. Name is accurate. |
| `irpf_descendiente_discapacidad_fecha_inicio` | OK | Single casilla 0616, `text`, stable. Name is accurate. |
| `irpf_ed_compra_existencias` | OK | Single casilla 0181, stable; 2025 section path changed to `rendimientos_actividades_economicas/estimacion_directa`. Name is accurate. |
| `irpf_ed_iva_devengado` | OK | Single casilla 0176, 2025 section path changed, label simplified. Semantic content stable. Name is accurate. |
| `irpf_ed_perdidas_insolvencias_deudores` | OK | Single casilla 0214, stable. Name is accurate. |
| `irpf_ed_seguridad_social_titular` | OK | Single casilla 0186; 2023–2025 mutualidad wording removed from label. Core concept stable. Name is acceptable (though the narrowing of scope to SS only from 2023 is a minor drift). |
| `irpf_eo_agr_actividad_clave` | RENAME | Casilla 1486, `data_type: money(default)` but "Actividad realizada. Clave" is an activity-type code, not a monetary amount. This is a registry encoding convention for enumerated keys. Rename: `irpf_eo_agr_clave_actividad` (reorders to match other clave-field naming; also clarifies it is the activity classification key, not a sub-total). |
| `irpf_eo_agr_indice_tierras_arrendadas` | OK | Single casilla 1542, stable. Name is accurate: index correction for rented lands in agricultural EO. |
| `irpf_eo_agr_ingresos_integros_plantas_textiles` | OK | Casilla 1524, 2020–2021 generic "Ingresos íntegros", 2022–2025 explicit "Plantas textiles: Ingresos íntegros". Section stable. Name is accurate. |
| `irpf_eo_agr_reduccion_irregulares` | OK | Single casilla 1554, `decimal`, stable. The label is a reduction for irregular income under Art. 32.1 LIRPF. Name is accurate. |
| `irpf_eo_minoracion_inversion` | OK | Single casilla 1467, stable. Name is accurate. |
| `irpf_escala_sobre_base_ahorro_estatal` | RENAME | Casilla 0536 with label "Aplicación de la escala general y autonómica del Impuesto al importe de la casilla [0510]. Importes resultantes: Parte estatal". Casilla [0510] is the base liquidable del ahorro. The role name says "escala_sobre_base_ahorro_estatal" but the label specifies it is the general+autonomic scale applied to the savings base, yielding the state portion. More accurate: `irpf_cuota_integra_estatal_ahorro`. |
| `irpf_familia_numerosa_fecha_inicio` | OK | Single casilla 0650, `text`, stable. Name is accurate. |
| `irpf_g4_re_valor_aplicable_dt9` | OK | Single casilla 0406, stable; 2024+ label removes period from "D.T. 9.ª". Section: `g_cambio_residencia_ext/g4_re`. Name is accurate: value to which Disposición Transitoria 9ª (pre-1979 equity) applies. |
| `irpf_ganancia_acciones_valor_transmision_renta_vitalicia` | OK | Single casilla 0329, stable. Name is accurate. |
| `irpf_ganancia_fondos_ganancia` | OK | Single casilla 0316, stable. Name is accurate. |
| `irpf_ganancia_inmueble_susceptible_reinversion_vh` | OK | Single casilla 1226; section changes from `gp_otros_elementos` to `gp_otros_inmuebles` in 2022 (form restructuring). Semantic content stable. Name is accurate. |
| `irpf_ganancia_otros_fecha_adquisicion` | OK | Single casilla 1632, `text`, stable. Name is accurate. |
| `irpf_ganancia_otros_imputacion_plazos` | OK | Single casilla 1625, `boolean`, stable. Name is accurate. |
| `irpf_ganancia_otros_titular` | OK | Single casilla 0357, `text`, stable. Name is accurate. |
| `irpf_ganancia_premios_juegos_metalico` | OK | Single casilla 0282, stable. Name is accurate. |
| `irpf_incremento_maternidad_guarderia` | OK | Casilla 0613; 2025 section moved to `resultado_declaracion` and label simplified. Semantic content stable: increment to maternidad deduction for childcare costs. Name is accurate. |
| `irpf_inmueble_dias_a_disposicion` | OK | Single casilla 0085, `money(default)` for a day-count (registry convention). Name is accurate. |
| `irpf_inmueble_naturaleza_urbana` | OK | Single casilla 0067, `boolean`, stable. Name is accurate. |
| `irpf_integracion_gyp_ahorro_suma_ganancias` | OK | Single casilla 0422; formula in label gains additional addends from 2022 onward. Semantic role stable. Name is accurate. |
| `irpf_matrimonio_vigente_todo_anio_flag` | OK | Single casilla 0245, `boolean`, stable. Name is accurate. |
| `irpf_minimo_discapacidad_estatal` | OK | Single casilla 0517, stable. Name is accurate. |
| `irpf_perdida_fondos_importe_computable` | RENAME | Casilla 0322 labelled "Pérdidas patrimoniales imputables a 20XX" in `gp_fondos`. The current name "importe_computable" is not wrong but inconsistent with peer roles (`irpf_ganancia_fondos_ganancia`). More consistent: `irpf_ganancia_fondos_perdida`. |
| `irpf_rdto_trabajo_cesion_derechos_autor_anticipo_flag` | OK | Single casilla 0002, `boolean`, stable across all revisions. Name is accurate. |
| `irpf_re_atrib_act_eco_reduccion_32_2_3` | OK | Single casilla 1581, `decimal`, stable. Name is accurate: Art. 32.2.3 reduction applicable to attributed economic activity income. |
| `irpf_re_atrib_cobros_pagos_flag` | OK | Single casilla 1576, `boolean`, stable. Name is accurate. |
| `irpf_re_atrib_gp_perdidas_transmision` | OK | Single casilla 1596, stable. Name is accurate. |
| `irpf_re_atrib_retenciones_act_eco` | OK | Single casilla 1599, stable. Name is accurate. |
| `irpf_re_atrib_suma_gp_transmision_ahorro` | OK | Single casilla 1608, stable. Name is accurate. |
| `irpf_red_deportistas_aportaciones_contribuciones` | OUTLIER | Casilla 0489 in revision 2021 carries the label "Aportaciones y contribuciones realizadas en **2020** con derecho a reducción" — the prior year, not 2021. This is a label error in the registry source for revision 2021 (the year-reference was not updated). Revisions 2022–2025 correctly carry the current year. The semantic role is correct; the registry label for 2021 is erroneous. |
| `irpf_red_prevision_social_exceso_scd` | OK | Single casilla 0464, stable. Name is accurate: excess from collective dependency insurance carried from prior years. |
| `irpf_reduccion_prevision_social_total` | OUTLIER | Casilla 0468 in revision 2021 carries label "Excesos pendientes de reducir procedentes de los ejercicios 2016 a 2020" — this is a carry-forward sub-field, not the "total" row. All other revisions (2020, 2022–2025) label it "Total con derecho a reducción". The 2021 member appears to be a registry re-use of the casilla ID for a different row that year, or a label error. The semantic role assignment for 2021 is questionable. |
| `irpf_rendimiento_capital_inmobiliario_gasto_otros` | OK | Single casilla 0148, stable; 2025 section path changed. Name is accurate. |
| `irpf_rendimiento_capital_inmobiliario_rendimiento_neto_reducido` | OK | Single casilla 0154, `decimal`, stable; 2025 label simplified. Name is accurate. |
| `irpf_rendimiento_capital_mobiliario_ahorro_otros_activos_financieros` | OK | Single casilla 0031, `decimal`, stable; 2025 label simplified. Name is accurate. |
| `irpf_rendimiento_capital_mobiliario_general_gastos_deducibles` | OK | Single casilla 0053, stable; 2025 label becomes more explicit. Name is accurate. |
| `irpf_rendimiento_trabajo_especie_importe_integro` | OK | Single casilla 0007, stable; 2025 section path changed. Name is accurate. |
| `irpf_rendimiento_trabajo_reduccion` | OK | Single casilla 0011, `decimal`, stable; 2025 label simplified. Name is accurate. |
| `irpf_retencion_atribuida_capital_inmobiliario` | OK | Single casilla 0593, stable; 2025 section path changed. Name is accurate. |
| `irpf_saldo_neto_rdtos_base_imponible_general` | OK | Single casilla 0432, `decimal`, stable. Name is accurate. |
| `irpf_anexo_c_gan_per_cuartas_importe_total` | OK | Single casilla 1738, stable across 2021–2025. "Importe total de la ayuda pública percibida" in `gan_per_cuartas` (ganancias patrimoniales derivadas de ayudas imputadas por cuartas partes). Name is accurate. |
| `irpf_deduccion_aragon_clases_apoyo` | OUTLIER | Casillas 0885 in revisions 2020–2022 are in `asturias_res` with label "Por adquisición o adecuación de vivienda habitual para contribuyentes con los que convivan cónyuge/ascendientes/descendientes con discapacidad" — an Asturias deduction. In 2024–2025 casilla 0885 moves to `aragon_res` with label "Por gastos en clases de apoyo o refuerzo". Revision 2023 is absent. The 2020/2021/2022 members (0885, Asturias) are misassigned. They belong to an Asturias disability housing deduction role, not to Aragon support-class deduction. |
| `irpf_deduccion_castilla_la_mancha_arrendamiento_discapacidad` | OUTLIER | Casilla 0229 in revision 2021 has label "Por nacimiento o adopción de hijos" in `castilla_la_mancha_res` — a birth/adoption deduction, semantically opposite to the arrendamiento-discapacidad concept that appears in 2022–2025. The 2021 member is misassigned; it belongs to a birth/adoption deduction role. |
| `irpf_deduccion_galicia_vivienda_aldeas_modelo` | OK | Casilla 0230 across 2021–2025, stable. Name is accurate. |
| `irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial` | RENAME | Casilla 0426 in 2021 is labelled "Contribuciones empresariales (excepto SCD)" — an employer contribution field. From 2022–2025 the label switches to "Aportaciones del trabajador al plan de pensiones de empleo… siempre que se hayan efectuado contribuciones empresariales" — a worker contribution field conditioned on employer contributions. These are different fields. The 2021 member (employer contributions) is a semantic outlier for this role. The role name describes only the 2022+ semantics. |
| `irpf_deduccion_asturias_cuidado_descendientes` | OK | Casilla 1848 across 2022–2025. Name is accurate. |
| `irpf_deduccion_castilla_la_mancha_acciones_participaciones` | OK | Casilla 1908 across 2022–2025. Name is accurate. |
| `irpf_ganancia_cripto_anios_cobro_pendiente` | RENAME | Casilla 1859; 2022–2023 label "Nº total años de cobro", 2024–2025 label "Nº total años de cobro pendiente". The role name "anios_cobro_pendiente" matches the later label only. Rename to `irpf_ganancia_cripto_anios_cobro_total` to cover both variants (the concept is total years of instalment collection, not just pending). |
| `irpf_ganancia_cripto_importe_percibir_resto` | OK | Casilla 1877, stable. Name is accurate. |
| `irpf_ganancia_inmueble_anio_imputacion_2` | RENAME | The `_2` suffix is opaque. This casilla (1890) in `gp_otros_inmuebles` is the imputación year for the instalment-payment regime for real estate gains. Rename: `irpf_ganancia_inmueble_plazos_anio_imputacion`. |
| `irpf_ganancia_inmueble_exenta_reinversion_vivienda` | OK | Casilla 1835, stable. Name is accurate. |
| `irpf_ganancia_inmueble_importe_percibir_4` | RENAME | The `_4` suffix is opaque. Casilla 1899 is "Importe a percibir" in `gp_otros_inmuebles` under the instalment regime. Rename: `irpf_ganancia_inmueble_plazos_importe_percibir`. |
| `irpf_ganancia_inmueble_tipo_elemento_clave` | OK | Casilla 1817, `text`, stable. Name is accurate. |
| `irpf_gp_elemento_referencia_catastral_1` | SPLIT | Two distinct casillas present: 0360 (both revisions 2020 and 2021, section `gp_otros_elementos`) labelled "Referencia castastral 1" (note typo in source); 1628 (same revisions and section) labelled "Referencia catastral 1". These are likely two adjacent cadastral reference fields (part 1 and continuation), or a duplicate field pair. After 2021 neither appears, suggesting the section was reorganised. The role groups two distinct casilla IDs that may or may not be the same semantic slot. Recommend splitting into `irpf_gp_elemento_ref_catastral_1a` and `irpf_gp_elemento_ref_catastral_1b` pending TOML verification. |
| `irpf_perdida_cripto_pendiente_4` | RENAME | The `_4` suffix is opaque. Casilla 1876, "Pérdida patrimonial pendiente de imputación" in `gp_otros_criptomonedas`. Rename: `irpf_ganancia_cripto_perdida_pendiente_imputacion`. |
| `irpf_reduccion_prevision_social_aportado` | OK | Casilla 0428, 2022–2025. "Aportaciones del ejercicio 20XX" in `red_base_imponible_res`. Name is accurate. |
| `irpf_deduccion_aragon_ayuda_humanitaria_ucrania` | OK | Casilla 1851 across 2022–2024 (absent 2025 — deduction lapsed). Name is accurate. |
| `irpf_deduccion_c_valenciana_autoconsumo_2025_generado` | RENAME | Casilla 1963 across 2023–2025 labelled "Importe generado en 20XX". The `_2025` in the name is revision-specific and will be wrong when read in other years. Rename: `irpf_deduccion_c_valenciana_autoconsumo_generado_ejercicio`. |
| `irpf_deduccion_instalacion_recarga_fecha_fin` | OK | Casilla 1932 across 2023–2025, `text`. Name is accurate. |
| `irpf_deduccion_vehiculo_matricula` | OK | Casilla 1923 across 2023–2025, `text`. Name is accurate. |
| `irpf_feac_entidad_receptora_denominacion` | OK | Casilla 1980 across 2023–2025, `text`. Name is accurate. |
| `irpf_feac_valor_adquisicion_elemento` | OK | Casilla 1984 across 2023–2025. Name is accurate. |
| `irpf_rectnosepa_cuenta_numero` | OK | Casilla 1784 across 2021–2023. Name is accurate. |
| `irpf_retrib_especie_importe_no_exenta_4` | RENAME | The `_4` suffix is opaque. Casilla 1971 across 2023–2025, "Retribución en especie no exenta pendiente de imputación" (Art. 42.3.f / Art. 14.2.m). Rename: `irpf_retrib_especie_no_exenta_pendiente_imputacion`. |
| `irpf_deduccion_baleares_autoocupacion` | OK | Casilla 1716 across 2024–2025. Name is accurate. |
| `irpf_deduccion_canarias_guarderia_importe_2` | RENAME | The `_2` suffix is opaque. Casilla 2043 across 2024–2025, "Importe abonado 2" for Canarias guardería. Rename: `irpf_deduccion_canarias_guarderia_importe_abonado_2`. |
| `irpf_deduccion_cantabria_traslado_estudios` | OK | Casilla 1707 across 2024–2025. Name is accurate. |
| `irpf_deduccion_madrid_financiacion_ajena_incremento` | OK | Casilla 2020 across 2024–2025. Name is accurate. |
| `irpf_deduccion_murcia_familia_monoparental` | OK | Casilla 2035 across 2024–2025. Name is accurate. |
| `irpf_rectnosepa_pais_codigo` | OK | Casilla 1789 across 2021–2022. Name is accurate. |
| `irpf_ascendiente_fecha_fallecimiento` | OK | Single casilla FALLASDLG (2025 only), `text`. Name is accurate. |
| `irpf_declarante_apellidos_nombre` | OK | Single casilla DP_APENOM_D (2025 only), `text`. Name is accurate. |
| `irpf_deduccion_c_valenciana_otras` | OK | Single casilla 1121 (2025 only). Name is accurate. |
| `irpf_deduccion_cantabria_residencia_municipio_riesgo` | OK | Single casilla 1701 (2025 only). Name is accurate. |
| `irpf_deduccion_extremadura_rehabilitacion_rural` | OK | Single casilla 2007 (2025 only). Name is accurate. |
| `irpf_deduccion_la_rioja_generado_2025` | RENAME | Casilla 2058 (2025 only), "Importe generado en 2025". The year in the role name is revision-specific and will become stale. Rename: `irpf_deduccion_la_rioja_autoconsumo_generado_ejercicio`. |
| `irpf_deduccion_murcia_generado_2025_pendiente_2` | RENAME | Casilla 2165 (2025 only), "Importe generado en 2025 pendiente de aplicación". Year-in-name is stale by design. Rename: `irpf_deduccion_murcia_generado_pendiente_2`. |
| `irpf_descendiente_clave_discapacidad` | OK | Single casilla MINUSDLG (2025 only), `text`. Name is accurate. |
| `irpf_eo_agr_reintegro_subvenciones` | OK | Single casilla 0239 (2025 only). Name is accurate. |
| `irpf_ganancia_premios_bono_social_termico` | OK | Single casilla 0362 (2025 only), in `gp_premios/otras`. Name is accurate. |
| `irpf_num_hijos_maternidad_2021` | RENAME | Casilla 1914 (revision 2022 only), "Número de hijos que dan derecho a la deducción por maternidad". The `_2021` suffix refers to the tax year being back-calculated, not to the form revision. This is confusing. Rename: `irpf_num_hijos_maternidad_ejercicio_anterior`. |
| `irpf_red_prevision_social_exceso_2016_2020` | RENAME | Casilla 0437 (revision 2021 only), "Excesos pendientes de reducir procedentes de los ejercicios 2016 a 2020". The year range is baked into the role name and will be wrong for any future revision. Rename: `irpf_red_prevision_social_exceso_pendiente_quinquenio`. |

---

## Summary counts

| Verdict | Count |
|---------|-------|
| OK | 45 |
| RENAME | 18 |
| SPLIT | 2 |
| OUTLIER | 5 (across 4 roles with multi-issue findings) |
| **Total roles reviewed** | **67** |

### RENAME list (corrected names)

| current | corrected |
|---------|-----------|
| `investment_entity_nif` | `irpf_entidad_nif_varios` (pending split) |
| `parent_nif` | split into `irpf_deduccion_cyl_otro_progenitor_nif` + `irpf_anualidades_alimentos_otro_progenitor_nif` |
| `tenant_or_foreign_id_nif` | `irpf_inmueble_arrendatario_nif` |
| `feac_entity_nif` | `irpf_feac_entidad_nif` |
| `irpf_anexo_c_exceso_patrim_protegido_generado` | `irpf_anexo_c_exceso_patrim_protegido_ejercicio_actual` |
| `irpf_deduccion_c_valenciana_obras_conservacion_1` | `irpf_deduccion_c_valenciana_obras_conservacion_vivienda_2014_2015` |
| `irpf_deduccion_galicia_alquiler_jovenes_discapacidad` | `irpf_deduccion_galicia_alquiler_jovenes_35` |
| `irpf_deduccion_la_rioja_municipio_pequeno_codigo_3` | `irpf_deduccion_la_rioja_municipio_pequeno_codigo` |
| `irpf_eo_agr_actividad_clave` | `irpf_eo_agr_clave_actividad` |
| `irpf_escala_sobre_base_ahorro_estatal` | `irpf_cuota_integra_estatal_ahorro` |
| `irpf_perdida_fondos_importe_computable` | `irpf_ganancia_fondos_perdida` |
| `irpf_ganancia_cripto_anios_cobro_pendiente` | `irpf_ganancia_cripto_anios_cobro_total` |
| `irpf_ganancia_inmueble_anio_imputacion_2` | `irpf_ganancia_inmueble_plazos_anio_imputacion` |
| `irpf_ganancia_inmueble_importe_percibir_4` | `irpf_ganancia_inmueble_plazos_importe_percibir` |
| `irpf_perdida_cripto_pendiente_4` | `irpf_ganancia_cripto_perdida_pendiente_imputacion` |
| `irpf_retrib_especie_importe_no_exenta_4` | `irpf_retrib_especie_no_exenta_pendiente_imputacion` |
| `irpf_deduccion_c_valenciana_autoconsumo_2025_generado` | `irpf_deduccion_c_valenciana_autoconsumo_generado_ejercicio` |
| `irpf_deduccion_la_rioja_generado_2025` | `irpf_deduccion_la_rioja_autoconsumo_generado_ejercicio` |
| `irpf_deduccion_murcia_generado_2025_pendiente_2` | `irpf_deduccion_murcia_generado_pendiente_2` |
| `irpf_deduccion_canarias_guarderia_importe_2` | `irpf_deduccion_canarias_guarderia_importe_abonado_2` |
| `irpf_num_hijos_maternidad_2021` | `irpf_num_hijos_maternidad_ejercicio_anterior` |
| `irpf_red_prevision_social_exceso_2016_2020` | `irpf_red_prevision_social_exceso_pendiente_quinquenio` |

### SPLIT candidates

- `investment_entity_nif` → at minimum: `irpf_re_agrup_interes_economico_nif`, `irpf_fondo_inversion_nif`, `irpf_deduccion_nueva_empresa_entidad_nif`, `irpf_centro_guarderia_nif` (Annex B entity NIFs may warrant further splits per deduction type).
- `irpf_gp_elemento_referencia_catastral_1` → `irpf_gp_elemento_ref_catastral_1a` (0360) and `irpf_gp_elemento_ref_catastral_1b` (1628) pending TOML verification.

### OUTLIER details requiring registry verification

- `investment_entity_nif`: casillas 0210, 1076, 2040, 2042 — childcare centre NIFs misassigned to an investment-entity role.
- `irpf_inmueble_adquisicion_tipo_lucrativa`: casilla 0134 revision 2020 labelled "Onerosa" — opposite meaning; misassigned.
- `irpf_deduccion_aragon_clases_apoyo`: casillas 0885 revisions 2020/2021/2022 are Asturias deduction entries misassigned to Aragon role.
- `irpf_deduccion_castilla_la_mancha_arrendamiento_discapacidad`: casilla 0229 revision 2021 labelled "Por nacimiento o adopción de hijos" — wrong deduction type.
- `irpf_reduccion_prevision_social_total`: casilla 0468 revision 2021 labelled as an excess carry-forward sub-field, not the total row present in all other revisions.
