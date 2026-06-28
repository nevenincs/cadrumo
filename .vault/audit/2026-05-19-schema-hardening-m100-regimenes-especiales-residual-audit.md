---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
---

# schema-hardening m100 regimenes-especiales-residual role assignment

## Scope

Cluster: `regimenes-especiales-residual`
Total casilla ids classified: 49
Sections covered: `g4_re`, `feac`, `elemento_patrimonial`, `dt9`, `regularizacion_res`, `retrib_especie_anexo_c`, `rectnosepa`, `rectsepa`, `an_b_inf_adc_inst_auto`, `inmueble`
Source: `.vault-scratch/m100-clusters/regimenes-especiales-residual.json`
Existing-roles reference: `.vault-scratch/m100-clusters/_existing-roles.txt` (1334 entries)

## Role assignments

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0157 | `irpf_inmueble_gasto_deducible_alquiler_locales` | Gasto deducible correspondiente a alquileres de locales a determinados empresarios | money(default) | 2021 | New role. Section `inmuebles/inmueble`. Deductible expense for local rentals. |
| 0309 | `irpf_dt9_valor_transmision_acumulado` | Valor total acumulado de transmisión sobre el que se ha aplicado DT 9.ª | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Accumulated transmission value against which DT 9.ª reduction has been applied in prior years. |
| 0356 | `irpf_gp_elemento_numero_orden` | Número de orden del elemento | money(default) | 2020 | New role. Section `gp_otros_elementos/elemento_patrimonial`. Data type anomaly: integer semantics encoded as money(default); see data-type divergences. |
| 0360 | `irpf_gp_elemento_referencia_catastral_1` | Referencia castastral 1 | text | 2020, 2021 | New role. Note: label has typo "castastral" (should be "catastral") in source. |
| 0361 | `irpf_gp_elemento_referencia_catastral_2` | Referencia castastral 2 | text | 2020, 2021 | New role. Same typo in source label. |
| 0362 | `irpf_gp_elemento_referencia_catastral_3` | Referencia castastral 3 | text | 2020, 2021 | New role. Same typo in source label. |
| 0401 | `irpf_g4_re_transmision_intervivos_flag` | Si se trata de un contribuyente que ha transmitido intervivos las acciones o participaciones | boolean | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Section `g_cambio_residencia_ext/g4_re`. Flags an inter vivos transfer. |
| 0404 | `irpf_g4_re_valor_mercado_acciones` | Valor de mercado de las acciones o participaciones | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Market value of shares/participations at time of residence change. |
| 0405 | `irpf_g4_re_valor_transmision_acciones` | Valor de transmisión de las acciones o participaciones (sólo en caso de transmisión interv… | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Transmission value (only populated when inter vivos flag is set). |
| 0406 | `irpf_g4_re_valor_aplicable_dt9` | Valor al que resulta aplicable la DT 9.ª | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Label wording varies slightly across revisions (abbreviation of "D.T. 9.ª" vs "DT 9.ª") — same concept. |
| 0407 | `irpf_g4_re_valor_adquisicion_acciones` | Valor de adquisición de las acciones o participaciones | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Acquisition value (tax basis) of shares. |
| 0408 | `irpf_g4_re_ganancia_patrimonial` | Ganancias patrimoniales | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Calculated capital gain in the g4_re special regime. |
| 0409 | `irpf_g4_re_ganancia_susceptible_reduccion_dt9` | Parte de las ganancias patrimoniales susceptibles de reducción (DT 9.ª) | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Portion of gain eligible for DT9 transitional reduction. Label abbreviation varies across revisions. |
| 0410 | `irpf_g4_re_reduccion_dt9` | Reducción aplicable (DT 9.ª) | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Applied DT9 reduction amount. Label abbreviation varies. |
| 0411 | `irpf_g4_re_ganancia_reducida` | Ganancias patrimoniales reducidas ([0408] - [0410]) | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Net gain after DT9 reduction. |
| 0680 | `irpf_regularizacion_resultado` | Resultado de la declaración complementaria | decimal | 2020, 2021, 2022, 2023 | REUSED. Existing role. Section `resultados/regularizacion_res`. Result of the complementary/rectification return. |
| 0681 | `irpf_regularizacion_autoliquidaciones_anteriores_ingresar` | Resultados a ingresar de anteriores autoliquidaciones o liquidaciones administrativas | money(default) | 2020, 2021, 2022, 2023 | REUSED. Existing role. Amounts previously assessed that must be paid. |
| 0682 | `irpf_regularizacion_autoliquidaciones_anteriores_devolver` | Devoluciones solicitadas a la Agencia Tributaria como consecuencia de la tramitación de an… | money(default) | 2020, 2021, 2022, 2023 | REUSED. Existing role. Refunds already obtained from prior returns. |
| 0686 | `irpf_regularizacion_numero_justificante_rectificacion` | Número de justificante de la autoliquidación cuya rectificación se solicita | text | 2020, 2021, 2022, 2023 | New role. Reference number of the original self-assessment being rectified. |
| 0688 | `irpf_regularizacion_swift_bic` | SWIFT rectificación | text | 2020 | New role. SWIFT/BIC code for the rectification bank account (2020 only, later moved to sub-section `rectsepa`/`rectnosepa`). |
| 1207 | `irpf_anexo_b_inst_auto_importe_aplicado` | Importe satisfecho que se aplica en el ejercicio | money(default) | 2021, 2022 | New role. Section `an_b_inf_adc_inst_auto`. Amount paid via automated instalment applied in the current year. |
| 1208 | `irpf_anexo_b_inst_auto_importe_pendiente` | Importe satisfecho en [year] pendiente de aplicación en ejercicios futuros | money(default) | 2021, 2022 | New role. Label references specific year (2021 vs 2022) but concept is stable: instalment amount pending application in future years. See id-reuse hazards. |
| 1210 | `irpf_inmueble_numero_orden` | Número de orden del inmueble | integer | 2020 | New role. Section `inmuebles/inmueble`. Property sequence number within the declaration. |
| 1392 | `irpf_inmueble_numero_orden` | Número de orden del inmueble | integer | 2020 | New role (same as 1210). Two distinct casilla ids carry the same concept in the same revision. See id-reuse hazards. |
| 1627 | `irpf_gp_elemento_situacion_clave` | Situación. Clave | text | 2020, 2021 | New role. Location type key for the patrimonial element. |
| 1628 | `irpf_gp_elemento_referencia_catastral_1` | Referencia catastral 1 | text | 2020, 2021 | New role (same role as 0360). Later ids replace earlier ones from 2020 onward; both carry the same concept. Note correct spelling in label here vs typo in 0360. |
| 1629 | `irpf_gp_elemento_referencia_catastral_2` | Referencia catastral 2 | text | 2020, 2021 | New role (same role as 0361). |
| 1630 | `irpf_gp_elemento_referencia_catastral_3` | Referencia catastral 3 | text | 2020, 2021 | New role (same role as 0362). |
| 1643 | `irpf_gp_elemento_ganancia_exenta_reinversion_vh` | Ganancia exenta por reinversión en vivienda habitual | money(default) | 2020, 2021 | New role. Gain exempt via reinvestment in habitual residence, recorded at element level in gp_otros_elementos. |
| 1781 | `rectification_iban` | SEPA rectificación | text | 2021, 2022, 2023 | REUSED. Existing role. Section `rectsepa`. IBAN for SEPA-zone rectification refund. |
| 1782 | `irpf_rectsepa_swift_bic` | SWIFT rectificación | text | 2021, 2022, 2023 | New role. Section `rectsepa`. SWIFT/BIC indicator or code for SEPA rectification context. Parallel field to 1781 in the SEPA sub-block. |
| 1783 | `irpf_rectnosepa_swift_bic` | Código/Code SWIFT/BIC | text | 2021, 2022, 2023 | New role. Section `rectnosepa`. BIC code for non-SEPA foreign bank account. |
| 1784 | `irpf_rectnosepa_cuenta_numero` | Número de cuenta / Account no. | text | 2021, 2022, 2023 | New role. Foreign account number (non-IBAN format). |
| 1785 | `irpf_rectnosepa_banco_nombre` | Banco/Name of the bank | text | 2021, 2022, 2023 | New role. Name of the foreign bank. |
| 1786 | `irpf_rectnosepa_banco_direccion` | Dirección del Banco/Address of the bank | text | 2021, 2022 | New role. Address of the foreign bank. Present in 2021-2022 only (dropped in 2023). |
| 1787 | `irpf_rectnosepa_banco_ciudad` | Ciudad/City | text | 2021, 2022 | New role. City of the foreign bank. Present in 2021-2022 only (dropped in 2023). |
| 1789 | `irpf_rectnosepa_pais_codigo` | Código País/Country code | text | 2021, 2022 | New role. Country code for the foreign bank. Present in 2021-2022 only (dropped in 2023). |
| 1966 | `irpf_contribuyente_titular` | Contribuyente titular | text | 2023, 2024, 2025 | REUSED. Existing role. Section `retrib_especie_anexo_c`. Taxpayer key indicating which contributor (D/C) the in-kind remuneration belongs to. |
| 1967 | `irpf_retrib_especie_anio_percepcion` | Año en el que se percibe la retribución en especie | money(default) | 2023, 2024, 2025 | New role. Year in which the in-kind remuneration is received. Data type anomaly: year encoded as money(default); see data-type divergences. |
| 1968 | `irpf_retrib_especie_importe_no_exenta_1` | Retribución en especie (no exenta por superar la cuantía prevista en el artículo 42.3.f)… | money(default) | 2023, 2024, 2025 | New role. First tranche of non-exempt in-kind remuneration (Art. 42.3.f LIRPF threshold exceeded). |
| 1969 | `irpf_retrib_especie_importe_no_exenta_2` | Retribución en especie (no exenta por superar la cuantía prevista en el artículo 42.3.f)… | money(default) | 2023, 2024, 2025 | New role. Second tranche. Labels are truncated in the cluster JSON; TOML confirms distinct positions. |
| 1970 | `irpf_retrib_especie_importe_no_exenta_3` | Retribución en especie (no exenta por superar la cuantía prevista en el artículo 42.3.f)… | money(default) | 2023, 2024, 2025 | New role. Third tranche. |
| 1971 | `irpf_retrib_especie_importe_no_exenta_4` | Retribución en especie (no exenta por superar la cuantía prevista en el artículo 42.3.f)… | money(default) | 2023, 2024, 2025 | New role. Fourth tranche. |
| 1973 | `irpf_feac_tipo_operacion` | Tipo de operación (1: Fusión; 2: Escisión; 3: Canje de Valores; 4: Aportación no dineraria…) | text | 2023, 2024, 2025 | New role. Section `regimen_especial/feac`. Operation type for the FEAC corporate restructuring. See id-reuse hazards for label evolution. |
| 1975 | `irpf_feac_entidad_transmitida_sin_nif_flag` | Si no tiene NIF, marque con una X | boolean | 2023, 2024, 2025 | New role. Flag indicating the transmitting entity has no NIF. |
| 1976 | `irpf_feac_entidad_transmitida_denominacion` | Denominación social | text | 2023, 2024, 2025 | New role. Legal name of the transmitting entity. |
| 1977 | `irpf_feac_tipo_elemento_patrimonial_transmitido` | Tipo de elemento patrimonial transmitido (1: Acciones; 2: Bienes Inmuebles; 3: Otros…) | text | 2023, 2024, 2025 | New role. See id-reuse hazards: earlier label was "Tipo de operación"; 2025 TOML confirms element-type concept. |
| 1979 | `irpf_feac_entidad_receptora_sin_nif_flag` | Si no tiene NIF, marque con una X | boolean | 2023, 2024, 2025 | New role. Flag indicating the receiving entity has no NIF. |
| 1980 | `irpf_feac_entidad_receptora_denominacion` | Denominación social | text | 2023, 2024, 2025 | New role. Legal name of the receiving entity in the FEAC operation. |
| 1981 | `irpf_feac_inmueble_situacion_clave` | Situación (clave) | text | 2023, 2024, 2025 | New role. Location type key for the real-estate patrimonial element in the FEAC transaction. |
| 1982 | `irpf_feac_inmueble_referencia_catastral` | Referencia catastral | text | 2023, 2024, 2025 | New role. Catastral reference for the real-estate element being transferred. |
| 1983 | `irpf_feac_elemento_descripcion` | Descripción | text | 2023, 2024, 2025 | New role. Free-text description of the patrimonial element transmitted. |
| 1984 | `irpf_feac_valor_adquisicion_elemento` | Valor de adquisición del elemento patrimonial transmitido (valor a efectos fiscales) | money(default) | 2023, 2024, 2025 | New role. Fiscal acquisition value of the transmitted element. |
| 1985 | `irpf_feac_fecha_adquisicion_elemento` | Fecha de adquisición del elemento patrimonial transmitido | text | 2023, 2024, 2025 | New role. Acquisition date (stored as text, ISO format expected). |
| 1986 | `irpf_feac_valor_mercado_elemento` | Valor de Mercado del elemento patrimonial transmitido | money(default) | 2023, 2024, 2025 | New role. Fair market value at time of FEAC operation. |
| 1987 | `irpf_feac_fecha_operacion` | Fecha de la operación (fecha de inscripción de la escritura pública…) | text | 2023, 2024, 2025 | New role. Date of the corporate restructuring deed registration. |
| 1988 | `irpf_feac_ganancia_patrimonial_diferida` | Ganancia patrimonial diferida (Capítulo VII del Título VII de la Ley del IS) | money(default) | 2023, 2024, 2025 | New role. Capital gain deferred under the FEAC special regime (LIS Chap. VII). |
| 1989 | `irpf_feac_perdida_patrimonial_diferida` | Pérdida patrimonial diferida (Capítulo VII del Título VII de la Ley del IS) | money(default) | 2023, 2024, 2025 | New role. Capital loss deferred under the FEAC special regime. |

## Id-reuse hazards

### 1208 — label references specific year

Casilla `1208` appears in revisions 2021 and 2022 with labels:
- 2021: "Importe satisfecho en 2021 pendiente de aplicación en ejercicios futuros"
- 2022: "Importe satisfecho en 2022 pendiente de aplicación en ejercicios futuros"

The concept is stable (instalment amount from the current year's payment, pending application in future years). The year token in the label is a dynamic substitution, not a distinct semantic concept. No split warranted. Role `irpf_anexo_b_inst_auto_importe_pendiente` covers both revisions.

### 1210 and 1392 — two ids, same concept, same revision

Both `1210` and `1392` appear in revision 2020 only, both in section `toma_datos_ampliada/inmuebles/inmueble`, both labelled "Número de orden del inmueble" with integer data type. This is a structural duplicate within the 2020 revision — two casilla ids assigned to the same semantic slot. Both receive role `irpf_inmueble_numero_orden`. Downstream consumers should treat them as equivalent for the 2020 revision.

### 1977 — label evolution across revisions

Casilla `1977` in section `regimen_especial/feac` has two labels in the cluster JSON:
- "Tipo de elemento patrimonial transmitido (1: Acciones o participaciones; 2: Bienes Inmuebles…)"
- "Tipo de operación"

The 2025 TOML (`1966-1977.toml`) confirms the first label for 2025. The shorter label "Tipo de operación" appears to be an earlier label variant from 2023 or 2024 where the field was described more generically. The concept is distinguishable from `1973` (operation type for the FEAC transaction category) — `1977` is the **element type** (what kind of asset was transferred), while `1973` is the **corporate operation type** (merger, demerger, etc.). No revision range split is warranted as both labels ultimately describe element type classification. Role `irpf_feac_tipo_elemento_patrimonial_transmitido` is assigned for all revisions 2023–2025.

### 0406 — label punctuation variant across revisions

Casilla `0406` holds two label forms:
- "Valor al que resulta aplicable la D.T. 9.ª" (older revisions)
- "Valor al que resulta aplicable la DT 9.ª" (newer revisions)

This is purely typographic (abbreviation style). Single role `irpf_g4_re_valor_aplicable_dt9` covers all revisions.

### 0360/0361/0362 vs 1628/1629/1630 — parallel catastral reference ids in elemento_patrimonial

Section `gp_otros_elementos/elemento_patrimonial` contains two sets of catastral reference ids for the same logical fields, both in 2020 and 2021:
- `0360`/`0361`/`0362` labelled "Referencia castastral 1/2/3" (typo in source)
- `1628`/`1629`/`1630` labelled "Referencia catastral 1/2/3" (correct spelling)

Both id-sets are present in the same revisions (2020, 2021) in the same section. This pattern may indicate a form redesign mid-revision where old casilla numbers were retained alongside new ones, or the cluster JSON is aggregating from both old and new form pages. Each pair receives the same semantic role. Flag for investigation: determine whether both id-sets are truly active simultaneously or represent mutually exclusive paths.

## Data-type divergences

| id | expected_type | actual_type | notes |
|----|---------------|-------------|-------|
| 0356 | integer | money(default) | "Número de orden del elemento" is a sequence integer; money(default) is incorrect encoding. |
| 1967 | integer | money(default) | "Año en el que se percibe la retribución en especie" is a calendar year; money(default) is incorrect encoding. |
| 0680 | money(default) | decimal | "Resultado de la declaración complementaria" is a monetary result; `decimal` diverges from the `money(default)` used for the logically equivalent 0681/0682 fields in the same section. |
