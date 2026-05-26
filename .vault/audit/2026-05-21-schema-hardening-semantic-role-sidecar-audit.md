---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-21'
related:
  - '[[2026-05-18-schema-hardening-adr]]'
  - '[[2026-05-19-schema-hardening-role-taxonomy-reference]]'
  - '[[2026-05-20-schema-hardening-verification-ledger]]'
  - '[[2026-05-20-schema-hardening-plan]]'
---

# `schema-hardening` semantic_role sidecar audit

## Purpose

This audit records the semantic-role taxonomy sidecar review requested for
the large singleton warning clusters in Modelo 100 and Modelo 200. The review
was explicitly concerned with avoiding blind or programmatic normalization of
legally binding tax semantics.

The sidecar did not modify registry source files. Its purpose was to identify
which warning clusters are mechanical taxonomy-axis noise and which clusters
carry region, year-window, regime, article, transitional-provision, or
event-specific legal meaning that must remain policy gated.

## Process correction

The initial sidecar work was reported as read-only because the original task
requested no file edits. The current instruction requires this work to be
tracked through the vault workflow. This document is the durable audit/review
record for the sidecar findings, and the continuation plan is recorded in
`2026-05-21-schema-hardening-plan`.

The first continuation plan was incorrectly authored by hand after checking
for a `vault` executable instead of the project command
`uv run vaultspec-core vault plan`. That hand-authored plan was removed and
recreated through `vaultspec-core` before execution continued.

## Grounding sources

- Modelo 200 official manual: `src/aeat/_data/corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf`.
- Renta 2025 autonomous deductions manual: `src/aeat/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf`.
- Modelo 200 registry fragments under `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/`.
- Modelo 100 2025 registry fragments under `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/`.
- Existing semantic-role authority: `2026-05-18-schema-hardening-adr`, `2026-05-19-schema-hardening-role-taxonomy-reference`, and `2026-05-20-schema-hardening-verification-ledger`.

`pdftotext` emitted embedded-font warnings while extracting text from the
official PDFs, but the relevant labels, headings, and table-axis text were
recoverable and were cross-checked against registry labels.

## Slice 1 - Modelo 200 correction-axis surface

Fresh parsing of the Modelo 200 2024+ casilla fragments found 472
correction-axis role assignments across 72 base groups. 253 of those
assignments were singleton roles. The dominant pattern is a legal/concept
base slug with table axes embedded into the role name.

Examples:

- `is_correccion_cambio_criterios_contables_art11_3_temporaria_ejercicio_aumento`
- `is_correccion_deterioro_valores_representativos_permanente_disminucion`
- `is_correccion_operaciones_vinculadas_valor_mercado_temporaria_anteriores_aumento`
- `is_correccion_operaciones_art19_otras_saldo_inicial`

The Modelo 200 manual grounds these as form/table axes for correction detail:
permanent versus temporary corrections, current versus prior exercise origin,
increase versus decrease, and opening versus closing pending balances.

Finding: this is the strongest mechanical burn-down candidate. The role base
must remain the legal/concept identity; the suffixes are candidates for
structured metadata.

## Slice 2 - Modelo 200 legally meaningful bases

The same Modelo 200 surface contains base slugs whose legal markers must not
be normalized away. Labels and role stems include article, transitional
provision, additional provision, final provision, regime, SICAV, cooperative,
port-authority, and special-event markers.

Examples to keep policy gated:

- `is_correccion_copa_america_ley_31_2022`
- `is_correccion_deterioro_participaciones_dt16`
- `is_correccion_reinversion_beneficios_extraordinarios_dt24`
- `is_correccion_impuesto_margen_intereses_comisiones_df9`
- `is_correccion_montes_vecinales_cap_xv`
- `is_correccion_socio_sicav_liquidaciones`
- `is_correccion_cooperativas_fondo_reserva_obligatorio`
- `is_correccion_asimetrias_hibridas_art15bis`

Finding: mechanical extraction may remove table axes from the role identity,
but it must not collapse these legal/concept bases without a separate
policy-backed decision.

## Slice 3 - Modelo 200 label-vs-role axis mismatches

A label-versus-role comparison found 23 records across 8 base groups where
the official label text says a temporary correction axis while the current
role suffix says `permanente_*`.

Affected base groups:

- `is_correccion_amortizacion_intangible_fondo_comercio`
- `is_correccion_bases_negativas_grupo_fiscal`
- `is_correccion_deterioro_art13_1_provisiones`
- `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias`
- `is_correccion_deterioro_valores_participaciones_art13_2b`
- `is_correccion_impuesto_extranjero_deduccion_doble_imposicion`
- `is_correccion_libertad_amortizacion_vehiculos`
- `is_correccion_valoracion_bienes_derechos_regimen_especial`

Finding: these records must be carved out of any blind suffix-based
extraction. Either the axis must be derived from official labels or each
mismatch must be reviewed and corrected under policy.

### Slice 3a - Exact mismatch inventory

Continuation parsing used `tomllib` against the Modelo 200 2024+ casilla
fragments and selected records whose registry label contains `Temporarias`
while `semantic_role` contains `_permanente`. This reproduces the 23-record
mismatch count exactly.

The registry labels are truncated with ellipses for most of these records, so
this table records only the axis evidence visible in the current registry
source. The Modelo 200 manual confirms the correction-table distinction
between `Temporarias (con origen en el ejercicio)` and `Temporarias (con
origen en ejercicios anteriores)`, but the current registry label text does
not expose the full origin phrase for most rows. Those rows must not have
origin inferred mechanically from file ordering.

| id | file | current role | label axis evidence |
|---|---|---|---|
| `01961` | `0612-libertad-de-amortizacion-de-determinados-vehiculos-disminucion.toml` | `is_correccion_libertad_amortizacion_vehiculos_permanente_disminucion` | `Temporarias`; origin phrase truncated in registry label |
| `01962` | `0612-libertad-de-amortizacion-de-determinados-vehiculos-disminucion.toml` | `is_correccion_libertad_amortizacion_vehiculos_permanente_disminucion` | `Temporarias`; origin phrase truncated in registry label |
| `02583` | `0772-amortizacion-del-inmovilizado-intangible-y-fondo-d-aumento.toml` | `is_correccion_amortizacion_intangible_fondo_comercio_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `02588` | `0773-amortizacion-del-inmovilizado-intangible-y-fondo-d-disminucion.toml` | `is_correccion_amortizacion_intangible_fondo_comercio_permanente_disminucion` | `Temporarias`; origin phrase truncated in registry label |
| `02662` | `0788-perdidas-por-deterioro-del-art-13-1-lis-y-provisio-aumento.toml` | `is_correccion_deterioro_art13_1_provisiones_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `02663` | `0788-perdidas-por-deterioro-del-art-13-1-lis-y-provisio-aumento.toml` | `is_correccion_deterioro_art13_1_provisiones_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `02667` | `0789-perdidas-por-deterioro-del-art-13-1-lis-y-provisio-disminucion.toml` | `is_correccion_deterioro_art13_1_provisiones_permanente_disminucion` | `Temporarias`; origin phrase truncated in registry label |
| `02668` | `0789-perdidas-por-deterioro-del-art-13-1-lis-y-provisio-disminucion.toml` | `is_correccion_deterioro_art13_1_provisiones_permanente_disminucion` | `Temporarias`; origin phrase truncated in registry label |
| `02672` | `0790-perdidas-por-deterioro-de-im-inversiones-inmobilia-aumento.toml` | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `02673` | `0790-perdidas-por-deterioro-de-im-inversiones-inmobilia-aumento.toml` | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `02682` | `0792-ajustes-por-perdidas-por-deterioro-de-valores-repr-aumento.toml` | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `02683` | `0792-ajustes-por-perdidas-por-deterioro-de-valores-repr-aumento.toml` | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `02687` | `0793-ajustes-por-perdidas-por-deterioro-de-valores-repr-disminucion.toml` | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_disminucion` | `Temporarias`; origin phrase truncated in registry label |
| `02688` | `0793-ajustes-por-perdidas-por-deterioro-de-valores-repr-disminucion.toml` | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_disminucion` | `Temporarias`; origin phrase truncated in registry label |
| `03052` | `0885-impuesto-extranjero-soportado-por-el-contribuyente-aumento.toml` | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `03053` | `0885-impuesto-extranjero-soportado-por-el-contribuyente-aumento.toml` | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `03122` | `0898-bases-imp-negativas-generadas-dentro-del-grupo-fis-aumento.toml` | `is_correccion_bases_negativas_grupo_fiscal_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `03123` | `0898-bases-imp-negativas-generadas-dentro-del-grupo-fis-aumento.toml` | `is_correccion_bases_negativas_grupo_fiscal_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `03127` | `0899-bases-imp-negativas-generadas-dentro-del-grupo-fis-disminucion.toml` | `is_correccion_bases_negativas_grupo_fiscal_permanente_disminucion` | `Temporarias`; origin phrase truncated in registry label |
| `03128` | `0899-bases-imp-negativas-generadas-dentro-del-grupo-fis-disminucion.toml` | `is_correccion_bases_negativas_grupo_fiscal_permanente_disminucion` | `Temporarias`; origin phrase truncated in registry label |
| `03143` | `0902-valoracion-de-bienes-y-derechos-regimen-especial-o-aumento.toml` | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_aumento` | `Temporarias`; origin phrase truncated in registry label |
| `03147` | `0903-valoracion-de-bienes-y-derechos-regimen-especial-o-disminucion.toml` | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_disminucion` | `Temporarias (con origen en el ejercicio)` |
| `03148` | `0903-valoracion-de-bienes-y-derechos-regimen-especial-o-disminucion.toml` | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_disminucion` | `Temporarias`; origin phrase truncated in registry label |

Review consequence: an implementation can mechanically exclude these 23 IDs
from suffix-derived permanent-axis handling. It cannot mechanically assign
their temporary-origin subaxis until a full-label source is consulted or the
registry label source is repaired.

## Slice 6 - Modelo 200 suffix grammar inventory

Continuation parsing of Modelo 200 2024+ casilla fragments found 399 distinct
`is_correccion_*` roles across 703 assignments.

The planned correction-axis grammar accounts for 472 assignments across 72
base stems:

| suffix axis | assignments |
|---|---:|
| `permanente_aumento` | 71 |
| `permanente_disminucion` | 66 |
| `temporaria_ejercicio_aumento` | 43 |
| `temporaria_ejercicio_disminucion` | 44 |
| `temporaria_anteriores_aumento` | 39 |
| `temporaria_anteriores_disminucion` | 40 |
| `saldo_inicial` | 95 |
| `saldo_final` | 74 |

Coverage by base stem is uneven:

| axis count on base | base stems |
|---|---:|
| 8 axes | 23 |
| 7 axes | 13 |
| 6 axes | 3 |
| 5 axes | 2 |
| 4 axes | 3 |
| 3 axes | 3 |
| 2 axes | 5 |
| 1 axis | 20 |

Finding: the 8-axis and 7-axis bases are the best candidates for a first
mechanical implementation slice. One-axis and two-axis bases may still be
valid, but should not be used to generalize the grammar without checking the
source label and legal context.

### Legally marked base stems inside the matched grammar

The matched grammar contains 38 base stems with visible legal markers in the
role stem. These markers are lexical evidence only; this audit does not define
the legal concepts. They remain preserve-list candidates during sidecar
extraction.

Examples:

- `is_correccion_adquisicion_participaciones_no_residentes_dt14`
- `is_correccion_asimetrias_hibridas_art15bis`
- `is_correccion_cambio_criterios_contables_art11_3`
- `is_correccion_cambio_residencia_ue_eee_art19`
- `is_correccion_copa_america_ley_31_2022`
- `is_correccion_deterioro_participaciones_dt16`
- `is_correccion_impuesto_margen_intereses_comisiones_df9`
- `is_correccion_montes_vecinales_cap_xv`
- `is_correccion_operaciones_a_plazos_dt1`
- `is_correccion_reinversion_beneficios_extraordinarios_dt24`
- `is_correccion_rentas_transmision_inmovilizado_autoridades_portuarias`
- `is_correccion_socio_sicav_liquidaciones`
- `is_correccion_socio_sicav_reducciones_capital`

Implementation consequence: extracting `permanente`, `temporaria`, movement,
origin, and balance axes must leave these base stems intact unless a separate
policy review authorizes a base-name change.

### Unmatched correction roles

Forty-five distinct `is_correccion_*` roles covering 231 assignments do not
match the narrow suffix grammar above. This is not automatically a defect.
The unmatched set contains several different table shapes:

- Net-balance conventions such as
  `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial_neto`,
  `is_correccion_deterioro_art13_1_no_afectado_saldo_final_neto`, and
  `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final_neto`.
- Generic detail rows such as
  `is_correccion_detalle_resultado_temporaria_aumento`,
  `is_correccion_detalle_correcciones_resultado_saldo_inicial_aumento`, and
  `is_correccion_temporarias_saldo_final_disminuciones_futuras`.
- Year-generation grids such as
  `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones`,
  `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones`,
  and `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas`.
- Coarse or already-misaligned roles such as
  `is_correccion_disminucion`, `is_correccion_exencion_aumento`,
  `is_correccion_regimenes_especiales_aumento`,
  `is_correccion_libertad_amortizacion_vehiculos_aumento`, and
  `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_disminucion`.

Finding: the unmatched set should be a later slice. It should not be pulled
into the first mechanical burn-down by broadening suffix parsing until each
subfamily has its own label-grounded contract.

## Slice 7 - Modelo 100 repeated-label exact inventory

Continuation parsing used `tomllib` against the Modelo 100 2025 casilla
fragments and grouped exact labels previously identified as high-risk for
blind normalization.

Finding: repeated captions cross autonomous-community and deduction-family
boundaries. They are not a role-equivalence proof.

### `Importe generado en 2025`

Count: 13 records, 13 distinct roles. All parsed records have blank
`data_type` in the current fragment source.

| id | section | current role |
|---|---|---|
| `0776` | `cantabria_res` | `irpf_deduccion_cantabria_generado_pendiente` |
| `0829` | `galicia_res` | `irpf_deduccion_galicia_eficiencia_energetica_generado` |
| `1037` | `galicia_res` | `irpf_deduccion_galicia_generado_linea_2` |
| `1703` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_danos_vivienda_dana_generado` |
| `1705` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_aportaciones_fondos_propios_generado` |
| `1714` | `cantabria_res` | `irpf_deduccion_cantabria_generado_2025` |
| `1963` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_autoconsumo_2025_generado` |
| `2004` | `catalunya_res` | `irpf_deduccion_catalunya_generado_2025` |
| `2031` | `madrid_res` | `irpf_deduccion_madrid_nuevos_contribuyentes_generado` |
| `2038` | `murcia_res` | `irpf_deduccion_murcia_importe_generado` |
| `2058` | `la_rioja_res` | `irpf_deduccion_la_rioja_generado_2025` |
| `2156` | `murcia_res` | `irpf_deduccion_murcia_vehiculo_generado` |
| `2162` | `murcia_res` | `irpf_deduccion_murcia_infraestructuras_generado` |

### `Importe generado en 2025 pendiente de aplicación`

Count: 15 records, 15 distinct roles. All parsed records have blank
`data_type` in the current fragment source.

| id | section | current role |
|---|---|---|
| `0848` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_generado_pendiente` |
| `0956` | `cantabria_res` | `irpf_deduccion_cantabria_generado_ejercicio_pendiente` |
| `0981` | `galicia_res` | `irpf_deduccion_galicia_generado_2025_pendiente` |
| `0982` | `galicia_res` | `irpf_deduccion_galicia_pendiente_ejercicio_anterior_2` |
| `1690` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_generado_ejercicio_pendiente` |
| `1691` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_generado_2025_pendiente_2` |
| `1715` | `cantabria_res` | `irpf_deduccion_cantabria_generado_2025_pendiente` |
| `1717` | `cantabria_res` | `irpf_deduccion_cantabria_generado_2025_pendiente_2` |
| `1964` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente` |
| `2005` | `catalunya_res` | `irpf_deduccion_catalunya_pendiente_ejercicio_anterior` |
| `2032` | `madrid_res` | `irpf_deduccion_madrid_nuevos_contribuyentes_pendiente` |
| `2039` | `murcia_res` | `irpf_deduccion_murcia_generado_pendiente_aplicacion` |
| `2059` | `la_rioja_res` | `irpf_deduccion_la_rioja_generado_2025_pendiente` |
| `2164` | `murcia_res` | `irpf_deduccion_murcia_infraestructuras_2025_pendiente` |
| `2165` | `murcia_res` | `irpf_deduccion_murcia_generado_2025_pendiente_2` |

### `Importe generado en 2024 pendiente de aplicación`

Count: 14 records, 14 distinct roles. All parsed records have blank
`data_type` in the current fragment source.

| id | section | current role |
|---|---|---|
| `0807` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_pendiente_aplicacion` |
| `0998` | `cantabria_res` | `irpf_deduccion_cantabria_pendiente_aplicacion` |
| `1184` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_generado_2024_pendiente_2` |
| `1185` | `c_valenciana_res` | `irpf_anexo_b_energia_satisfecho_aplicado` |
| `1186` | `c_valenciana_res` | `irpf_anexo_b_energia_satisfecho_pendiente` |
| `1713` | `cantabria_res` | `irpf_deduccion_cantabria_ayuda_domestica_pendiente_ejercicio_anterior` |
| `1965` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente` |
| `2012` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_pendiente_2024_linea_4` |
| `2014` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_pendiente_linea_5` |
| `2015` | `c_valenciana_res` | `irpf_deduccion_c_valenciana_linea_6_importe_pendiente` |
| `2022` | `madrid_res` | `irpf_deduccion_madrid_generado_pendiente_aplicacion` |
| `2023` | `madrid_res` | `irpf_deduccion_madrid_generado_2024_pendiente_2` |
| `2163` | `murcia_res` | `irpf_deduccion_murcia_infraestructuras_2024_pendiente` |
| `2166` | `murcia_res` | `irpf_deduccion_murcia_generado_2024_pendiente` |

### `Código del municipio:`

Count: 6 records, 6 distinct roles. Four La Rioja records have blank
`data_type`; two Castilla-La Mancha records declare `text`.

| id | section | data_type | current role |
|---|---|---|---|
| `1064` | `la_rioja_res` | blank | `irpf_deduccion_la_rioja_vivienda_codigo_municipio` |
| `1067` | `la_rioja_res` | blank | `irpf_deduccion_la_rioja_adecuacion_municipio_codigo` |
| `1071` | `la_rioja_res` | blank | `irpf_deduccion_la_rioja_guarderia_municipio_codigo` |
| `1162` | `la_rioja_res` | blank | `irpf_deduccion_la_rioja_arrendamiento_municipio_codigo` |
| `1907` | `castilla_la_mancha_res` | `text` | `irpf_deduccion_castilla_la_mancha_municipio_codigo` |
| `1946` | `castilla_la_mancha_res` | `text` | `irpf_deduccion_castilla_la_mancha_municipio_codigo_2` |

### Approved pilot remains narrow

The `c_valenciana_autoconsumo` pilot members in the same 2025 registry parse
are:

| id | label | current role |
|---|---|---|
| `1114` | `Por cantidades invertidas hasta 2022...` | `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022` |
| `1962` | `Por cantidades invertidas a partir de 2023...` | `irpf_deduccion_c_valenciana_autoconsumo_desde_2023` |
| `1963` | `Importe generado en 2025` | `irpf_deduccion_c_valenciana_autoconsumo_2025_generado` |
| `1964` | `Importe generado en 2025 pendiente de aplicación` | `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente` |
| `1965` | `Importe generado en 2024 pendiente de aplicación` | `irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente` |

Implementation consequence: a future Modelo 100 slice may extract generated
year and pending state only inside a pre-approved family boundary like
`c_valenciana_autoconsumo`. It must not merge roles across CCAA sections or
deduction concepts by exact repeated label alone.

## Slice 8 - Modelo 100 generated/pending family grammar

Continuation parsing grouped the 42 Modelo 100 2025 generated/pending
repeated-label records by autonomous-community section and current role
suffix. The surface spans 7 CCAA sections and 42 distinct roles:

| section | records | immediate conclusion |
|---|---:|---|
| `c_valenciana_res` | 15 | many unrelated families; do not use generic CCAA prefix |
| `murcia_res` | 8 | one plausible `infraestructuras` triplet plus other unrelated roles |
| `cantabria_res` | 7 | multiple generic and numbered roles; needs manual family lookup |
| `galicia_res` | 4 | mixed efficiency, generic line, and pending roles |
| `madrid_res` | 4 | one plausible named pair plus generic pending rows |
| `catalunya_res` | 2 | possible pair, but family name absent from role |
| `la_rioja_res` | 2 | possible pair, but family name absent from role |

### Candidate family-local axes

These are not approved implementation targets yet; they are candidates for
manual lookup because the role stems appear family-local or at least tightly
paired in the current registry:

| candidate | records | reason it may be mechanical after policy lookup |
|---|---:|---|
| `irpf_deduccion_c_valenciana_autoconsumo` | 3 | already grounded by the Renta 2025 manual and current audit |
| `irpf_deduccion_murcia_infraestructuras` | 3 | has generated, 2024-pending, and 2025-pending members with stable stem |
| `irpf_deduccion_madrid_nuevos_contribuyentes` | 2 | has generated and pending members with stable named stem |
| `irpf_deduccion_la_rioja` generated/pending pair | 2 | exact pair exists, but role stem is CCAA-generic rather than family-specific |
| `irpf_deduccion_catalunya` generated/pending pair | 2 | exact pair exists, but role stem is CCAA-generic rather than family-specific |

Only `c_valenciana_autoconsumo` is approved for implementation planning from
this sidecar. The other candidates require manual source lookup in the Renta
2025 autonomous deductions manual before they can be promoted.

### Blockers and anti-patterns

The following patterns make blind suffix extraction unsafe:

- Generic CCAA stems, such as `irpf_deduccion_c_valenciana`,
  `irpf_deduccion_cantabria`, `irpf_deduccion_murcia`, and
  `irpf_deduccion_galicia`, collect multiple deduction concepts under a
  regional prefix. They are not legal-family identifiers.
- Numbered suffixes such as `_2`, `linea_4`, `linea_5`, and `linea_6` are
  position signals, not self-evident legal concepts.
- `irpf_anexo_b_energia_satisfecho_aplicado` and
  `irpf_anexo_b_energia_satisfecho_pendiente` share repeated generated/pending
  labels but belong to an Anexo B energy context and must not be folded into
  generic CCAA generated/pending roles.
- Role wording sometimes conflicts with the repeated label, e.g.
  `irpf_deduccion_cantabria_generado_pendiente` appears on label `Importe
  generado en 2025`, so suffix parsing alone may import stale or ambiguous
  semantics.

Implementation consequence: the Modelo 100 mechanical burn-down should use a
family allowlist, not a global suffix parser. A future implementation slice
should begin with `c_valenciana_autoconsumo`; any additional family must first
get a source-grounded audit entry naming the deduction, the exact member IDs,
and the allowed axes.

## Slice 9 - Modelo 100 municipality-code guard

Continuation parsing grouped exact `Código del municipio:` labels in Modelo
100 2025. The repeated label appears in 6 records across 2 CCAA sections:

| id | section | data_type | current role |
|---|---|---|---|
| `1064` | `la_rioja_res` | blank | `irpf_deduccion_la_rioja_vivienda_codigo_municipio` |
| `1067` | `la_rioja_res` | blank | `irpf_deduccion_la_rioja_adecuacion_municipio_codigo` |
| `1071` | `la_rioja_res` | blank | `irpf_deduccion_la_rioja_guarderia_municipio_codigo` |
| `1162` | `la_rioja_res` | blank | `irpf_deduccion_la_rioja_arrendamiento_municipio_codigo` |
| `1907` | `castilla_la_mancha_res` | `text` | `irpf_deduccion_castilla_la_mancha_municipio_codigo` |
| `1946` | `castilla_la_mancha_res` | `text` | `irpf_deduccion_castilla_la_mancha_municipio_codigo_2` |

Finding: this label is not a safe global role merge target. The La Rioja rows
encode distinct deduction contexts in the role name, and the Castilla-La
Mancha rows have numbered slots. The data-type shape also differs between
blank and `text`.

Implementation consequence: do not normalize these six records to one
`municipality_code` role by label alone. Any future change must first decide
whether municipality-code is a cross-deduction semantic atom for these annex
rows, whether the blank La Rioja `data_type` values are valid or incomplete,
and whether the Castilla-La Mancha `_2` role is a second slot or a naming
defect.

## Slice 10 - Modelo 200 implementation allowlist draft

Execution of `W02.P10.S17` derived the first implementation-readiness
allowlist from the audited suffix grammar. The parser stayed within the
committed Modelo 200 2024+ registry fragments and grouped only roles matching
the narrow correction-axis suffixes:

- `permanente_aumento`
- `permanente_disminucion`
- `temporaria_ejercicio_aumento`
- `temporaria_ejercicio_disminucion`
- `temporaria_anteriores_aumento`
- `temporaria_anteriores_disminucion`
- `saldo_inicial`
- `saldo_final`

### Tier A - complete 8-axis bases

These 23 base stems expose all 8 audited axes and cover 230 assignments:

| base stem | assignments |
|---|---:|
| `is_correccion_adquisicion_participaciones_no_residentes_dt14` | 10 |
| `is_correccion_amortizacion_inmovilizado_idi` | 10 |
| `is_correccion_aportaciones_entidades_sin_fines_lucro` | 10 |
| `is_correccion_cambio_criterios_contables_art11_3` | 10 |
| `is_correccion_correcciones_entidades_normativa_foral` | 10 |
| `is_correccion_deterioro_valores_participaciones_entidades` | 10 |
| `is_correccion_deterioro_valores_representativos` | 10 |
| `is_correccion_diferencias_amortizacion_contable_fiscal` | 10 |
| `is_correccion_disminucion_valor_criterio_valor_razonable` | 10 |
| `is_correccion_libertad_amortizacion_investigacion_desarrollo` | 10 |
| `is_correccion_libertad_amortizacion_mantenimiento_empleo` | 10 |
| `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo` | 10 |
| `is_correccion_limitacion_gastos_financieros_art16` | 10 |
| `is_correccion_operaciones_a_plazos_dt1` | 10 |
| `is_correccion_operaciones_jurisdicciones_no_cooperativas` | 10 |
| `is_correccion_operaciones_vinculadas_valor_mercado` | 10 |
| `is_correccion_otras_diferencias_imputacion_temporal` | 10 |
| `is_correccion_pensiones_provisiones_no_deducibles` | 10 |
| `is_correccion_reduccion_rentas_activos_intangibles` | 10 |
| `is_correccion_reinversion_beneficios_extraordinarios_dt24` | 10 |
| `is_correccion_rentas_operaciones_quita_espera` | 10 |
| `is_correccion_revalorizaciones_contables_art17_1` | 10 |
| `is_correccion_transmisiones_lucrativas_societarias` | 10 |

### Tier B - near-complete 7-axis bases

These 13 base stems expose 7 audited axes and cover 105 assignments. They are
implementation candidates only after review confirms the missing axis is truly
absent from the form surface rather than caused by source truncation, naming
drift, or a misclassified row:

| base stem | assignments |
|---|---:|
| `is_correccion_asimetrias_hibridas_art15bis` | 8 |
| `is_correccion_deterioro_art13_1_no_afectado` | 8 |
| `is_correccion_deuda_tributaria_ajd_itp` | 8 |
| `is_correccion_efectos_valoracion_contable_diferente_fiscal` | 8 |
| `is_correccion_eliminaciones_pendientes_grupo` | 9 |
| `is_correccion_libertad_amortizacion_inmovilizado_nuevo` | 8 |
| `is_correccion_libertad_amortizacion_otros_art12` | 8 |
| `is_correccion_operaciones_a_plazos_art11_4` | 8 |
| `is_correccion_operaciones_aumento_capital_fondos_propios` | 8 |
| `is_correccion_otras_correcciones_resultado` | 8 |
| `is_correccion_provisiones_no_deducibles_art14` | 8 |
| `is_correccion_rentas_negativas_art11_9_10` | 8 |
| `is_correccion_reversion_deterioro_elementos` | 8 |

Implementation consequence: Tier A is the first reasonable mechanical
allowlist for a Modelo 200 sidecar extraction implementation. Tier B should be
handled in the same code path only if a pre-implementation review records the
missing axis per base stem and confirms the base is still form-complete.
Neither tier authorizes changing the preserved base stem.

## Slice 11 - Modelo 200 mismatch exclusion guard

Execution of `W02.P10.S18` defines the exact exclusion guard for the 23 Modelo
200 mismatch IDs. This is a contract for the future sidecar extractor; no
registry source or runtime code exists yet for axis extraction, so implementing
it as code now would create dead code or a tautological test.

The extractor must reject blind suffix-derived `permanente_*` handling for
these casilla IDs:

| id | current role |
|---|---|
| `01961` | `is_correccion_libertad_amortizacion_vehiculos_permanente_disminucion` |
| `01962` | `is_correccion_libertad_amortizacion_vehiculos_permanente_disminucion` |
| `02583` | `is_correccion_amortizacion_intangible_fondo_comercio_permanente_aumento` |
| `02588` | `is_correccion_amortizacion_intangible_fondo_comercio_permanente_disminucion` |
| `02662` | `is_correccion_deterioro_art13_1_provisiones_permanente_aumento` |
| `02663` | `is_correccion_deterioro_art13_1_provisiones_permanente_aumento` |
| `02667` | `is_correccion_deterioro_art13_1_provisiones_permanente_disminucion` |
| `02668` | `is_correccion_deterioro_art13_1_provisiones_permanente_disminucion` |
| `02672` | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_aumento` |
| `02673` | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_aumento` |
| `02682` | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_aumento` |
| `02683` | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_aumento` |
| `02687` | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_disminucion` |
| `02688` | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_disminucion` |
| `03052` | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_aumento` |
| `03053` | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_aumento` |
| `03122` | `is_correccion_bases_negativas_grupo_fiscal_permanente_aumento` |
| `03123` | `is_correccion_bases_negativas_grupo_fiscal_permanente_aumento` |
| `03127` | `is_correccion_bases_negativas_grupo_fiscal_permanente_disminucion` |
| `03128` | `is_correccion_bases_negativas_grupo_fiscal_permanente_disminucion` |
| `03143` | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_aumento` |
| `03147` | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_disminucion` |
| `03148` | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_disminucion` |

Required behavior for future implementation:

- If a casilla ID is in this set, an extractor must not derive
  `correction_kind = permanente` from the current role suffix.
- If a casilla ID is in this set, the extractor must either derive the axis
  from full official label text or mark the record as policy-review required.
- The guard must key on `(modelo=200, revision=2024-y-siguientes, casilla_id)`,
  not just role name, because several affected roles also appear on valid
  permanent-label rows elsewhere.
- The guard must be tested with at least one duplicate-role case, such as
  `01961`/`01962`, to prove role-level exclusion is not used.

## Slice 12 - Modelo 200 legal-base preservation test contract

Execution of `W02.P10.S19` defines the future real-behavior test contract for
preserving legally marked Modelo 200 base stems during sidecar extraction.

No registry runtime test was added in this slice because there is not yet a
sidecar extractor or metadata field. Testing the private typo-warning suffix
splitter would not prove extraction behavior and would be tautological for
this plan step.

Future implementation tests must prove:

- Extracting suffix axes from
  `is_correccion_cambio_criterios_contables_art11_3_temporaria_ejercicio_aumento`
  preserves base `is_correccion_cambio_criterios_contables_art11_3`.
- Extracting suffix axes from
  `is_correccion_reinversion_beneficios_extraordinarios_dt24_temporaria_anteriores_disminucion`
  preserves base `is_correccion_reinversion_beneficios_extraordinarios_dt24`.
- Extracting suffix axes from
  `is_correccion_impuesto_margen_intereses_comisiones_df9_permanente_aumento`
  preserves base `is_correccion_impuesto_margen_intereses_comisiones_df9`.
- Extracting suffix axes from
  `is_correccion_asimetrias_hibridas_art15bis_temporaria_ejercicio_disminucion`
  preserves base `is_correccion_asimetrias_hibridas_art15bis`.
- Extracting suffix axes from
  `is_correccion_montes_vecinales_cap_xv_permanente_disminucion` preserves
  base `is_correccion_montes_vecinales_cap_xv`.
- Extracting suffix axes from
  `is_correccion_copa_america_ley_31_2022_temporaria_anteriores_disminucion`
  preserves base `is_correccion_copa_america_ley_31_2022`.

Required negative tests:

- A legal marker such as `art11_3`, `dt24`, `df9`, `art15bis`, `cap_xv`, or
  `ley_31_2022` must never be normalized away as an axis token.
- A preserve-listed base must remain distinct from a sibling base that differs
  only by article, transitional provision, final provision, event law, or
  regime marker.
- A future extractor must fail closed when it sees an unknown suffix shape on
  a preserve-listed base rather than widening the grammar silently.

## Slice 13 - C Valenciana autoconsumo manual confirmation

Execution of `W03.P11.S20` manually checked the approved
`c_valenciana_autoconsumo` pilot against the Renta 2025 autonomous deductions
manual. `pdftotext` again emitted embedded-font warnings, but the relevant
section title and Anexo B.12 references were recoverable.

Manual grounding:

- The Comunitat Valenciana section contains the deduction titled `Por
  cantidades invertidas en instalaciones de autoconsumo o de generación de
  energía eléctrica o térmica a través de fuentes renovables`.
- The manual cites the normative basis as Art. 4.Uno.o) and disposición
  adicional decimosexta of Ley 13/1997.
- The manual points to Anexo B.12 for additional information on amounts
  invested `hasta 2022`.
- The manual separately points to Anexo B.12 for additional information on
  amounts invested `a partir de 2023`.

Registry members confirmed for the pilot:

| id | current role | source meaning |
|---|---|---|
| `1114` | `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022` | Anexo B.12 amount invested up to 2022 |
| `1962` | `irpf_deduccion_c_valenciana_autoconsumo_desde_2023` | Anexo B.12 amount invested from 2023 onward |
| `1963` | `irpf_deduccion_c_valenciana_autoconsumo_2025_generado` | generated amount in 2025 within the same family |
| `1964` | `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente` | 2025 generated amount pending application within the same family |
| `1965` | `irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente` | 2024 generated amount pending application within the same family |

Implementation consequence: `hasta_2022` and `desde_2023` are source-grounded
legal year-window concepts. Only `generated_year` and pending/application
state may be extracted from IDs `1963`, `1964`, and `1965`, and only inside
this family boundary.

## Slice 14 - C Valenciana autoconsumo pilot metadata contract

Execution of `W03.P11.S21` defines the generated-year and pending-state
metadata contract for the approved family-local pilot.

Allowed family members:

| id | preserved base | generated_year | pending_state |
|---|---|---:|---|
| `1963` | `irpf_deduccion_c_valenciana_autoconsumo` | 2025 | `generated_current_year` |
| `1964` | `irpf_deduccion_c_valenciana_autoconsumo` | 2025 | `pending_application` |
| `1965` | `irpf_deduccion_c_valenciana_autoconsumo` | 2024 | `pending_application` |

Excluded from generated/pending extraction:

| id | current role | reason |
|---|---|---|
| `1114` | `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022` | legal year-window concept |
| `1962` | `irpf_deduccion_c_valenciana_autoconsumo_desde_2023` | legal year-window concept |

Implementation consequence: a future extractor must key this mapping by exact
family allowlist and casilla ID. It must not infer generated/pending metadata
from every Modelo 100 role ending in `_generado`, `_pendiente`, or a year
token.

## Slice 15 - C Valenciana autoconsumo pilot test contract

Execution of `W03.P11.S22` defines future tests for the approved pilot.

Required positive tests:

- ID `1963` extracts base `irpf_deduccion_c_valenciana_autoconsumo`,
  `generated_year = 2025`, and `pending_state = generated_current_year`.
- ID `1964` extracts base `irpf_deduccion_c_valenciana_autoconsumo`,
  `generated_year = 2025`, and `pending_state = pending_application`.
- ID `1965` extracts base `irpf_deduccion_c_valenciana_autoconsumo`,
  `generated_year = 2024`, and `pending_state = pending_application`.

Required negative tests:

- ID `1114` remains
  `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022` and does not produce a
  generated-year metadata axis.
- ID `1962` remains
  `irpf_deduccion_c_valenciana_autoconsumo_desde_2023` and does not produce a
  generated-year metadata axis.
- A non-allowlisted role such as
  `irpf_deduccion_murcia_infraestructuras_2025_pendiente` must not be accepted
  by the C Valenciana pilot extractor.
- A generic regional role such as
  `irpf_deduccion_c_valenciana_generado_2025_pendiente_2` must not be accepted
  by the C Valenciana pilot extractor.

No runtime test was added in this slice because the sidecar metadata surface
does not yet exist. These tests become mandatory in the implementation slice
that introduces that surface.

## Slice 16 - Murcia infraestructuras manual lookup

Execution of `W04.P12.S23` manually checked the candidate
`murcia_infraestructuras` family against the Renta 2025 autonomous deductions
manual.

Manual grounding:

- The Region of Murcia section contains the deduction titled `Por gastos en
  la instalación de infraestructuras de recarga de vehículos eléctricos`.
- The manual cites the normative basis as Art. 1.Veinte of the Texto Refundido
  de las disposiciones legales vigentes en la Región de Murcia en materia de
  tributos cedidos, approved by Decreto Legislativo 1/2010.
- The manual states that if the deduction cannot be fully applied in the
  investment period because the autonomous tax liability is insufficient, the
  remaining amount may be applied in the following three tax periods.

Registry members tied to the candidate:

| id | current role | label |
|---|---|---|
| `2162` | `irpf_deduccion_murcia_infraestructuras_generado` | `Importe generado en 2025` |
| `2163` | `irpf_deduccion_murcia_infraestructuras_2024_pendiente` | `Importe generado en 2024 pendiente de aplicación` |
| `2164` | `irpf_deduccion_murcia_infraestructuras_2025_pendiente` | `Importe generado en 2025 pendiente de aplicación` |

### Promotion decision

Execution of `W04.P12.S24` promotes `murcia_infraestructuras` from candidate
to source-grounded family-local allowlist candidate for future planning.

Allowed future extraction axes:

- `generated_year`: 2025 for ID `2162`, 2024 for ID `2163`, 2025 for ID
  `2164`.
- `pending_state`: `generated_current_year` for ID `2162`;
  `pending_application` for IDs `2163` and `2164`.

No-go conditions:

- Do not merge with `irpf_deduccion_murcia_vehiculo_generado`; that is a
  separate Murcia vehicle-acquisition deduction.
- Do not merge with generic roles such as
  `irpf_deduccion_murcia_generado_2025_pendiente_2` or
  `irpf_deduccion_murcia_generado_2024_pendiente`.
- Do not generalize from this family to all Murcia generated/pending labels.

Implementation consequence: `murcia_infraestructuras` may be added to a future
family-local implementation wave after a code-facing sidecar metadata surface
exists. It remains exact-ID allowlisted.

## Slice 17 - Madrid nuevos contribuyentes manual lookup

Execution of `W04.P13.S25` manually checked the candidate
`madrid_nuevos_contribuyentes` family against the Renta 2025 autonomous
deductions manual.

Manual grounding:

- The Comunidad de Madrid section contains the deduction titled `Por
  inversiones de nuevos contribuyentes procedentes del extranjero`.
- The manual cites the normative basis as Art. 17 bis of the Texto Refundido
  de las disposiciones legales de la Comunidad de Madrid en materia de
  tributos cedidos por el Estado, approved by Decreto Legislativo 1/2010.
- The manual states that the deduction may be applied in the investment year
  and in the five immediately following tax years if the tax liability is
  insufficient. If the investment was made in the year before acquiring Madrid
  IRPF taxpayer status, it may be applied in the year of acquiring that status
  or in the five immediately following tax years.

Registry members tied to the candidate:

| id | current role | label |
|---|---|---|
| `2031` | `irpf_deduccion_madrid_nuevos_contribuyentes_generado` | `Importe generado en 2025` |
| `2032` | `irpf_deduccion_madrid_nuevos_contribuyentes_pendiente` | `Importe generado en 2025 pendiente de aplicación` |

### Promotion decision

Execution of `W04.P13.S26` promotes `madrid_nuevos_contribuyentes` from
candidate to source-grounded family-local allowlist candidate for future
planning.

Allowed future extraction axes:

- `generated_year`: 2025 for IDs `2031` and `2032`.
- `pending_state`: `generated_current_year` for ID `2031`;
  `pending_application` for ID `2032`.

No-go conditions:

- Do not merge with `irpf_deduccion_madrid_generado_pendiente_aplicacion` or
  `irpf_deduccion_madrid_generado_2024_pendiente_2`; those are generic
  Madrid generated/pending roles from different candidate context.
- Do not merge with Madrid new-entity or alternative-market investment
  deductions; the manual states incompatibility with those deductions for the
  same investments.

Implementation consequence: `madrid_nuevos_contribuyentes` may be added to a
future family-local implementation wave after a code-facing sidecar metadata
surface exists. It remains exact-ID allowlisted.

## Slice 18 - La Rioja generated/pending manual lookup

Execution of `W04.P14.S27` manually checked the La Rioja generated/pending
pair against the Renta 2025 autonomous deductions manual and nearby registry
context.

Manual grounding:

- The La Rioja section contains the deduction titled `Para fomentar la
  fijación de población ocupada en el medio rural`.
- The manual cites the normative basis as Art. 32.8 of Ley 10/2017, de 27 de
  octubre, por la que se consolidan las disposiciones legales de la Comunidad
  Autónoma de La Rioja en materia de impuestos propios y tributos cedidos.
- The manual states that if the taxpayer lacks sufficient autonomous tax
  liability to apply the full deduction in the period when the right is
  generated, the unapplied amount may be applied in the following three years
  until exhausted.
- Registry adjacency supports this family: ID `2057` is labelled `Para
  fomentar la fijación de población ocupada en el medio rural`, followed by
  IDs `2058` and `2059`.

Registry members tied to the candidate:

| id | current role | label |
|---|---|---|
| `2058` | `irpf_deduccion_la_rioja_generado_2025` | `Importe generado en 2025` |
| `2059` | `irpf_deduccion_la_rioja_generado_2025_pendiente` | `Importe generado en 2025 pendiente de aplicación` |

### Promotion decision

Execution of `W04.P14.S28` blocks the current La Rioja pair from the
family-local allowlist despite the manual grounding.

Reason: the current role stems are CCAA-generic and do not encode the
source-grounded family. A future implementation would need the preserved base
to be something like the existing adjacent family role
`irpf_deduccion_la_rioja_fijacion_poblacion_rural`, not
`irpf_deduccion_la_rioja`.

No-go conditions:

- Do not extract generated/pending axes from IDs `2058` and `2059` while the
  preserved base would be the CCAA-generic `irpf_deduccion_la_rioja`.
- Do not merge with other La Rioja generated/pending or municipality-code
  rows.
- Do not rename the base role without a separate source-data change audit and
  registry validation.

Implementation consequence: La Rioja is source identified but not promoted.
It should become a future semantic-role correction slice before any sidecar
metadata extraction.

## Slice 19 - Catalunya generated/pending manual lookup

Execution of `W04.P15.S29` manually checked the Catalunya generated/pending
pair against the Renta 2025 autonomous deductions manual and nearby registry
context.

Manual grounding:

- The Catalunya section contains the deduction titled `Por inversión en
  sociedades cooperativas agrarias y de vivienda`.
- The manual cites the normative basis as Art. 612-12 of Decreto Legislativo
  1/2024, de 12 de marzo, approving book sixth of the Código tributario de
  Catalunya.
- The manual states under `Saldos pendientes de aplicación` that if the
  taxpayer lacks sufficient autonomous tax liability to apply the full
  deduction generated in each period, the undeducted amount may be compensated
  in future years.
- The manual states that the data is transferred to the additional-information
  section for the Catalunya autonomous deduction for investment in agricultural
  and housing cooperative societies in Anexo B.14.
- Registry adjacency supports this family: ID `2003` is labelled `Por
  inversión en sociedades cooperativas agrarias y de vivienda`, followed by
  IDs `2004` and `2005`.

Registry members tied to the candidate:

| id | current role | label |
|---|---|---|
| `2004` | `irpf_deduccion_catalunya_generado_2025` | `Importe generado en 2025` |
| `2005` | `irpf_deduccion_catalunya_pendiente_ejercicio_anterior` | `Importe generado en 2025 pendiente de aplicación` |

### Promotion decision

Execution of `W04.P15.S30` blocks the current Catalunya pair from the
family-local allowlist despite the manual grounding.

Reason: the current generated/pending role stems do not encode the
source-grounded cooperative-society family. Future extraction would need the
preserved base to be family-specific, aligned with the adjacent role
`irpf_deduccion_catalunya_cooperativas_agrarias`, not the CCAA-generic
`irpf_deduccion_catalunya`.

No-go conditions:

- Do not extract generated/pending axes from IDs `2004` and `2005` while the
  preserved base would be `irpf_deduccion_catalunya` or an inconsistent
  pending-only role.
- Do not merge with other Catalunya generated/pending rows or generic
  Catalunya deduction roles.
- Do not rename the base role without a separate source-data change audit and
  registry validation.

Implementation consequence: Catalunya is source identified but not promoted.
It should become a future semantic-role correction slice before any sidecar
metadata extraction.

## Slice 20 - Future repeated-surface discovery scan

Execution of `W05.P16.S31` performed a read-only scan across Modelo 100
casilla registry rows for revisions 2020 through 2025 and Modelo 200
`2024-y-siguientes` casilla registry rows.

Scan counts:

- Total casilla rows read: 14,528.
- Modelo 100 rows read: 11,302.
- Modelo 200 rows read: 3,226.

Additional Modelo 100 repeated surfaces:

| surface | rows | distinct roles | distinct labels | examples |
|---|---:|---:|---:|---|
| Anexo C carryforward year/state rows | 709 | 36 | 29 | `irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio`, `irpf_anexo_c_saldo_neg_gyp_general_aplicado`, `irpf_anexo_c_saldo_neg_gyp_general_pendiente_fin` |
| Ganancias/pérdidas deferred-imputation slot rows | 220 | 50 | 4 | `irpf_ganancia_otros_anio_imputacion`, `irpf_ganancia_otros_importe_percibir_1`, `irpf_ganancia_otros_ganancia_pendiente_2`, `irpf_perdida_otros_pendiente_3` |
| Cadastral reference 1/2 and missing-reference flags | 77 | 15 | 3 | `irpf_deduccion_canarias_referencia_catastral_1`, `irpf_anexo_b_arrendamiento_referencia_catastral`, `irpf_gp_elemento_referencia_catastral_2` |
| Cross-CCAA deduction titles | 59 | 11 | 2 | `irpf_deduccion_andalucia_nacimiento_adopcion`, `irpf_deduccion_canarias_familia_numerosa`, `irpf_deduccion_madrid_nacimiento_adopcion` |

Additional Modelo 200 broad-role grid surfaces:

| current role | rows | distinct labels | visible axes in labels |
|---|---:|---:|---|
| `is_conversion_aid_art130_importe` | 111 | 66 | generation year, pending/generated, applied, initial-period state |
| `is_gastos_financieros_pendiente_deducir` | 72 | 72 | generation year, pending at start, applied, pending future |
| `is_deduccion_donativos_general` | 72 | 72 | year, reiterated/non-reiterated donation branch, pending/generated, applied, future |
| `is_cooperativa_compensacion_cuotas` | 70 | 70 | year, applied, pending start, pending future |
| `is_deduccion_inversion_canarias_importe` | 59 | 59 | investment family, year, pending/generated, applied, future |
| `is_deduccion_idi_excluida_limite_investigacion` | 49 | 49 | year, investigation branch, pending/generated, reduced, applied |
| `is_deduccion_idi_excluida_limite_innovacion` | 49 | 49 | year, innovation branch, pending/generated, reduced, applied, abono |
| `is_bin_detalle_compensacion` | 39 | 39 | year, pending/generated at start, future state |

Discovery finding: the next repeated-surface work should treat these as
table-axis or row-axis candidates, not as ad hoc per-modelo legal rewrites.
However, broad-role reuse does not by itself prove that every label component
is safe metadata. Each candidate needs manual source lookup against the
official form/manual table before any extraction.

## Slice 21 - Candidate intake records and no-go conditions

Execution of `W05.P16.S32` converted the discovery scan into candidate intake
records. These records are not implementation approval.

### Candidate A - Modelo 100 Anexo C carryforward year/state grid

Observed examples:

- `Ejercicio 2016: Pendiente de aplicación  al principio del periodo`
- `Ejercicio 2019: Aplicado en esta  declaración`
- `Ejercicio 2023: Pendiente de aplicación en ejercicios futuros`
- Roles include `irpf_inmueble_gastos_pendientes_inicio_periodo`,
  `irpf_anexo_c_saldo_neg_gyp_ahorro_aplicado`, and
  `irpf_anexo_c_exceso_sps_rt_pendiente_fin`.

Possible mechanical axes after source lookup: `origin_year` and
`carryforward_state`.

Source requirement: Renta manual/form source for Anexo C row groups and each
legal basket represented by the preserved base.

No-go conditions:

- Do not merge the legal baskets behind the bases; losses, excess
  contributions, rental-property expenses, and other Anexo C concepts remain
  separate.
- Do not infer a valid year range from one filing year into another without
  checking that revision's form table.

### Candidate B - Modelo 100 deferred-imputation slot grid

Observed labels: `Año de imputación`, `Importe a percibir`, `Ganancia
patrimonial pendiente  de imputación`, and `Pérdida patrimonial pendiente  de
imputación`.

Observed roles include `irpf_ganancia_otros_importe_percibir_1`,
`irpf_ganancia_otros_importe_percibir_2`,
`irpf_ganancia_otros_ganancia_pendiente_imputacion`, and
`irpf_perdida_otros_pendiente_resto`.

Possible mechanical axes after source lookup: slot/order axis and amount-type
axis for the same deferred-imputation table.

Source requirement: official Renta source for the gains/losses deferred
imputation table and its row-slot semantics.

No-go conditions:

- Do not normalize away `resto`; it may be a residual bucket rather than a
  simple ordinal slot.
- Do not merge gain and loss bases.

### Candidate C - Modelo 100 cadastral reference repeated fields

Observed examples:

- `irpf_deduccion_canarias_referencia_catastral_1`
- `irpf_deduccion_canarias_referencia_catastral_2`
- `irpf_anexo_b_arrendamiento_referencia_catastral`
- `irpf_gp_elemento_referencia_catastral_1`
- `irpf_gp_elemento_referencia_catastral_2`

Possible mechanical axes after source lookup: reference slot number and
missing-reference flag.

Source requirement: official form/manual source for each repeated cadastral
reference table.

No-go conditions:

- Do not merge Canarias deduction references, Anexo B rental references, and
  gains/losses property references into one legal base.
- Do not treat reference slot `1`/`2` as semantic noise until source confirms
  table cardinality.

### Candidate D - Modelo 200 compensation and carryforward grids

Observed roles include `is_gastos_financieros_pendiente_deducir`,
`is_bin_detalle_compensacion`, and `is_cooperativa_compensacion_cuotas`.

Possible mechanical axes after source lookup: generation year and state
(`pending_or_generated_start`, `applied_current_liquidation`,
`pending_future`).

Source requirement: Modelo 200 official form/manual table source for each
compensation grid.

No-go conditions:

- Do not merge financial-expense limits, negative tax bases, and cooperative
  quota compensation into one base.
- Do not flatten years such as `1999`, `2000`, or `2007 y anteriores`; source
  wording determines whether the value is a year or a grouped legal bucket.

### Candidate E - Modelo 200 deduction grid families

Observed roles include `is_deduccion_donativos_general`,
`is_deduccion_inversion_canarias_importe`,
`is_deduccion_idi_excluida_limite_investigacion`, and
`is_deduccion_idi_excluida_limite_innovacion`.

Possible mechanical axes after source lookup: year, row state
(`pending_generated`, `reduced`, `applied`, `abono`, `future`), and statutory
sub-branch.

Source requirement: Modelo 200 official form/manual table source for each
deduction grid, including statutory article and regional-regime references
shown in the labels.

No-go conditions:

- Do not merge general donations, Canarias investment incentives, and I+D+i
  branches.
- Do not normalize away statutory branches such as `investigacion`,
  `innovacion`, `Canarias`, or donation reiteration status without policy
  review.

### Candidate F - Modelo 100 cross-CCAA deduction-title repeats

Observed examples:

- `irpf_deduccion_andalucia_nacimiento_adopcion`
- `irpf_deduccion_canarias_nacimiento_adopcion`
- `irpf_deduccion_castilla_la_mancha_familia_numerosa`
- `irpf_deduccion_madrid_nacimiento_adopcion`

Finding: this is a no-normalization candidate. The repeated title is a UX
caption pattern across autonomous-community deductions, not evidence of one
legal concept.

Source requirement: autonomous-community manual sections and legal references
for any region-specific family considered later.

No-go conditions:

- Do not merge cross-CCAA deduction roles by title alone.
- Do not treat same Spanish caption as same legal rule across communities.

## Slice 22 - Future promotion gate

Execution of `W05.P16.S33` did not promote any newly discovered candidate to a
new implementation wave.

Reason: the W05 scan identified high-value mechanical surfaces, but none of
the new candidates has completed manual source lookup comparable to the
Murcia, Madrid, La Rioja, and Catalunya slices. Promotion would be premature
and would risk enrolling legally incorrect metadata.

Next slice recommended:

1. Start with Modelo 200 compensation/carryforward grids because the table
   shape is large, repetitive, and visibly axis-like.
2. Manually source-check `is_gastos_financieros_pendiente_deducir`,
   `is_bin_detalle_compensacion`, and `is_cooperativa_compensacion_cuotas`
   against official Modelo 200 form/manual tables.
3. Only after the table axes are source-confirmed, use the plan CLI to add a
   dedicated wave for one grid family with exact-ID allowlists and no-go
   conditions.

## Slice 23 - Modelo 200 financial-expense carryforward source lookup

Execution of `W06.P17.S34` manually checked the Modelo 200 financial-expense
pending-deduction grid against the official AEAT `Manual práctico Sociedades
2024`.

Manual grounding:

- The manual describes the adjustments for `Ajustes por la limitación en la
  deducibilidad en gastos financieros (art. 16 LIS)` on page 12 of Modelo 200.
- For the carryforward table, the manual describes a column for `Pendiente de
  aplicación a principio del período. Por límite 16.5 y 83 LIS`, covering
  financial expenses from debts used to acquire shareholdings generated in the
  relevant prior periods.
- The manual separately describes `Pendiente de aplicación a principio del
  período. Resto`, for net financial expenses generated in prior periods and
  pending by application of the art. 16.1 LIS limit or by art. 20 TRLIS for
  2012 through 2014.
- The manual describes `Aplicado en esta liquidación` as the part of pending
  prior-period financial expenses applied in the current tax period.
- The manual separately describes future-pending columns for `Por límite 16.5
  y 83 LIS` and `Resto`.

Registry members tied to the current broad role:

| current role | rows | label-derived years | label-derived states |
|---|---:|---|---|
| `is_gastos_financieros_pendiente_deducir` | 72 | `2012` through `2025`, plus `Total` | `start_limit`, `start_resto`, `applied`, `future_limit`, `future_resto` |

Observed registry examples:

| id | label-derived axes |
|---|---|
| `01098` | generation year `2021`, `start_limit` |
| `01099` | generation year `2021`, `start_resto` |
| `01100` | generation year `2022`, `applied` |
| `01101` | generation year `2022`, `future_limit` |
| `01102` | generation year `2022`, `future_resto` |
| `01212` | `Total`, `start_limit` |
| `01213` | `Total`, `start_resto` |
| `01214` | `Total`, `applied` |
| `01215` | `Total`, `future_limit` |
| `01216` | `Total`, `future_resto` |

### Promotion decision

Execution of `W06.P17.S35` promotes the financial-expense carryforward grid to
a source-grounded table-axis candidate for future implementation planning.

Allowed future extraction axes:

- `generation_year`: explicit label year for ordinary rows.
- `row_kind`: `year` or `total`.
- `carryforward_state`: `pending_start`, `applied_current_liquidation`, or
  `pending_future`.
- `limit_branch`: `art_16_5_or_83_lis` for `Por límite 16.5 y 83 LIS`, `resto`
  for `Resto`, and absent for `applied_current_liquidation`.

No-go conditions:

- Do not collapse `Por límite 16.5 y 83 LIS` and `Resto`; the manual assigns
  different legal branches to those columns.
- Do not synthesize missing `Por límite` rows for years where the official
  table only exposes `Resto`.
- Do not treat `Total` rows as generation-year rows.
- Do not merge this grid with other financial-expense limit rows on page 20,
  such as current-period deductible/non-deductible calculations.

Implementation consequence: this grid may become a future exact-ID table-axis
implementation wave. The preserved base should remain
`is_gastos_financieros_pendiente_deducir`, with axes carried in sidecar
metadata rather than by role-name proliferation.

## Slice 24 - Modelo 200 negative tax-base compensation source lookup

Execution of `W06.P18.S36` manually checked the Modelo 200 negative tax-base
compensation grid against the official AEAT `Manual práctico Sociedades 2024`.

Manual grounding:

- The manual section `Cumplimentación del cuadro Detalle de la compensación de
  bases imponibles` describes page 15 of Modelo 200.
- The manual states that the declarant, except for cooperatives, fiscal-group
  entities, and entities applying the special Canary Islands shipping regime,
  completes the table by year of origin for negative tax bases pending at the
  start of the tax period.
- The manual describes the column `Pendiente de aplicación a principio del
  período/generada en el período` for negative tax bases generated in 1997
  through 2024 and pending at the start of the period, with special handling
  for a short tax period also started in 2024.
- The manual describes `Aplicado en esta liquidación` as the part of that
  pending/generated amount applied in the current liquidation.
- The manual describes `Pendiente de aplicación en períodos futuros` as the
  positive difference between the pending/generated amount and the amount
  applied in the current liquidation.

Registry members tied to the table:

| current role | rows | visible role coverage |
|---|---:|---|
| `is_bin_detalle_compensacion` | 39 | mostly pending/generated start and future-pending rows, plus two applied rows |
| `is_compensacion_bases_negativas` | 16 | applied rows for most years |

Observed registry examples:

| id | current role | label-derived axes |
|---|---|---|
| `00646` | `is_bin_detalle_compensacion` | year `1999`, `pending_start_or_generated` |
| `00647` | `is_compensacion_bases_negativas` | year `1999`, `applied_current_liquidation` |
| `00648` | `is_bin_detalle_compensacion` | year `1999`, `pending_future` |
| `01048` | `is_bin_detalle_compensacion` | year `2025`, `pending_start_or_generated` |
| `01049` | `is_bin_detalle_compensacion` | year `2025`, `pending_future` |
| `02316` | `is_bin_detalle_compensacion` | year `2025(*)`, `pending_start_or_generated` |
| `02317` | `is_compensacion_bases_negativas` | year `2025(*)`, `applied_current_liquidation` |
| `02318` | `is_bin_detalle_compensacion` | year `2025(*)`, `pending_future` |

### Promotion decision

Execution of `W06.P18.S37` blocks a single-role sidecar extraction for the
negative tax-base compensation grid, despite the source-confirmed table shape.

Reason: the current registry roles split one official table across at least
two semantic roles. A future extraction that only preserves
`is_bin_detalle_compensacion` would omit or mis-base most
`Aplicado en esta liquidación` rows. A future extraction that rewrites
`is_compensacion_bases_negativas` into the BIN detail base would be a registry
semantic-role correction and needs its own audit and validation.

Allowed future candidate shape after policy review:

- `origin_year`: explicit label year, including special handling for
  `2025(*)`.
- `carryforward_state`: `pending_start_or_generated`,
  `applied_current_liquidation`, or `pending_future`.
- `table_scope`: general BIN compensation table only.

No-go conditions:

- Do not promote `is_bin_detalle_compensacion` alone as a complete table-axis
  extractor.
- Do not silently merge `is_compensacion_bases_negativas` into
  `is_bin_detalle_compensacion` without a separate semantic-role correction
  audit.
- Do not include cooperative, fiscal-group, or Canary Islands shipping-regime
  special tables in the general BIN table; the manual explicitly excludes
  those cases from this general table.
- Do not treat `2025(*)` as an ordinary calendar-year row without preserving
  its short-period marker.

Implementation consequence: the general BIN table is source identified but not
promoted for implementation in the current sidecar shape. The next safe slice
would be an exact-ID table inventory that includes both current roles and
decides, by policy, whether a base-role correction is required.

## Slice 25 - Modelo 200 cooperative quota compensation source lookup

Execution of `W06.P19.S38` manually checked the Modelo 200 cooperative quota
compensation grid against the official AEAT `Manual práctico Sociedades 2024`
and the current Modelo 200 registry labels.

Manual grounding:

- The manual describes `Compensación de cuotas negativas de períodos
  anteriores` as a cooperative-only concept.
- For cooperatives that are not fiscally protected, the manual states that the
  relevant casilla is used for negative quotas to compensate from prior
  periods.
- For fiscally protected cooperatives, the manual states that cooperatives
  exercising the ability to compensate negative quotas from prior tax periods
  include those quotas in the corresponding cooperative casilla.
- The manual cites the quantitative limit by reference to art. 24.1 of Ley
  20/1990 and the replacement limits in the additional provision eighth of Ley
  20/1990 for entities above the turnover thresholds.
- The manual also notes the quitas/esperas exception and distinguishes
  cooperative and extracooperative results for that exception.

Registry members tied to the current role:

| current role | rows | visible years | visible states |
|---|---:|---|---|
| `is_cooperativa_compensacion_cuotas` | 70 | `2000` through `2025`, plus `Total` | `pending_start`, `applied`, `pending_future` |

Observed registry examples:

| id | label-derived axes |
|---|---|
| `00673` | year `2000`, `pending_start` |
| `00674` | year `2000`, `applied_current_liquidation` |
| `00678` | year `2001`, `pending_future` |
| `00694` | `Total`, `pending_start` |
| `00695` | `Total`, `pending_future` |
| `01186` | year `2021`, `pending_start` |
| `01187` | year `2021`, `applied_current_liquidation` |
| `01190` | year `2021`, `pending_future` |
| `03633` | year `2025(*)`, `pending_start` |
| `03634` | year `2025(*)`, `applied_current_liquidation` |
| `03635` | year `2025(*)`, `pending_future` |

### Promotion decision

Execution of `W06.P19.S39` promotes the cooperative quota compensation grid to
a source-grounded exact-ID table-axis candidate for future implementation
planning.

Allowed future extraction axes:

- `origin_year`: explicit label year, with `2025(*)` preserved as a marked
  short-period/current-period row.
- `row_kind`: `year` or `total`.
- `compensation_state`: `pending_start`, `applied_current_liquidation`, or
  `pending_future`.
- `legal_family`: cooperative negative-quota compensation under Ley 20/1990.

No-go conditions:

- Do not merge this grid with general BIN compensation. Cooperative negative
  quotas are legally distinct from general negative tax bases.
- Do not infer whether a row is for protected or non-protected cooperatives
  from the shared role alone; that distinction is governed by the cooperative
  regime context and the marked casillas, not by the row labels here.
- Do not treat `Total` as an origin year.
- Do not normalize `2025(*)` to ordinary `2025` without preserving the marker.
- Do not synthesize missing applied/future rows for years where the current
  registry does not expose a full three-state set.

Implementation consequence: this grid may become a future exact-ID table-axis
implementation wave. The preserved base should remain
`is_cooperativa_compensacion_cuotas`, with year/state/total axes carried in
sidecar metadata.

## Slice 26 - Modelo 200 general donations deduction source lookup

Execution of `W07.P20.S40` manually checked the Modelo 200 general donations
deduction grid against the official AEAT `Manual práctico Sociedades 2024`.

Manual grounding:

- The manual describes deductions for donations to non-profit entities under
  Ley 49/2002.
- For `Donaciones de carácter general`, the manual describes the column
  `Deducción pendiente/generada` for current-year generated deductions and
  prior-year deductions pending at the start of the tax period.
- The manual describes `Aplicado en esta liquidación` as the amount applied in
  the current liquidation.
- The manual describes `Pendiente de aplicación en períodos futuros` as the
  positive difference between pending/generated deduction and the amount
  applied in the current liquidation, except when the current period is the
  final period in which the deduction may be applied.
- From 2015 onward, the manual requires differentiating donations made `sin
  reiteración` and `con reiteración` to the same entity.
- The manual describes subtotal rows for 2015 through 2024 with and without
  reiteration, and a total row for donations from 2014 through 2024.

Registry members tied to the current role:

| current role | rows | visible years | visible states | visible branches |
|---|---:|---|---|---|
| `is_deduccion_donativos_general` | 72 | `2015` through `2025`, `2025(*)`, subtotal rows, and `Total` | `pending_generated`, `applied`, `pending_future` | `sin_reiteracion`, `con_reiteracion`, subtotal/total rows |

Observed registry examples:

| id | label-derived axes |
|---|---|
| `00369` | year `2024`, `sin_reiteracion`, `pending_generated` |
| `00818` | year `2015`, `con_reiteracion`, `pending_generated` |
| `00819` | year `2015`, `con_reiteracion`, `applied_current_liquidation` |
| `00834` | year `2016`, `con_reiteracion`, `pending_future` |
| `00993` | year `2016`, `sin_reiteracion`, `pending_generated` |
| `01692` | subtotal `2015-2025`, `sin_reiteracion`, `pending_generated` |
| `01695` | subtotal `2015-2025`, `con_reiteracion`, `pending_generated` |
| `01698` | `Total`, `pending_generated` |
| `03543` | year `2025(*)`, `sin_reiteracion`, `pending_generated` |
| `03546` | year `2025(*)`, `con_reiteracion`, `pending_generated` |
| `03552` | year `2025`, `con_reiteracion`, `pending_generated` |

### Promotion decision

Execution of `W07.P20.S41` promotes the general donations deduction grid to a
source-grounded exact-ID table-axis candidate for future implementation
planning.

Allowed future extraction axes:

- `origin_year`: explicit label year for year rows.
- `row_kind`: `year`, `subtotal`, or `total`.
- `period_marker`: preserve `2025(*)` separately from ordinary `2025`.
- `donation_reiteration`: `sin_reiteracion`, `con_reiteracion`, or absent for
  rows where the official table does not apply the distinction.
- `deduction_state`: `pending_generated`, `applied_current_liquidation`, or
  `pending_future`.
- `deduction_family`: general donations to non-profit entities under Ley
  49/2002.

No-go conditions:

- Do not collapse `sin_reiteracion` and `con_reiteracion`; the manual uses
  that distinction for different donation treatment from 2015 onward.
- Do not merge this grid with `is_deduccion_donativos_prioritarias`; priority
  patronage activities are a separate table with separate percentages and
  limits.
- Do not treat subtotal rows as ordinary year rows.
- Do not treat `Total` as an origin year.
- Do not normalize `2025(*)` to ordinary `2025` without preserving the marker.

Implementation consequence: this grid may become a future exact-ID table-axis
implementation wave. The preserved base should remain
`is_deduccion_donativos_general`, with reiteration/year/state/subtotal axes
carried in sidecar metadata.

## Slice 27 - Modelo 200 Canarias investment deduction source lookup

Execution of `W07.P21.S42` manually checked the Modelo 200 Canarias investment
deduction grid against the official AEAT `Manual práctico Sociedades 2024`.

Manual grounding:

- The manual states that entities entitled to deductions for investments made
  in Canarias enter the amount in casilla `[00590]` and that it is derived from
  the `Deducciones inversión en Canarias con límites incrementados` breakdown
  on pages 16 bis and 17 of Modelo 200.
- The manual states that the table covers deductions for fixed assets and
  investments under the Canary Islands regime, and it separately names rows
  for `Activos fijos`, `Inversiones en Canarias`, and `Inversiones en La
  Palma, La Gomera y El Hierro`.
- The manual states that rows marked `2024(*)` are only completed for pending
  deductions from another tax period started in 2024.
- The manual describes `Deducción pendiente/generada` for prior-period and
  current-period generated deductions pending at the start of the period.
- The manual describes `Pendiente de aplicación en períodos futuros` as the
  positive difference between the pending/generated deduction and the amount
  applied in the current liquidation.
- The manual records special increased limits for La Palma, La Gomera, and El
  Hierro, so those rows are not cosmetic regional labels.

Registry members tied to the table:

| current role | rows | visible coverage |
|---|---:|---|
| `is_deduccion_inversion_canarias_importe` | 59 | pending/generated and applied rows, plus some future-pending rows |
| `is_deduccion_inversion_canarias_pendiente` | 18 | future-pending rows for activos fijos and inversiones Canarias |

Observed registry examples:

| id | current role | label-derived axes |
|---|---|---|
| `00852` | `is_deduccion_inversion_canarias_importe` | `activos_fijos`, year `2018`, `pending_generated` |
| `00853` | `is_deduccion_inversion_canarias_importe` | `activos_fijos`, year `2018`, `applied_current_liquidation` |
| `00856` | `is_deduccion_inversion_canarias_importe` | `activos_fijos`, year `2018`, `pending_future` |
| `00859` | `is_deduccion_inversion_canarias_pendiente` | `activos_fijos`, year `2011`, `pending_future` |
| `01058` | `is_deduccion_inversion_canarias_importe` | `inversiones_canarias`, year `2016`, `pending_generated` |
| `01060` | `is_deduccion_inversion_canarias_pendiente` | `inversiones_canarias`, year `2016`, `pending_future` |
| `01763` | `is_deduccion_inversion_canarias_importe` | `activos_fijos_palma_gomera_hierro`, year `2024`, `pending_generated` |
| `01805` | `is_deduccion_inversion_canarias_importe` | `inversiones_palma_gomera_hierro`, year `2024`, `pending_generated` |
| `03433` | `is_deduccion_inversion_canarias_importe` | `inversiones_palma_gomera_hierro`, year `2025`, `pending_generated` |

### Promotion decision

Execution of `W07.P21.S43` blocks a single-role sidecar extraction for the
Canarias investment deduction grid.

Reason: the source-confirmed table is split across at least two current roles,
and the visible subfamilies are legally meaningful. A single parser over
`is_deduccion_inversion_canarias_importe` would miss future-pending rows that
currently use `is_deduccion_inversion_canarias_pendiente`. A parser that
flattens all labels to one Canarias investment role would also erase the
manual's distinction between fixed assets, general Canarias investments, and
La Palma/La Gomera/El Hierro rows.

Allowed future candidate shape after policy review:

- `origin_year`: explicit label year, preserving any star marker.
- `deduction_state`: `pending_generated`, `applied_current_liquidation`, or
  `pending_future`.
- `canarias_subfamily`: at minimum `activos_fijos`,
  `inversiones_canarias`, `activos_fijos_palma_gomera_hierro`, and
  `inversiones_palma_gomera_hierro`.
- `legal_region_marker`: preserve La Palma, La Gomera, and El Hierro as a
  legal limit marker, not text noise.

No-go conditions:

- Do not promote `is_deduccion_inversion_canarias_importe` alone as a complete
  table-axis extractor.
- Do not merge `is_deduccion_inversion_canarias_pendiente` into the importe
  base without a separate exact-ID semantic-role policy decision.
- Do not collapse La Palma, La Gomera, and El Hierro rows into ordinary
  Canarias rows.
- Do not merge this grid with other Canary-regime deductions, I+D+i Canarias
  grids, or cinematographic Canary grids.

Implementation consequence: the Canarias investment table is source
identified but not promoted for single-role implementation. The next safe
slice is an exact-ID inventory across both current roles and all visible
subfamilies.

## Slice 28 - Modelo 200 I+D+i excluded-limit deduction source lookup

Execution of `W07.P22.S44` manually checked the Modelo 200 I+D+i
excluded-limit grids against the official AEAT `Manual práctico Sociedades
2024`.

Manual grounding:

- The manual describes `Deducciones excluidas del límite I+D+i (art. 39.2
  LIS)` for entities that opt to exclude research, development, and
  technological innovation deductions from the art. 39.1 joint limits.
- The manual states that the option is exercised by marking casilla `[00059]`
  `Opción art. 39.2 LIS`.
- The manual describes the page 19 table `Deducciones I + D + i excluidas de
  límite. Opción art. 39.2 LIS`.
- The manual states that the table records deductions for research and
  development and technological innovation generated in 2013 through 2024 that
  could be or can be carried to future periods.
- The manual states that `Investigación y desarrollo 2024(*)` and
  `Innovación tecnológica 2024(*)` rows are only completed for pending
  deductions from an earlier tax period started in 2024.
- The manual describes `Deducción pendiente/generada`, `Deducción reducida`
  after the 20 percent discount, `Aplicado en esta liquidación`, and `Importe
  abonado por insuficiencia de cuota`.

Registry members tied to the current roles:

| current role | rows | visible years | visible states |
|---|---:|---|---|
| `is_deduccion_idi_excluida_limite_investigacion` | 49 | `2013` through `2025(*)` | `pending_generated`, `reduced`, `applied`, `abono` |
| `is_deduccion_idi_excluida_limite_innovacion` | 49 | `2013` through `2025(*)` | `pending_generated`, `reduced`, `applied`, `abono` |

Observed registry examples:

| id | current role | label-derived axes |
|---|---|---|
| `00918` | `is_deduccion_idi_excluida_limite_investigacion` | year `2013`, `pending_generated` |
| `00919` | `is_deduccion_idi_excluida_limite_investigacion` | year `2013`, `reduced` |
| `01125` | `is_deduccion_idi_excluida_limite_investigacion` | year `2015`, `applied_current_liquidation` |
| `01126` | `is_deduccion_idi_excluida_limite_investigacion` | year `2015`, `abono_insufficient_quota` |
| `00976` | `is_deduccion_idi_excluida_limite_innovacion` | year `2013`, `reduced` |
| `00977` | `is_deduccion_idi_excluida_limite_innovacion` | year `2013`, `applied_current_liquidation` |
| `01094` | `is_deduccion_idi_excluida_limite_innovacion` | year `2021`, `pending_generated` |
| `01097` | `is_deduccion_idi_excluida_limite_innovacion` | year `2021`, `abono_insufficient_quota` |
| `03575` | `is_deduccion_idi_excluida_limite_investigacion` | `2025(*)`, `pending_generated` |
| `03579` | `is_deduccion_idi_excluida_limite_innovacion` | `2025(*)`, `pending_generated` |

### Promotion decision

Execution of `W07.P22.S45` promotes both I+D+i excluded-limit roles to
source-grounded exact-ID table-axis candidates for future implementation
planning.

Allowed future extraction axes:

- `origin_year`: explicit label year.
- `period_marker`: preserve `2025(*)` separately from ordinary years.
- `idi_branch`: `investigacion_desarrollo` or `innovacion_tecnologica`.
- `deduction_state`: `pending_generated`, `reduced`,
  `applied_current_liquidation`, or `abono_insufficient_quota`.
- `option`: `art_39_2_lis_excluded_limit`.

No-go conditions:

- Do not merge research/development and technological innovation into one
  branch-neutral I+D+i role; the manual and labels preserve them separately.
- Do not infer a `pending_future` row for this surface unless an exact registry
  row is identified for it.
- Do not merge this excluded-limit table with ordinary I+D+i deductions that
  remain subject to the art. 39.1 limits.
- Do not normalize `2025(*)` to ordinary `2025` without preserving the marker.
- Do not ignore the `abono` state; it is a distinct table column tied to
  insufficient quota.

Implementation consequence: both roles may become future exact-ID table-axis
implementation candidates, preserving their current branch-specific bases and
carrying year/state/option markers in sidecar metadata.

## Slice 29 - Modelo 100 Anexo C carryforward source lookup

Execution of `W08.P23.S46` manually checked the Modelo 100 2025 Anexo C
carryforward repeated labels against the official AEAT Renta 2025 manual and
the official AEAT Modelo 100 declaration dictionary.

Source grounding:

- The Renta manual identifies Anexo C as additional information attached to
  the declaration and explicitly names Anexo C.1 for gains and losses with
  deferred collection and Anexo C.5 for carryforward deduction amounts.
- The official declaration dictionary records Anexo C.2 fields under paths
  such as `AnexoCRes/SaldosNegGyPGeneralRes` with labels for `Ejercicio
  2021: Pendiente de aplicación al principio del periodo`, `Ejercicio 2021:
  Aplicado en esta declaración`, and later `Pendiente de aplicación en
  ejercicios futuros`.
- The official declaration dictionary records the same label pattern in
  basket-specific paths, not one generic carryforward container.

Observed Modelo 100 2025 registry shape:

| surface | rows | roles | labels | sections |
|---|---:|---:|---:|---:|
| Anexo C carryforward-like rows | 148 | 45 | 24 | 12 |

Representative current roles:

| role | count | basket |
|---|---:|---|
| `irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio` | 4 | negative gains/losses, base general |
| `irpf_anexo_c_saldo_neg_gyp_ahorro_aplicado` | 4 | negative gains/losses, base ahorro |
| `irpf_anexo_c_rdto_cm_negativo_pendiente_fin` | 3 | negative capital-mobiliario income |
| `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | 5 | social-prevision excesses |
| `irpf_anexo_c_exceso_scd_aplicado` | 5 | collective dependency insurance excesses |
| `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_fin` | 4 | disabled-relative social-prevision excesses |
| `irpf_anexo_c_exceso_patrim_protegido_generado` | 1 | protected-patrimony excesses |
| `irpf_anexo_c_base_liq_neg_pendiente_inicio` | 4 | negative liquidable base |
| `irpf_anexo_c_exceso_eeficiencia_pendiente_fin` | 3 | energy-efficiency deduction excesses |

### Promotion decision

Execution of `W08.P23.S47` promotes Anexo C carryforward rows only as
basket-preserving exact-ID table-axis candidates.

Allowed future extraction axes:

- `origin_year`: explicit dictionary label year.
- `carryforward_state`: `pending_start_period`, `applied_current_return`,
  `pending_future`, or `generated_current_year`.
- `anexo_c_basket`: preserve the existing legal basket from the current role
  and dictionary path.
- `contributor_marker`: preserve contributor/titular rows separately from
  monetary rows.

No-go conditions:

- Do not merge Anexo C baskets because they share year/state captions.
- Do not infer a `pending_future` row for the earliest prior year where the
  official table has only beginning balance and applied amount.
- Do not merge `base_general`, `base_ahorro`, capital-mobiliario, social
  prevision, protected-patrimony, deportista, negative-base, and
  energy-efficiency surfaces.
- Do not normalize typo-adjacent role stems such as
  `irpf_anexo_c_exceso_eeficiencia_*` without a separate semantic-role rename
  policy.

Implementation consequence: Anexo C is a strong mechanical axis candidate, but
only after an exact-ID allowlist is generated per basket. The next safe slice
is a metadata extractor contract scoped to Anexo C IDs, not a generic
`pendiente/aplicado` parser.

## Slice 30 - Modelo 100 deferred-imputation source lookup

Execution of `W08.P24.S48` manually checked deferred-imputation rows against
the official AEAT Renta 2025 manual and official Modelo 100 declaration
dictionary.

Manual grounding:

- The Renta manual explains that for operations with instalment or deferred
  price, the taxpayer may allocate gains or losses proportionally as payments
  become due.
- The manual states that exercising that option is done element by element in
  the Anexo C.1 section for gains and losses with deferred price pending
  allocation in future years.

Official dictionary grounding:

- The declaration dictionary records repeated four-column slot groups with
  labels `Año de imputación`, `Importe a percibir`, `Ganancia patrimonial
  pendiente de imputación`, and `Pérdida patrimonial pendiente de imputación`.
- The dictionary paths split those slots across ordinary patrimonial elements,
  cryptocurrency elements, and immovable-property elements.

Observed Modelo 100 2025 registry shape:

| branch | rows | labels |
|---|---:|---:|
| `gp_otros_elementos.elemento_patrimonial` | 16 | 4 |
| `gp_otros_criptomonedas.elemento_criptomoneda` | 16 | 4 |
| `gp_otros_inmuebles.elemento_inmueble` | 16 | 4 |

Representative current roles:

| role | example id | label |
|---|---|---|
| `irpf_ganancia_otros_anio_imputacion` | `0363` | `Año de imputación` |
| `irpf_ganancia_otros_importe_percibir_2` | `0368` | `Importe a percibir` |
| `irpf_ganancia_cripto_ganancia_pendiente_3` | `1871` | `Ganancia patrimonial pendiente de imputación` |
| `irpf_perdida_inmueble_pendiente_imputacion` | `1893` | `Pérdida patrimonial pendiente de imputación` |
| `irpf_ganancia_cripto_importe_percibir_resto` | `1877` | residual amount slot |

### Promotion decision

Execution of `W08.P24.S49` promotes deferred-imputation rows only as
branch-preserving exact-ID slot-axis candidates.

Allowed future extraction axes:

- `deferred_slot`: explicit slot number where present.
- `deferred_slot_kind`: `ordinary_slot` or `resto`.
- `deferred_field`: `imputation_year`, `amount_to_receive`,
  `pending_gain`, or `pending_loss`.
- `asset_branch`: ordinary patrimonial element, cryptocurrency, or immovable
  property.

No-go conditions:

- Do not merge ordinary, cryptocurrency, and immovable-property branches into
  one branch-neutral role.
- Do not merge gain and loss pending amounts.
- Do not normalize `resto` into slot 5 unless the official dictionary or a
  policy decision explicitly says it is a numbered continuation.
- Do not infer legal definitions for the deferred-price option beyond the
  manual's element-by-element Anexo C.1 wording.

Implementation consequence: the repeated four-column layout is mechanically
useful, but only as an exact-ID slot extractor preserving branch and
gain/loss polarity.

## Slice 31 - Modelo 100 cadastral reference source lookup

Execution of `W08.P25.S50` manually checked repeated cadastral-reference and
no-reference marker labels against the official AEAT Renta 2025 manual and
official Modelo 100 declaration dictionaries.

Source grounding:

- The Renta manual states that when the relevant situation key is used, the
  cadastral reference of the immovable property must be provided, and identifies
  the reference as a property-identification datum.
- The official declaration dictionary records many separate cadastral-reference
  paths using text type `X`, and many separate no-reference markers using
  logical type `LGC`.
- The official toma-de-datos dictionary records additional family-local
  repeated windows for regional deductions, including Canarias, Cantabria,
  Extremadura, Galicia, Madrid, and other autonomous deduction surfaces.

Observed Modelo 100 2025 registry shape:

| surface | rows | roles | labels | sections |
|---|---:|---:|---:|---:|
| cadastral-reference or no-reference labels | 44 | 22 | 11 | 13 |

Representative current roles:

| role | count | example surface |
|---|---:|---|
| `irpf_inmueble_referencia_catastral` | 3 | ordinary property data |
| `irpf_anexo_b_no_catastral_flag` | 12 | multiple Anexo B windows |
| `irpf_anexo_b_arrendamiento_referencia_catastral` | 3 | Anexo B rental data |
| `irpf_deduccion_canarias_referencia_catastral_1` | 1 | Canarias deduction |
| `irpf_deduccion_canarias_referencia_catastral_1_flag` | 1 | Canarias no-reference marker |
| `irpf_deduccion_eficiencia_energetica_vivienda_referencia_catastral` | 3 | energy-efficiency deduction |
| `irpf_ganancia_inmueble_referencia_catastral_1` | 1 | immovable-property gain/loss |
| `irpf_deduccion_murcia_infraestructuras_referencia_catastral` | 1 | Murcia infrastructure deduction |

### Promotion decision

Execution of `W08.P25.S51` blocks global cadastral-reference normalization.

Allowed future extraction shape after policy review:

- Family-local `cadastral_reference_index` axis only where an exact window has
  repeated numbered slots.
- Separate `no_cadastral_reference_flag` axis only where the official field
  type is logical and the registry role is already scoped to the same family.
- Preserve property, gain/loss, Anexo A, Anexo B, FEAC, regional deduction,
  and ordinary inmueble contexts.

No-go conditions:

- Do not replace all reference roles with a single
  `irpf_referencia_catastral` semantic role.
- Do not merge text reference fields with logical no-reference marker fields.
- Do not merge regional deduction windows by shared cadastral labels.
- Do not treat the toma-de-datos dictionary's `###` dynamic windows as the same
  surface as numbered declaration-output casillas without a separate mapping
  policy.

Implementation consequence: cadastral labels are useful for local slot metadata
inside already-scoped families, but are not a safe global sidecar burn-down
candidate.

## Slice 32 - W09 warning-sidecar implementation contract

Execution of `W09.P26.S52` implemented the first code-bearing warning-sidecar
slice in the semantic-role validator.

Implementation boundary:

- The code recognizes Anexo C carryforward state suffixes only inside the
  audited basket stems.
- The code recognizes deferred-imputation slot suffixes only inside the
  audited ordinary, cryptocurrency, and immovable-property branches.
- The code does not change registry `semantic_role` values.
- The code does not add a global cadastral-reference sibling rule.

Source-to-code mapping:

| audited decision | implementation behavior |
|---|---|
| Anexo C state labels repeat within basket-specific dictionary paths | same-basket Anexo C carryforward state roles are not typo warnings |
| Anexo C baskets are legally distinct | `gyp_general` and `gyp_ahorro` remain non-siblings |
| deferred-imputation slots repeat by branch | slot numbers and `resto` are warning-sidecar axes within a branch and field |
| deferred-imputation branches and gain/loss polarity are distinct | ordinary, crypto, inmueble, gain, and loss roles remain non-siblings |
| cadastral labels are not globally normalizable | reference fields and no-reference flags remain non-siblings |

Execution of `W09.P26.S53` added regression tests for both approved
recognizers and the negative boundaries.

Test contract:

- `test_anexo_c_carryforward_state_roles_do_not_warn_as_typos`
- `test_anexo_c_carryforward_baskets_are_not_axis_siblings`
- `test_deferred_imputation_slot_roles_do_not_warn_as_typos`
- `test_deferred_imputation_branches_and_polarity_are_not_axis_siblings`
- `test_cadastral_reference_fields_and_flags_are_not_axis_siblings`

Implementation consequence: the singleton-warning surface can burn down these
audited repeated patterns mechanically, but the validator still treats
cross-basket, cross-branch, gain/loss, and cadastral field-type differences as
possible real semantic differences.

## Slice 33 - W10 Modelo 200 correction warning-sidecar hardening

Execution of `W10.P28.S55` hardened the existing correction-axis warning
behavior against the audited Modelo 200 contract.

Implementation boundary:

- The validator now recognizes balance-only `saldo_inicial` and `saldo_final`
  correction suffixes as typo-warning axes when the preserved base stem is the
  same.
- The validator continues to treat permanent/temporary correction-table
  suffixes as warning-only axes.
- The code does not rewrite Modelo 200 registry `semantic_role` values.
- The code does not extract structured correction metadata from the 23-record
  mismatch bucket where source labels indicate temporary corrections but the
  current role suffix says `permanente_*`.

Execution of `W10.P28.S56` added regression tests for the new balance-only
axis and the mismatch-bucket warning-only boundary.

Test contract:

- `test_correction_balance_axis_roles_do_not_warn_as_typos`
- `test_correction_mismatch_bucket_roles_remain_warning_only_axes`

Implementation consequence: Modelo 200 balance-only correction rows can be
removed from the singleton typo-warning surface mechanically, while the known
label-versus-role mismatch groups remain blocked for any future metadata
extraction or semantic-role rewrite until source policy resolves them.

## Slice 34 - W11 family-local generated/pending warning guard

Execution of `W11.P30.S58` implemented warning-only sibling recognition for
source-approved Modelo 100 family-local generated/pending surfaces.

Implementation boundary:

- The guard is an exact family allowlist, not a generic regional suffix parser.
- The approved family bases are
  `irpf_deduccion_c_valenciana_autoconsumo`,
  `irpf_deduccion_murcia_infraestructuras`, and
  `irpf_deduccion_madrid_nuevos_contribuyentes`.
- The allowed warning-only suffixes are `generado`, `pendiente`,
  `2025_generado`, `2025_pendiente`, and `2024_pendiente`.
- The code does not rewrite registry `semantic_role` values.
- The code does not promote La Rioja or Catalunya generated/pending pairs
  while their preserved role bases are CCAA-generic.

Source-to-code mapping:

| audited decision | implementation behavior |
|---|---|
| C Valenciana autoconsumo has an approved family-local generated/pending pilot | same-family generated/pending rows are warning siblings |
| Murcia infraestructuras was promoted by W04 manual lookup | same-family generated/pending rows are warning siblings |
| Madrid nuevos contribuyentes was promoted by W04 manual lookup | same-family generated/pending rows are warning siblings |
| La Rioja pair is source-identified but CCAA-generic | La Rioja generated/pending roles remain non-siblings |
| Catalunya pair is source-identified but CCAA-generic | Catalunya generated/pending roles remain non-siblings |
| C Valenciana `hasta_2022` and `desde_2023` are legal windows | those legal-window roles remain non-siblings |

Execution of `W11.P30.S59` added regression tests for the approved families
and blocked boundaries.

Test contract:

- `test_approved_family_local_generated_pending_roles_do_not_warn_as_typos`
- `test_family_local_generated_pending_guard_preserves_blocked_generic_bases`

Implementation consequence: the generated/pending warning surface can burn
down only the approved family-local rows. Broader CCAA-generated or
family-renaming work remains a separate policy slice.

## Slice 35 - W12 cross-CCAA warning-boundary hardening

Execution of `W12.P32.S61` removed broad autonomous-community token
normalization from typo-warning sibling recognition.

Reason:

- Earlier source-audit slices established that repeated labels and similar
  role stems across autonomous communities are not legal equivalence proof.
- The broad CCAA guard could hide legitimate region-local singleton roles by
  treating the community token itself as a harmless axis.
- A corpus inspection after removal exposed four current Modelo 100 singleton
  roles that had been hidden by the broad guard:
  `irpf_deduccion_madrid_generado_pendiente_aplicacion`,
  `irpf_deduccion_murcia_vehiculo_matricula`,
  `irpf_deduccion_murcia_vehiculo_importe`, and
  `irpf_deduccion_canarias_acciones_participaciones`.

Execution of `W12.P32.S64` marked those four roles as explicit
`intentional_singleton` registry entries instead of reintroducing broad CCAA
warning suppression.

Source grounding:

- The Renta 2025 autonomous deductions manual separates Madrid, Murcia, and
  Canarias deduction sections and cites separate autonomous legal bases.
- The Murcia vehicle rows are grounded in the manual's Region of Murcia
  vehicle-acquisition deduction under Art. 1.Diecinueve of the Murcia ceded-tax
  text.
- The Canarias shares/participations row is a Canarias Anexo B.11
  region-local investment row, not a cross-CCAA investment-axis role.
- The Madrid generated/pending row remains section-local and policy-gated; it
  is not promoted into the approved Madrid nuevos contribuyentes family.

Execution of `W12.P32.S62` replaced the artificial "CCAA axis" warning test
with a direct legal-boundary test.

Test contract:

- Cross-CCAA vehicle roles are not axis siblings.
- Cross-CCAA birth/adoption roles are not axis siblings.
- The committed-registry singleton marker test covers the four newly reviewed
  Modelo 100 singleton roles.
- The corpus singleton warning-count gate remains clean.

Implementation consequence: the validator no longer treats autonomous
community as a generic typo-warning axis. Current legitimate region-local
singletons are recorded in source data with explicit reasons, and future
cross-CCAA normalization requires exact source-backed policy.

## Slice 36 - W13 legal-reference warning-boundary hardening

Execution of `W13.P34.S66` removed broad legal-reference token stripping from
typo-warning sibling recognition.

Reason:

- Article, transitional-provision, RDLeg, and LIS markers are source-visible
  identity in the Modelo 200 registry labels and must not be treated as
  harmless spelling noise.
- The previous broad guard could hide legal-reference-specific singleton roles
  by stripping `art*`, `dt*`, `rdleg`, and `lis` tokens before comparing role
  stems.
- Corpus inspection after removing the guard exposed 13 current Modelo 200
  singleton roles that had been hidden by legal-marker stripping.

Execution of `W13.P34.S67` marked those 13 roles as explicit
`intentional_singleton` registry entries instead of reintroducing generic
legal-reference warning suppression.

Source grounding:

- The affected `operaciones a plazos` labels explicitly distinguish
  `art. 11.4 LIS` rows on page 026b export casillas `02511`-`02513` and
  `02516`-`02518` from `DT 1a LIS` rows on page 026g export casillas
  `03321`-`03323` and `03326`-`03328`.
- The affected double-imposition row is labelled
  `Deducciones doble imposición internacional RDLeg. 4/2004 - DI internacional
  2008 - Pendiente aplic. en períodos futuros [00827]`.
- The registry source rows carry `source_refs = ["aeat-dr-200-2025",
  "aeat-modelo-200-manual-2024"]`; the audit records those labels and source
  references as identity evidence, not as a newly authored legal definition.

Roles now marked as source-grounded legal-reference singletons:

- `is_correccion_operaciones_a_plazos_art11_4_permanente_aumento`
- `is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_aumento`
- `is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_aumento`
- `is_correccion_operaciones_a_plazos_art11_4_permanente_disminucion`
- `is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_disminucion`
- `is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_disminucion`
- `is_correccion_operaciones_a_plazos_dt1_permanente_aumento`
- `is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_aumento`
- `is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_aumento`
- `is_correccion_operaciones_a_plazos_dt1_permanente_disminucion`
- `is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_disminucion`
- `is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_disminucion`
- `is_deduccion_di_internacional_rdleg_pendiente`

Execution of `W13.P34.S68` replaced the artificial legal-reference warning
tests with a direct boundary test.

Test contract:

- `art11_4` and `dt1` operaciones-a-plazos roles are not axis siblings.
- `rdleg` and current DI internacional pending roles are not axis siblings.
- The committed-registry singleton marker test covers the 13 newly reviewed
  Modelo 200 singleton roles.
- The corpus singleton warning-count gate remains clean.

Implementation consequence: the validator no longer treats legal-reference
markers as a generic typo-warning axis. Current legitimate legal-reference
singletons are recorded in source data with explicit reasons, and future
legal-reference normalization requires exact source-backed policy.

## Slice 37 - W14 warning-suppressor control census

Execution of `W14.P36.S70` inventoried the remaining semantic-role
typo-warning suppressors after the CCAA and legal-reference removals.

Current helper classes:

- `tax_domain_suffix`: final-token `irpf`/`is`/`iva` domain sibling guard.
- `correction_suffix`: Modelo 200 correction axes such as
  `permanente_aumento`, `temporaria_ejercicio_disminucion`, `saldo_inicial`,
  and `saldo_final`.
- `axis_token_group`: legacy one-token axis groups such as
  `clave`/`subclave`, `count`/`amount`, `interna`/`internacional`,
  `i`/`ii`/`iii`/`iv`, `detalle`/`otras`,
  `ascendiente`/`descendiente`, and `nacimiento`/`fallecimiento`.
- `optional_or_numeric_token_strip`: legacy stripping of `sin`, `agr`, `pub`,
  `coti`, `aav`, `b`, `anio`, `precio`, and all numeric tokens.
- `anexo_c_carryforward`: exact W08 allowlist for same-basket Anexo C state
  axes.
- `deferred_imputation_slot`: exact W08 allowlist for branch-local deferred
  imputation slots.
- `family_local_generated_pending`: exact W11 allowlist for C Valenciana
  autoconsumo, Murcia infraestructuras, and Madrid nuevos contribuyentes.

Execution of `W14.P36.S71` simulated disabling each helper against the current
Modelo 100 and Modelo 200 corpus. The base warning count remains zero, but
helper-specific exposure is not zero.

Disabling individual helpers would expose:

| helper disabled | added warnings | interpretation |
|---|---:|---|
| `correction_suffix` | 151 | Expected Modelo 200 correction-table warning noise; already source-audited and warning-only. |
| `axis_token_group` | 17 | Mixed legacy helper; needs token-group manual review before further hardening. |
| `optional_or_numeric_token_strip` | 36 | Highest-risk broad helper; should be burned down by exact family policies. |
| `tax_domain_suffix` | 0 | No independent current Modelo 100/200 exposure. |
| `numeric_same_length` | 0 | Its current exposure is covered by the broader optional/numeric stripper. |
| `anexo_c_carryforward` | 0 | No independent new exposure beyond the current exact allowlist. |
| `deferred_imputation_slot` | 0 | No independent new exposure beyond the current exact allowlist. |
| `family_local_generated_pending` | 0 | No independent new exposure because adjacent numeric stripping also suppresses the only current pair. |

Notable `axis_token_group` exposure:

- `irpf_anexo_c_exceso_sps_rg_aportaciones_periodo` vs
  `irpf_anexo_c_exceso_sps_rg_aportaciones_aplicado`
- `irpf_ric_canarias_inversion_tipo_ab` vs
  `irpf_ric_canarias_inversion_tipo_c`
- `irpf_declarante_fecha_nacimiento` vs
  `irpf_declarante_fecha_fallecimiento`
- `irpf_descendiente_fecha_nacimiento` vs
  `irpf_ascendiente_fecha_nacimiento`
- `is_liquidacion_i_importe` vs `is_liquidacion_iv_importe`
- `is_deduccion_di_interna_rdleg_pendiente` vs
  `is_deduccion_di_internacional_rdleg_pendiente`
- `is_correccion_otras_correcciones_resultado_permanente_disminucion` vs
  `is_correccion_detalle_correcciones_resultado_permanente_disminucion`

Notable `optional_or_numeric_token_strip` exposure:

- `irpf_deduccion_c_valenciana_ayudas_publicas_generalitat_2020` vs
  `irpf_deduccion_c_valenciana_ayudas_publicas_generalitat`
- `irpf_eo_reintegro_subvenciones` vs
  `irpf_eo_agr_reintegro_subvenciones`
- `irpf_ganancia_premios_juegos_valoracion_b` vs
  `irpf_ganancia_premios_juegos_valoracion`
- `irpf_ganancia_inmueble_catastral_4` vs
  `irpf_ganancia_inmueble_catastral_1_b`
- `irpf_deduccion_cantabria_generado_2025_pendiente` vs
  `irpf_deduccion_cantabria_generado_pendiente`
- `irpf_deduccion_c_valenciana_pendiente_2023_linea_4` vs
  `irpf_deduccion_c_valenciana_pendiente_linea_5`
- `irpf_deduccion_murcia_generado_2025_pendiente_2` vs
  `irpf_deduccion_murcia_generado_2024_pendiente`
- `irpf_anexo_b_aav_importe_satisfecho` vs
  `irpf_anexo_b_importe_satisfecho`
- `irpf_ganancia_fondos_coti_ganancia` vs
  `irpf_ganancia_fondos_ganancia`
- `is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento`
  vs
  `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento`

Execution of `W14.P37.S72` ran the fresh residual warning census:

- Modelo 100 and Modelo 200 declare 2,262 distinct semantic roles.
- 454 roles are currently unmarked singletons.
- 28 roles are currently marked `intentional_singleton`.
- The current emitted singleton typo-warning count is zero.

Candidate ranking for the next implementation wave:

1. `optional_or_numeric_token_strip` hardening. This is the broadest remaining
   suppressor with independent current exposure and it erases year, line,
   optional-branch, catastral-slot, and legal-regime words by generic token
   stripping. Next action: source lookup and exact-family replacement rules,
   not registry rewrites.
2. `axis_token_group` hardening. This mixed helper includes some obviously
   structured pairs, but also legal/context-sensitive axes such as
   internal/international DI, liquidacion roman numerals, and detail/other
   corrections. Next action: token-group-by-token-group manual source review.
3. Modelo 200 correction suffix extraction readiness. The guard is high-volume
   and already source-audited; it remains a good implementation target, but it
   is less urgent as a legal-risk reduction than burning down broad generic
   token stripping.
4. Cadastral-reference family-local review. Still blocked globally; exact
   families can be considered after the optional/numeric stripping work
   separates text slots from no-reference flags and line markers.

No source registry edit is authorized by this slice. It is a control census
that identifies the next legal-source lookup target.

## Slice 4 - Modelo 100 regional repeated-label surface

Modelo 100 2025 has repeated labels that are mostly singleton roles:

- `Importe generado en 2025`: 13 rows, 13 singleton roles.
- `Importe generado en 2025 pendiente de aplicación`: 15 rows, 14 singleton roles.
- `Importe generado en 2024 pendiente de aplicación`: 14 rows, 14 singleton roles.
- `Código del municipio:`: 6 rows, 6 singleton roles.

Examples:

- `irpf_deduccion_cantabria_generado_2025`
- `irpf_deduccion_galicia_generado_2025_pendiente`
- `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente`
- `irpf_deduccion_murcia_infraestructuras_2025_pendiente`
- `irpf_deduccion_la_rioja_generado_2025_pendiente`

The Renta 2025 autonomous deductions manual confirms that these labels sit
inside separate autonomous-community deduction families. The same caption does
not establish the same legal concept.

Finding: Modelo 100 should not be normalized across regions or deduction
families by repeated label alone. Only already-confirmed family-local axes
should be extracted.

## Slice 5 - Modelo 100 `c_valenciana_autoconsumo`

This is the best narrow Modelo 100 pilot because the official manual and
registry labels both expose the family boundaries.

Fields inspected:

- `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022`
- `irpf_deduccion_c_valenciana_autoconsumo_desde_2023`
- `irpf_deduccion_c_valenciana_autoconsumo_2025_generado`
- `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente`
- `irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente`

The manual explicitly distinguishes quantities invested up to 2022 from those
invested from 2023, and separately describes generated, applied, and pending
amounts with carryforward into the following three tax periods.

Finding: `hasta_2022` and `desde_2023` are legal/year-window concepts, not
cleanup noise. The generated/pending suffixes are candidate metadata inside
this already-confirmed family.

## Review conclusion

The next implementation work must proceed in two guarded tracks:

1. Modelo 200 correction-axis extraction, excluding the 23 mismatch records
   and preserving every legal/concept base slug.
2. Modelo 100 family-local carryforward-axis extraction, starting with
   `c_valenciana_autoconsumo`, with no cross-region merge by repeated label.

No source registry edit should proceed without a per-slice audit entry stating
the official source, the proposed role/base split, and the legal-policy
boundary for concepts that must not be normalized.

## Slice 6 - Optional/numeric burn-down first implementation

The 2026-05-22 optional/numeric sub-plan executed the first implementation
slice against the broad `optional_or_numeric_token_strip` helper.

Source-grounded decision:

- The local official AEAT Sociedades 2024 manual distinguishes `Libertad de
  amortización con mantenimiento de empleo` under `RDL 6/2010` from `Libertad
  de amortización sin mantenimiento de empleo` under `RDL 13/2010`, while both
  reference `DT 13a.2 LIS`.
- The committed Modelo 200 registry mirrors that split across casillas `02631`
  through `02650`.
- Therefore `sin` is a legally meaningful negation marker in this family, not
  an optional typo-warning token.

Implementation:

- Removed `sin` from the global optional semantic-role token list.
- Marked these 12 exposed correction rows as source-reviewed
  `intentional_singleton` roles: `02631`, `02632`, `02633`, `02636`, `02637`,
  `02638`, `02641`, `02642`, `02643`, `02646`, `02647`, and `02648`.
- Added regression coverage that unmarked `con`/`sin` maintenance roles are not
  axis siblings and should warn, while the committed reviewed rows remain
  warning-clean through explicit singleton metadata.

Blocked families retained for later exact source slices:

- `gp_fondos_coti` versus `gp_fondos`: official Modelo 100 2025 order creates
  a separate quoted-fund/SICAV-index section, so `coti` is not globally
  optional.
- Generated/pending year and line families: labels encode generated year,
  pending application, and sometimes line position inside CCAA-local deduction
  families.
- Cadastral slots, prize valuation second blocks, objective-estimation
  agricultural rows, Madrid parent/detail housing rows, and Anexo B `aav`
  branch rows remain source-visible structures, not generic cleanup tokens.

Verification:

- Focused semantic-role tests passed.
- Touched validator/test ruff check passed.
- Cross-revision singleton drift, Modelo 200 registry tests, committed-registry
  tests, and a direct Modelo 100/200 warning probe passed.

## Slice 7 - Quoted-fund `coti` optional-token burn-down

The 2026-05-22 `schema-hardening-coti` sub-plan executed the second
optional/numeric implementation slice.

Source-grounded decision:

- Local BOE corpus for the Modelo 100 2025 order records a new specific
  section for operations involving quoted funds and quoted index SICAVs.
- Local BOE corpus for the IRPF law distinguishes quoted investment funds and
  quoted index SICAVs in the relevant collective-investment and capital-gains
  context.
- The committed Modelo 100 2025 registry places casillas `2225` through `2236`
  under `gp_fondos_coti`, separate from the general `gp_fondos` rows.

Implementation:

- Removed `coti` from the global optional semantic-role token list.
- Marked the six currently exposed quoted-fund rows as source-reviewed
  `intentional_singleton` roles: `2227`, `2228`, `2229`, `2230`, `2231`, and
  `2234`.
- Added regression coverage that unmarked `coti` roles are not axis siblings
  and should warn, while the committed reviewed rows remain warning-clean
  through explicit singleton metadata.

Blocked rows and families:

- `2233` remains outside this slice because prior audit flagged a possible
  rename issue.
- `agr`, `aav`, `b`, `anio`, `precio`, and numeric stripping remain broad debt
  requiring family-local source review.

Verification:

- Focused semantic-role tests passed.
- Touched validator/test ruff check passed.
- Cross-revision singleton drift, Modelo 100 registry tests, committed-registry
  tests, and a direct Modelo 100/200 warning probe passed.
