---
tags:
  - "#audit"
  - "#schema-hardening"
date: 2026-05-20
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-r7-m100-batch-1-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-2-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-3-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-4-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-5-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-6-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-7-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-8-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-9-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-10-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-11-audit]]"
  - "[[2026-05-20-schema-hardening-r7-m100-batch-12-audit]]"
---

# schema-hardening r7 m100 consolidated corrections

Definitive per-(id, revision) `semantic_role` correction map for Modelo 100 (IRPF) revisions 2020-2025. Produced by consolidating twelve semantic-review audit batches (R7 campaign). Apply by script: for each row change the `semantic_role` field on the casilla TOML identified by `(id, revision)` from `current_role` to `correct_role`.

## Scope

- Source data: 1,560 `semantic_role` assignments across revisions 2020-2025.
- Batches reviewed: batch-1 through batch-12 (all 1,560 roles).
- Unit of correction: **(id, revision)** pair. The same casilla id can represent a different tax concept in a different revision year (id-reuse). Corrections are never issued on a bare id.
- OK verdicts produce no entry; role unchanged.
- RENAME: every (id, revision) member of the source role receives the new role name.
- SPLIT: each (id, revision) member is assigned to exactly one sub-role; no member is dropped.
- OUTLIER: only the named (id, revision) pair moves; remaining members keep the source role.
- Corrected role names: `irpf_` prefix, snake_case, lowercase ASCII, stable tax terminology, no year literals, no transient metadata.

## Cross-batch conflicts resolved

| conflict | resolution |
| --- | --- |
| `irpf_intereses_demora_perdida_deduccion_autonomica`: batch 1 renamed the `_2`-suffix source role to this target; batch 12 identifies 0578/2020 and 0578/2021 within that role as estatal, not autonomica. | RENAME applies to all members; 0578/2020 and 0578/2021 are additionally overridden by OUTLIER to `irpf_intereses_demora_perdida_deduccion_estatal`. Both rows appear in the corrections table; the OUTLIER row takes precedence for those two pairs. |
| `landlord_or_foreign_id_nif` (batch 4) and `landlord_nif` (batch 10) both rename to `irpf_arrendador_nif`. | No conflict; two distinct source roles converging on the same canonical target. |
| `irpf_gyp_ganancias_bruto` (batch 9 RENAME) and `irpf_gyp_perdidas_bruto` (batch 10 SPLIT) appear related but are independent roles. | RENAME applies to `irpf_gyp_ganancias_bruto` as a whole; per-asset-class SPLIT applies only to `irpf_gyp_perdidas_bruto`. |
| `irpf_anexo_c_exceso_eeficiencia_aplicado` outlier 1696/2022 (batch 7/10) and `irpf_anexo_c_exceso_eeficiencia_pendiente_inicio` outlier 1692/2022 (batch 11) are different roles, different casilla IDs, same RIC Canarias id-reuse pattern. | Treated as independent outliers. |
| `irpf_deduccion_aragon_formacion_autonomia` (batch 6): 0888/2020-2022 are Asturias donacion fincas rusticas; 0888/2024-2025 correctly remain Aragon formacion autonomia. | SPLIT applied; only 0888/2020-2022 emit correction rows. |
| `irpf_deduccion_baleares_ela` (batch 11): 0770/2022 = acogida Ucrania, 0770/2023 = alza precios, 0770/2024-2025 = ELA. | SPLIT applied for 2022-2023; 0770/2024-2025 emit no correction. |
| `irpf_deduccion_c_valenciana_generado_2024_pendiente` (batch 3) and `irpf_deduccion_c_valenciana_generado_2022_pendiente` (batch 10) both rename to near-identical targets with slight name difference. | Accepted both as distinct source roles; each renamed to its most stable form. |
| `irpf_deduccion_galicia_generado_2025_linea_2` (batch 6 SPLIT): 1037/2020-2024 are daños pirotecnia (distinct concept); 1037/2025 is importe generado linea 2. | SPLIT applied; 1037/2025 gets the RENAME-equivalent `irpf_deduccion_galicia_generado_linea_2`. |

## Corrections

| id | revision | current_role | correct_role | reason |
| --- | --- | --- | --- | --- |
| 0001 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0001 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0001 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0001 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0001 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0001 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0026 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0026 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0026 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0026 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0026 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0026 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0042 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0042 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0042 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0042 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0042 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0042 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0045 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0045 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0045 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0045 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0045 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0045 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0062 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0062 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0062 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0062 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0062 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0062 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0077 | 2020 | spouse_or_foreign_id_nif | irpf_inmueble_exconyuge_nif | RENAME: English name; NIF del exconyugue (0077) real-estate section |
| 0077 | 2021 | spouse_or_foreign_id_nif | irpf_inmueble_exconyuge_nif | RENAME: English name; NIF del exconyugue (0077) real-estate section |
| 0077 | 2022 | spouse_or_foreign_id_nif | irpf_inmueble_exconyuge_nif | RENAME: English name; NIF del exconyugue (0077) real-estate section |
| 0077 | 2023 | spouse_or_foreign_id_nif | irpf_inmueble_exconyuge_nif | RENAME: English name; NIF del exconyugue (0077) real-estate section |
| 0077 | 2024 | spouse_or_foreign_id_nif | irpf_inmueble_exconyuge_nif | RENAME: English name; NIF del exconyugue (0077) real-estate section |
| 0077 | 2025 | spouse_or_foreign_id_nif | irpf_inmueble_exconyuge_nif | RENAME: English name; NIF del exconyugue (0077) real-estate section |
| 0079 | 2020 | irpf_inmueble_dias_uso_vivienda_habitual_conyuge | irpf_inmueble_dias_uso | RENAME: label generic dias uso; vivienda_habitual_conyuge too specific |
| 0079 | 2021 | irpf_inmueble_dias_uso_vivienda_habitual_conyuge | irpf_inmueble_dias_uso | RENAME: label generic dias uso; vivienda_habitual_conyuge too specific |
| 0079 | 2022 | irpf_inmueble_dias_uso_vivienda_habitual_conyuge | irpf_inmueble_dias_uso | RENAME: label generic dias uso; vivienda_habitual_conyuge too specific |
| 0079 | 2023 | irpf_inmueble_dias_uso_vivienda_habitual_conyuge | irpf_inmueble_dias_uso | RENAME: label generic dias uso; vivienda_habitual_conyuge too specific |
| 0079 | 2024 | irpf_inmueble_dias_uso_vivienda_habitual_conyuge | irpf_inmueble_dias_uso | RENAME: label generic dias uso; vivienda_habitual_conyuge too specific |
| 0079 | 2025 | irpf_inmueble_dias_uso_vivienda_habitual_conyuge | irpf_inmueble_dias_uso | RENAME: label generic dias uso; vivienda_habitual_conyuge too specific |
| 0083 | 2020 | irpf_inmueble_valor_catastral | irpf_inmueble_1_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0083 | 2021 | irpf_inmueble_valor_catastral | irpf_inmueble_1_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0083 | 2022 | irpf_inmueble_valor_catastral | irpf_inmueble_1_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0083 | 2023 | irpf_inmueble_valor_catastral | irpf_inmueble_1_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0083 | 2024 | irpf_inmueble_valor_catastral | irpf_inmueble_1_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0083 | 2025 | irpf_inmueble_valor_catastral | irpf_inmueble_1_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0091 | 2020 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0091 | 2021 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0091 | 2022 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0091 | 2023 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0091 | 2024 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0091 | 2025 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0094 | 2020 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0094 | 2021 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0094 | 2022 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0094 | 2023 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0094 | 2024 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0094 | 2025 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0097 | 2020 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0097 | 2021 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0097 | 2022 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0097 | 2023 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0097 | 2024 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0097 | 2025 | tenant_or_foreign_id_nif | irpf_inmueble_arrendatario_nif | RENAME: English name; NIF arrendatario capital inmobiliario (0091/0094/0097) |
| 0123 | 2020 | irpf_inmueble_valor_catastral | irpf_inmueble_2_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0123 | 2021 | irpf_inmueble_valor_catastral | irpf_inmueble_2_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0123 | 2022 | irpf_inmueble_valor_catastral | irpf_inmueble_2_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0123 | 2023 | irpf_inmueble_valor_catastral | irpf_inmueble_2_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0123 | 2024 | irpf_inmueble_valor_catastral | irpf_inmueble_2_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0123 | 2025 | irpf_inmueble_valor_catastral | irpf_inmueble_2_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0134 | 2020 | irpf_inmueble_adquisicion_tipo_lucrativa | irpf_inmueble_adquisicion_tipo_onerosa | OUTLIER: 2020 label Onerosa (compraventa); id-reuse |
| 0138 | 2020 | irpf_inmueble_valor_catastral | irpf_inmueble_3_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0138 | 2021 | irpf_inmueble_valor_catastral | irpf_inmueble_3_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0138 | 2022 | irpf_inmueble_valor_catastral | irpf_inmueble_3_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0138 | 2023 | irpf_inmueble_valor_catastral | irpf_inmueble_3_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0138 | 2024 | irpf_inmueble_valor_catastral | irpf_inmueble_3_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0138 | 2025 | irpf_inmueble_valor_catastral | irpf_inmueble_3_valor_catastral | SPLIT: three distinct property-slot valor catastral fields |
| 0153 | 2020 | retenciones_ingresos_a_cuenta | irpf_inmueble_retenciones_ingresos_a_cuenta | RENAME: missing irpf_ prefix; capital inmobiliario retention |
| 0153 | 2021 | retenciones_ingresos_a_cuenta | irpf_inmueble_retenciones_ingresos_a_cuenta | RENAME: missing irpf_ prefix; capital inmobiliario retention |
| 0153 | 2022 | retenciones_ingresos_a_cuenta | irpf_inmueble_retenciones_ingresos_a_cuenta | RENAME: missing irpf_ prefix; capital inmobiliario retention |
| 0153 | 2023 | retenciones_ingresos_a_cuenta | irpf_inmueble_retenciones_ingresos_a_cuenta | RENAME: missing irpf_ prefix; capital inmobiliario retention |
| 0153 | 2024 | retenciones_ingresos_a_cuenta | irpf_inmueble_retenciones_ingresos_a_cuenta | RENAME: missing irpf_ prefix; capital inmobiliario retention |
| 0153 | 2025 | retenciones_ingresos_a_cuenta | irpf_inmueble_retenciones_ingresos_a_cuenta | RENAME: missing irpf_ prefix; capital inmobiliario retention |
| 0158 | 2021 | tenant_nif | irpf_inmueble_arrendatario_nif | OUTLIER: 0158/2021 inmueble arrendatario NIF (different section); id-reuse |
| 0165 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0165 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0165 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0165 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0165 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0165 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0210 | 2024 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0210 | 2025 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0224 | 2021 | irpf_rendimiento_act_eco_estimacion_directa_rdto_neto | irpf_ed_rdto_neto_previo_reduccion | RENAME: ED rdto neto previo reduccion |
| 0224 | 2022 | irpf_rendimiento_act_eco_estimacion_directa_rdto_neto | irpf_ed_rdto_neto_previo_reduccion | RENAME: ED rdto neto previo reduccion |
| 0224 | 2023 | irpf_rendimiento_act_eco_estimacion_directa_rdto_neto | irpf_ed_rdto_neto_previo_reduccion | RENAME: ED rdto neto previo reduccion |
| 0224 | 2024 | irpf_rendimiento_act_eco_estimacion_directa_rdto_neto | irpf_ed_rdto_neto_previo_reduccion | RENAME: ED rdto neto previo reduccion |
| 0224 | 2025 | irpf_rendimiento_act_eco_estimacion_directa_rdto_neto | irpf_ed_rdto_neto_previo_reduccion | RENAME: ED rdto neto previo reduccion |
| 0229 | 2021 | irpf_deduccion_castilla_la_mancha_arrendamiento_discapacidad | irpf_deduccion_castilla_la_mancha_nacimiento_adopcion | OUTLIER: 2021 label nacimiento o adopcion hijos; id-reuse |
| 0246 | 2020 | irpf_matrimonio_mes_inicio | irpf_conyuge_discapacidad_matrimonio_mes_inicio | RENAME: context is conyuge discapacidad matrimonio |
| 0246 | 2021 | irpf_matrimonio_mes_inicio | irpf_conyuge_discapacidad_matrimonio_mes_inicio | RENAME: context is conyuge discapacidad matrimonio |
| 0246 | 2022 | irpf_matrimonio_mes_inicio | irpf_conyuge_discapacidad_matrimonio_mes_inicio | RENAME: context is conyuge discapacidad matrimonio |
| 0246 | 2023 | irpf_matrimonio_mes_inicio | irpf_conyuge_discapacidad_matrimonio_mes_inicio | RENAME: context is conyuge discapacidad matrimonio |
| 0246 | 2024 | irpf_matrimonio_mes_inicio | irpf_conyuge_discapacidad_matrimonio_mes_inicio | RENAME: context is conyuge discapacidad matrimonio |
| 0246 | 2025 | irpf_matrimonio_mes_inicio | irpf_conyuge_discapacidad_matrimonio_mes_inicio | RENAME: context is conyuge discapacidad matrimonio |
| 0250 | 2021 | irpf_deduccion_la_rioja_donaciones_fomento_cultura | irpf_deduccion_la_rioja_fomento_mecenazgo | RENAME: labels confirm mecenazgo, not fomento cultura |
| 0250 | 2022 | irpf_deduccion_la_rioja_donaciones_fomento_cultura | irpf_deduccion_la_rioja_fomento_mecenazgo | RENAME: labels confirm mecenazgo, not fomento cultura |
| 0250 | 2023 | irpf_deduccion_la_rioja_donaciones_fomento_cultura | irpf_deduccion_la_rioja_fomento_mecenazgo | RENAME: labels confirm mecenazgo, not fomento cultura |
| 0250 | 2024 | irpf_deduccion_la_rioja_donaciones_fomento_cultura | irpf_deduccion_la_rioja_fomento_mecenazgo | RENAME: labels confirm mecenazgo, not fomento cultura |
| 0250 | 2025 | irpf_deduccion_la_rioja_donaciones_fomento_cultura | irpf_deduccion_la_rioja_fomento_mecenazgo | RENAME: labels confirm mecenazgo, not fomento cultura |
| 0253 | 2021 | irpf_deduccion_la_rioja_donacion_bienes_culturales_autores | irpf_deduccion_la_rioja_fomento_mecenazgo | OUTLIER: 2021 label mecenazgo cultural; id-reuse |
| 0256 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0256 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0256 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0256 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0256 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0256 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0257 | 2020 | investment_entity_nif | irpf_re_agrup_interes_economico_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0257 | 2021 | investment_entity_nif | irpf_re_agrup_interes_economico_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0257 | 2022 | investment_entity_nif | irpf_re_agrup_interes_economico_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0257 | 2023 | investment_entity_nif | irpf_re_agrup_interes_economico_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0257 | 2024 | investment_entity_nif | irpf_re_agrup_interes_economico_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0257 | 2025 | investment_entity_nif | irpf_re_agrup_interes_economico_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0259 | 2020 | base_imponible_irpf | irpf_re_agrup_interes_economico_base_imponible_imputada | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0259 | 2021 | base_imponible_irpf | irpf_re_agrup_interes_economico_base_imponible_imputada | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0259 | 2022 | base_imponible_irpf | irpf_re_agrup_interes_economico_base_imponible_imputada | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0259 | 2023 | base_imponible_irpf | irpf_re_agrup_interes_economico_base_imponible_imputada | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0259 | 2024 | base_imponible_irpf | irpf_re_agrup_interes_economico_base_imponible_imputada | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0259 | 2025 | base_imponible_irpf | irpf_re_agrup_interes_economico_base_imponible_imputada | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0267 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0267 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0267 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0267 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0267 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0267 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0271 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0271 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0271 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0271 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0271 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0271 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0276 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0276 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0276 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0276 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0276 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0276 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0281 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0281 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0281 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0281 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0281 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0281 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0288 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0288 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0288 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0288 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0288 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0288 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0289 | 2020 | irpf_gyp_perdidas_bruto | irpf_gyp_juegos_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0289 | 2021 | irpf_gyp_perdidas_bruto | irpf_gyp_juegos_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0289 | 2022 | irpf_gyp_perdidas_bruto | irpf_gyp_juegos_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0289 | 2023 | irpf_gyp_perdidas_bruto | irpf_gyp_juegos_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0289 | 2024 | irpf_gyp_perdidas_bruto | irpf_gyp_juegos_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0289 | 2025 | irpf_gyp_perdidas_bruto | irpf_gyp_juegos_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0290 | 2020 | irpf_gyp_saldo_neto_general | irpf_gp_juegos_saldo_neto | RENAME: members are saldo neto juegos section, not general gyp |
| 0290 | 2021 | irpf_gyp_saldo_neto_general | irpf_gp_juegos_saldo_neto | RENAME: members are saldo neto juegos section, not general gyp |
| 0290 | 2022 | irpf_gyp_saldo_neto_general | irpf_gp_juegos_saldo_neto | RENAME: members are saldo neto juegos section, not general gyp |
| 0290 | 2023 | irpf_gyp_saldo_neto_general | irpf_gp_juegos_saldo_neto | RENAME: members are saldo neto juegos section, not general gyp |
| 0290 | 2024 | irpf_gyp_saldo_neto_general | irpf_gp_juegos_saldo_neto | RENAME: members are saldo neto juegos section, not general gyp |
| 0290 | 2025 | irpf_gyp_saldo_neto_general | irpf_gp_juegos_saldo_neto | RENAME: members are saldo neto juegos section, not general gyp |
| 0291 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0291 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0291 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0291 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0291 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0291 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0297 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0297 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0297 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0297 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0297 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0297 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0298 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0298 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0298 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0298 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0298 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0298 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0303 | 2020 | irpf_ganancia_premios_ayuda_alquiler | irpf_ganancia_renta_basica_emancipacion | OUTLIER: 2020 label Renta basica emancipacion; id-reuse |
| 0303 | 2021 | irpf_ganancia_premios_ayuda_alquiler | irpf_ganancia_renta_basica_emancipacion | OUTLIER: 2021 label Renta basica emancipacion; id-reuse |
| 0306 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0306 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0306 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0306 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0306 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0306 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0307 | 2020 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_perdidas_no_transmision | SPLIT: per-asset-class gyp perdidas subtotals |
| 0307 | 2021 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_perdidas_no_transmision | SPLIT: per-asset-class gyp perdidas subtotals |
| 0307 | 2022 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_perdidas_no_transmision | SPLIT: per-asset-class gyp perdidas subtotals |
| 0307 | 2023 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_perdidas_no_transmision | SPLIT: per-asset-class gyp perdidas subtotals |
| 0307 | 2024 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_perdidas_no_transmision | SPLIT: per-asset-class gyp perdidas subtotals |
| 0307 | 2025 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_perdidas_no_transmision | SPLIT: per-asset-class gyp perdidas subtotals |
| 0308 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0308 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0308 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0308 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0308 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0308 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0310 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0310 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0310 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0310 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0310 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0310 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0311 | 2020 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0311 | 2021 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0311 | 2022 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0311 | 2023 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0311 | 2024 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0311 | 2025 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0321 | 2020 | irpf_perdida_fondos_importe_obtenido | irpf_perdida_fondos_importe | RENAME: suffix _obtenido redundant; Perdidas patrimoniales fondos |
| 0321 | 2021 | irpf_perdida_fondos_importe_obtenido | irpf_perdida_fondos_importe | RENAME: suffix _obtenido redundant; Perdidas patrimoniales fondos |
| 0321 | 2022 | irpf_perdida_fondos_importe_obtenido | irpf_perdida_fondos_importe | RENAME: suffix _obtenido redundant; Perdidas patrimoniales fondos |
| 0321 | 2023 | irpf_perdida_fondos_importe_obtenido | irpf_perdida_fondos_importe | RENAME: suffix _obtenido redundant; Perdidas patrimoniales fondos |
| 0321 | 2024 | irpf_perdida_fondos_importe_obtenido | irpf_perdida_fondos_importe | RENAME: suffix _obtenido redundant; Perdidas patrimoniales fondos |
| 0321 | 2025 | irpf_perdida_fondos_importe_obtenido | irpf_perdida_fondos_importe | RENAME: suffix _obtenido redundant; Perdidas patrimoniales fondos |
| 0324 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0324 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0324 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0324 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0324 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0324 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0325 | 2020 | irpf_gyp_perdidas_bruto | irpf_gyp_renta_fija_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0325 | 2021 | irpf_gyp_perdidas_bruto | irpf_gyp_renta_fija_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0325 | 2022 | irpf_gyp_perdidas_bruto | irpf_gyp_renta_fija_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0325 | 2023 | irpf_gyp_perdidas_bruto | irpf_gyp_renta_fija_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0325 | 2024 | irpf_gyp_perdidas_bruto | irpf_gyp_renta_fija_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0325 | 2025 | irpf_gyp_perdidas_bruto | irpf_gyp_renta_fija_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0326 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0326 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0326 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0326 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0326 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0326 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0339 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0339 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0339 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0339 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0339 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0339 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0340 | 2020 | irpf_gyp_perdidas_bruto | irpf_gyp_acciones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0340 | 2021 | irpf_gyp_perdidas_bruto | irpf_gyp_acciones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0340 | 2022 | irpf_gyp_perdidas_bruto | irpf_gyp_acciones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0340 | 2023 | irpf_gyp_perdidas_bruto | irpf_gyp_acciones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0340 | 2024 | irpf_gyp_perdidas_bruto | irpf_gyp_acciones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0340 | 2025 | irpf_gyp_perdidas_bruto | irpf_gyp_acciones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0341 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0341 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0341 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0341 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0341 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0341 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0343 | 2023 | irpf_ganancia_derechos_valor_transmision_global | irpf_ganancia_transmisiones_importe_global_2024 | OUTLIER: 2023 label Importe global transmisiones 2024; id-reuse |
| 0354 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0354 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0354 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0354 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0354 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0354 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0355 | 2020 | irpf_gyp_perdidas_bruto | irpf_gyp_derechos_suscripcion_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0355 | 2021 | irpf_gyp_perdidas_bruto | irpf_gyp_derechos_suscripcion_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0355 | 2022 | irpf_gyp_perdidas_bruto | irpf_gyp_derechos_suscripcion_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0355 | 2023 | irpf_gyp_perdidas_bruto | irpf_gyp_derechos_suscripcion_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0355 | 2024 | irpf_gyp_perdidas_bruto | irpf_gyp_derechos_suscripcion_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0355 | 2025 | irpf_gyp_perdidas_bruto | irpf_gyp_derechos_suscripcion_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0363 | 2020 | irpf_ganancia_otros_anio_imputacion_1 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _1 transient; anio imputacion stable |
| 0363 | 2021 | irpf_ganancia_otros_anio_imputacion_1 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _1 transient; anio imputacion stable |
| 0363 | 2022 | irpf_ganancia_otros_anio_imputacion_1 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _1 transient; anio imputacion stable |
| 0363 | 2023 | irpf_ganancia_otros_anio_imputacion_1 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _1 transient; anio imputacion stable |
| 0363 | 2024 | irpf_ganancia_otros_anio_imputacion_1 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _1 transient; anio imputacion stable |
| 0363 | 2025 | irpf_ganancia_otros_anio_imputacion_1 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _1 transient; anio imputacion stable |
| 0370 | 2020 | irpf_perdida_otros_pendiente_2 | irpf_perdida_otros_pendiente | RENAME: numeric suffix _2 transient; stable perdida otros pendiente |
| 0370 | 2021 | irpf_perdida_otros_pendiente_2 | irpf_perdida_otros_pendiente | RENAME: numeric suffix _2 transient; stable perdida otros pendiente |
| 0370 | 2022 | irpf_perdida_otros_pendiente_2 | irpf_perdida_otros_pendiente | RENAME: numeric suffix _2 transient; stable perdida otros pendiente |
| 0370 | 2023 | irpf_perdida_otros_pendiente_2 | irpf_perdida_otros_pendiente | RENAME: numeric suffix _2 transient; stable perdida otros pendiente |
| 0370 | 2024 | irpf_perdida_otros_pendiente_2 | irpf_perdida_otros_pendiente | RENAME: numeric suffix _2 transient; stable perdida otros pendiente |
| 0370 | 2025 | irpf_perdida_otros_pendiente_2 | irpf_perdida_otros_pendiente | RENAME: numeric suffix _2 transient; stable perdida otros pendiente |
| 0371 | 2020 | irpf_ganancia_otros_anio_imputacion_3 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _3 transient; same concept as batch 10 _1 rename |
| 0371 | 2021 | irpf_ganancia_otros_anio_imputacion_3 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _3 transient; same concept as batch 10 _1 rename |
| 0371 | 2022 | irpf_ganancia_otros_anio_imputacion_3 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _3 transient; same concept as batch 10 _1 rename |
| 0371 | 2023 | irpf_ganancia_otros_anio_imputacion_3 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _3 transient; same concept as batch 10 _1 rename |
| 0371 | 2024 | irpf_ganancia_otros_anio_imputacion_3 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _3 transient; same concept as batch 10 _1 rename |
| 0371 | 2025 | irpf_ganancia_otros_anio_imputacion_3 | irpf_ganancia_otros_anio_imputacion | RENAME: numeric suffix _3 transient; same concept as batch 10 _1 rename |
| 0373 | 2020 | irpf_ganancia_otros_ganancia_pendiente_3 | irpf_ganancia_otros_ganancia_pendiente_imputacion | RENAME: numeric suffix _3 transient; ganancia pendiente imputacion stable |
| 0373 | 2021 | irpf_ganancia_otros_ganancia_pendiente_3 | irpf_ganancia_otros_ganancia_pendiente_imputacion | RENAME: numeric suffix _3 transient; ganancia pendiente imputacion stable |
| 0373 | 2022 | irpf_ganancia_otros_ganancia_pendiente_3 | irpf_ganancia_otros_ganancia_pendiente_imputacion | RENAME: numeric suffix _3 transient; ganancia pendiente imputacion stable |
| 0373 | 2023 | irpf_ganancia_otros_ganancia_pendiente_3 | irpf_ganancia_otros_ganancia_pendiente_imputacion | RENAME: numeric suffix _3 transient; ganancia pendiente imputacion stable |
| 0373 | 2024 | irpf_ganancia_otros_ganancia_pendiente_3 | irpf_ganancia_otros_ganancia_pendiente_imputacion | RENAME: numeric suffix _3 transient; ganancia pendiente imputacion stable |
| 0373 | 2025 | irpf_ganancia_otros_ganancia_pendiente_3 | irpf_ganancia_otros_ganancia_pendiente_imputacion | RENAME: numeric suffix _3 transient; ganancia pendiente imputacion stable |
| 0385 | 2020 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0385 | 2021 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0385 | 2022 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0385 | 2023 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0385 | 2024 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0385 | 2025 | irpf_gyp_perdidas_bruto | irpf_gyp_otras_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0386 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0386 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0386 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0386 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0386 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0386 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0387 | 2020 | irpf_gyp_saldo_neto_ahorro | irpf_gyp_actividades_economicas_suma_ganancias | RENAME: labels are Suma ganancias derivadas transmisiones; role name incorrect |
| 0387 | 2021 | irpf_gyp_saldo_neto_ahorro | irpf_gyp_actividades_economicas_suma_ganancias | RENAME: labels are Suma ganancias derivadas transmisiones; role name incorrect |
| 0387 | 2022 | irpf_gyp_saldo_neto_ahorro | irpf_gyp_actividades_economicas_suma_ganancias | RENAME: labels are Suma ganancias derivadas transmisiones; role name incorrect |
| 0387 | 2023 | irpf_gyp_saldo_neto_ahorro | irpf_gyp_actividades_economicas_suma_ganancias | RENAME: labels are Suma ganancias derivadas transmisiones; role name incorrect |
| 0387 | 2024 | irpf_gyp_saldo_neto_ahorro | irpf_gyp_actividades_economicas_suma_ganancias | RENAME: labels are Suma ganancias derivadas transmisiones; role name incorrect |
| 0387 | 2025 | irpf_gyp_saldo_neto_ahorro | irpf_gyp_actividades_economicas_suma_ganancias | RENAME: labels are Suma ganancias derivadas transmisiones; role name incorrect |
| 0388 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0388 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0388 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0388 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0388 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0388 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0390 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0390 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0390 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0390 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0390 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0390 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0391 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0391 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0391 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0391 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0391 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0391 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0393 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0393 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0393 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0393 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0393 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0393 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0394 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0394 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0394 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0394 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0394 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0394 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0396 | 2020 | irpf_gyp_perdidas_bruto | irpf_gyp_feac_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0396 | 2021 | irpf_gyp_perdidas_bruto | irpf_gyp_feac_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0396 | 2022 | irpf_gyp_perdidas_bruto | irpf_gyp_feac_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0396 | 2023 | irpf_gyp_perdidas_bruto | irpf_gyp_feac_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0396 | 2024 | irpf_gyp_perdidas_bruto | irpf_gyp_feac_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0396 | 2025 | irpf_gyp_perdidas_bruto | irpf_gyp_feac_transmisiones_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 0397 | 2022 | pension_plan_employer_nif | irpf_pension_plan_empleo_nif | RENAME: English name; NIF plan pensiones sistema empleo |
| 0397 | 2023 | employer_nif | irpf_empleador_nif | RENAME: English name; NIF del empleador |
| 0397 | 2024 | employer_nif | irpf_empleador_nif | RENAME: English name; NIF del empleador |
| 0397 | 2025 | employer_nif | irpf_empleador_nif | RENAME: English name; NIF del empleador |
| 0398 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0398 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0398 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0398 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0398 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0398 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0400 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0400 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0400 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0400 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0400 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0400 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0402 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0402 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0402 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0402 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0402 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0402 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0403 | 2020 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0403 | 2021 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0403 | 2022 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0403 | 2023 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0403 | 2024 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0403 | 2025 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0412 | 2020 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0412 | 2021 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0412 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0412 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0412 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0412 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 0430 | 2020 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_imputado | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0430 | 2021 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_imputado | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0430 | 2022 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_imputado | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0430 | 2023 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_imputado | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0430 | 2024 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_imputado | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0430 | 2025 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_imputado | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0435 | 2020 | base_imponible_irpf | irpf_base_imponible_general | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0435 | 2021 | base_imponible_irpf | irpf_base_imponible_general | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0435 | 2022 | base_imponible_irpf | irpf_base_imponible_general | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0435 | 2023 | base_imponible_irpf | irpf_base_imponible_general | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0435 | 2024 | base_imponible_irpf | irpf_base_imponible_general | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0435 | 2025 | base_imponible_irpf | irpf_base_imponible_general | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0436 | 2020 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente_reduccion | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0436 | 2021 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente_reduccion | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0436 | 2022 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente_reduccion | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0436 | 2023 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente_reduccion | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0436 | 2024 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente_reduccion | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0436 | 2025 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente_reduccion | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0443 | 2020 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0443 | 2021 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0443 | 2022 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0443 | 2023 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0443 | 2024 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0443 | 2025 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0444 | 2020 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0444 | 2021 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0444 | 2022 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0444 | 2023 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0444 | 2024 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0444 | 2025 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0445 | 2020 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0445 | 2021 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0445 | 2022 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0445 | 2023 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0445 | 2024 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0445 | 2025 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0447 | 2020 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0447 | 2021 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0447 | 2022 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0447 | 2023 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0447 | 2024 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0447 | 2025 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0449 | 2020 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0449 | 2021 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0449 | 2022 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0449 | 2023 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0449 | 2024 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0449 | 2025 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0450 | 2020 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0450 | 2021 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0450 | 2022 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0450 | 2023 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0450 | 2024 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0450 | 2025 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0451 | 2020 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0451 | 2021 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0451 | 2022 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0451 | 2023 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0451 | 2024 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0451 | 2025 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0452 | 2020 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0452 | 2021 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0452 | 2022 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0452 | 2023 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0452 | 2024 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0452 | 2025 | irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente | irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores | SPLIT: 0430=imputado ahorro, 0436=pendiente reduccion, 0443-0447=resto pendiente, 0449-0452=ejercicios anteriores |
| 0456 | 2020 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0456 | 2021 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0456 | 2022 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0456 | 2023 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0456 | 2024 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0456 | 2025 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0457 | 2020 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0457 | 2021 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0457 | 2022 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0457 | 2023 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0457 | 2024 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0457 | 2025 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0458 | 2020 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0458 | 2021 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0458 | 2022 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0458 | 2023 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0458 | 2024 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0458 | 2025 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0459 | 2020 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0459 | 2021 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0459 | 2022 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0459 | 2023 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0459 | 2024 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0459 | 2025 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 0460 | 2020 | base_imponible_irpf | irpf_base_imponible_ahorro | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0460 | 2021 | base_imponible_irpf | irpf_base_imponible_ahorro | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0460 | 2022 | base_imponible_irpf | irpf_base_imponible_ahorro | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0460 | 2023 | base_imponible_irpf | irpf_base_imponible_ahorro | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0460 | 2024 | base_imponible_irpf | irpf_base_imponible_ahorro | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0460 | 2025 | base_imponible_irpf | irpf_base_imponible_ahorro | SPLIT: missing irpf_ prefix; 0435=base general, 0460=base ahorro, 0259=RE agrupacion BI imputada |
| 0461 | 2020 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_importe | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0461 | 2021 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_importe | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0461 | 2022 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_importe | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0461 | 2023 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_importe | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0461 | 2024 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_importe | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0461 | 2025 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_importe | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0462 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0462 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0462 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0462 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0462 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0462 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0468 | 2021 | irpf_reduccion_prevision_social_total | irpf_reduccion_prevision_social_excesos_pendientes | OUTLIER: 2021 label excesos pendientes de reducir; id-reuse |
| 0470 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0470 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0470 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0470 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0470 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0470 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0471 | 2020 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0471 | 2021 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0471 | 2022 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0471 | 2023 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0471 | 2024 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0471 | 2025 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0477 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0477 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0477 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0477 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0477 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0477 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0478 | 2020 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0478 | 2021 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0478 | 2022 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0478 | 2023 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0478 | 2024 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0478 | 2025 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 0482 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0482 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0482 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0482 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0482 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0482 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0483 | 2020 | pension_recipient_nif | irpf_reduccion_pension_compensatoria_receptor_nif | RENAME: English name; NIF persona que recibe pension/anualidad reduccion |
| 0483 | 2021 | pension_recipient_nif | irpf_reduccion_pension_compensatoria_receptor_nif | RENAME: English name; NIF persona que recibe pension/anualidad reduccion |
| 0483 | 2022 | pension_recipient_nif | irpf_reduccion_pension_compensatoria_receptor_nif | RENAME: English name; NIF persona que recibe pension/anualidad reduccion |
| 0483 | 2023 | pension_recipient_nif | irpf_reduccion_pension_compensatoria_receptor_nif | RENAME: English name; NIF persona que recibe pension/anualidad reduccion |
| 0483 | 2024 | pension_recipient_nif | irpf_reduccion_pension_compensatoria_receptor_nif | RENAME: English name; NIF persona que recibe pension/anualidad reduccion |
| 0483 | 2025 | pension_recipient_nif | irpf_reduccion_pension_compensatoria_receptor_nif | RENAME: English name; NIF persona que recibe pension/anualidad reduccion |
| 0487 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0487 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0487 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0487 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0487 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0487 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 0491 | 2020 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0491 | 2021 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0491 | 2022 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0491 | 2023 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0491 | 2024 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0491 | 2025 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0506 | 2020 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0506 | 2021 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0506 | 2022 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0506 | 2023 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0506 | 2024 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0506 | 2025 | irpf_reduccion_tributacion_conjunta | irpf_reduccion_tributacion_conjunta_aplicada | SPLIT: 0461=reduction amount; 0491/0506=applied/remainder carry-forward |
| 0534 | 2020 | irpf_tipo_medio_gravamen_general_estatal | irpf_tipo_medio_gravamen_base_liquidable_general_estatal | RENAME: clarify base_liquidable context |
| 0534 | 2021 | irpf_tipo_medio_gravamen_general_estatal | irpf_tipo_medio_gravamen_base_liquidable_general_estatal | RENAME: clarify base_liquidable context |
| 0534 | 2022 | irpf_tipo_medio_gravamen_general_estatal | irpf_tipo_medio_gravamen_base_liquidable_general_estatal | RENAME: clarify base_liquidable context |
| 0534 | 2023 | irpf_tipo_medio_gravamen_general_estatal | irpf_tipo_medio_gravamen_base_liquidable_general_estatal | RENAME: clarify base_liquidable context |
| 0534 | 2024 | irpf_tipo_medio_gravamen_general_estatal | irpf_tipo_medio_gravamen_base_liquidable_general_estatal | RENAME: clarify base_liquidable context |
| 0534 | 2025 | irpf_tipo_medio_gravamen_general_estatal | irpf_tipo_medio_gravamen_base_liquidable_general_estatal | RENAME: clarify base_liquidable context |
| 0537 | 2020 | irpf_escala_sobre_base_ahorro_autonomico | irpf_escala_general_resultado_autonomico | RENAME: labels confirm general scale resultado autonomico, not base ahorro scale |
| 0537 | 2021 | irpf_escala_sobre_base_ahorro_autonomico | irpf_escala_general_resultado_autonomico | RENAME: labels confirm general scale resultado autonomico, not base ahorro scale |
| 0537 | 2022 | irpf_escala_sobre_base_ahorro_autonomico | irpf_escala_general_resultado_autonomico | RENAME: labels confirm general scale resultado autonomico, not base ahorro scale |
| 0537 | 2023 | irpf_escala_sobre_base_ahorro_autonomico | irpf_escala_general_resultado_autonomico | RENAME: labels confirm general scale resultado autonomico, not base ahorro scale |
| 0537 | 2024 | irpf_escala_sobre_base_ahorro_autonomico | irpf_escala_general_resultado_autonomico | RENAME: labels confirm general scale resultado autonomico, not base ahorro scale |
| 0537 | 2025 | irpf_escala_sobre_base_ahorro_autonomico | irpf_escala_general_resultado_autonomico | RENAME: labels confirm general scale resultado autonomico, not base ahorro scale |
| 0578 | 2020 | irpf_intereses_demora_perdida_deduccion_autonomica | irpf_intereses_demora_perdida_deduccion_estatal | OUTLIER: 2020 intereses demora estatal; id-reuse |
| 0578 | 2021 | irpf_intereses_demora_perdida_deduccion_autonomica | irpf_intereses_demora_perdida_deduccion_estatal | OUTLIER: 2021 intereses demora estatal; id-reuse |
| 0580 | 2020 | irpf_flag_regularizacion_da45_autonomico | irpf_flag_regularizacion_da45 | RENAME: suffix _autonomico incorrect; DA45 applies to both state and autonomic |
| 0580 | 2021 | irpf_flag_regularizacion_da45_autonomico | irpf_flag_regularizacion_da45 | RENAME: suffix _autonomico incorrect; DA45 applies to both state and autonomic |
| 0580 | 2022 | irpf_flag_regularizacion_da45_autonomico | irpf_flag_regularizacion_da45 | RENAME: suffix _autonomico incorrect; DA45 applies to both state and autonomic |
| 0580 | 2023 | irpf_flag_regularizacion_da45_autonomico | irpf_flag_regularizacion_da45 | RENAME: suffix _autonomico incorrect; DA45 applies to both state and autonomic |
| 0580 | 2024 | irpf_flag_regularizacion_da45_autonomico | irpf_flag_regularizacion_da45 | RENAME: suffix _autonomico incorrect; DA45 applies to both state and autonomic |
| 0580 | 2025 | irpf_flag_regularizacion_da45_autonomico | irpf_flag_regularizacion_da45 | RENAME: suffix _autonomico incorrect; DA45 applies to both state and autonomic |
| 0614 | 2020 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0614 | 2021 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0614 | 2022 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0614 | 2023 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0614 | 2024 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0614 | 2025 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0620 | 2020 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0620 | 2021 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0620 | 2022 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0620 | 2023 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0620 | 2024 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0620 | 2025 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0622 | 2020 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0622 | 2021 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0622 | 2022 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0622 | 2023 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0622 | 2024 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0622 | 2025 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0625 | 2020 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0625 | 2021 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0625 | 2022 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0625 | 2023 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0625 | 2024 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0625 | 2025 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0631 | 2020 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0631 | 2021 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0631 | 2022 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0631 | 2023 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0631 | 2024 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0631 | 2025 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0632 | 2020 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0632 | 2021 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0632 | 2022 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0632 | 2023 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0632 | 2024 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0632 | 2025 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0633 | 2020 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0633 | 2021 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0633 | 2022 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0633 | 2023 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0633 | 2024 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0633 | 2025 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0635 | 2020 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0635 | 2021 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0635 | 2022 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0635 | 2023 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0635 | 2024 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0635 | 2025 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0638 | 2020 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0638 | 2021 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0638 | 2022 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0638 | 2023 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0638 | 2024 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0638 | 2025 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0640 | 2020 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0640 | 2021 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0640 | 2022 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0640 | 2023 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0640 | 2024 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0640 | 2025 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0641 | 2020 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0641 | 2021 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0641 | 2022 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0641 | 2023 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0641 | 2024 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0641 | 2025 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0643 | 2020 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0643 | 2021 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0643 | 2022 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0643 | 2023 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0643 | 2024 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0643 | 2025 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 0646 | 2020 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 0646 | 2021 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 0646 | 2022 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 0646 | 2023 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 0646 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 0646 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 0654 | 2020 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0654 | 2021 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0654 | 2022 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0654 | 2023 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0654 | 2024 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0654 | 2025 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0655 | 2020 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0655 | 2021 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0655 | 2022 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0655 | 2023 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0655 | 2024 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0655 | 2025 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0656 | 2020 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0656 | 2021 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0656 | 2022 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0656 | 2023 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0656 | 2024 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0656 | 2025 | assignor_nif | irpf_cedente_nif | RENAME: English name; NIF del cedente |
| 0658 | 2020 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0658 | 2021 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0658 | 2022 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0658 | 2023 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0658 | 2024 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0658 | 2025 | beneficiary_nif | irpf_deduccion_familiar_beneficiario_nif | RENAME: English name; NIF beneficiario deducciones familiares |
| 0665 | 2020 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0665 | 2021 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0665 | 2022 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0665 | 2023 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0665 | 2024 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0665 | 2025 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 0667 | 2020 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0667 | 2021 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0667 | 2022 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0667 | 2023 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0667 | 2024 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0667 | 2025 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| 0680 | 2020 | irpf_regularizacion_resultado | irpf_regularizacion_complementaria_resultado | SPLIT: 0680 declaracion complementaria resultado; 0685 solicitud rectificacion autoliquidacion |
| 0680 | 2021 | irpf_regularizacion_resultado | irpf_regularizacion_complementaria_resultado | SPLIT: 0680 declaracion complementaria resultado; 0685 solicitud rectificacion autoliquidacion |
| 0680 | 2022 | irpf_regularizacion_resultado | irpf_regularizacion_complementaria_resultado | SPLIT: 0680 declaracion complementaria resultado; 0685 solicitud rectificacion autoliquidacion |
| 0680 | 2023 | irpf_regularizacion_resultado | irpf_regularizacion_complementaria_resultado | SPLIT: 0680 declaracion complementaria resultado; 0685 solicitud rectificacion autoliquidacion |
| 0685 | 2020 | irpf_regularizacion_resultado | irpf_regularizacion_rectificacion_resultado | SPLIT: 0680 declaracion complementaria resultado; 0685 solicitud rectificacion autoliquidacion |
| 0685 | 2021 | irpf_regularizacion_resultado | irpf_regularizacion_rectificacion_resultado | SPLIT: 0680 declaracion complementaria resultado; 0685 solicitud rectificacion autoliquidacion |
| 0685 | 2022 | irpf_regularizacion_resultado | irpf_regularizacion_rectificacion_resultado | SPLIT: 0680 declaracion complementaria resultado; 0685 solicitud rectificacion autoliquidacion |
| 0685 | 2023 | irpf_regularizacion_resultado | irpf_regularizacion_rectificacion_resultado | SPLIT: 0680 declaracion complementaria resultado; 0685 solicitud rectificacion autoliquidacion |
| 0685 | 2024 | irpf_regularizacion_resultado | irpf_regularizacion_rectificacion_resultado | SPLIT: 0680 declaracion complementaria resultado; 0685 solicitud rectificacion autoliquidacion |
| 0685 | 2025 | irpf_regularizacion_resultado | irpf_regularizacion_rectificacion_resultado | SPLIT: 0680 declaracion complementaria resultado; 0685 solicitud rectificacion autoliquidacion |
| 0687 | 2020 | rectification_iban | irpf_rectificacion_iban | RENAME: English name; IBAN rectificacion |
| 0696 | 2020 | spouse_compensation_iban | irpf_compensacion_conyuges_iban | RENAME: English name; compensacion conyuges IBAN |
| 0697 | 2020 | irpf_compensacion_conyuges_swift_flag | irpf_compensacion_conyuges_swift_bic | RENAME: SWIFT field is BIC code, not a flag |
| 0701 | 2020 | irpf_resultado_rectificacion_devolucion | irpf_deduccion_autonomica_parte_autonomica_importe | OUTLIER: 2020 label Parte autonomica importe deduccion; id-reuse |
| 0706 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_vivienda_habitual_pagos_promotor_importe | OUTLIER: 2020 label pagos al promotor; id-reuse |
| 0707 | 2020 | construction_entity_nif | irpf_vivienda_habitual_promotor_nif | SPLIT: 0707/2020 promotor constructor; 1918 vendedor EV; 1931 instalador EV |
| 0711 | 2020 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0711 | 2021 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0711 | 2022 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0711 | 2023 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0711 | 2024 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0711 | 2025 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0713 | 2020 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0713 | 2021 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0713 | 2022 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0713 | 2023 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0713 | 2024 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0713 | 2025 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 0715 | 2020 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0715 | 2021 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0715 | 2022 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0715 | 2023 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0715 | 2024 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0715 | 2025 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0717 | 2020 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0717 | 2021 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0717 | 2022 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0717 | 2023 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0717 | 2024 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0717 | 2025 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 0721 | 2020 | irpf_deduccion_general_importe | irpf_deduccion_cuota_general_importe | RENAME: context is deduccion cuota general |
| 0721 | 2021 | irpf_deduccion_general_importe | irpf_deduccion_cuota_general_importe | RENAME: context is deduccion cuota general |
| 0721 | 2022 | irpf_deduccion_general_importe | irpf_deduccion_cuota_general_importe | RENAME: context is deduccion cuota general |
| 0721 | 2023 | irpf_deduccion_general_importe | irpf_deduccion_cuota_general_importe | RENAME: context is deduccion cuota general |
| 0721 | 2024 | irpf_deduccion_general_importe | irpf_deduccion_cuota_general_importe | RENAME: context is deduccion cuota general |
| 0721 | 2025 | irpf_deduccion_general_importe | irpf_deduccion_cuota_general_importe | RENAME: context is deduccion cuota general |
| 0722 | 2020 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0722 | 2021 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0722 | 2022 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0722 | 2023 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0722 | 2024 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0722 | 2025 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0723 | 2020 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0723 | 2021 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0723 | 2022 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0723 | 2023 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0723 | 2024 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0723 | 2025 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0724 | 2020 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0724 | 2021 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0724 | 2022 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0724 | 2023 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0724 | 2024 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0724 | 2025 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0725 | 2020 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0725 | 2021 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0725 | 2022 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0725 | 2023 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0725 | 2024 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0725 | 2025 | irpf_anexo_a_donativo_deduccion_importe | irpf_anexo_a_deducciones_donativo_importe | RENAME: section heading deducciones; donativo_importe consistent |
| 0770 | 2022 | irpf_deduccion_baleares_ela | irpf_deduccion_baleares_acogida_ucrania | SPLIT: 0770/2022 acogida Ucrania; 0770/2023 alza precios; 0770/2024-2025 ELA; id-reuse |
| 0770 | 2023 | irpf_deduccion_baleares_ela | irpf_deduccion_baleares_subvenciones_alza_precios | SPLIT: 0770/2022 acogida Ucrania; 0770/2023 alza precios; 0770/2024-2025 ELA; id-reuse |
| 0800 | 2022 | irpf_deduccion_asturias_vivienda_protegida_pendiente | irpf_deduccion_asturias_vivienda_protegida_anio_anterior_pendiente | RENAME: clarify anio anterior context |
| 0800 | 2023 | irpf_deduccion_asturias_vivienda_protegida_pendiente | irpf_deduccion_asturias_vivienda_protegida_anio_anterior_pendiente | RENAME: clarify anio anterior context |
| 0800 | 2024 | irpf_deduccion_asturias_vivienda_protegida_pendiente | irpf_deduccion_asturias_vivienda_protegida_anio_anterior_pendiente | RENAME: clarify anio anterior context |
| 0800 | 2025 | irpf_deduccion_asturias_vivienda_protegida_pendiente | irpf_deduccion_asturias_vivienda_protegida_anio_anterior_pendiente | RENAME: clarify anio anterior context |
| 0804 | 2022 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0804 | 2023 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0804 | 2024 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0804 | 2025 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0807 | 2022 | irpf_deduccion_c_valenciana_generado_2024_pendiente | irpf_deduccion_c_valenciana_pendiente_aplicacion | RENAME: year-literal in role name; pendiente aplicacion stable |
| 0807 | 2023 | irpf_deduccion_c_valenciana_generado_2024_pendiente | irpf_deduccion_c_valenciana_pendiente_aplicacion | RENAME: year-literal in role name; pendiente aplicacion stable |
| 0807 | 2024 | irpf_deduccion_c_valenciana_generado_2024_pendiente | irpf_deduccion_c_valenciana_pendiente_aplicacion | RENAME: year-literal in role name; pendiente aplicacion stable |
| 0807 | 2025 | irpf_deduccion_c_valenciana_generado_2024_pendiente | irpf_deduccion_c_valenciana_pendiente_aplicacion | RENAME: year-literal in role name; pendiente aplicacion stable |
| 0808 | 2022 | irpf_deduccion_c_valenciana_generado_pendiente_aplicacion | irpf_deduccion_c_valenciana_aplicado_ejercicio | SPLIT: 0808/2022 importe aplicado; 0848/2024-2025 generado pendiente; id-reuse |
| 0814 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_deduccion_cop25_importe | OUTLIER: 2020 label COP25 conference deduction; id-reuse |
| 0822 | 2020 | irpf_deduccion_asturias_subvenciones_rehabilitacion | irpf_deduccion_paliar_covid_subvenciones_importe | OUTLIER: 2020 label subvenciones ayudas COVID; id-reuse |
| 0822 | 2021 | irpf_deduccion_asturias_subvenciones_rehabilitacion | irpf_deduccion_paliar_covid_subvenciones_importe | OUTLIER: 2021 label subvenciones ayudas COVID; id-reuse |
| 0827 | 2020 | irpf_deduccion_galicia_certificado_eficiencia_2 | irpf_deduccion_galicia_eficiencia_energetica_obras_edificios | OUTLIER: 2020 label obras mejora eficiencia edificios; id-reuse |
| 0829 | 2025 | irpf_deduccion_galicia_generado_2025 | irpf_deduccion_galicia_eficiencia_energetica_generado | RENAME: year-literal; eficiencia energetica generado |
| 0848 | 2024 | irpf_deduccion_c_valenciana_generado_pendiente_aplicacion | irpf_deduccion_c_valenciana_generado_pendiente | SPLIT: 0808/2022 importe aplicado; 0848/2024-2025 generado pendiente; id-reuse |
| 0848 | 2025 | irpf_deduccion_c_valenciana_generado_pendiente_aplicacion | irpf_deduccion_c_valenciana_generado_pendiente | SPLIT: 0808/2022 importe aplicado; 0848/2024-2025 generado pendiente; id-reuse |
| 0859 | 2020 | irpf_deduccion_andalucia_empleada_hogar_ccc_1 | irpf_deduccion_andalucia_empleada_hogar_ccc | RENAME: numeric suffix _1 transient; single CCC field |
| 0859 | 2021 | irpf_deduccion_andalucia_empleada_hogar_ccc_1 | irpf_deduccion_andalucia_empleada_hogar_ccc | RENAME: numeric suffix _1 transient; single CCC field |
| 0859 | 2022 | irpf_deduccion_andalucia_empleada_hogar_ccc_1 | irpf_deduccion_andalucia_empleada_hogar_ccc | RENAME: numeric suffix _1 transient; single CCC field |
| 0859 | 2023 | irpf_deduccion_andalucia_empleada_hogar_ccc_1 | irpf_deduccion_andalucia_empleada_hogar_ccc | RENAME: numeric suffix _1 transient; single CCC field |
| 0859 | 2024 | irpf_deduccion_andalucia_empleada_hogar_ccc_1 | irpf_deduccion_andalucia_empleada_hogar_ccc | RENAME: numeric suffix _1 transient; single CCC field |
| 0859 | 2025 | irpf_deduccion_andalucia_empleada_hogar_ccc_1 | irpf_deduccion_andalucia_empleada_hogar_ccc | RENAME: numeric suffix _1 transient; single CCC field |
| 0862 | 2020 | irpf_deduccion_andalucia_empleada_hogar_importe_2 | irpf_deduccion_andalucia_empleada_hogar_importe | RENAME: numeric suffix _2 transient; single importe field |
| 0862 | 2021 | irpf_deduccion_andalucia_empleada_hogar_importe_2 | irpf_deduccion_andalucia_empleada_hogar_importe | RENAME: numeric suffix _2 transient; single importe field |
| 0862 | 2022 | irpf_deduccion_andalucia_empleada_hogar_importe_2 | irpf_deduccion_andalucia_empleada_hogar_importe | RENAME: numeric suffix _2 transient; single importe field |
| 0862 | 2023 | irpf_deduccion_andalucia_empleada_hogar_importe_2 | irpf_deduccion_andalucia_empleada_hogar_importe | RENAME: numeric suffix _2 transient; single importe field |
| 0862 | 2024 | irpf_deduccion_andalucia_empleada_hogar_importe_2 | irpf_deduccion_andalucia_empleada_hogar_importe | RENAME: numeric suffix _2 transient; single importe field |
| 0862 | 2025 | irpf_deduccion_andalucia_empleada_hogar_importe_2 | irpf_deduccion_andalucia_empleada_hogar_importe | RENAME: numeric suffix _2 transient; single importe field |
| 0870 | 2020 | irpf_deduccion_aragon_donativos_ecologicos_id | irpf_deduccion_aragon_donativos_ecologicos | RENAME: suffix _id transient; stable deduccion |
| 0870 | 2021 | irpf_deduccion_aragon_donativos_ecologicos_id | irpf_deduccion_aragon_donativos_ecologicos | RENAME: suffix _id transient; stable deduccion |
| 0870 | 2022 | irpf_deduccion_aragon_donativos_ecologicos_id | irpf_deduccion_aragon_donativos_ecologicos | RENAME: suffix _id transient; stable deduccion |
| 0870 | 2023 | irpf_deduccion_aragon_donativos_ecologicos_id | irpf_deduccion_aragon_donativos_ecologicos | RENAME: suffix _id transient; stable deduccion |
| 0870 | 2024 | irpf_deduccion_aragon_donativos_ecologicos_id | irpf_deduccion_aragon_donativos_ecologicos | RENAME: suffix _id transient; stable deduccion |
| 0870 | 2025 | irpf_deduccion_aragon_donativos_ecologicos_id | irpf_deduccion_aragon_donativos_ecologicos | RENAME: suffix _id transient; stable deduccion |
| 0885 | 2020 | irpf_deduccion_aragon_clases_apoyo | irpf_deduccion_asturias_vivienda_protegida | OUTLIER: 0885/2020 label Asturias vivienda protegida; id-reuse |
| 0885 | 2021 | irpf_deduccion_aragon_clases_apoyo | irpf_deduccion_asturias_vivienda_protegida | OUTLIER: 0885/2021 label Asturias vivienda protegida; id-reuse |
| 0885 | 2022 | irpf_deduccion_aragon_clases_apoyo | irpf_deduccion_asturias_vivienda_protegida | OUTLIER: 0885/2022 label Asturias vivienda protegida; id-reuse |
| 0888 | 2020 | irpf_deduccion_aragon_formacion_autonomia | irpf_deduccion_asturias_donacion_fincas_rusticas | SPLIT: 0888/2020-2022 Asturias donacion fincas rusticas; 0888/2024+ Aragon formacion autonomia; id-reuse |
| 0888 | 2021 | irpf_deduccion_aragon_formacion_autonomia | irpf_deduccion_asturias_donacion_fincas_rusticas | SPLIT: 0888/2020-2022 Asturias donacion fincas rusticas; 0888/2024+ Aragon formacion autonomia; id-reuse |
| 0888 | 2022 | irpf_deduccion_aragon_formacion_autonomia | irpf_deduccion_asturias_donacion_fincas_rusticas | SPLIT: 0888/2020-2022 Asturias donacion fincas rusticas; 0888/2024+ Aragon formacion autonomia; id-reuse |
| 0904 | 2020 | irpf_deduccion_baleares_donaciones_investigacion_2 | irpf_deduccion_baleares_mecenazgo_deportivo | RENAME: labels confirm mecenazgo deportivo |
| 0904 | 2021 | irpf_deduccion_baleares_donaciones_investigacion_2 | irpf_deduccion_baleares_mecenazgo_deportivo | RENAME: labels confirm mecenazgo deportivo |
| 0904 | 2022 | irpf_deduccion_baleares_donaciones_investigacion_2 | irpf_deduccion_baleares_mecenazgo_deportivo | RENAME: labels confirm mecenazgo deportivo |
| 0904 | 2023 | irpf_deduccion_baleares_donaciones_investigacion_2 | irpf_deduccion_baleares_mecenazgo_deportivo | RENAME: labels confirm mecenazgo deportivo |
| 0904 | 2024 | irpf_deduccion_baleares_donaciones_investigacion_2 | irpf_deduccion_baleares_mecenazgo_deportivo | RENAME: labels confirm mecenazgo deportivo |
| 0904 | 2025 | irpf_deduccion_baleares_donaciones_investigacion_2 | irpf_deduccion_baleares_mecenazgo_deportivo | RENAME: labels confirm mecenazgo deportivo |
| 0911 | 2020 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 0911 | 2021 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 0911 | 2022 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 0911 | 2023 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 0911 | 2024 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 0911 | 2025 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 0921 | 2020 | irpf_deduccion_andalucia_ejercicio_fisico | irpf_deduccion_canarias_donacion_descendientes | OUTLIER: 2020 label donaciones Canarias descendientes; id-reuse |
| 0944 | 2020 | irpf_deduccion_canarias_seguros_credito_impago | irpf_deduccion_canarias_arrendamiento_precio_social | OUTLIER: 2020 label arrendamientos sostenibilidad social; id-reuse |
| 0949 | 2020 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 0949 | 2021 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 0949 | 2022 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 0949 | 2023 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 0949 | 2024 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 0949 | 2025 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 0950 | 2020 | irpf_deduccion_cantabria_obras_mejora_generado | irpf_deduccion_cantabria_importe | RENAME: labels generic Importe; obras_mejora too narrow |
| 0950 | 2021 | irpf_deduccion_cantabria_obras_mejora_generado | irpf_deduccion_cantabria_importe | RENAME: labels generic Importe; obras_mejora too narrow |
| 0950 | 2022 | irpf_deduccion_cantabria_obras_mejora_generado | irpf_deduccion_cantabria_importe | RENAME: labels generic Importe; obras_mejora too narrow |
| 0950 | 2023 | irpf_deduccion_cantabria_obras_mejora_generado | irpf_deduccion_cantabria_importe | RENAME: labels generic Importe; obras_mejora too narrow |
| 0950 | 2024 | irpf_deduccion_cantabria_obras_mejora_generado | irpf_deduccion_cantabria_importe | RENAME: labels generic Importe; obras_mejora too narrow |
| 0950 | 2025 | irpf_deduccion_cantabria_obras_mejora_generado | irpf_deduccion_cantabria_importe | RENAME: labels generic Importe; obras_mejora too narrow |
| 0980 | 2020 | irpf_deduccion_castilla_y_leon_rehabilitacion_rural | irpf_deduccion_castilla_y_leon_fomento_emprendimiento | OUTLIER: 2020 label fomento emprendimiento; id-reuse |
| 0980 | 2021 | irpf_deduccion_castilla_y_leon_rehabilitacion_rural | irpf_deduccion_castilla_y_leon_fomento_emprendimiento | OUTLIER: 2021 label fomento emprendimiento; id-reuse |
| 0982 | 2025 | irpf_deduccion_galicia_generado_2025_pendiente_2 | irpf_deduccion_galicia_pendiente_ejercicio_anterior_2 | RENAME: year-literal; pendiente ejercicio anterior stable |
| 0988 | 2020 | irpf_deduccion_castilla_y_leon_partos_multiples_2023 | irpf_deduccion_castilla_y_leon_partos_multiples | RENAME: year-literal; partos multiples stable |
| 0988 | 2021 | irpf_deduccion_castilla_y_leon_partos_multiples_2023 | irpf_deduccion_castilla_y_leon_partos_multiples | RENAME: year-literal; partos multiples stable |
| 0988 | 2022 | irpf_deduccion_castilla_y_leon_partos_multiples_2023 | irpf_deduccion_castilla_y_leon_partos_multiples | RENAME: year-literal; partos multiples stable |
| 0988 | 2023 | irpf_deduccion_castilla_y_leon_partos_multiples_2023 | irpf_deduccion_castilla_y_leon_partos_multiples | RENAME: year-literal; partos multiples stable |
| 0988 | 2024 | irpf_deduccion_castilla_y_leon_partos_multiples_2023 | irpf_deduccion_castilla_y_leon_partos_multiples | RENAME: year-literal; partos multiples stable |
| 0988 | 2025 | irpf_deduccion_castilla_y_leon_partos_multiples_2023 | irpf_deduccion_castilla_y_leon_partos_multiples | RENAME: year-literal; partos multiples stable |
| 0989 | 2020 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0989 | 2021 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0989 | 2022 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0989 | 2023 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0989 | 2024 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0989 | 2025 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0991 | 2020 | irpf_deduccion_castilla_y_leon_nacimiento_adopcion | irpf_deduccion_castilla_y_leon_paternidad | OUTLIER: 2020 label Por paternidad; id-reuse |
| 0993 | 2020 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0993 | 2021 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0993 | 2022 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0993 | 2023 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0993 | 2024 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0993 | 2025 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 0995 | 2020 | irpf_deduccion_andalucia_gastos_veterinarios | irpf_deduccion_canarias_arrendamiento_precio_social | OUTLIER: 2020 label arrendamientos sostenibilidad social Canarias; id-reuse |
| 0998 | 2024 | irpf_deduccion_cantabria_generado_2024_pendiente | irpf_deduccion_cantabria_pendiente_aplicacion | RENAME: year-literal in role name; pendiente aplicacion stable |
| 0998 | 2025 | irpf_deduccion_cantabria_generado_2024_pendiente | irpf_deduccion_cantabria_pendiente_aplicacion | RENAME: year-literal in role name; pendiente aplicacion stable |
| 1037 | 2020 | irpf_deduccion_galicia_generado_2025_linea_2 | irpf_deduccion_galicia_danos_pirotecnia | SPLIT: 1037/2020-2024 daños pirotecnia; 1037/2025 importe generado linea 2; year-literal + id-reuse |
| 1037 | 2021 | irpf_deduccion_galicia_generado_2025_linea_2 | irpf_deduccion_galicia_danos_pirotecnia | SPLIT: 1037/2020-2024 daños pirotecnia; 1037/2025 importe generado linea 2; year-literal + id-reuse |
| 1037 | 2022 | irpf_deduccion_galicia_generado_2025_linea_2 | irpf_deduccion_galicia_danos_pirotecnia | SPLIT: 1037/2020-2024 daños pirotecnia; 1037/2025 importe generado linea 2; year-literal + id-reuse |
| 1037 | 2023 | irpf_deduccion_galicia_generado_2025_linea_2 | irpf_deduccion_galicia_danos_pirotecnia | SPLIT: 1037/2020-2024 daños pirotecnia; 1037/2025 importe generado linea 2; year-literal + id-reuse |
| 1037 | 2024 | irpf_deduccion_galicia_generado_2025_linea_2 | irpf_deduccion_galicia_danos_pirotecnia | SPLIT: 1037/2020-2024 daños pirotecnia; 1037/2025 importe generado linea 2; year-literal + id-reuse |
| 1037 | 2025 | irpf_deduccion_galicia_generado_2025_linea_2 | irpf_deduccion_galicia_generado_linea_2 | RENAME: year-literal in role name |
| 1050 | 2020 | irpf_deduccion_madrid_donativos_importe | irpf_deduccion_madrid_cuidado_hijos_dependientes | RENAME: labels confirm cuidado hijos/dependientes, not donativos |
| 1050 | 2021 | irpf_deduccion_madrid_donativos_importe | irpf_deduccion_madrid_cuidado_hijos_dependientes | RENAME: labels confirm cuidado hijos/dependientes, not donativos |
| 1050 | 2022 | irpf_deduccion_madrid_donativos_importe | irpf_deduccion_madrid_cuidado_hijos_dependientes | RENAME: labels confirm cuidado hijos/dependientes, not donativos |
| 1050 | 2023 | irpf_deduccion_madrid_donativos_importe | irpf_deduccion_madrid_cuidado_hijos_dependientes | RENAME: labels confirm cuidado hijos/dependientes, not donativos |
| 1050 | 2024 | irpf_deduccion_madrid_donativos_importe | irpf_deduccion_madrid_cuidado_hijos_dependientes | RENAME: labels confirm cuidado hijos/dependientes, not donativos |
| 1050 | 2025 | irpf_deduccion_madrid_donativos_importe | irpf_deduccion_madrid_cuidado_hijos_dependientes | RENAME: labels confirm cuidado hijos/dependientes, not donativos |
| 1063 | 2020 | irpf_deduccion_la_rioja_vivienda_municipio | irpf_deduccion_la_rioja_vivienda_habitual_jovenes | RENAME: labels confirm vivienda habitual jovenes |
| 1063 | 2021 | irpf_deduccion_la_rioja_vivienda_municipio | irpf_deduccion_la_rioja_vivienda_habitual_jovenes | RENAME: labels confirm vivienda habitual jovenes |
| 1063 | 2022 | irpf_deduccion_la_rioja_vivienda_municipio | irpf_deduccion_la_rioja_vivienda_habitual_jovenes | RENAME: labels confirm vivienda habitual jovenes |
| 1063 | 2023 | irpf_deduccion_la_rioja_vivienda_municipio | irpf_deduccion_la_rioja_vivienda_habitual_jovenes | RENAME: labels confirm vivienda habitual jovenes |
| 1063 | 2024 | irpf_deduccion_la_rioja_vivienda_municipio | irpf_deduccion_la_rioja_vivienda_habitual_jovenes | RENAME: labels confirm vivienda habitual jovenes |
| 1063 | 2025 | irpf_deduccion_la_rioja_vivienda_municipio | irpf_deduccion_la_rioja_vivienda_habitual_jovenes | RENAME: labels confirm vivienda habitual jovenes |
| 1064 | 2020 | irpf_deduccion_la_rioja_vivienda_municipio_codigo | irpf_deduccion_la_rioja_vivienda_codigo_municipio | RENAME: reorder for clarity; codigo_municipio standard pattern |
| 1064 | 2021 | irpf_deduccion_la_rioja_vivienda_municipio_codigo | irpf_deduccion_la_rioja_vivienda_codigo_municipio | RENAME: reorder for clarity; codigo_municipio standard pattern |
| 1064 | 2022 | irpf_deduccion_la_rioja_vivienda_municipio_codigo | irpf_deduccion_la_rioja_vivienda_codigo_municipio | RENAME: reorder for clarity; codigo_municipio standard pattern |
| 1064 | 2023 | irpf_deduccion_la_rioja_vivienda_municipio_codigo | irpf_deduccion_la_rioja_vivienda_codigo_municipio | RENAME: reorder for clarity; codigo_municipio standard pattern |
| 1064 | 2024 | irpf_deduccion_la_rioja_vivienda_municipio_codigo | irpf_deduccion_la_rioja_vivienda_codigo_municipio | RENAME: reorder for clarity; codigo_municipio standard pattern |
| 1064 | 2025 | irpf_deduccion_la_rioja_vivienda_municipio_codigo | irpf_deduccion_la_rioja_vivienda_codigo_municipio | RENAME: reorder for clarity; codigo_municipio standard pattern |
| 1070 | 2021 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1070 | 2022 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1070 | 2023 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1070 | 2024 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1070 | 2025 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1071 | 2020 | irpf_deduccion_la_rioja_guarderia_municipio_codigo | irpf_deduccion_la_rioja_guarderia_importe | OUTLIER: 2020 label Importe de la deduccion; id-reuse |
| 1076 | 2020 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1076 | 2021 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1076 | 2022 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1076 | 2023 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1076 | 2024 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1076 | 2025 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1078 | 2025 | irpf_anexo_b_carry_forward_pending | irpf_deduccion_inmueble_vacio_adecuacion_pendiente | OUTLIER: 2025 label gastos adecuacion inmueble vacio; id-reuse |
| 1091 | 2020 | irpf_deduccion_extremadura_vivienda_zonas_rurales | irpf_deduccion_extremadura_conciliacion_familiar | OUTLIER: 2020 label realizacion conyuge conciliacion; id-reuse |
| 1091 | 2021 | irpf_deduccion_extremadura_vivienda_zonas_rurales | irpf_deduccion_extremadura_conciliacion_familiar | OUTLIER: 2021 label realizacion conyuge conciliacion; id-reuse |
| 1096 | 2020 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1096 | 2021 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1096 | 2022 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1096 | 2023 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1096 | 2024 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1096 | 2025 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1097 | 2020 | irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto | irpf_deduccion_c_valenciana_arrendamiento_vivienda | SPLIT: 1097/2020-2021 rentas arrendamiento vivienda old law; 1097/2022+ municipio distinto |
| 1097 | 2021 | irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto | irpf_deduccion_c_valenciana_arrendamiento_vivienda | SPLIT: 1097/2020-2021 rentas arrendamiento vivienda old law; 1097/2022+ municipio distinto |
| 1098 | 2020 | irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto_flag | irpf_deduccion_c_valenciana_arrendador_nif_extranjero_flag | RENAME: label confirms arrendador NIF extranjero flag |
| 1098 | 2021 | irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto_flag | irpf_deduccion_c_valenciana_arrendador_nif_extranjero_flag | RENAME: label confirms arrendador NIF extranjero flag |
| 1098 | 2022 | irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto_flag | irpf_deduccion_c_valenciana_arrendador_nif_extranjero_flag | RENAME: label confirms arrendador NIF extranjero flag |
| 1098 | 2023 | irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto_flag | irpf_deduccion_c_valenciana_arrendador_nif_extranjero_flag | RENAME: label confirms arrendador NIF extranjero flag |
| 1098 | 2024 | irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto_flag | irpf_deduccion_c_valenciana_arrendador_nif_extranjero_flag | RENAME: label confirms arrendador NIF extranjero flag |
| 1098 | 2025 | irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto_flag | irpf_deduccion_c_valenciana_arrendador_nif_extranjero_flag | RENAME: label confirms arrendador NIF extranjero flag |
| 1105 | 2020 | irpf_deduccion_extremadura_residencia_municipios_pequenos | irpf_deduccion_c_valenciana_ayudas_publicas_generalitat | OUTLIER: 2020 label ayudas publicas Generalitat Valencia; id-reuse |
| 1107 | 2020 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1107 | 2021 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1107 | 2022 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1107 | 2023 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1107 | 2024 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1107 | 2025 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1109 | 2020 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1109 | 2021 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1109 | 2022 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1109 | 2023 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1109 | 2024 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1109 | 2025 | service_provider_nif | irpf_vivienda_habitual_obras_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1114 | 2021 | irpf_deduccion_c_valenciana_autoconsumo_hasta_2022 | irpf_deduccion_c_valenciana_autoconsumo_total_importe | OUTLIER: 2021 label importe total deduccion (sum); id-reuse |
| 1115 | 2023 | irpf_anexo_b_carry_forward_pending | irpf_deduccion_autonomica_cuidado_ascendientes_pendiente | OUTLIER: 2023 label cuidado ascendientes; id-reuse |
| 1116 | 2020 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_arrendamiento_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1116 | 2021 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_arrendamiento_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1116 | 2022 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_arrendamiento_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1116 | 2023 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_arrendamiento_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1116 | 2024 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_arrendamiento_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1116 | 2025 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_arrendamiento_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1117 | 2020 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_arrendamiento_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1117 | 2021 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_arrendamiento_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1117 | 2022 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_arrendamiento_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1117 | 2023 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_arrendamiento_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1117 | 2024 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_arrendamiento_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1117 | 2025 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_arrendamiento_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1118 | 2023 | irpf_anexo_b_carry_forward_pending | irpf_deduccion_estudios_intereses_prestamo_pendiente | OUTLIER: 2023 label intereses prestamos estudios; id-reuse |
| 1119 | 2020 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_nacimiento_vivienda_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1119 | 2021 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_nacimiento_vivienda_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1119 | 2022 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_nacimiento_vivienda_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1119 | 2023 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_nacimiento_vivienda_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1119 | 2024 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_nacimiento_vivienda_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1119 | 2025 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_nacimiento_vivienda_importe_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1120 | 2020 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_nacimiento_vivienda_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1120 | 2021 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_nacimiento_vivienda_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1120 | 2022 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_nacimiento_vivienda_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1120 | 2023 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_nacimiento_vivienda_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1120 | 2024 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_nacimiento_vivienda_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1120 | 2025 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_nacimiento_vivienda_importe_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1122 | 2020 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1122 | 2021 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1122 | 2022 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1122 | 2023 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1122 | 2024 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1122 | 2025 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1124 | 2020 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1124 | 2021 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1124 | 2022 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1124 | 2023 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1124 | 2024 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1124 | 2025 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1125 | 2020 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1125 | 2021 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1125 | 2022 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1125 | 2023 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1125 | 2024 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1125 | 2025 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 1127 | 2020 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1127 | 2021 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1127 | 2022 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1127 | 2023 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1127 | 2024 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1127 | 2025 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1130 | 2020 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1130 | 2021 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1130 | 2022 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1130 | 2023 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1130 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1130 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1131 | 2020 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1131 | 2021 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1131 | 2022 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1131 | 2023 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1131 | 2024 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1131 | 2025 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1132 | 2020 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1132 | 2021 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1132 | 2022 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1132 | 2023 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1132 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1132 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1133 | 2020 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1133 | 2021 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1133 | 2022 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1133 | 2023 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1133 | 2024 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1133 | 2025 | investment_entity_nif | irpf_deduccion_nueva_empresa_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1134 | 2020 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1134 | 2021 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1134 | 2022 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1134 | 2023 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1134 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1134 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1135 | 2020 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1135 | 2021 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1135 | 2022 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1135 | 2023 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1135 | 2024 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1135 | 2025 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1136 | 2020 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_nueva_empresa_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1136 | 2021 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_nueva_empresa_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1136 | 2022 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_nueva_empresa_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1136 | 2023 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_nueva_empresa_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1136 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_nueva_empresa_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1136 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_nueva_empresa_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1137 | 2020 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1137 | 2021 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1137 | 2022 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1137 | 2023 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1137 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1137 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1138 | 2020 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1138 | 2021 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1138 | 2022 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1138 | 2023 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1138 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1138 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1139 | 2020 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1139 | 2021 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1139 | 2022 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1139 | 2023 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1139 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1139 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1140 | 2020 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1140 | 2021 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1140 | 2022 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1140 | 2023 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1140 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1140 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1141 | 2020 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1141 | 2021 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1141 | 2022 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1141 | 2023 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1141 | 2024 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1141 | 2025 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1142 | 2020 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1142 | 2021 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1142 | 2022 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1142 | 2023 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1142 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1142 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1143 | 2020 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1143 | 2021 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1143 | 2022 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1143 | 2023 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1143 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1143 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1144 | 2020 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1144 | 2021 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1144 | 2022 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1144 | 2023 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1144 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1144 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1145 | 2020 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1145 | 2021 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1145 | 2022 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1145 | 2023 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1145 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1145 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1146 | 2020 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1146 | 2021 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1146 | 2022 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1146 | 2023 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1146 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1146 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1147 | 2020 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1147 | 2021 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1147 | 2022 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1147 | 2023 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1147 | 2024 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1147 | 2025 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1148 | 2020 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1148 | 2021 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1148 | 2022 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1148 | 2023 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1148 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1148 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1149 | 2020 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1149 | 2021 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1149 | 2022 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1149 | 2023 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1149 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1149 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1150 | 2020 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1150 | 2021 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1150 | 2022 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1150 | 2023 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1150 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1150 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1151 | 2020 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1151 | 2021 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1151 | 2022 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1151 | 2023 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1151 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1151 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1152 | 2020 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1152 | 2021 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1152 | 2022 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1152 | 2023 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1152 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1152 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1153 | 2020 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1153 | 2021 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1153 | 2022 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1153 | 2023 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1153 | 2024 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1153 | 2025 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1154 | 2020 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1154 | 2021 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1154 | 2022 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1154 | 2023 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1154 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1154 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_inversion_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1155 | 2020 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1155 | 2021 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1155 | 2022 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1155 | 2023 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1155 | 2024 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1155 | 2025 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 1159 | 2020 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1159 | 2021 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1159 | 2022 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1159 | 2023 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1159 | 2024 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1159 | 2025 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 1168 | 2020 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1168 | 2021 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1168 | 2022 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1170 | 2020 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_viv_hab_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1170 | 2021 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_viv_hab_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1170 | 2022 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_viv_hab_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1170 | 2023 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_viv_hab_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1170 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_viv_hab_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1170 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_viv_hab_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1171 | 2020 | irpf_deduccion_c_valenciana_ayudas_publicas_generalitat | irpf_deduccion_c_valenciana_ayudas_publicas_generalitat_2020 | OUTLIER: 2020 concept differs from 2021+; rolling window |
| 1173 | 2020 | irpf_deduccion_c_valenciana_donaciones_danos_naturales | irpf_deduccion_c_valenciana_donaciones_covid19 | RENAME: labels confirm COVID-19 pandemic, not natural damages |
| 1173 | 2021 | irpf_deduccion_c_valenciana_donaciones_danos_naturales | irpf_deduccion_c_valenciana_donaciones_covid19 | RENAME: labels confirm COVID-19 pandemic, not natural damages |
| 1173 | 2022 | irpf_deduccion_c_valenciana_donaciones_danos_naturales | irpf_deduccion_c_valenciana_donaciones_covid19 | RENAME: labels confirm COVID-19 pandemic, not natural damages |
| 1173 | 2023 | irpf_deduccion_c_valenciana_donaciones_danos_naturales | irpf_deduccion_c_valenciana_donaciones_covid19 | RENAME: labels confirm COVID-19 pandemic, not natural damages |
| 1173 | 2024 | irpf_deduccion_c_valenciana_donaciones_danos_naturales | irpf_deduccion_c_valenciana_donaciones_covid19 | RENAME: labels confirm COVID-19 pandemic, not natural damages |
| 1173 | 2025 | irpf_deduccion_c_valenciana_donaciones_danos_naturales | irpf_deduccion_c_valenciana_donaciones_covid19 | RENAME: labels confirm COVID-19 pandemic, not natural damages |
| 1174 | 2020 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1174 | 2021 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1174 | 2022 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1174 | 2023 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1174 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1174 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1175 | 2020 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1175 | 2021 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1175 | 2022 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1175 | 2023 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1175 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1175 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1176 | 2020 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1176 | 2021 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1176 | 2022 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1176 | 2023 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1176 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1176 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 1177 | 2020 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1177 | 2021 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1177 | 2022 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1177 | 2023 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1177 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1177 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1178 | 2020 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1178 | 2021 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1178 | 2022 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1178 | 2023 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1178 | 2024 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1178 | 2025 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 1179 | 2020 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_otro_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1179 | 2021 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_otro_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1179 | 2022 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_otro_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1179 | 2023 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_otro_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1179 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_otro_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1179 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_otro_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1185 | 2021 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_energia_satisfecho_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1185 | 2022 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_energia_satisfecho_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1185 | 2023 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_energia_satisfecho_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1185 | 2024 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_energia_satisfecho_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1185 | 2025 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_energia_satisfecho_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1186 | 2021 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_energia_satisfecho_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1186 | 2022 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_energia_satisfecho_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1186 | 2023 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_energia_satisfecho_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1186 | 2024 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_energia_satisfecho_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1186 | 2025 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_energia_satisfecho_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1187 | 2020 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1187 | 2021 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1187 | 2022 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1187 | 2023 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1187 | 2024 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1187 | 2025 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1189 | 2020 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1189 | 2021 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1189 | 2022 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1189 | 2023 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1189 | 2024 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1189 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1191 | 2020 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1191 | 2021 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1191 | 2022 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1191 | 2023 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1191 | 2024 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1191 | 2025 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1192 | 2020 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1192 | 2021 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1192 | 2022 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1192 | 2023 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1192 | 2024 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1192 | 2025 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1194 | 2020 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1194 | 2021 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1194 | 2022 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1194 | 2023 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1194 | 2024 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1194 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1196 | 2020 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1196 | 2021 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1196 | 2022 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1196 | 2023 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1196 | 2024 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1196 | 2025 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1197 | 2020 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1197 | 2021 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1197 | 2022 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1197 | 2023 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1197 | 2024 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1197 | 2025 | tenant_nif | irpf_arrendatario_nif | RENAME: English name; NIF/NIE arrendatario capital inmobiliario |
| 1199 | 2020 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1199 | 2021 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1199 | 2022 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1199 | 2023 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1199 | 2024 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1199 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_arrendamiento_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1201 | 2020 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1201 | 2021 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1201 | 2022 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1201 | 2023 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1201 | 2024 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1201 | 2025 | irpf_anexo_b_insurance_premium | irpf_anexo_b_prima_seguro_credito_arrendamiento | RENAME: English suffix; primas seguro credito impagos arrendamiento |
| 1202 | 2020 | irpf_anexo_b_insurance_premium_total | irpf_eps_primas_seguro_deducibles_total | RENAME: English name; primas seguro satisfechas con derecho deduccion EPS |
| 1202 | 2021 | irpf_anexo_b_insurance_premium_total | irpf_eps_primas_seguro_deducibles_total | RENAME: English name; primas seguro satisfechas con derecho deduccion EPS |
| 1202 | 2022 | irpf_anexo_b_insurance_premium_total | irpf_eps_primas_seguro_deducibles_total | RENAME: English name; primas seguro satisfechas con derecho deduccion EPS |
| 1202 | 2023 | irpf_anexo_b_insurance_premium_total | irpf_eps_primas_seguro_deducibles_total | RENAME: English name; primas seguro satisfechas con derecho deduccion EPS |
| 1202 | 2024 | irpf_anexo_b_insurance_premium_total | irpf_eps_primas_seguro_deducibles_total | RENAME: English name; primas seguro satisfechas con derecho deduccion EPS |
| 1202 | 2025 | irpf_anexo_b_insurance_premium_total | irpf_eps_primas_seguro_deducibles_total | RENAME: English name; primas seguro satisfechas con derecho deduccion EPS |
| 1203 | 2020 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1203 | 2021 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_arrendamiento_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1203 | 2022 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_seguro_credito_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1203 | 2023 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_seguro_credito_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1203 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_seguro_credito_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1203 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_seguro_credito_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 1206 | 2023 | irpf_deduccion_castilla_y_leon_progenitor_1_nif_texto | irpf_deduccion_castilla_y_leon_otro_progenitor_1_nif | RENAME: otro_progenitor context; _texto suffix transient |
| 1206 | 2024 | irpf_deduccion_castilla_y_leon_progenitor_1_nif_texto | irpf_deduccion_castilla_y_leon_otro_progenitor_1_nif | RENAME: otro_progenitor context; _texto suffix transient |
| 1206 | 2025 | irpf_deduccion_castilla_y_leon_progenitor_1_nif_texto | irpf_deduccion_castilla_y_leon_otro_progenitor_1_nif | RENAME: otro_progenitor context; _texto suffix transient |
| 1207 | 2023 | irpf_anexo_b_catastral_ref | irpf_anexo_b_eficiencia_energetica_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1207 | 2024 | irpf_anexo_b_catastral_ref | irpf_anexo_b_eficiencia_energetica_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1207 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_eficiencia_energetica_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1208 | 2023 | irpf_anexo_b_catastral_ref | irpf_anexo_b_eficiencia_energetica_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1208 | 2024 | irpf_anexo_b_catastral_ref | irpf_anexo_b_eficiencia_energetica_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1208 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_eficiencia_energetica_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 1209 | 2021 | parent_nif | irpf_deduccion_cyl_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1209 | 2022 | parent_nif | irpf_deduccion_cyl_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1231 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1231 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1231 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1231 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1231 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1231 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1237 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1237 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1237 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1237 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1237 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1237 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1244 | 2021 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1244 | 2022 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1244 | 2023 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1244 | 2024 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1244 | 2025 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1245 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1245 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1245 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1245 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1245 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1245 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1258 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1258 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1258 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1258 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1258 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1258 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1271 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1271 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1271 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1271 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1271 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1271 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1284 | 2020 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1284 | 2021 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1284 | 2022 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1284 | 2023 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1284 | 2024 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1284 | 2025 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1300 | 2020 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1300 | 2021 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1300 | 2022 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1300 | 2023 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1300 | 2024 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1300 | 2025 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1316 | 2020 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1316 | 2021 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1316 | 2022 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1316 | 2023 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1316 | 2024 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1316 | 2025 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1332 | 2020 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1332 | 2021 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1332 | 2022 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1332 | 2023 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1332 | 2024 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1332 | 2025 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1333 | 2020 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1333 | 2021 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1333 | 2022 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1333 | 2023 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1333 | 2024 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1333 | 2025 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1349 | 2020 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1349 | 2021 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1349 | 2022 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1349 | 2023 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1349 | 2024 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1349 | 2025 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1350 | 2020 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1350 | 2021 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1350 | 2022 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1350 | 2023 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1350 | 2024 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1350 | 2025 | disabled_person_nif | irpf_discapacitado_nif | RENAME: English name; NIF persona con discapacidad |
| 1363 | 2020 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1363 | 2021 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1363 | 2022 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1363 | 2023 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1363 | 2024 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1363 | 2025 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1379 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1379 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1379 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1379 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1379 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1379 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1395 | 2020 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1395 | 2021 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1395 | 2022 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1395 | 2023 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1395 | 2024 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1395 | 2025 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1397 | 2020 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1397 | 2021 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1397 | 2022 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1397 | 2023 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1397 | 2024 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1397 | 2025 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1399 | 2020 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1399 | 2021 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1399 | 2022 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1399 | 2023 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1399 | 2024 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1399 | 2025 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1401 | 2020 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1401 | 2021 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1401 | 2022 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1401 | 2023 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1401 | 2024 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1401 | 2025 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1403 | 2020 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1403 | 2021 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1403 | 2022 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1403 | 2023 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1403 | 2024 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1403 | 2025 | service_provider_nif | irpf_inmueble_gasto_reparacion_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1406 | 2020 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1406 | 2021 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1406 | 2022 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1406 | 2023 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1406 | 2024 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1406 | 2025 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1407 | 2020 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1407 | 2021 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1407 | 2022 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1407 | 2023 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1407 | 2024 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1407 | 2025 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1408 | 2020 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1408 | 2021 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1408 | 2022 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1408 | 2023 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1408 | 2024 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1408 | 2025 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1409 | 2020 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1409 | 2021 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1409 | 2022 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1409 | 2023 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1409 | 2024 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1409 | 2025 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1410 | 2020 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1410 | 2021 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1410 | 2022 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1410 | 2023 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1410 | 2024 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1410 | 2025 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_1_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1411 | 2020 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1411 | 2021 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1411 | 2022 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1411 | 2023 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1411 | 2024 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1411 | 2025 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1412 | 2020 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1412 | 2021 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1412 | 2022 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1412 | 2023 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1412 | 2024 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1412 | 2025 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1413 | 2020 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1413 | 2021 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1413 | 2022 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1413 | 2023 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1413 | 2024 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1413 | 2025 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1414 | 2020 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1414 | 2021 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1414 | 2022 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1414 | 2023 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1414 | 2024 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1414 | 2025 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1415 | 2020 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1415 | 2021 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1415 | 2022 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1415 | 2023 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1415 | 2024 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1415 | 2025 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_2_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1416 | 2020 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1416 | 2021 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1416 | 2022 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1416 | 2023 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1416 | 2024 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1416 | 2025 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1417 | 2020 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1417 | 2021 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1417 | 2022 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1417 | 2023 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1417 | 2024 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1417 | 2025 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1418 | 2020 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1418 | 2021 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1418 | 2022 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1418 | 2023 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1418 | 2024 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1418 | 2025 | irpf_inmueble_gasto_financiacion_proveedor_nif | irpf_inmueble_gasto_proveedor_nif | RENAME: financiacion too specific; covers both financiacion and other gasto contexts |
| 1419 | 2020 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1419 | 2021 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1419 | 2022 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1419 | 2023 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1419 | 2024 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1419 | 2025 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1420 | 2020 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1420 | 2021 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1420 | 2022 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1420 | 2023 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1420 | 2024 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1420 | 2025 | irpf_inmueble_gasto_financiacion_importe | irpf_inmueble_3_gasto_financiacion_importe | SPLIT: three property-slot gasto financiacion importe fields (inmueble 1/2/3) |
| 1441 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1441 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1441 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1441 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1441 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1441 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1485 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1485 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1485 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1485 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1485 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1485 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1561 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1561 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1561 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1561 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1561 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1561 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1571 | 2020 | irpf_re_atrib_cap_inmo_rdto_neto_entidad | irpf_re_atrib_rdto_neto_entidad | RENAME: cap_inmo prefix too narrow; applies to multiple RE attribution contexts |
| 1571 | 2021 | irpf_re_atrib_cap_inmo_rdto_neto_entidad | irpf_re_atrib_rdto_neto_entidad | RENAME: cap_inmo prefix too narrow; applies to multiple RE attribution contexts |
| 1571 | 2022 | irpf_re_atrib_cap_inmo_rdto_neto_entidad | irpf_re_atrib_rdto_neto_entidad | RENAME: cap_inmo prefix too narrow; applies to multiple RE attribution contexts |
| 1571 | 2023 | irpf_re_atrib_cap_inmo_rdto_neto_entidad | irpf_re_atrib_rdto_neto_entidad | RENAME: cap_inmo prefix too narrow; applies to multiple RE attribution contexts |
| 1571 | 2024 | irpf_re_atrib_cap_inmo_rdto_neto_entidad | irpf_re_atrib_rdto_neto_entidad | RENAME: cap_inmo prefix too narrow; applies to multiple RE attribution contexts |
| 1571 | 2025 | irpf_re_atrib_cap_inmo_rdto_neto_entidad | irpf_re_atrib_rdto_neto_entidad | RENAME: cap_inmo prefix too narrow; applies to multiple RE attribution contexts |
| 1610 | 2021 | irpf_deduccion_asturias_vivienda_protegida_2021 | irpf_deduccion_asturias_vivienda_protegida_generado_pendiente | RENAME: year-literal; generado pendiente stable |
| 1610 | 2022 | irpf_deduccion_asturias_vivienda_protegida_2021 | irpf_deduccion_asturias_vivienda_protegida_generado_pendiente | RENAME: year-literal; generado pendiente stable |
| 1610 | 2023 | irpf_deduccion_asturias_vivienda_protegida_2021 | irpf_deduccion_asturias_vivienda_protegida_generado_pendiente | RENAME: year-literal; generado pendiente stable |
| 1610 | 2024 | irpf_deduccion_asturias_vivienda_protegida_2021 | irpf_deduccion_asturias_vivienda_protegida_generado_pendiente | RENAME: year-literal; generado pendiente stable |
| 1610 | 2025 | irpf_deduccion_asturias_vivienda_protegida_2021 | irpf_deduccion_asturias_vivienda_protegida_generado_pendiente | RENAME: year-literal; generado pendiente stable |
| 1611 | 2021 | irpf_deduccion_asturias_vivienda_protegida_2021_pendiente | irpf_deduccion_asturias_vivienda_protegida_pendiente_ejercicio_anterior | RENAME: year-literal; pendiente ejercicio anterior stable |
| 1611 | 2022 | irpf_deduccion_asturias_vivienda_protegida_2021_pendiente | irpf_deduccion_asturias_vivienda_protegida_pendiente_ejercicio_anterior | RENAME: year-literal; pendiente ejercicio anterior stable |
| 1611 | 2023 | irpf_deduccion_asturias_vivienda_protegida_2021_pendiente | irpf_deduccion_asturias_vivienda_protegida_pendiente_ejercicio_anterior | RENAME: year-literal; pendiente ejercicio anterior stable |
| 1611 | 2024 | irpf_deduccion_asturias_vivienda_protegida_2021_pendiente | irpf_deduccion_asturias_vivienda_protegida_pendiente_ejercicio_anterior | RENAME: year-literal; pendiente ejercicio anterior stable |
| 1611 | 2025 | irpf_deduccion_asturias_vivienda_protegida_2021_pendiente | irpf_deduccion_asturias_vivienda_protegida_pendiente_ejercicio_anterior | RENAME: year-literal; pendiente ejercicio anterior stable |
| 1614 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1614 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1614 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1614 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1614 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1614 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1624 | 2020 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1624 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1624 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1624 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1624 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1624 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1635 | 2020 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_vivienda_reinversion_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1635 | 2021 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_vivienda_reinversion_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1635 | 2022 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_vivienda_reinversion_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1635 | 2023 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_vivienda_reinversion_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1635 | 2024 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_vivienda_reinversion_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1635 | 2025 | irpf_anexo_b_carry_forward_applied | irpf_anexo_b_vivienda_reinversion_aplicado | SPLIT: 1116=arrendamiento aplicado, 1119=nacimiento vivienda, 1185=energia, 1635=reinversion |
| 1655 | 2021 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1655 | 2022 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1655 | 2023 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1655 | 2024 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1655 | 2025 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1656 | 2021 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1656 | 2022 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1656 | 2023 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1656 | 2024 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1656 | 2025 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1657 | 2021 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1657 | 2022 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1657 | 2023 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1657 | 2024 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1657 | 2025 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1658 | 2021 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1658 | 2022 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1658 | 2023 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1658 | 2024 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1658 | 2025 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1660 | 2021 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1660 | 2022 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1660 | 2023 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1660 | 2024 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1660 | 2025 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1663 | 2021 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1663 | 2022 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1663 | 2023 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1663 | 2024 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1663 | 2025 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1664 | 2021 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1664 | 2022 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1664 | 2023 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1664 | 2024 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1664 | 2025 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1665 | 2021 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1665 | 2022 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1665 | 2023 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1665 | 2024 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1665 | 2025 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1666 | 2021 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1666 | 2022 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1666 | 2023 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1666 | 2024 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1666 | 2025 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1668 | 2021 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1668 | 2022 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1668 | 2023 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1668 | 2024 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1668 | 2025 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1671 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1671 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1671 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1671 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1671 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1672 | 2021 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1672 | 2022 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1672 | 2023 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1672 | 2024 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1672 | 2025 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_eficiencia_energetica_vivienda_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1673 | 2021 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1673 | 2022 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1673 | 2023 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1673 | 2024 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1673 | 2025 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1674 | 2021 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1674 | 2022 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1674 | 2023 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1674 | 2024 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1674 | 2025 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1675 | 2021 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1675 | 2022 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1675 | 2023 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1675 | 2024 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1675 | 2025 | service_provider_nif | irpf_deduccion_eficiencia_energetica_obra_proveedor_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 1677 | 2021 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1677 | 2022 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1677 | 2023 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1677 | 2024 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1677 | 2025 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_eficiencia_energetica_vivienda_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1678 | 2021 | irpf_anexo_a_mejora_energia_base_deduccion | irpf_anexo_a_mejora_energia_edificio_deduccion_importe | OUTLIER: 2021 label importe deduccion obras edificios; id-reuse |
| 1682 | 2023 | irpf_anexo_a_rib_dotacion_anio | irpf_ric_canarias_dotacion_anio | SPLIT: RIC Canarias (1682/2023-2024) vs RIB Baleares; id-reuse |
| 1682 | 2024 | irpf_anexo_a_rib_dotacion_anio | irpf_ric_canarias_dotacion_anio | SPLIT: RIC Canarias (1682/2023-2024) vs RIB Baleares; id-reuse |
| 1682 | 2025 | irpf_anexo_a_rib_dotacion_anio | irpf_rib_baleares_dotacion_anio | SPLIT: RIC Canarias (1682/2023-2024) vs RIB Baleares; id-reuse |
| 1684 | 2023 | irpf_anexo_a_rib_inversion_tipo_ab | irpf_ric_canarias_inversion_tipo_ab | OUTLIER: 1684/2023 RIC Canarias; id-reuse |
| 1685 | 2023 | irpf_anexo_a_rib_inversion_tipo_c | irpf_ric_canarias_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1685 | 2024 | irpf_anexo_a_rib_inversion_tipo_c | irpf_ric_canarias_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1685 | 2025 | irpf_anexo_a_rib_inversion_tipo_c | irpf_rib_baleares_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1690 | 2024 | irpf_deduccion_c_valenciana_generado_2025_pendiente | irpf_deduccion_c_valenciana_generado_ejercicio_pendiente | RENAME: year-literal; generado ejercicio pendiente stable |
| 1690 | 2025 | irpf_deduccion_c_valenciana_generado_2025_pendiente | irpf_deduccion_c_valenciana_generado_ejercicio_pendiente | RENAME: year-literal; generado ejercicio pendiente stable |
| 1692 | 2022 | irpf_anexo_c_exceso_eeficiencia_pendiente_inicio | irpf_ric_canarias_inversiones_pendiente | OUTLIER: 1692/2022 RIC Canarias; id-reuse |
| 1696 | 2022 | irpf_anexo_c_exceso_eeficiencia_aplicado | irpf_ric_canarias_inversiones_aplicado | OUTLIER: 1696/2022 RIC Canarias; id-reuse |
| 1699 | 2024 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1699 | 2025 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1700 | 2024 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1700 | 2025 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1709 | 2022 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_vivienda_reinversion_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1709 | 2023 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_vivienda_reinversion_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1709 | 2024 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_vivienda_reinversion_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1709 | 2025 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_b_vivienda_reinversion_pendiente | SPLIT: 1117=arrendamiento pendiente, 1120=nacimiento vivienda, 1186=energia, 1709=reinversion |
| 1713 | 2024 | irpf_deduccion_cantabria_ayuda_domestica_2024_pendiente | irpf_deduccion_cantabria_ayuda_domestica_pendiente_ejercicio_anterior | RENAME: year-literal; pendiente ejercicio anterior stable |
| 1713 | 2025 | irpf_deduccion_cantabria_ayuda_domestica_2024_pendiente | irpf_deduccion_cantabria_ayuda_domestica_pendiente_ejercicio_anterior | RENAME: year-literal; pendiente ejercicio anterior stable |
| 1714 | 2024 | irpf_deduccion_cantabria_generado_2025 | irpf_deduccion_cantabria_ascendentes_mayores_importe | OUTLIER: 2024 label ascendentes mayores 65 anos; id-reuse |
| 1715 | 2024 | worker_nif | irpf_deduccion_autonomica_empleada_hogar_nif | RENAME: English name; NIF empleada hogar/escuela/guarderia |
| 1724 | 2021 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1724 | 2022 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1724 | 2023 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1724 | 2024 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1724 | 2025 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1725 | 2021 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1725 | 2022 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1725 | 2023 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1725 | 2024 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1725 | 2025 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1726 | 2021 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1726 | 2022 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1726 | 2023 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1726 | 2024 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1726 | 2025 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1732 | 2021 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1732 | 2022 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1732 | 2023 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1732 | 2024 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1732 | 2025 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1733 | 2021 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1733 | 2022 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1733 | 2023 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1733 | 2024 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1733 | 2025 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1734 | 2021 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1734 | 2022 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1734 | 2023 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1734 | 2024 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1734 | 2025 | producer_nif | irpf_deduccion_inversion_empresarial_productor_nif | RENAME: English name; NIF del productor inversion empresarial |
| 1735 | 2021 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1735 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1735 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1735 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1735 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1741 | 2021 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1742 | 2021 | irpf_anexo_c_exceso_sps_rt_pendiente_inicio | irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_inicio | SPLIT: 1742/1744/1747/1750/1753/2021 employer contribution sub-series pendiente inicio |
| 1742 | 2022 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1742 | 2023 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1742 | 2024 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1742 | 2025 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1743 | 2022 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1743 | 2023 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1743 | 2024 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1743 | 2025 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1744 | 2021 | irpf_anexo_c_exceso_sps_rt_pendiente_inicio | irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_inicio | SPLIT: 1742/1744/1747/1750/1753/2021 employer contribution sub-series pendiente inicio |
| 1745 | 2022 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1745 | 2023 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1745 | 2024 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1745 | 2025 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1746 | 2021 | irpf_anexo_c_exceso_sps_rt_pendiente_fin | irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_fin | SPLIT: 1746/1749/1752/1755/2021 employer contribution sub-series pendiente fin |
| 1746 | 2022 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1746 | 2023 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1746 | 2024 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1746 | 2025 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1747 | 2021 | irpf_anexo_c_exceso_sps_rt_pendiente_inicio | irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_inicio | SPLIT: 1742/1744/1747/1750/1753/2021 employer contribution sub-series pendiente inicio |
| 1747 | 2022 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1747 | 2023 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1747 | 2024 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1747 | 2025 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1748 | 2022 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1748 | 2023 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1748 | 2024 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1748 | 2025 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1749 | 2021 | irpf_anexo_c_exceso_sps_rt_pendiente_fin | irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_fin | SPLIT: 1746/1749/1752/1755/2021 employer contribution sub-series pendiente fin |
| 1750 | 2021 | irpf_anexo_c_exceso_sps_rt_pendiente_inicio | irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_inicio | SPLIT: 1742/1744/1747/1750/1753/2021 employer contribution sub-series pendiente inicio |
| 1750 | 2022 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1750 | 2023 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1750 | 2024 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1750 | 2025 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1751 | 2022 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1751 | 2023 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1751 | 2024 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1751 | 2025 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1752 | 2021 | irpf_anexo_c_exceso_sps_rt_pendiente_fin | irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_fin | SPLIT: 1746/1749/1752/1755/2021 employer contribution sub-series pendiente fin |
| 1752 | 2022 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1752 | 2023 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1752 | 2024 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1752 | 2025 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1753 | 2021 | irpf_anexo_c_exceso_sps_rt_pendiente_inicio | irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_inicio | SPLIT: 1742/1744/1747/1750/1753/2021 employer contribution sub-series pendiente inicio |
| 1753 | 2022 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1753 | 2023 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1753 | 2024 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1753 | 2025 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1755 | 2021 | irpf_anexo_c_exceso_sps_rt_pendiente_fin | irpf_anexo_c_contribucion_empleador_sps_rt_pendiente_fin | SPLIT: 1746/1749/1752/1755/2021 employer contribution sub-series pendiente fin |
| 1755 | 2022 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1755 | 2023 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1755 | 2024 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1755 | 2025 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1756 | 2021 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1756 | 2022 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1756 | 2023 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1756 | 2024 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1756 | 2025 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1757 | 2022 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1757 | 2023 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1757 | 2024 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1757 | 2025 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |
| 1758 | 2022 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1758 | 2023 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1758 | 2024 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1758 | 2025 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1760 | 2021 | irpf_anexo_c_contribuyente_con_derecho_reduccion | irpf_anexo_c_reductor_contribuyente_codigo | RENAME: stores a code not a flag; contribuyente derecho reduccion codigo |
| 1760 | 2022 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1760 | 2023 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1760 | 2024 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1760 | 2025 | parent_nif | irpf_anualidades_alimentos_otro_progenitor_nif | SPLIT: 1209/2021-2022 CyL deduccion otro progenitor; 1244/1742+ anualidades alimentos otro progenitor |
| 1761 | 2022 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1761 | 2023 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1761 | 2024 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1761 | 2025 | irpf_datos_adicionales_nif_ausente_flag | irpf_descendiente_adicional_nif_ausente_flag | SPLIT: 0457/0459 primary child NIF absent flag; 1743+ extended child slots (2022+) |
| 1762 | 2021 | irpf_anexo_c_exceso_sps_rg_contribuciones_aplicado | irpf_anexo_c_contribucion_empresarial_rg_aplicado | SPLIT: 1762/2021 employer contribution applied; 1762/2022-2023 id-reuse alza precios |
| 1762 | 2022 | irpf_anexo_c_exceso_sps_rg_contribuciones_aplicado | irpf_deduccion_alza_precios_importe | SPLIT: 1762/2021 employer contribution applied; 1762/2022-2023 id-reuse alza precios |
| 1762 | 2023 | irpf_anexo_c_exceso_sps_rg_contribuciones_aplicado | irpf_deduccion_alza_precios_importe | SPLIT: 1762/2021 employer contribution applied; 1762/2022-2023 id-reuse alza precios |
| 1762 | 2024 | beneficiary_annuity_payer_nif | irpf_anualidades_alimentos_pagador_nif | RENAME: English name; NIF del pagador anualidades |
| 1762 | 2025 | beneficiary_annuity_payer_nif | irpf_anualidades_alimentos_pagador_nif | RENAME: English name; NIF del pagador anualidades |
| 1763 | 2021 | irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin | irpf_anexo_c_contribucion_empresarial_rg_pendiente_fin | SPLIT: 1763/2021 employer contribution pending fin; 1763/2022+ id-reuse other deductions |
| 1763 | 2022 | irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin | irpf_deduccion_actividad_economica_importe | SPLIT: 1763/2021 employer contribution pending fin; 1763/2022+ id-reuse other deductions |
| 1763 | 2024 | irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin | irpf_deduccion_actividad_economica_importe | SPLIT: 1763/2021 employer contribution pending fin; 1763/2022+ id-reuse other deductions |
| 1763 | 2025 | irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin | irpf_deduccion_actividad_economica_importe | SPLIT: 1763/2021 employer contribution pending fin; 1763/2022+ id-reuse other deductions |
| 1780 | 2021 | rectification_iban | irpf_rectificacion_iban | RENAME: English name; IBAN rectificacion |
| 1780 | 2022 | rectification_iban | irpf_rectificacion_iban | RENAME: English name; IBAN rectificacion |
| 1780 | 2023 | rectification_iban | irpf_rectificacion_iban | RENAME: English name; IBAN rectificacion |
| 1781 | 2024 | irpf_anexo_a_rib_dotacion_anio | irpf_rib_baleares_dotacion_anio | SPLIT: RIC Canarias (1682/2023-2024) vs RIB Baleares; id-reuse |
| 1781 | 2025 | irpf_anexo_a_rib_dotacion_anio | irpf_rib_baleares_dotacion_anio | SPLIT: RIC Canarias (1682/2023-2024) vs RIB Baleares; id-reuse |
| 1783 | 2024 | irpf_anexo_a_rib_inversion_tipo_c | irpf_rib_baleares_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1783 | 2025 | irpf_anexo_a_rib_inversion_tipo_c | irpf_rib_baleares_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1786 | 2023 | beneficiary_annuity_payer_nif | irpf_compensacion_conyuges_banco_direccion | OUTLIER: 2023 label bank address (Direccion); id-reuse |
| 1786 | 2024 | beneficiary_annuity_payer_nif | irpf_anualidades_alimentos_pagador_nif | RENAME: English name; NIF del pagador anualidades |
| 1786 | 2025 | beneficiary_annuity_payer_nif | irpf_anualidades_alimentos_pagador_nif | RENAME: English name; NIF del pagador anualidades |
| 1787 | 2023 | beneficiary_annuity_payer_nif | irpf_compensacion_conyuges_banco_ciudad | OUTLIER: 2023 label bank city (Ciudad); id-reuse |
| 1787 | 2024 | beneficiary_annuity_payer_nif | irpf_anualidades_alimentos_pagador_nif | RENAME: English name; NIF del pagador anualidades |
| 1787 | 2025 | beneficiary_annuity_payer_nif | irpf_anualidades_alimentos_pagador_nif | RENAME: English name; NIF del pagador anualidades |
| 1788 | 2024 | beneficiary_annuity_payer_nif | irpf_anualidades_alimentos_pagador_nif | RENAME: English name; NIF del pagador anualidades |
| 1788 | 2025 | beneficiary_annuity_payer_nif | irpf_anualidades_alimentos_pagador_nif | RENAME: English name; NIF del pagador anualidades |
| 1789 | 2023 | beneficiary_annuity_payer_nif | irpf_compensacion_conyuges_banco_pais_codigo | OUTLIER: 2023 label country code (Codigo Pais); id-reuse |
| 1789 | 2024 | beneficiary_annuity_payer_nif | irpf_anualidades_alimentos_pagador_nif | RENAME: English name; NIF del pagador anualidades |
| 1789 | 2025 | beneficiary_annuity_payer_nif | irpf_anualidades_alimentos_pagador_nif | RENAME: English name; NIF del pagador anualidades |
| 1790 | 2021 | spouse_compensation_iban | irpf_compensacion_conyuges_iban | RENAME: English name; compensacion conyuges IBAN |
| 1790 | 2022 | spouse_compensation_iban | irpf_compensacion_conyuges_iban | RENAME: English name; compensacion conyuges IBAN |
| 1790 | 2023 | spouse_compensation_iban | irpf_compensacion_conyuges_iban | RENAME: English name; compensacion conyuges IBAN |
| 1790 | 2024 | spouse_compensation_iban | irpf_compensacion_conyuges_iban | RENAME: English name; compensacion conyuges IBAN |
| 1790 | 2025 | spouse_compensation_iban | irpf_compensacion_conyuges_iban | RENAME: English name; compensacion conyuges IBAN |
| 1791 | 2021 | irpf_compensacion_conyuges_sepa_flag | irpf_compensacion_conyuges_sepa_codigo | RENAME: field stores SEPA code, not a flag |
| 1791 | 2022 | irpf_compensacion_conyuges_sepa_flag | irpf_compensacion_conyuges_sepa_codigo | RENAME: field stores SEPA code, not a flag |
| 1791 | 2023 | irpf_compensacion_conyuges_sepa_flag | irpf_compensacion_conyuges_sepa_codigo | RENAME: field stores SEPA code, not a flag |
| 1791 | 2024 | irpf_compensacion_conyuges_sepa_flag | irpf_compensacion_conyuges_sepa_codigo | RENAME: field stores SEPA code, not a flag |
| 1791 | 2025 | irpf_compensacion_conyuges_sepa_flag | irpf_compensacion_conyuges_sepa_codigo | RENAME: field stores SEPA code, not a flag |
| 1792 | 2021 | irpf_compensacion_conyuges_swift_flag | irpf_compensacion_conyuges_swift_bic | RENAME: SWIFT field is BIC code, not a flag |
| 1792 | 2022 | irpf_compensacion_conyuges_swift_flag | irpf_compensacion_conyuges_swift_bic | RENAME: SWIFT field is BIC code, not a flag |
| 1792 | 2023 | irpf_compensacion_conyuges_swift_flag | irpf_compensacion_conyuges_swift_bic | RENAME: SWIFT field is BIC code, not a flag |
| 1792 | 2024 | irpf_compensacion_conyuges_swift_flag | irpf_compensacion_conyuges_swift_bic | RENAME: SWIFT field is BIC code, not a flag |
| 1792 | 2025 | irpf_compensacion_conyuges_swift_flag | irpf_compensacion_conyuges_swift_bic | RENAME: SWIFT field is BIC code, not a flag |
| 1794 | 2021 | irpf_compensacion_conyuges_account_no | irpf_compensacion_conyuges_numero_cuenta | RENAME: English name; numero cuenta compensacion conyuges |
| 1794 | 2022 | irpf_compensacion_conyuges_account_no | irpf_compensacion_conyuges_numero_cuenta | RENAME: English name; numero cuenta compensacion conyuges |
| 1794 | 2023 | irpf_compensacion_conyuges_account_no | irpf_compensacion_conyuges_numero_cuenta | RENAME: English name; numero cuenta compensacion conyuges |
| 1794 | 2024 | irpf_compensacion_conyuges_account_no | irpf_compensacion_conyuges_numero_cuenta | RENAME: English name; numero cuenta compensacion conyuges |
| 1794 | 2025 | irpf_compensacion_conyuges_account_no | irpf_compensacion_conyuges_numero_cuenta | RENAME: English name; numero cuenta compensacion conyuges |
| 1795 | 2021 | irpf_compensacion_conyuges_bank_name | irpf_compensacion_conyuges_entidad_bancaria_nombre | RENAME: English suffix bank_name; nombre entidad bancaria |
| 1795 | 2022 | irpf_compensacion_conyuges_bank_name | irpf_compensacion_conyuges_entidad_bancaria_nombre | RENAME: English suffix bank_name; nombre entidad bancaria |
| 1795 | 2023 | irpf_compensacion_conyuges_bank_name | irpf_compensacion_conyuges_entidad_bancaria_nombre | RENAME: English suffix bank_name; nombre entidad bancaria |
| 1795 | 2024 | irpf_compensacion_conyuges_bank_name | irpf_compensacion_conyuges_entidad_bancaria_nombre | RENAME: English suffix bank_name; nombre entidad bancaria |
| 1795 | 2025 | irpf_compensacion_conyuges_bank_name | irpf_compensacion_conyuges_entidad_bancaria_nombre | RENAME: English suffix bank_name; nombre entidad bancaria |
| 1797 | 2021 | irpf_compensacion_conyuges_bank_city | irpf_compensacion_conyuges_entidad_ciudad | RENAME: English bank_city; ciudad de la entidad bancaria |
| 1797 | 2022 | irpf_compensacion_conyuges_bank_city | irpf_compensacion_conyuges_entidad_ciudad | RENAME: English bank_city; ciudad de la entidad bancaria |
| 1797 | 2023 | irpf_compensacion_conyuges_bank_city | irpf_compensacion_conyuges_entidad_ciudad | RENAME: English bank_city; ciudad de la entidad bancaria |
| 1797 | 2024 | irpf_compensacion_conyuges_bank_city | irpf_compensacion_conyuges_entidad_ciudad | RENAME: English bank_city; ciudad de la entidad bancaria |
| 1797 | 2025 | irpf_compensacion_conyuges_bank_city | irpf_compensacion_conyuges_entidad_ciudad | RENAME: English bank_city; ciudad de la entidad bancaria |
| 1799 | 2021 | taxpayer_country | irpf_compensacion_conyuges_nosepa_pais_codigo | RENAME: English name; Codigo Pais compensacion conyuges no-SEPA |
| 1799 | 2022 | taxpayer_country | irpf_compensacion_conyuges_nosepa_pais_codigo | RENAME: English name; Codigo Pais compensacion conyuges no-SEPA |
| 1799 | 2023 | taxpayer_country | irpf_compensacion_conyuges_nosepa_pais_codigo | RENAME: English name; Codigo Pais compensacion conyuges no-SEPA |
| 1799 | 2024 | taxpayer_country | irpf_compensacion_conyuges_nosepa_pais_codigo | RENAME: English name; Codigo Pais compensacion conyuges no-SEPA |
| 1799 | 2025 | taxpayer_country | irpf_compensacion_conyuges_nosepa_pais_codigo | RENAME: English name; Codigo Pais compensacion conyuges no-SEPA |
| 1800 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1800 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1800 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1800 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1813 | 2022 | irpf_gyp_perdidas_bruto | irpf_gyp_cripto_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 1813 | 2023 | irpf_gyp_perdidas_bruto | irpf_gyp_cripto_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 1813 | 2024 | irpf_gyp_perdidas_bruto | irpf_gyp_cripto_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 1813 | 2025 | irpf_gyp_perdidas_bruto | irpf_gyp_cripto_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 1814 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 1814 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 1814 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 1814 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 1815 | 2022 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1815 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1815 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1815 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1819 | 2022 | irpf_ganancia_inmueble_catastral_1 | irpf_ganancia_inmueble_referencia_catastral_1 | RENAME: explicit referencia_catastral for clarity |
| 1819 | 2023 | irpf_ganancia_inmueble_catastral_1 | irpf_ganancia_inmueble_referencia_catastral_1 | RENAME: explicit referencia_catastral for clarity |
| 1819 | 2024 | irpf_ganancia_inmueble_catastral_1 | irpf_ganancia_inmueble_referencia_catastral_1 | RENAME: explicit referencia_catastral for clarity |
| 1819 | 2025 | irpf_ganancia_inmueble_catastral_1 | irpf_ganancia_inmueble_referencia_catastral_1 | RENAME: explicit referencia_catastral for clarity |
| 1844 | 2022 | irpf_gyp_perdidas_bruto | irpf_gyp_inmueble_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 1844 | 2023 | irpf_gyp_perdidas_bruto | irpf_gyp_inmueble_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 1844 | 2024 | irpf_gyp_perdidas_bruto | irpf_gyp_inmueble_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 1844 | 2025 | irpf_gyp_perdidas_bruto | irpf_gyp_inmueble_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 1845 | 2022 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 1845 | 2023 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 1845 | 2024 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 1845 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 1846 | 2022 | irpf_gyp_saldo_neto_ahorro | irpf_gyp_actividades_economicas_suma_ganancias | RENAME: labels are Suma ganancias derivadas transmisiones; role name incorrect |
| 1846 | 2023 | irpf_gyp_saldo_neto_ahorro | irpf_gyp_actividades_economicas_suma_ganancias | RENAME: labels are Suma ganancias derivadas transmisiones; role name incorrect |
| 1846 | 2024 | irpf_gyp_saldo_neto_ahorro | irpf_gyp_actividades_economicas_suma_ganancias | RENAME: labels are Suma ganancias derivadas transmisiones; role name incorrect |
| 1846 | 2025 | irpf_gyp_saldo_neto_ahorro | irpf_gyp_actividades_economicas_suma_ganancias | RENAME: labels are Suma ganancias derivadas transmisiones; role name incorrect |
| 1857 | 2022 | irpf_anexo_c_exceso_eeficiencia_generado | irpf_anexo_c_exceso_eficiencia_energetica_generado | RENAME: typo eeficiencia; expand abbreviation |
| 1857 | 2023 | irpf_anexo_c_exceso_eeficiencia_generado | irpf_anexo_c_exceso_eficiencia_energetica_generado | RENAME: typo eeficiencia; expand abbreviation |
| 1857 | 2024 | irpf_anexo_c_exceso_eeficiencia_generado | irpf_anexo_c_exceso_eficiencia_energetica_generado | RENAME: typo eeficiencia; expand abbreviation |
| 1857 | 2025 | irpf_anexo_c_exceso_eeficiencia_generado | irpf_anexo_c_exceso_eficiencia_energetica_generado | RENAME: typo eeficiencia; expand abbreviation |
| 1871 | 2022 | irpf_ganancia_cripto_ganancia_pendiente_3 | irpf_ganancia_cripto_ganancia_pendiente_imputacion | RENAME: numeric suffix _3 transient; cripto ganancia pendiente imputacion stable |
| 1871 | 2023 | irpf_ganancia_cripto_ganancia_pendiente_3 | irpf_ganancia_cripto_ganancia_pendiente_imputacion | RENAME: numeric suffix _3 transient; cripto ganancia pendiente imputacion stable |
| 1871 | 2024 | irpf_ganancia_cripto_ganancia_pendiente_3 | irpf_ganancia_cripto_ganancia_pendiente_imputacion | RENAME: numeric suffix _3 transient; cripto ganancia pendiente imputacion stable |
| 1871 | 2025 | irpf_ganancia_cripto_ganancia_pendiente_3 | irpf_ganancia_cripto_ganancia_pendiente_imputacion | RENAME: numeric suffix _3 transient; cripto ganancia pendiente imputacion stable |
| 1892 | 2022 | irpf_ganancia_inmueble_ganancia_pendiente_2 | irpf_ganancia_inmueble_ganancia_pendiente_imputacion | RENAME: numeric suffix _2 transient; stable pattern |
| 1892 | 2023 | irpf_ganancia_inmueble_ganancia_pendiente_2 | irpf_ganancia_inmueble_ganancia_pendiente_imputacion | RENAME: numeric suffix _2 transient; stable pattern |
| 1892 | 2024 | irpf_ganancia_inmueble_ganancia_pendiente_2 | irpf_ganancia_inmueble_ganancia_pendiente_imputacion | RENAME: numeric suffix _2 transient; stable pattern |
| 1892 | 2025 | irpf_ganancia_inmueble_ganancia_pendiente_2 | irpf_ganancia_inmueble_ganancia_pendiente_imputacion | RENAME: numeric suffix _2 transient; stable pattern |
| 1893 | 2022 | irpf_perdida_inmueble_pendiente_2 | irpf_perdida_inmueble_pendiente_imputacion | RENAME: numeric suffix _2 transient; stable perdida pendiente imputacion |
| 1893 | 2023 | irpf_perdida_inmueble_pendiente_2 | irpf_perdida_inmueble_pendiente_imputacion | RENAME: numeric suffix _2 transient; stable perdida pendiente imputacion |
| 1893 | 2024 | irpf_perdida_inmueble_pendiente_2 | irpf_perdida_inmueble_pendiente_imputacion | RENAME: numeric suffix _2 transient; stable perdida pendiente imputacion |
| 1893 | 2025 | irpf_perdida_inmueble_pendiente_2 | irpf_perdida_inmueble_pendiente_imputacion | RENAME: numeric suffix _2 transient; stable perdida pendiente imputacion |
| 1900 | 2022 | irpf_ganancia_inmueble_ganancia_pendiente_4 | irpf_ganancia_inmueble_ganancia_pendiente | RENAME: numeric suffix _4 transient; stable pattern |
| 1900 | 2023 | irpf_ganancia_inmueble_ganancia_pendiente_4 | irpf_ganancia_inmueble_ganancia_pendiente | RENAME: numeric suffix _4 transient; stable pattern |
| 1900 | 2024 | irpf_ganancia_inmueble_ganancia_pendiente_4 | irpf_ganancia_inmueble_ganancia_pendiente | RENAME: numeric suffix _4 transient; stable pattern |
| 1900 | 2025 | irpf_ganancia_inmueble_ganancia_pendiente_4 | irpf_ganancia_inmueble_ganancia_pendiente | RENAME: numeric suffix _4 transient; stable pattern |
| 1901 | 2022 | irpf_perdida_inmueble_pendiente_4 | irpf_perdida_inmueble_pendiente | RENAME: numeric suffix _4 transient; stable perdida inmueble pendiente |
| 1901 | 2023 | irpf_perdida_inmueble_pendiente_4 | irpf_perdida_inmueble_pendiente | RENAME: numeric suffix _4 transient; stable perdida inmueble pendiente |
| 1901 | 2024 | irpf_perdida_inmueble_pendiente_4 | irpf_perdida_inmueble_pendiente | RENAME: numeric suffix _4 transient; stable perdida inmueble pendiente |
| 1901 | 2025 | irpf_perdida_inmueble_pendiente_4 | irpf_perdida_inmueble_pendiente | RENAME: numeric suffix _4 transient; stable perdida inmueble pendiente |
| 1913 | 2022 | irpf_incremento_maternidad_guarderia_no_aplicado_2020 | irpf_incremento_maternidad_guarderia_no_aplicado_ejercicio | RENAME: year-literal; no aplicado ejercicio stable |
| 1918 | 2023 | construction_entity_nif | irpf_vehiculo_electrico_vendedor_nif | SPLIT: 0707/2020 promotor constructor; 1918 vendedor EV; 1931 instalador EV |
| 1918 | 2024 | construction_entity_nif | irpf_vehiculo_electrico_vendedor_nif | SPLIT: 0707/2020 promotor constructor; 1918 vendedor EV; 1931 instalador EV |
| 1918 | 2025 | construction_entity_nif | irpf_vehiculo_electrico_vendedor_nif | SPLIT: 0707/2020 promotor constructor; 1918 vendedor EV; 1931 instalador EV |
| 1929 | 2023 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_vehiculo_electrico_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1929 | 2024 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_vehiculo_electrico_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1929 | 2025 | irpf_deduccion_eficiencia_energetica_situacion_clave | irpf_deduccion_vehiculo_electrico_situacion_clave | SPLIT: 1655/1663/1672 housing energy situacion clave; 1929 EV charging situacion clave |
| 1930 | 2023 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_vehiculo_electrico_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1930 | 2024 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_vehiculo_electrico_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1930 | 2025 | irpf_deduccion_eficiencia_energetica_referencia_catastral | irpf_vehiculo_electrico_referencia_catastral | SPLIT: 1656/1664/1673 housing energy; 1930 EV charging catastral |
| 1931 | 2023 | construction_entity_nif | irpf_vehiculo_electrico_instalador_nif | SPLIT: 0707/2020 promotor constructor; 1918 vendedor EV; 1931 instalador EV |
| 1931 | 2024 | construction_entity_nif | irpf_vehiculo_electrico_instalador_nif | SPLIT: 0707/2020 promotor constructor; 1918 vendedor EV; 1931 instalador EV |
| 1931 | 2025 | construction_entity_nif | irpf_vehiculo_electrico_instalador_nif | SPLIT: 0707/2020 promotor constructor; 1918 vendedor EV; 1931 instalador EV |
| 1933 | 2023 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_vehiculo_electrico_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1933 | 2024 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_vehiculo_electrico_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1933 | 2025 | irpf_deduccion_eficiencia_energetica_cantidades_satisfechas | irpf_deduccion_vehiculo_electrico_cantidades_satisfechas | SPLIT: 1660/1668/1677 vivienda energia; 1933 vehiculo electrico punto recarga |
| 1935 | 2023 | irpf_anexo_a_mejora_energia_deduccion_importe | irpf_deduccion_vehiculo_electrico_importe | OUTLIER: 1935/2023 EV (vehiculo electrico); id-reuse |
| 1938 | 2023 | irpf_anexo_a_rib_dotacion_anio | irpf_rib_baleares_dotacion_anio | SPLIT: RIC Canarias (1682/2023-2024) vs RIB Baleares; id-reuse |
| 1938 | 2024 | irpf_anexo_a_rib_dotacion_anio | irpf_rib_baleares_dotacion_anio | SPLIT: RIC Canarias (1682/2023-2024) vs RIB Baleares; id-reuse |
| 1938 | 2025 | irpf_anexo_a_rib_dotacion_anio | irpf_rib_baleares_dotacion_anio | SPLIT: RIC Canarias (1682/2023-2024) vs RIB Baleares; id-reuse |
| 1940 | 2023 | irpf_anexo_a_rib_inversion_tipo_c | irpf_rib_baleares_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1940 | 2024 | irpf_anexo_a_rib_inversion_tipo_c | irpf_rib_baleares_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1940 | 2025 | irpf_anexo_a_rib_inversion_tipo_c | irpf_rib_baleares_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1943 | 2023 | irpf_anexo_a_rib_inversion_tipo_c | irpf_rib_baleares_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1943 | 2024 | irpf_anexo_a_rib_inversion_tipo_c | irpf_rib_baleares_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1943 | 2025 | irpf_anexo_a_rib_inversion_tipo_c | irpf_rib_baleares_inversion_tipo_c | SPLIT: 1685/2023-2024 RIC Canarias tipo C; others RIB Baleares tipo C; id-reuse |
| 1961 | 2023 | irpf_deduccion_c_valenciana_generado_2022_pendiente | irpf_deduccion_c_valenciana_generado_pendiente | RENAME: year-literal; generado pendiente stable |
| 1961 | 2024 | irpf_deduccion_c_valenciana_generado_2022_pendiente | irpf_deduccion_c_valenciana_generado_pendiente | RENAME: year-literal; generado pendiente stable |
| 1961 | 2025 | irpf_deduccion_c_valenciana_generado_2022_pendiente | irpf_deduccion_c_valenciana_generado_pendiente | RENAME: year-literal; generado pendiente stable |
| 1966 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1966 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1966 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1972 | 2023 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1972 | 2024 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1972 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 1974 | 2023 | feac_entity_nif | irpf_feac_entidad_nif | RENAME: English name; NIF entidad FEAC |
| 1974 | 2024 | feac_entity_nif | irpf_feac_entidad_nif | RENAME: English name; NIF entidad FEAC |
| 1974 | 2025 | feac_entity_nif | irpf_feac_entidad_nif | RENAME: English name; NIF entidad FEAC |
| 1978 | 2023 | feac_entity_nif | irpf_feac_entidad_nif | RENAME: English name; NIF entidad FEAC |
| 1978 | 2024 | feac_entity_nif | irpf_feac_entidad_nif | RENAME: English name; NIF entidad FEAC |
| 1978 | 2025 | feac_entity_nif | irpf_feac_entidad_nif | RENAME: English name; NIF entidad FEAC |
| 1990 | 2023 | irpf_anexo_b_birth_deduction_amount | irpf_anexo_b_baleares_deduccion_nacimiento_importe | RENAME: English name; Baleares deduccion nacimiento importe |
| 1990 | 2024 | irpf_anexo_b_birth_deduction_amount | irpf_anexo_b_baleares_deduccion_nacimiento_importe | RENAME: English name; Baleares deduccion nacimiento importe |
| 1990 | 2025 | irpf_anexo_b_birth_deduction_amount | irpf_anexo_b_baleares_deduccion_nacimiento_importe | RENAME: English name; Baleares deduccion nacimiento importe |
| 1991 | 2023 | irpf_anexo_b_birth_advance_paid | irpf_anexo_b_deduccion_nacimiento_abono_anticipado | RENAME: English name; Baleares deduccion nacimiento abono anticipado |
| 1991 | 2024 | irpf_anexo_b_birth_advance_paid | irpf_anexo_b_deduccion_nacimiento_abono_anticipado | RENAME: English name; Baleares deduccion nacimiento abono anticipado |
| 1991 | 2025 | irpf_anexo_b_birth_advance_paid | irpf_anexo_b_deduccion_nacimiento_abono_anticipado | RENAME: English name; Baleares deduccion nacimiento abono anticipado |
| 1992 | 2023 | irpf_anexo_b_birth_pending_claim | irpf_baleares_deduccion_nacimiento_importe_pendiente | RENAME: English name; Baleares deduccion nacimiento importe pendiente solicitar |
| 1992 | 2024 | irpf_anexo_b_birth_pending_claim | irpf_baleares_deduccion_nacimiento_importe_pendiente | RENAME: English name; Baleares deduccion nacimiento importe pendiente solicitar |
| 1992 | 2025 | irpf_anexo_b_birth_pending_claim | irpf_baleares_deduccion_nacimiento_importe_pendiente | RENAME: English name; Baleares deduccion nacimiento importe pendiente solicitar |
| 1997 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1997 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1999 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 1999 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2000 | 2024 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 2000 | 2025 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 2001 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2001 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2005 | 2025 | irpf_deduccion_catalunya_generado_2025_pendiente | irpf_deduccion_catalunya_pendiente_ejercicio_anterior | RENAME: year-literal; pendiente ejercicio anterior stable |
| 2014 | 2025 | irpf_deduccion_c_valenciana_pendiente_2024_linea_5 | irpf_deduccion_c_valenciana_pendiente_linea_5 | RENAME: year-literal; pendiente linea 5 stable |
| 2015 | 2025 | irpf_deduccion_c_valenciana_pendiente_2024_linea_6 | irpf_deduccion_c_valenciana_linea_6_importe_pendiente | RENAME: year-literal; linea 6 importe pendiente stable |
| 2022 | 2025 | irpf_deduccion_madrid_generado_2024_pendiente | irpf_deduccion_madrid_generado_pendiente_aplicacion | RENAME: year-literal; pendiente aplicacion stable |
| 2027 | 2024 | irpf_deduccion_madrid_vivienda_municipio_riesgo | irpf_deduccion_madrid_vivienda_nacimiento_adopcion | OUTLIER: 2024 label nacimiento o adopcion, not municipio riesgo; id-reuse |
| 2038 | 2024 | irpf_deduccion_murcia_generado_2025 | irpf_deduccion_murcia_importe_generado | RENAME: year-literal; importe generado stable |
| 2038 | 2025 | irpf_deduccion_murcia_generado_2025 | irpf_deduccion_murcia_importe_generado | RENAME: year-literal; importe generado stable |
| 2039 | 2024 | irpf_deduccion_murcia_generado_2025_pendiente | irpf_deduccion_murcia_generado_pendiente_aplicacion | RENAME: year-literal; pendiente aplicacion stable |
| 2039 | 2025 | irpf_deduccion_murcia_generado_2025_pendiente | irpf_deduccion_murcia_generado_pendiente_aplicacion | RENAME: year-literal; pendiente aplicacion stable |
| 2040 | 2024 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2040 | 2025 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2042 | 2024 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2042 | 2025 | investment_entity_nif | irpf_centro_guarderia_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2044 | 2024 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2044 | 2025 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2045 | 2024 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2045 | 2025 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2046 | 2024 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2046 | 2025 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2047 | 2024 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2047 | 2025 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2052 | 2024 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2052 | 2025 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2053 | 2024 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2053 | 2025 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2054 | 2024 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2054 | 2025 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2055 | 2024 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2055 | 2025 | canarias_nif_or_nie | irpf_deduccion_canarias_nif_nie | RENAME: English name; NIF o NIE deduccion Canarias |
| 2062 | 2024 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 2062 | 2025 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 2064 | 2024 | irpf_anexo_b_catastral_ref | irpf_anexo_b_residencia_estudiantes_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2064 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_residencia_estudiantes_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2066 | 2024 | college_entity_nif | irpf_residencia_estudiantes_nif | RENAME: English name; NIF colegio mayor/residencia estudiantes |
| 2066 | 2025 | college_entity_nif | irpf_residencia_estudiantes_nif | RENAME: English name; NIF colegio mayor/residencia estudiantes |
| 2067 | 2024 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 2067 | 2025 | landlord_nif | irpf_arrendador_nif | RENAME: English name; NIF del arrendador (capital inmobiliario and deduction sections) |
| 2069 | 2024 | irpf_anexo_b_catastral_ref | irpf_anexo_b_residencia_estudiantes_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2069 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_residencia_estudiantes_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2071 | 2024 | college_entity_nif | irpf_residencia_estudiantes_nif | RENAME: English name; NIF colegio mayor/residencia estudiantes |
| 2071 | 2025 | college_entity_nif | irpf_residencia_estudiantes_nif | RENAME: English name; NIF colegio mayor/residencia estudiantes |
| 2072 | 2024 | irpf_anexo_b_catastral_ref | irpf_anexo_b_baleares_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2072 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_baleares_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2074 | 2024 | irpf_anexo_b_catastral_ref | irpf_anexo_b_baleares_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2074 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_baleares_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2076 | 2024 | irpf_anexo_b_catastral_ref | irpf_anexo_b_baleares_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2076 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_baleares_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2078 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2078 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2079 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2079 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2080 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2080 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2081 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2081 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2082 | 2024 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 2082 | 2025 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 2083 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2083 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2084 | 2024 | irpf_anexo_b_contributor_key | irpf_anexo_b_contribuyente_con_derecho_clave | RENAME: English name; Contribuyente con derecho a deduccion |
| 2084 | 2025 | irpf_anexo_b_contributor_key | irpf_anexo_b_contribuyente_con_derecho_clave | RENAME: English name; Contribuyente con derecho a deduccion |
| 2085 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2085 | 2025 | service_provider_nif | irpf_deduccion_autonomica_servicio_medico_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2086 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2086 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2087 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2087 | 2025 | service_provider_nif | irpf_deduccion_autonomica_servicio_medico_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2088 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2088 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2089 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2089 | 2025 | service_provider_nif | irpf_deduccion_autonomica_servicio_medico_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2090 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2090 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2091 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2091 | 2025 | service_provider_nif | irpf_deduccion_autonomica_servicio_medico_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2092 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2092 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2093 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2093 | 2025 | service_provider_nif | irpf_deduccion_autonomica_servicio_medico_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2094 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2094 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2095 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2095 | 2025 | service_provider_nif | irpf_deduccion_autonomica_servicio_medico_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2096 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2096 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2097 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2097 | 2025 | service_provider_nif | irpf_deduccion_autonomica_servicio_medico_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2098 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2098 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2099 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2099 | 2025 | service_provider_nif | irpf_deduccion_autonomica_servicio_medico_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2100 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2100 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2103 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2103 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2104 | 2024 | irpf_anexo_b_contributor_key | irpf_anexo_b_contribuyente_con_derecho_clave | RENAME: English name; Contribuyente con derecho a deduccion |
| 2104 | 2025 | irpf_anexo_b_contributor_key | irpf_anexo_b_contribuyente_con_derecho_clave | RENAME: English name; Contribuyente con derecho a deduccion |
| 2105 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2105 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2106 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2106 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2107 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2107 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2108 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2108 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2109 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2109 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2110 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2110 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2111 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2111 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2112 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2112 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2113 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2113 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2114 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2114 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2115 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2115 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2116 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2116 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2117 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2117 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2118 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2118 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2119 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2119 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2120 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2120 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2122 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2122 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2123 | 2024 | irpf_anexo_b_contributor_key | irpf_anexo_b_contribuyente_con_derecho_clave | RENAME: English name; Contribuyente con derecho a deduccion |
| 2123 | 2025 | irpf_anexo_b_contributor_key | irpf_anexo_b_contribuyente_con_derecho_clave | RENAME: English name; Contribuyente con derecho a deduccion |
| 2124 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2124 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2125 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2125 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2126 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2126 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2127 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2127 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2128 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2128 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2129 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2129 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2130 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2130 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2131 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2131 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2132 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2132 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2133 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2133 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2134 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2134 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2135 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2135 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2136 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2136 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2137 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2137 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2138 | 2024 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2138 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2139 | 2024 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2139 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2140 | 2024 | irpf_anexo_b_other_service_amount | irpf_anexo_b_otros_gastos_importe_anual | RENAME: English suffix; otros gastos importe anual |
| 2140 | 2025 | irpf_anexo_b_other_service_amount | irpf_anexo_b_otros_gastos_importe_anual | RENAME: English suffix; otros gastos importe anual |
| 2142 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2142 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2143 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2143 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2144 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2144 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2145 | 2024 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2145 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2146 | 2024 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2146 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2147 | 2024 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 2147 | 2025 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 2148 | 2024 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2148 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2159 | 2025 | irpf_deduccion_murcia_infraestructuras_referencia_catastral_flag | irpf_deduccion_murcia_sin_referencia_catastral_flag | RENAME: flag indicates absence of catastral reference; sin_referencia_catastral correct |
| 2167 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2168 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2169 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2170 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2171 | 2025 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 2172 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2173 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2175 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2176 | 2025 | irpf_anexo_b_catastral_ref | irpf_anexo_b_referencia_catastral | SPLIT: 1189/1194/1199=arrendamiento, 1207/1208=eficiencia energetica, 2064/2069=residencia estudiantes, 2072/2074/2076=Baleares |
| 2178 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2179 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2180 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2181 | 2025 | investment_entity_nif | irpf_deduccion_inversion_empresarial_entidad_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2182 | 2025 | irpf_anexo_b_investment_amount | irpf_anexo_b_deduccion_inversion_importe | RENAME: English suffix; deduccion inversion importe Anexo B |
| 2183 | 2025 | irpf_anexo_b_investment_amount_total | irpf_anexo_b_importe_total_deduccion_por_tipo | RENAME: English suffix; importe total deduccion por tipo |
| 2184 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2185 | 2025 | irpf_anexo_b_contributor_key | irpf_anexo_b_contribuyente_con_derecho_clave | RENAME: English name; Contribuyente con derecho a deduccion |
| 2186 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2187 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2188 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2189 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2190 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2191 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2192 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2193 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2194 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2195 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2196 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2197 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2198 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2199 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2200 | 2025 | service_provider_nif | irpf_deduccion_autonomica_prestador_servicio_nif | SPLIT: vivienda obras/inmueble reparacion/eficiencia energetica/servicio medico/prestador servicio NIF |
| 2201 | 2025 | irpf_anexo_b_service_amount | irpf_anexo_b_importe_anual_satisfecho | RENAME: English suffix; importe anual satisfecho |
| 2202 | 2025 | irpf_anexo_b_aav_amount_current | irpf_anexo_b_aav_importe_satisfecho | RENAME: English suffix; importe satisfecho AAV |
| 2204 | 2025 | irpf_anexo_b_aav_amount_pending | irpf_anexo_b_aav_importe_pendiente | RENAME: English suffix; importe satisfecho pendiente aplicacion AAV |
| 2205 | 2025 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 2207 | 2025 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 2208 | 2025 | landlord_or_foreign_id_nif | irpf_arrendador_nif | RENAME: English name; NIF/NIE del arrendador |
| 2210 | 2025 | irpf_anexo_b_rental_amount | irpf_anexo_b_importe_satisfecho | RENAME: all members labeled Cantidades satisfechas; rental too narrow |
| 2213 | 2025 | irpf_anexo_b_deduccion_autonomica | irpf_deduccion_autonomica_importe | SPLIT: multiple distinct deduccion autonomica types in Anexo B |
| 2214 | 2025 | irpf_anexo_b_account_holder_key | irpf_anexo_b_cm_viv_hab_titular_cuenta | RENAME: English name; CM vivienda habitual titular cuenta |
| 2219 | 2025 | irpf_anexo_b_account_holder_key | irpf_anexo_b_cm_viv_hab_titular_cuenta | RENAME: English name; CM vivienda habitual titular cuenta |
| 2224 | 2025 | irpf_contribuyente_titular | irpf_toma_datos_declarante_selector | RENAME: declarante selector field, not a person identifier |
| 2225 | 2025 | investment_entity_nif | irpf_fondo_inversion_nif | SPLIT: 0257=RE agrupacion, 0311/0403/2225=fondo inversion, 0711/0713/1131/1133=nueva empresa, 0210/1076/2040/2042=guarderia, other |
| 2235 | 2025 | irpf_gyp_ganancias_bruto | irpf_gyp_subtotales_ganancias_patrimoniales | RENAME: labels are Suma ganancias patrimoniales (subtotals); bruto imprecise |
| 2236 | 2025 | irpf_gyp_perdidas_bruto | irpf_gyp_renta_fija_suma_perdidas | SPLIT: per-asset-class gyp perdidas subtotals |
| 2239 | 2025 | irpf_deduccion_galicia_ayudas_talidomida_celiacos | irpf_deduccion_galicia_ayudas_als | RENAME: 2025 label ALS esclerosis lateral amiotrofica; id-reuse across concept years |
| DNIASDLG | 2025 | ascendant_nif | irpf_ascendiente_nif | RENAME: English name; NIF del ascendiente |
| DPNIF_D | 2025 | taxpayer_nif | irpf_declarante_nif | RENAME: English name; Primer declarante NIF |
| NIFDLG | 2025 | descendant_nif | irpf_descendiente_nif | RENAME: English name; NIF del descendiente |

## Summary

- Total (id, revision) pairs changing role: **2155**
- Rows sourced from RENAME verdicts: **1302**
- Rows sourced from SPLIT verdicts: **809**
- Rows sourced from OUTLIER verdicts: **44**
- Distinct source roles corrected: **163**
- Distinct correct (target) roles produced: **220**
- Revisions covered: 2020, 2021, 2022, 2023, 2024, 2025
- Batches consolidated: 12 (batch-1 through batch-12)
- Conflicts adjudicated: 8 (see Cross-batch conflicts section)
