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

# schema-hardening m100 identity-residual role assignment

## Scope

46 casilla IDs from the M100 identity-residual cluster. Sources:

- `datos_identificativos/declarante` — declarant identity fields
- `datos_identificativos/conyuge` — spouse identity fields
- `datos_identificativos/hijos` and `hijos/hijo` — descendant identity fields
- `datos_identificativos/ascendientes/ascendiente` — ascendant identity fields
- `datos_identificativos/declaracion` — declaration-level metadata
- `resultados/deduccion_autonomica_res/la_rioja_res` — La Rioja CCAA residuals
- `resultados/deduccion_autonomica_res/canarias_res` — Canarias CCAA residuals
- `resultados/deduccion_autonomica_res/aragon_res` — Aragón CCAA residuals
- `resultados/deduccion_autonomica_res/c_valenciana_res` — C. Valenciana CCAA residuals
- `resultados/deduccion_autonomica_res/castilla_la_mancha_res` — Castilla-La Mancha CCAA residuals
- `resultados/deduccion_autonomica_res/castilla_y_leon_res` — Castilla y León CCAA residuals
- `resultados/deduccion_autonomica_res/i_baleares_res` — Illes Balears CCAA residuals
- `resultados/deduccion_autonomica_res/extremadura_res` — Extremadura CCAA residuals
- `resultados/deduccion_autonomica_res/galicia_res` — Galicia CCAA residuals
- `resultados/deduccion_autonomica_res/cantabria_res` — Cantabria CCAA residuals
- `rendimientos_trabajo` / `resultados/rdto_trabajo_res` — work-income residuals
- `resultado_declaracion` — result-level residuals
- `resultados/calculo_impuesto_res/gravamenes_res` — tax calculation residuals
- `resultados/compensacion_conyuges_res` — spouse compensation residuals
- `resultados/anexo_a_res/deduccion_vivienda_habitual_res` — main residence deduction residuals
- `toma_datos_ampliada/anexo_a/vehiculos_elec_y_puntos_carga` — EV deduction ancillary data

Reuse check performed against 1334 existing roles in `_existing-roles.txt`. TOML samples read for casillas `DPNIF_D`, `SEXO_D`, `NIFDLG`, `DNIASDLG`, `0057`, `0414`.

## Role assignments

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| `ANOASDLG` | `irpf_ascendiente_fecha_nacimiento` | Ascendiente fecha de nacimiento | text | 2025 | NEW |
| `APENOMDLG` | `irpf_descendiente_apellidos_nombre` | Hijo o descendiente apellidos y nombre | text | 2025 | NEW |
| `APENOMDLG_ASC` | `irpf_ascendiente_apellidos_nombre` | Ascendiente apellidos y nombre | text | 2025 | NEW |
| `CONVASDLG` | `irpf_ascendiente_convivientes` | Ascendiente descendientes convivientes | integer | 2025 | NEW |
| `DECFAL` | `irpf_declarante_fecha_fallecimiento` | Primer declarante fecha de fallecimiento | text | 2025 | NEW |
| `DPFNAC_C` | `irpf_conyuge_fecha_nacimiento` | Conyuge fecha de nacimiento | text | 2025 | NEW |
| `DPFNAC_D` | `irpf_declarante_fecha_nacimiento` | Primer declarante fecha de nacimiento | text | 2025 | NEW |
| `DPGMIN_C` | `irpf_conyuge_grado_discapacidad` | Conyuge grado de discapacidad | text | 2025 | NEW; existing `irpf_conyuge_discapacidad_*` covers benefit details, not the raw grade code |
| `DPGMIN_D` | `irpf_declarante_grado_discapacidad` | Primer declarante grado de discapacidad | text | 2025 | NEW |
| `DP_APENOM_C` | `irpf_conyuge_apellidos_nombre` | Conyuge apellidos y nombre | text | 2025 | NEW |
| `DP_APENOM_D` | `irpf_declarante_apellidos_nombre` | Primer declarante apellidos y nombre | text | 2025 | NEW |
| `ECIVIL` | `irpf_declarante_estado_civil` | Primer declarante estado civil a 31/12 | text | 2025 | NEW |
| `FALLASDLG` | `irpf_ascendiente_fecha_fallecimiento` | Ascendiente fecha de fallecimiento | text | 2025 | NEW |
| `FALLDLG` | `irpf_descendiente_fecha_fallecimiento` | Hijo o descendiente fecha de fallecimiento | text | 2025 | NEW |
| `FNACDLG` | `irpf_descendiente_fecha_nacimiento` | Hijo o descendiente fecha de nacimiento | text | 2025 | NEW |
| `HIJOSUE` | `irpf_hijos_residentes_ue_eee_flag` | Hijos o descendientes UE o EEE | boolean | 2025 | NEW |
| `MINUSDLG` | `irpf_descendiente_clave_discapacidad` | Hijo o descendiente clave discapacidad | text | 2025 | NEW; distinct from `irpf_deduccion_descendiente_discapacidad` which is the monetary deduction |
| `NORESIDENTE` | `irpf_conyuge_no_residente_flag` | Conyuge no residente y no contribuyente IRPF | boolean | 2025 | NEW |
| `PCTMINASDLG` | `irpf_ascendiente_clave_discapacidad` | Ascendiente clave discapacidad | text | 2025 | NEW |
| `PH18` | `irpf_hijos_menores_unidad_familiar_flag` | Hijos menores en unidad familiar | boolean | 2025 | NEW |
| `RESIDENTEUE` | `irpf_conyuge_residente_ue_eee_flag` | Conyuge residente UE o EEE | boolean | 2025 | NEW |
| `SEXO_C` | `irpf_conyuge_sexo` | Conyuge sexo | text | 2025 | NEW |
| `SEXO_D` | `irpf_declarante_sexo` | Primer declarante sexo | text | 2025 | NEW; TOML 0005-sexo-d.toml has no semantic_role yet |
| `TIPOTRIBUTACION` | `irpf_declaracion_tipo_tributacion` | Opcion de tributacion elegida | text | 2025 | NEW |
| `ZCCAD` | `irpf_declaracion_ccaa` | Comunidad autonoma de la declaracion | text | 2025 | NEW |
| `ZRUE2` | `irpf_conyuge_pais_residencia_ue_eee` | Conyuge pais de residencia UE o EEE | text | 2025 | NEW |
| `0057` | `irpf_rendimiento_trabajo_copa_america_reduccion` | Reduccion rendimientos régimen fiscal Copa America | money(default) | 2023, 2024, 2025 | NEW; event-specific work-income reduction under Copa América Barcelona tax regime |
| `0210` | `irpf_deduccion_castilla_la_mancha_guarderia` | Por gastos de guardería (CLM) | text | 2021, 2022, 2023 | REUSED (existing role line 454). DATA_TYPE DIVERGENCE: existing role uses money(default) in other casillas; this instance is text (eligibility flag/code). See divergences section. |
| `0414` | `irpf_deduccion_obtencion_rendimientos_trabajo` | Deduccion por obtencion de rendimientos del trabajo | money(default) | 2025 | NEW |
| `0504` | `irpf_incremento_cuota_autonomica_perdida_nacimiento` | Incremento cuota líquida autonomica pérdida deducción nacimiento | money(default) | 2023, 2024, 2025 | NEW |
| `0697` | `irpf_compensacion_conyuges_swift_flag` | Compensación entre cónyuges: SWIFT | text | 2020 | REUSED (existing role line 180). The existing role is typed boolean in other revisions; text encoding used in 2020 form. See divergences section. |
| `0700` | `irpf_anexo_a_deduccion_vivienda_estatal` | Parte estatal: Importe de la deducción | money(default) | 2020 | REUSED (existing role line 24) |
| `0808` | `irpf_deduccion_c_valenciana_generado_pendiente_aplicacion` | Importe aplicado en el ejercicio (C. Valenciana) | money(default) | 2022 | REUSED (existing role line 352) |
| `0819` | `irpf_deduccion_cantabria_arrendamiento_municipios_riesgo` | Por contratos arrendamiento viviendas Cantabria riesgo despoblación | money(default) | 2020, 2021 | REUSED (existing role line 410) |
| `0846` | `irpf_deduccion_canarias_palma_desarraigo` | Por desarraigo por la erupción volcánica en La Palma | money(default) | 2021, 2022 | NEW |
| `0847` | `irpf_deduccion_canarias_palma_cesion_inmueble` | Por la cesión de uso temporal y gratuita de inmuebles La Palma | money(default) | 2021, 2022 | NEW |
| `0848` | `irpf_deduccion_canarias_palma_gastos_enfermedad` | Por gastos de enfermedad para residentes en La Palma | money(default) | 2021, 2022 | NEW |
| `0981` | `irpf_deduccion_castilla_y_leon_importe_pendiente_aplicacion` | Importe generado pendiente de aplicación (CyL rolling carry-forward) | money(default) | 2020, 2021, 2022, 2023 | NEW; rolling-year label changes each revision (2017→2020 generated), same semantic |
| `0982` | `irpf_deduccion_castilla_y_leon_importe_pendiente_aplicacion` | Importe generado pendiente de aplicación (CyL rolling carry-forward) | money(default) | 2020, 2021, 2022, 2023, 2024 | NEW; same role as 0981 — adjacent slot in carry-forward schedule |
| `0991` | `irpf_deduccion_castilla_y_leon_nacimiento_adopcion` | Por paternidad (CyL) | money(default) | 2020 | REUSED (existing role line 478); paternidad is a nacimiento/adopcion deduction variant |
| `0997` | `irpf_deduccion_castilla_y_leon_importe_pendiente_aplicacion` | Importe generado pendiente de aplicación (CyL rolling carry-forward) | money(default) | 2020, 2021, 2022 | NEW; same role family as 0981/0982 |
| `0998` | `irpf_deduccion_castilla_y_leon_importe_pendiente_aplicacion` | Importe generado pendiente de aplicación (CyL rolling carry-forward) | money(default) | 2020, 2021, 2022, 2023 | NEW; same role family as 0981/0982 |
| `0999` | `irpf_deduccion_castilla_y_leon_importe_pendiente_aplicacion` | Importe generado pendiente de aplicación (CyL rolling carry-forward) | money(default) | 2020, 2021, 2022, 2023, 2024 | NEW; same role family as 0981/0982 |
| `1020` | `irpf_deduccion_extremadura_otras` | Otras deducciones (Extremadura) | money(default) | 2024 | NEW |
| `1038` | `irpf_deduccion_galicia_otras` | Otras deducciones (Galicia) | money(default) | 2023, 2024 | NEW |
| `1070` | `irpf_deduccion_la_rioja_municipio_codigo` | Código del municipio (La Rioja) | text | 2020 | NEW; generic La Rioja municipality code not covered by arrendamiento- or guarderia-specific existing roles |
| `1077` | `irpf_deduccion_la_rioja_vehiculos_electricos` | Por adquisición de vehículos eléctricos nuevos | money(default) | 2020, 2021, 2022, 2023 | REUSED (existing role line 618) |
| `1082` | `irpf_deduccion_la_rioja_otras` | Otras deducciones (La Rioja) | money(default) | 2020, 2024 | NEW |
| `1096` | `irpf_deduccion_c_valenciana_rentas_arrendamiento` | Por obtención de rentas arrendamiento vivienda (C. Valenciana) | text | 2020, 2021 | REUSED (existing role line 365). DATA_TYPE DIVERGENCE: text here vs money(default) in other casillas sharing same role. See divergences section. |
| `1171` | `irpf_deduccion_c_valenciana_ayudas_publicas_generalitat` | Por cantidades ayudas públicas Generalitat Valenciana | money(default) | 2020 | REUSED (existing role line 325) |
| `1851` | `irpf_deduccion_aragon_ayuda_humanitaria_ucrania` | Por ayudas humanitarias al pueblo ucraniano | money(default) | 2022, 2023, 2024 | NEW |
| `1852` | `irpf_deduccion_aragon_acogimiento_ucrania` | Por acogimiento de personas o familias ucranianas desplazadas | money(default) | 2022, 2023, 2024 | NEW |
| `1905` | `irpf_deduccion_baleares_prestamo_hipotecario_incremento` | Para compensar incremento coste préstamos hipotecarios tipo variable | money(default) | 2022, 2023, 2024 | NEW |
| `1907` | `irpf_deduccion_castilla_la_mancha_compensacion_inflacion` | Para compensar los efectos de la inflación (CLM) | money(default) | 2022 | NEW |
| `1916` | `irpf_deduccion_vehiculo_electrico_categoria` | Categoría vehículo eléctrico (datos_ampliada EV deduction) | text | 2023, 2024, 2025 | NEW; ancillary category code field for the EV purchase deduction annexe; distinct from `irpf_deduccion_vehiculo_tipo` (money/amount context) |

## Id-reuse hazards

### `0981` / `0982` / `0997` / `0998` / `0999` — Castilla y León rolling carry-forward

These five numeric IDs share the label pattern "Importe generado en {year} pendiente de aplicación" but the referenced year shifts by one each revision, producing entirely different year-specific meanings across the 2020–2024 range. The assigned role `irpf_deduccion_castilla_y_leon_importe_pendiente_aplicacion` is intentionally generic (carry-forward slot, not year-pinned), matching the economic invariant rather than the rolling label. The registry must record `revisions_present` ranges per ID to track which generation slot each revision uses.

### `1082` — La Rioja otras deducciones (2020, 2024 gap)

The label "Otras deducciones" is stable but the `revs` list shows 2020 and 2024 with no intermediate years recorded. If the 2021–2023 period used a different casilla ID or the deduction was suspended, this ID may represent two distinct incarnations. Single role assignment is appropriate if the underlying deduction category is continuous; flag for registry-level verification.

### `0057` — Copa América label truncation

The JSON holds two label variants, one with a trailing `\"` escape artefact. Both refer to the same Copa América XXXVII Barcelona event. No cross-revision id-reuse; single role assignment is correct.

## Data_type divergences

### `0210` — `irpf_deduccion_castilla_la_mancha_guarderia`: text vs money(default)

This cluster instance of casilla `0210` carries `data_type = text` (an eligibility/code field in the guardería deduction for Castilla-La Mancha). Other casillas assigned the same role `irpf_deduccion_castilla_la_mancha_guarderia` in the existing role taxonomy use `money(default)`. The text instance likely represents an eligibility indicator or guardian-code companion field rather than the monetary amount. The registry should split this into a dedicated role such as `irpf_deduccion_castilla_la_mancha_guarderia_codigo` to maintain strict data_type consistency within a role. Pending schema team decision; current assignment uses the closest existing role.

### `0697` — `irpf_compensacion_conyuges_swift_flag`: text vs implied boolean

The existing role `irpf_compensacion_conyuges_swift_flag` (line 180) implies a boolean flag by name convention. The 2020 form encodes this as `data_type = text`. If other revisions encode it as boolean, this constitutes a type drift. Verify against 2021+ TOML files for `compensacion_conyuges_res`. No new role created; flag for constraint enforcement.

### `1096` — `irpf_deduccion_c_valenciana_rentas_arrendamiento`: text vs money(default)

Casilla `1096` (2020, 2021) carries `data_type = text` under the C. Valenciana rental income deduction. The role `irpf_deduccion_c_valenciana_rentas_arrendamiento` (line 365) is expected to be a monetary amount. The 2020–2021 text instance may be an eligibility qualifier or NIF/code field preceding the monetary entry. Recommend splitting to `irpf_deduccion_c_valenciana_rentas_arrendamiento_flag` for the text variant. Pending schema team decision; current assignment uses the closest existing role.
