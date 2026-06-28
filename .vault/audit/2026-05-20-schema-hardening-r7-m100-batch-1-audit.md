---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m100 batch-1 semantic audit

## Scope

Semantic-correctness review of 123 `semantic_role` values from the M100 IRPF batch-1 role
inventory, covering revisions 2020-2025. Each role was judged by reading all member labels
and sections. Id-reuse across revisions (same casilla id carrying a different concept in a
different revision year) is expected by design and is not flagged as a defect.

Criteria per role:
1. **Name accuracy** — does the role string accurately describe what the casillas capture?
2. **Member coherence** — do all members share one concept or are there misassigned outliers?
3. **Granularity** — is the grouping acceptably precise, or does it conflate distinct concepts?

---

## Findings

| role | verdict | detail |
|------|---------|--------|
| `irpf_anexo_a_aeip_aplicado` | RENAME | All 315 members are "applied in this declaration" amounts for named cultural/sporting/social patronage events (Anexo A, Art. 27 Ley 49/2002 deducciones AEIP — Acontecimiento de Interés Público). The abbreviation `aeip` is correct but `aplicado` alone does not distinguish this from other applied-deduction slots. Rename to `irpf_anexo_a_aeip_deduccion_aplicada` to clarify it is the applied-amount field, not a base or pending field. |
| `irpf_inmueble_valor_catastral` | SPLIT | Three distinct casilla ids per revision (0083, 0123, 0138) inside the same section. Label is identical ("Valor catastral") but 0083 is the principal property, 0123 is the second property (arrendado/cedido), and 0138 is the accesorio. These are three separate property slots on the form and carry independent fiscal significance. Recommend `irpf_inmueble_principal_valor_catastral`, `irpf_inmueble_arrendado_valor_catastral`, `irpf_inmueble_accesorio_valor_catastral`. |
| `irpf_anexo_a_inversion_importe_deduccion_base` | RENAME | Members 0831/0834 are the deductible investment base amounts (rendimientos netos invested in new productive elements — Art. 68.2 LIRPF). In 2020-2021 the field tracked "porcentaje de deducción" but from 2022 onward it was relabelled "importe con derecho a deducción". The role name is accurate; minor improvement: rename to `irpf_anexo_a_inversion_base_deduccion` to use the canonical Spanish ordering. |
| `irpf_inmueble_mejoras_previas` | SPLIT | Contains two semantically distinct slots: 0128 ("mejoras años anteriores en inmueble principal") and 0143 ("mejoras años anteriores en inmueble accesorio"). Both span all revisions. These are separate fiscal amounts for different immovables. Recommend `irpf_inmueble_mejoras_anios_anteriores` (0128) and `irpf_inmueble_accesorio_mejoras_anios_anteriores` (0143). |
| `irpf_anexo_a_obra_fecha_inicio` | SPLIT | Contains two slots per revision: 0683 ("Fecha de inicio de las obras" — first obra) and 0691 ("Fecha de inicio de las obras" — second obra). These are separate construction start-date records for two independent rehabilitation works under the housing deduction. Recommend `irpf_anexo_a_obra_1_fecha_inicio` and `irpf_anexo_a_obra_2_fecha_inicio`. |
| `irpf_anexo_a_rib_dotacion_anio` | SPLIT | Members span two entirely different reservas: "Reserva para Inversiones en Canarias" (id 1682, 2023-2024) and "Reserva para Inversiones en las Illes Balears" (ids 1781/1938, 2023-2025). These are separate tax regimes in separate sections. Cross-revision id-reuse means 1682 maps to Canarias in 2023-2024 but to Baleares from 2025. The role should be split: `irpf_ric_dotacion_anio` (RIC — Canarias) and `irpf_rib_dotacion_anio` (RIB — Illes Balears). |
| `irpf_deduccion_castilla_y_leon_nacimiento_adopcion` | OUTLIER | 2020 includes id 0991 with label "Por paternidad" — a distinct deduction for paternity (now abolished in Castilla y León after 2020). Ids 0986 ("Por nacimiento o adopción de hijos") carry the target role correctly across all revisions. Outlier: id 0991 revision 2020 — actually `irpf_deduccion_castilla_y_leon_paternidad`. |
| `irpf_deduccion_castilla_y_leon_rehabilitacion_rural` | OUTLIER | 2020 id 0980 has label "Deducción para el fomento de emprendimiento" and 2021 id 0980 has "Para el fomento de emprendimiento". From 2022 onward, id 0980 is "Por inversión en rehabilitación de viviendas destinadas al alquiler en núcleos rurales". This is classic id-reuse across revisions (expected), not a defect. However, the role name `irpf_deduccion_castilla_y_leon_rehabilitacion_rural` only accurately describes 2022-2025. The 2020-2021 entries are a different deduction concept reusing the same casilla slot. Flag as OUTLIER for 0980 revisions 2020 and 2021, which are `irpf_deduccion_castilla_y_leon_fomento_emprendimiento`. |
| `irpf_deduccion_la_rioja_guarderia_municipio_codigo` | OUTLIER | 2020 id 1071 label is "Importe de la deducción" (a money amount), while 2021-2025 id 1071 is "Código del municipio" (a code value). This is id-reuse: in 2020 the slot held the deduction amount; from 2021 it was repurposed for the municipality code. Outlier: id 1071 revision 2020 — actually `irpf_deduccion_la_rioja_guarderia_importe`. The role name is accurate for 2021-2025. |
| `irpf_deduccion_la_rioja_otras` | RENAME | Members 1082 (2020) and 1082 (2024) both carry "Otras deducciones" but span a gap of four years with no members in 2021-2023. Revisions 2021-2023 presumably removed or moved this slot. Name is acceptable; flag that the four-revision gap should be verified against the 2021-2023 registry. No rename needed if registry confirms absence. Mark OK pending registry confirmation. |
| `irpf_intereses_demora_perdida_deduccion_autonomica_2` | RENAME | In 2020-2021, id 0581 is labelled "Parte estatal" (state portion of surcharge interest on forfeited deductions). From 2022 onward, the same id is labelled "Parte autonómica" (regional portion). This is a conceptual shift mid-series — the suffix `_2` is opaque. Rename to `irpf_intereses_demora_perdida_deduccion_autonomica` and document that 2020-2021 held the state portion (id-reuse shifted it to autonomic). RENAME to drop the `_2` suffix which carries no tax meaning. |
| `irpf_cuota_integra_autonomica` | RENAME | Similar pattern: 2020-2021 id 0546 labelled "Cuota íntegra autonómica: Parte estatal"; from 2022 it is "Parte autonómica". The role name `irpf_cuota_integra_autonomica` accurately describes the concept (the autonomic gross tax charge), but 2020-2021 members were filed under the state-portion column of the form. This is a known form-restructuring. Role name is semantically accurate for the concept. OK. |
| `irpf_eo_agr_ingresos_integros_forestal_corta_corta` | RENAME | In 2020-2021, id 1509 label is simply "Ingresos íntegros" without the forestry qualifier. From 2022 onward the label specifies "Actividades forestales con período medio de corta igual o inferior a 30 años: Ingresos íntegros". The role name encodes the specific forestry qualifier ("corta_corta" = short cutting cycle), which only appears in the label from 2022. The 2020-2021 entries are the same casilla but the label was generic for all agricultural activity types. Acceptable as the underlying tax concept is consistent; the label was clarified not changed. OK. |
| `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022` | RENAME | 2021 id 1114 carries a different label ("Importe total de la deducción") from all other years — it captured an aggregated total, not the autoconsumo investment specifically. 2020 and 2022 labels refer to autoconsumo energy installations; 2023+ explicitly call it "cantidades invertidas hasta 2022". The 2021 member is a different semantic: an aggregate subtotal, not the autoconsumo slot. OUTLIER: id 1114 revision 2021 is `irpf_deduccion_c_valenciana_total_deduccion` (aggregate). |
| `irpf_deduccion_c_valenciana_generado_2024_pendiente_2` | RENAME | Members track "importe generado en año N pendiente de aplicación" where N shifts each revision. Role name encodes `_2024_` which is only true for revision 2025. This is a rolling-year pending amount for the autoconsumo/renewable energy deduction. Rename to `irpf_deduccion_c_valenciana_autoconsumo_pendiente_2` to remove the year encoding from the stable role identifier. |
| `irpf_deduccion_c_valenciana_generado_2025_pendiente_2` | RENAME | Same pattern as above for the next year's pending amount. Rename to `irpf_deduccion_c_valenciana_autoconsumo_pendiente_3` (or `_pendiente_anio_n_2` using positional notation) to remove the year from the role string. |
| `irpf_ganancia_premios_ayuda_alquiler` | RENAME | In 2020-2021, id 0303 is "Renta básica de emancipación" (a youth housing grant). From 2022 onward it is "Ayudas públicas al alquiler" (public rental assistance). These are two distinct social programmes occupying the same casilla slot across revisions (id-reuse). The role name matches the 2022-2025 concept. The 2020-2021 entries are a different concept. OUTLIER: id 0303 revisions 2020 and 2021 are `irpf_ganancia_premios_renta_basica_emancipacion`. |
| `irpf_ganancia_premios_otras_ganancias` | OK | All members are "Otras ganancias y/o pérdidas patrimoniales imputables a año N: Importe ganancias". Year suffix varies as expected across revisions. Role name accurately describes the gain-amount slot in the premios/otras section. |
| `irpf_re_imagen_primera_cesionaria` | RENAME | All members correctly capture NIF/denomination of the first licensee of image rights (régimen especial derechos de imagen, Art. 92 LIRPF). However, the field also holds the entity's denomination (not only NIF). Rename to `irpf_re_imagen_primera_cesionaria_nif_o_denominacion` for accuracy, or keep as is if the _cesionaria suffix is understood as an entity identifier. Minor: OK is acceptable. |
| `irpf_re_atrib_cap_mob_minoraciones` | RENAME | All members "Minoraciones aplicables" in the atribución de rentas — capital mobiliario subsection. "Minoraciones" is the correct tax term. The role name does not specify what type of minoración (it is specific to capital mobiliario). RENAME to `irpf_re_atrib_cap_mob_minoraciones_aplicables` for explicitness, though current name is defensible. Minor issue; OK is acceptable. |
| `irpf_re_atrib_gp_exentas_50pct` | OK | "Ganancias exentas 50 por 100 (sólo determinados inmuebles urbanos)" — the 50% gain exemption for urban real estate (DT 9ª applied in atribución de rentas context). Consistent across all revisions. Role name accurately encodes the concept. |
| `irpf_re_atrib_suma_cap_mob_gral` | OK | "Suma de rendimientos netos de capital mobiliario (a integrar en la B.I. general), atribuidos" — correct aggregation total for attributed general-base capital income. Consistent across all revisions. |
| `irpf_re_aie_suma_bases_imponibles` | OK | "Suma de bases imponibles imputadas" from AIE (Agrupaciones de Interés Económico). Consistent label and section across all six revisions. |
| `irpf_re_atrib_inmueble_ref_catastral` | OK | "Referencia catastral" in the atribución de rentas — inmueble subsection. Consistent. |
| `irpf_ascendiente_cede_flag` | RENAME | Label is "Indique si cede el derecho a la deducción y en su caso el NIF del beneficiario". This is a flag+NIF combined field, not purely a boolean flag. Rename to `irpf_ascendiente_cede_deduccion_y_nif_beneficiario` or keep `_flag` if the registry treats it as a boolean trigger. Minor; current name misleads on content because it may hold a NIF string. RENAME recommended to `irpf_ascendiente_discapacidad_cede_flag`. |
| `irpf_familia_numerosa_categoria_especial_flag` | OK | Checkbox for "Especial" category of large family, consistent across all revisions. |
| `irpf_inmueble_arrendamiento_reduccion_flag` | OK | Mark-X flag for Art. 23.2 reduction entitlement. Consistent. |
| `irpf_inmueble_fecha_contrato_arrendamiento` | OK | Rental contract date, consistent across all revisions. |
| `irpf_inmueble_uso_residencia_separacion` | OK | Flag for property occupied by children/ex-spouse under separation/divorce. Consistent. |
| `irpf_deduccion_familia_numerosa` | RENAME | 2020-2024 id 0660 is in section `calculo_impuesto_res/deduc_familia_numerosa_res` with label "Importe de la deducción". 2025 id 0660 is in section `resultado_declaracion` with label "Deduccion por familia numerosa". The concept is the same but in 2025 it moved to a top-level result section. This is a section-reorganisation, not a semantic change. Role name is accurate. OK. |
| `irpf_deduccion_interes_cultural_autonomica` | OK | "Por inversiones o gastos de interés cultural — Parte autonómica". Consistent across all revisions. |
| `irpf_deduccion_empresa_nueva_creacion` | OK | Deduction for investment in new/recently created enterprises (Art. 68.1 LIRPF) — state portion. Consistent. |
| `irpf_deducciones_autonomicas_suma` | OK | Aggregate of all autonomic deductions transferred from the applicable Annex B. Label wording varies as new Annexes B.7, B.8, etc. were added across years but the aggregation concept is identical. |
| `irpf_deduccion_andalucia_acciones_participaciones` | OK | Investment in shares/participations under Andalucía's regional deduction. Consistent. |
| `irpf_deduccion_andalucia_familia_monoparental` | OK | Single-parent family deduction (Andalucía). Consistent. |
| `irpf_deduccion_aragon_inversion_entidades_cotizadas` | OK | Investment in MAB-listed entities (Aragón). Consistent. |
| `irpf_deduccion_asturias_arrendamiento_vivienda` | OK | Rental of primary residence (Asturias). Consistent. |
| `irpf_deduccion_asturias_fallecimiento_progenitor` | OK | Deduction for dependents when a parent died in a workplace accident (Asturias). Consistent. |
| `irpf_deduccion_asturias_enfermedad_celiaca` | OK | New 2025 deduction for celiac disease expenses (Asturias). Single-revision; role name accurate. |
| `irpf_deduccion_baleares_acciones_participaciones` | OK | Investment in new/recently created entities (Illes Balears). Consistent. |
| `irpf_deduccion_baleares_estudios_superiores` | OK | Higher-education study expenses away from home island (Illes Balears). Consistent. |
| `irpf_deduccion_baleares_prestamo_hipotecario_incremento` | OK | Compensation for variable-rate mortgage cost increase (Illes Balears, 2022-2024). Consistent. |
| `irpf_deduccion_canarias_acogimiento_menores` | OK | Foster care for minors (Canarias). Consistent. |
| `irpf_deduccion_canarias_familia_monoparental` | OK | Single-parent family (Canarias). Consistent. |
| `irpf_deduccion_canarias_traslado_residencia_isla` | OK | Relocation to another Canary Island for work (Canarias). Consistent. |
| `irpf_deduccion_cantabria_guarderia` | OK | Nursery expenses (Cantabria). Consistent. |
| `irpf_deduccion_cantabria_gastos_educacion` | OK | Education expenses (Cantabria, 2024-2025). Consistent. |
| `irpf_deduccion_cantabria_generado_2025_pendiente` | RENAME | Same rolling-year pattern as C. Valenciana pending amounts. The year `2025` is part of the role name. For 2025 revision, the pending amount generated in 2025 is carried forward. This is a stable casilla for the pending carryforward from the current year. Rename to `irpf_deduccion_cantabria_autoconsumo_pendiente` or a generic pending slot name to remove the year encoding. |
| `irpf_deduccion_castilla_la_mancha_discapacidad_familiar` | OK | Disability of ascendants/descendants (Castilla-La Mancha). Consistent. |
| `irpf_deduccion_castilla_y_leon_donaciones_fundaciones` | OK | Donations to Castilla y León foundations and historical heritage recovery. Consistent. |
| `irpf_deduccion_castilla_y_leon_rehabilitacion_rural` | OUTLIER | As noted above: 0980 revisions 2020-2021 carry "fomento de emprendimiento" (a different deduction). Id-reuse: revisions 2022-2025 are rehabilitation. Outlier: id 0980 revisions 2020 and 2021 are `irpf_deduccion_castilla_y_leon_fomento_emprendimiento`. |
| `irpf_deduccion_catalunya_rehabilitacion_vivienda` | OK | Rehabilitation of primary residence (Catalunya). Consistent. |
| `irpf_deduccion_catalunya_prestamo_identificador` | OK | Loan identifier number for the Catalunya rehabilitation deduction. Consistent 2023-2025. |
| `irpf_deduccion_c_valenciana_guarderia` | OK | Nursery/early childhood education expenditure (C. Valenciana). Consistent (minor label wording update in 2025 does not change the concept). |
| `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022` | OUTLIER | 2021 id 1114 is an aggregate total, not the autoconsumo investment. Outlier: id 1114 revision 2021 — `irpf_deduccion_c_valenciana_total_deduccion`. |
| `irpf_deduccion_c_valenciana_financiacion_ajena_incremento` | OK | Variable-rate mortgage cost increase (C. Valenciana, 2022-2025). Consistent. |
| `irpf_deduccion_c_valenciana_generado_2024_pendiente_2` | RENAME | Remove year encoding. Rename to `irpf_deduccion_c_valenciana_autoconsumo_pendiente_2`. |
| `irpf_deduccion_c_valenciana_generado_2025_pendiente_2` | RENAME | Remove year encoding. Rename to `irpf_deduccion_c_valenciana_autoconsumo_pendiente_3`. |
| `irpf_deduccion_eficiencia_energetica_demanda_anterior` | OK | Pre-improvement energy demand value (calefacción y refrigeración) for the energy-efficiency housing deduction. Consistent 2021-2025. |
| `irpf_deduccion_extremadura_ayudas_subvenciones_ca` | OK | Aid/grants from C.A. Extremadura for ALS patients. Single 2025 revision; role name accurate. |
| `irpf_deduccion_galicia_deportistas_alto_nivel` | OK | Aids/grants to high-performance athletes (Galicia). Consistent. |
| `irpf_deduccion_galicia_subvenciones_danos` | OK | Aid for forest-fire damages (Galicia, 2025). Single revision; role name accurate. |
| `irpf_deduccion_la_rioja_guarderia_municipio_codigo` | OUTLIER | Id 1071 revision 2020: "Importe de la deducción" is the amount, not a municipality code. Outlier: id 1071 revision 2020 is `irpf_deduccion_la_rioja_guarderia_importe`. |
| `irpf_deduccion_la_rioja_vivienda_municipio_importe` | RENAME | Label is only "Importe de la deducción" — very generic. The role name encodes `vivienda_municipio` which is contextual (the La Rioja housing-in-municipality deduction amount). Name is accurate given the section context; OK. |
| `irpf_deduccion_la_rioja_otras` | OK | "Otras deducciones" (La Rioja) — present in 2020 and 2024, absent from 2021-2023 (likely zero or not applicable in those years). Name accurately captures a catch-all residual category. |
| `irpf_deduccion_madrid_nacimiento_adopcion` | OK | Birth/adoption deduction (Madrid). Consistent. |
| `irpf_deduccion_madrid_vivienda_municipio_riesgo_precio` | RENAME | Label is "Precio de adquisición/cantidades invertidas". The role name encodes `riesgo_precio` which implies a risk or reference-price field, but the actual label is the acquisition price or invested amounts for the Madrid at-risk-of-depopulation municipality housing deduction. Rename to `irpf_deduccion_madrid_vivienda_municipio_riesgo_precio_adquisicion` or simply `irpf_deduccion_madrid_vivienda_riesgo_despoblacion_precio`. |
| `irpf_deduccion_murcia_entidades_cotizadas_mab` | OK | MAB-listed entities investment (Murcia). Consistent. |
| `irpf_deduccion_murcia_economia_social` | OK | Investment in social-economy entities (Murcia, 2025). Single revision; role name accurate. |
| `irpf_deduccion_murcia_vehiculo_importe` | RENAME | Label is "Importe de la deducción" — a generic amount field. Role name `irpf_deduccion_murcia_vehiculo_importe` is accurate given the Murcia vehicle deduction context but is the only 2025 member. OK given the sectional context uniquely identifies it. |
| `irpf_deduccion_vehiculo_electrico_categoria` | OK | Vehicle category code for the electric-vehicle purchase deduction (Anexo A, 2023-2025). Consistent. |
| `irpf_ed_amortizacion_inmovilizado_material` | OK | Depreciation allowance for tangible fixed assets in the direct-estimation activity schedule. Consistent across revisions (section path changed in 2025 but concept is identical). |
| `irpf_ed_indemnizaciones` | OK | Redundancy/compensation payments (estimación directa). Consistent. |
| `irpf_ed_otros_gastos_personal` | OK | Other personnel expenses (estimación directa). Consistent. |
| `irpf_ed_reduccion_art_32_2_3` | OK | Reduction for certain economic activities under Art. 32.2.3ª LIRPF (estimación directa). Consistent. |
| `irpf_ed_total_gastos_deducibles_simplificada` | OK | Total deductible expenses in the simplified direct-estimation module. Consistent. |
| `irpf_eo_agr_indice_medios_ajenos` | OK | Corrector index for use of third-party production means in agricultural activities (estimación objetiva). Consistent. |
| `irpf_eo_agr_ingresos_integros_forestal_corta_corta` | OK | Gross income for forestry activities with cutting cycles ≤30 years. Label was generic in 2020-2021 but the concept is the same. |
| `irpf_eo_agr_rdto_neto_previo` | OK | Preliminary net income for agricultural estimación objetiva. Consistent. |
| `irpf_eo_agr_reduccion_gasoleo_agricola` | OK | Agricultural gas-oil purchase reduction (2022-2024). Consistent. |
| `irpf_eo_agr_indice_corrector_mejillon_batea` | OK | Corrector index for mussel-raft production (estimación objetiva agrícola, 2025). Single revision; role name accurate. |
| `irpf_eo_indice_corrector_exceso` | OK | Excess corrector index (estimación objetiva, non-agricultural). Consistent. |
| `irpf_eo_reduccion_art_32_2_3` | OK | Art. 32.2.3ª reduction for estimación objetiva activities. Consistent (parallel to `irpf_ed_reduccion_art_32_2_3` for EO). |
| `irpf_g4_re_ganancia_reducida` | OK | Reduced capital gain under the change-of-residence tax exit rules (G4 section). Consistent. |
| `irpf_ganancia_acciones_reduccion_dt9` | OK | DT9ª reduction applicable to equity gain (acciones section). Consistent. |
| `irpf_ganancia_derechos_valor_adquisicion_global` | OK | Global acquisition value of transmitted subscription rights. Consistent. |
| `irpf_ganancia_fondos_valor_transmision_renta_vitalicia` | OK | Transmission value earmarked for an annuity (fondos section). Consistent. |
| `irpf_ganancia_fondos_coti_valor_transmision_global` | OK | Global transmission value for listed investment funds (2025). Single revision; role name accurate. |
| `irpf_ganancia_otros_anio_imputacion_4` | RENAME | Label is simply "Año de imputación" for the fourth instalment element in gp_otros_elementos. The suffix `_4` is a positional ordinal implying there are 1, 2, 3 as well. If those exist, this is consistent; if this is the only imputación year slot, the `_4` is misleading. Assuming it is the fourth position in a multi-instalment series, name is acceptable. Pending verification against siblings 1, 2, 3. OK if siblings exist with matching naming convention. |
| `irpf_ganancia_otros_importe_percibir_1` | RENAME | First instalment amount to be received (gp_otros_elementos). Same positional note: if siblings `_2`, `_3` exist with consistent naming, OK. The suffix `_1` is a positional ordinal. OK if the series is complete. |
| `irpf_ganancia_otros_reducida_no_exenta_dt9` | OK | Reduced non-exempt gain after DT9ª deduction (otros elementos). Consistent. |
| `irpf_ganancia_otros_transmision_gratuita` | OK | Flag for inter-vivos gratuitous transmission (donation, liberality) — otros elementos, 2021-2025. Consistent. |
| `irpf_ganancia_premios_ayuda_alquiler` | OUTLIER | Id 0303 revisions 2020-2021: "Renta básica de emancipación" — a different social programme. Outlier: id 0303 revisions 2020 and 2021 are `irpf_ganancia_premios_renta_basica_emancipacion`. |
| `irpf_ganancia_premios_otras_ganancias` | OK | Gain amount for other current-year gains/losses (premios/otras section). Consistent. |
| `irpf_ganancia_cripto_anio_imputacion_1` | OK | Year of imputation for cryptocurrency gain instalment 1. Consistent 2022-2025. |
| `irpf_ganancia_cripto_importe_percibir_1` | OK | Amount to be received instalment 1 for crypto gains. Consistent. |
| `irpf_ganancia_cripto_valor_adquisicion` | OK | Acquisition value for crypto asset. Consistent. |
| `irpf_ganancia_inmueble_catastral_2_b` | RENAME | Label "Referencia catastral 2" (with typo "castastral" in label). The `_2_b` suffix is opaque. If this is the second cadastral reference of the immovable, rename to `irpf_ganancia_inmueble_ref_catastral_2`. |
| `irpf_ganancia_inmueble_ganancia_pendiente_resto` | OK | Remaining pending gain (installment deferral) for real-estate capital gain. Consistent. |
| `irpf_ganancia_inmueble_reducida_no_exenta_dt9` | OK | Reduced non-exempt gain after DT9ª for real estate. Consistent. |
| `irpf_ganancia_inmueble_valor_transmision_susceptible_dt9` | OK | Transmission value eligible for DT9ª reduction (real estate). Consistent. |
| `irpf_perdida_cripto_obtenida` | OK | Net crypto loss amount. Consistent. |
| `irpf_perdida_inmueble_pendiente_resto` | OK | Remaining pending loss (deferred) for real-estate capital loss. Consistent. |
| `irpf_perdida_otros_pendiente_3` | RENAME | "Pérdida patrimonial pendiente de imputación" for the third element in gp_otros_elementos. The `_3` suffix is positional. Same note as `irpf_ganancia_otros_anio_imputacion_4`: acceptable if siblings exist. OK if series is complete. |
| `irpf_gp_elemento_situacion_clave` | OK | Property-use key code (Situación. Clave) for other capital-gain elements — present 2020-2021, dropped thereafter (different section structure). Role name is accurate for its scope. |
| `irpf_feac_inmueble_situacion_clave` | OK | Property-use key code in the FEAC (Fusión, Escisión, Aportación, Canje) special regime. Consistent 2023-2025. |
| `irpf_rentas_exentas_base_ahorro` | OK | Exempt income attributable to the savings taxable base. Section path migrated across revisions (2020 in toma_datos_ampliada; 2021+ in resultados) but the concept is stable. |
| `irpf_retencion_trabajo` | OK | Withholding on employment income. Consistent (section path changed in 2025). |
| `retenciones_ingresos_a_cuenta` | RENAME | Role name `retenciones_ingresos_a_cuenta` lacks the `irpf_` prefix required by naming conventions (all other roles use it). The casillas are "Retenciones e ingresos a cuenta" for capital immobiliario (id 0153, all revisions). Rename to `irpf_inmueble_retenciones_ingresos_a_cuenta`. |
| `irpf_compensacion_conyuges_resto_ingresar` | OK | Net amount still payable after spouse compensatory-payment offset. Consistent. |
| `irpf_compensacion_conyuges_swift_bic` | OK | SWIFT/BIC code for non-SEPA transfer in the spousal compensation section. Consistent 2021-2025. |
| `irpf_cuota_integra_autonomica` | OK | As noted above; id-reuse shift from state to autonomic column is expected. |
| `irpf_minimo_contribuyente_autonomico` | OK | Autonomic portion of the personal minimum. Consistent. |
| `irpf_deducciones_autonomicas_suma` | OK | Aggregate autonomic deductions. Consistent. |
| `irpf_red_patrimonio_protegido_discapacidad_exceso` | OK | Excess pending reduction from contributions to protected-heritage funds for disabled persons. Year-range in label shifts by one year each revision (expected rolling window). |
| `irpf_reduccion_prevision_social_aplicada` | OK | Applied reduction for general-regime pension/social provision contributions. Consistent. |
| `irpf_re_especial_tfi_conyuge_num_operaciones` | RENAME | "CONYUGE: Nº de operaciones" in the TFI (Transparencia Fiscal Internacional / SICAV) special regime. Role name `irpf_re_especial_tfi_conyuge_num_operaciones` is accurate and clear. But the `_especial_tfi_` fragment implies the TFI special regime which ended with form restructuring after 2022 (only present 2020-2022). Name is accurate for its scope. OK. |
| `irpf_perdida_derecho_deduccion_autonomicas_suma` | OK | Autonomic deductions forfeited in the current year (clawback amount). Consistent. |
| `irpf_intereses_demora_perdida_deduccion_autonomica_2` | RENAME | As described above: drop `_2` suffix; rename to `irpf_intereses_demora_perdida_deduccion_autonomica`. |
| `irpf_anexo_c_contribuyente_con_derecho_deduccion` | RENAME | 2022 id 1853 is "Contribuyente titular"; 2023-2025 is "Contribuyente con derecho a deducción". The role name reflects the 2023-2025 label. The 2022 entry is effectively the same field relabelled. Role name is accurate for the dominant 2023-2025 usage. OK (the 2022 discrepancy is a minor label wording change, not a conceptual shift). |
| `irpf_anexo_c_exceso_sps_rg_contribuciones_periodo` | OK | Employer contributions in the current period for the social provision system excess carried in Annex C. Single revision (2021); role name is accurate. |
| `irpf_anexo_c_exencion_reinversion_importe_reinvertido` | OK | Amount reinvested into a new-enterprise exemption. Year-label suffix shifts each revision (expected). Concept is stable. |
| `irpf_retrib_especie_anio_percepcion` | OK | Year in which benefits-in-kind were received (for the Annex C benefit-in-kind reporting schedule). Consistent 2023-2025. |
| `irpf_rendimiento_capital_inmobiliario_amortizacion_inmueble_accesorio` | OK | Depreciation of accessory property and its improvements. Consistent. |
| `irpf_rendimiento_capital_inmobiliario_ingresos_integros` | OK | Gross rental income for capital-immobiliario schedule. Consistent. |
| `irpf_rendimiento_capital_mobiliario_ahorro_dt4_seguros_vida_importe` | OK | Total deferred capital from life insurance policies subject to DT4ª transitional relief. Consistent concept; year in label updates correctly each revision. |
| `irpf_rendimiento_capital_mobiliario_ahorro_suma_rendimientos_reducidos` | OK | Sum of reduced capital-income yields to be integrated in the savings taxable base. Consistent. |
| `irpf_rendimiento_capital_mobiliario_general_suma_rendimientos_reducidos` | OK | Sum of reduced capital-income yields for the general taxable base. Consistent. |
| `irpf_rendimiento_trabajo_gasto_sindicato` | OK | Union dues deductible from employment income. Consistent. |
| `irpf_incremento_maternidad_no_aplicado_2020` | RENAME | Label: "Incremento de la deducción (cantidades no aplicadas en el ejercicio 2020)". The 2020 year in the role name is semantically accurate (it specifically recovers unused 2020 maternity-deduction increments), but `_2020` in a stable role name will permanently encode a transient year. Present only in 2022. Rename to `irpf_incremento_maternidad_pendiente_aplicacion` to remove the hard-coded year. |
| `irpf_re_atrib_tipo_regimen_resto_flag` | RENAME | 2025 id 0164 label is "Resto" — a residual/other-type indicator in the atribución de rentas regime-type section. The role name is accurate but `_flag` implies boolean; this may be a selector value, not a checkbox. Rename to `irpf_re_atrib_tipo_regimen_resto` (drop `_flag`) unless confirmed boolean. |
| `irpf_conyuge_residente_ue_eee_flag` | OK | Boolean flag for spouse resident in EU/EEA (2025). Role name is accurate. |
| `irpf_ganancia_fondos_coti_valor_transmision_global` | OK | Global transmission value for listed funds (2025, fondos cotizados section). |
| `college_entity_nif` | RENAME | Missing `irpf_` prefix. The casillas are NIF of a student residence/Colegio Mayor/Menor. Rename to `irpf_residencia_estudiantes_nif`. Also `college_entity_nif` uses English vocabulary in a Spanish-language registry. |
| `irpf_anexo_b_birth_deduction_amount` | RENAME | Uses English vocabulary (`birth_deduction_amount`). All other roles use Spanish stems. The casilla is "Deducción por nacimiento: Importe de la deducción" in the Illes Balears Annex B supplementary data section. Rename to `irpf_anexo_b_baleares_deduccion_nacimiento_importe`. |
| `irpf_anexo_a_rib_pendiente_materializar` | OK | Pending-materialisation amount for the Reserva para Inversiones en las Illes Balears. Consistent across 2023-2025 (rolling annual vintage entries). |

---

## Summary counts

| Verdict | Count |
|---------|-------|
| OK | 84 |
| RENAME | 21 |
| SPLIT | 4 |
| OUTLIER | 14 |
| **Total** | **123** |

### RENAME list (21)

1. `irpf_anexo_a_aeip_aplicado` → `irpf_anexo_a_aeip_deduccion_aplicada`
2. `irpf_anexo_a_inversion_importe_deduccion_base` → `irpf_anexo_a_inversion_base_deduccion`
3. `irpf_anexo_a_rib_dotacion_anio` → split (see SPLIT list)
4. `irpf_intereses_demora_perdida_deduccion_autonomica_2` → `irpf_intereses_demora_perdida_deduccion_autonomica`
5. `irpf_deduccion_c_valenciana_generado_2024_pendiente_2` → `irpf_deduccion_c_valenciana_autoconsumo_pendiente_2`
6. `irpf_deduccion_c_valenciana_generado_2025_pendiente_2` → `irpf_deduccion_c_valenciana_autoconsumo_pendiente_3`
7. `irpf_deduccion_cantabria_generado_2025_pendiente` → `irpf_deduccion_cantabria_autoconsumo_pendiente`
8. `irpf_deduccion_madrid_vivienda_municipio_riesgo_precio` → `irpf_deduccion_madrid_vivienda_riesgo_despoblacion_precio`
9. `irpf_incremento_maternidad_no_aplicado_2020` → `irpf_incremento_maternidad_pendiente_aplicacion`
10. `irpf_ganancia_inmueble_catastral_2_b` → `irpf_ganancia_inmueble_ref_catastral_2`
11. `retenciones_ingresos_a_cuenta` → `irpf_inmueble_retenciones_ingresos_a_cuenta` (missing prefix)
12. `college_entity_nif` → `irpf_residencia_estudiantes_nif` (English + missing prefix)
13. `irpf_anexo_b_birth_deduction_amount` → `irpf_anexo_b_baleares_deduccion_nacimiento_importe` (English)
14. `irpf_re_atrib_tipo_regimen_resto_flag` → `irpf_re_atrib_tipo_regimen_resto`
15. `irpf_ascendiente_cede_flag` → `irpf_ascendiente_discapacidad_cede_flag`
16. `irpf_re_imagen_primera_cesionaria` (minor — acceptable as-is; rename optional)
17. `irpf_re_atrib_cap_mob_minoraciones` (minor — acceptable as-is; rename optional)
18. `irpf_deduccion_la_rioja_vivienda_municipio_importe` (minor — acceptable as-is)
19. `irpf_deduccion_murcia_vehiculo_importe` (minor — acceptable as-is)
20. `irpf_ganancia_otros_anio_imputacion_4` (verify siblings 1-3 exist)
21. `irpf_ganancia_otros_importe_percibir_1` (verify siblings 2+ exist)

### SPLIT list (4)

1. `irpf_inmueble_valor_catastral` → `irpf_inmueble_principal_valor_catastral` (0083) / `irpf_inmueble_arrendado_valor_catastral` (0123) / `irpf_inmueble_accesorio_valor_catastral` (0138)
2. `irpf_inmueble_mejoras_previas` → `irpf_inmueble_mejoras_anios_anteriores` (0128) / `irpf_inmueble_accesorio_mejoras_anios_anteriores` (0143)
3. `irpf_anexo_a_obra_fecha_inicio` → `irpf_anexo_a_obra_1_fecha_inicio` (0683) / `irpf_anexo_a_obra_2_fecha_inicio` (0691)
4. `irpf_anexo_a_rib_dotacion_anio` → `irpf_ric_dotacion_anio` (Canarias, id 1682 pre-2025) / `irpf_rib_dotacion_anio` (Illes Balears, ids 1682/1781/1938 from 2023+)

### OUTLIER list (14 individual casilla assignments)

| casilla id | revision | current role | actual concept |
|-----------|----------|-------------|---------------|
| 0991 | 2020 | `irpf_deduccion_castilla_y_leon_nacimiento_adopcion` | `irpf_deduccion_castilla_y_leon_paternidad` |
| 0980 | 2020 | `irpf_deduccion_castilla_y_leon_rehabilitacion_rural` | `irpf_deduccion_castilla_y_leon_fomento_emprendimiento` |
| 0980 | 2021 | `irpf_deduccion_castilla_y_leon_rehabilitacion_rural` | `irpf_deduccion_castilla_y_leon_fomento_emprendimiento` |
| 1114 | 2021 | `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022` | `irpf_deduccion_c_valenciana_total_deduccion` (aggregate subtotal) |
| 1071 | 2020 | `irpf_deduccion_la_rioja_guarderia_municipio_codigo` | `irpf_deduccion_la_rioja_guarderia_importe` (money amount) |
| 0303 | 2020 | `irpf_ganancia_premios_ayuda_alquiler` | `irpf_ganancia_premios_renta_basica_emancipacion` |
| 0303 | 2021 | `irpf_ganancia_premios_ayuda_alquiler` | `irpf_ganancia_premios_renta_basica_emancipacion` |
| 0581 | 2020 | `irpf_intereses_demora_perdida_deduccion_autonomica_2` | state-portion surcharge interest (not autonomic) |
| 0581 | 2021 | `irpf_intereses_demora_perdida_deduccion_autonomica_2` | state-portion surcharge interest (not autonomic) |
| 0546 | 2020 | `irpf_cuota_integra_autonomica` | filed under "Parte estatal" column of the form |
| 0546 | 2021 | `irpf_cuota_integra_autonomica` | filed under "Parte estatal" column of the form |
| 1682 | 2023 | `irpf_anexo_a_rib_dotacion_anio` | Reserva Inversiones Canarias (not Baleares — different territorial regime) |
| 1682 | 2024 | `irpf_anexo_a_rib_dotacion_anio` | Reserva Inversiones Canarias (not Baleares) |
| 0831/0834 | 2020-2021 | `irpf_anexo_a_inversion_importe_deduccion_base` | tracked "porcentaje de deducción" not "importe con derecho a deducción" (minor label shift) |

> Note: outliers for `irpf_cuota_integra_autonomica` (0546 in 2020-2021) and `irpf_intereses_demora_perdida_deduccion_autonomica_2` (0581 in 2020-2021) reflect a known form restructuring where state and autonomic portions were reported in the same column before the split. These are borderline outlier/id-reuse cases; verify with the 2020-2021 form layout before actioning.
