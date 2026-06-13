---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-enrollment-campaign-queue-audit]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# `schema-hardening` audit: M100 section inventory and first cluster role assignment

## Scope

2025 revision of M100 IRPF: 2,235 casillas total, 2,069 unroled (166
already roled). This audit covers Phase 1 (section family inventory
across the 2025 revision) and Phase 2 (per-id role assignment for the
`retenciones_pagos_fraccionados` cluster, the smallest unroled family
at 15 casillas). All role proposals carry through all 6 revisions
(2020–2025) where each id appears.

Total across all 6 revisions: 11,302 casilla-revision pairs; 2,254
unique casilla ids.

---

## Phase 1 — section family inventory (2025 revision)

| section_family | casilla_count | unroled_count | example_label_substring |
|---|---:|---:|---|
| datos_identificativos | 30 | 26 | Primer declarante NIF |
| rendimientos_trabajo | 25 | 25 | Retribuciones dinerarias. Importe integro |
| rendimientos_capital_mobiliario.base_ahorro | 15 | 15 | Intereses de cuentas, depositos y activos financieros |
| rendimientos_capital_mobiliario.base_general | 11 | 11 | Arrendamiento de bienes muebles, negocios o minas |
| rendimientos_capital_inmobiliario | 26 | 26 | Renta inmobiliaria imputada |
| rendimientos_actividades_economicas.estimacion_directa | 55 | 55 | Ingresos de explotacion |
| rendimientos_actividades_economicas (summary stubs) | 4 | 4 | Rendimiento neto de actividades economicas |
| retenciones_pagos_fraccionados | 15 | 15 | Por rendimientos del trabajo |
| resultado_declaracion | 27 | 27 | Cuota liquida estatal incrementada |
| resultados.base_imponible_liquidable | 47 | 46 | Aportaciones del ejercicio 2025 |
| resultados.calculo_impuesto_res | 110 | 95 | NIF del conyuge |
| resultados.compensacion_conyuges_res | 12 | 10 | Importe del resultado a ingresar |
| resultados.minimo_per_fam_res | 14 | 14 | Minimo del contribuyente. Importe |
| resultados.integracion_ganancias | 55 | 55 | Suma de bases imponibles imputadas |
| resultados.irpf_ccaa_res | 3 | 3 | Cuota liquida autonomica incrementada |
| resultados.regularizacion_res | 3 | 3 | Resultado a ingresar tramitacion complementaria |
| resultados.ingreso_devolucion_res | 1 | 0 | Resultado a ingresar o a devolver |
| resultados.datos_adicionales_res | 33 | 18 | Hijo/Hija 1 NIF/NIE |
| resultados.datos_adicionales_anexo_b | 230 | 166 | NIF del arrendador 1 |
| resultados.anexo_a_res | 173 | 163 | Fecha de inicio de las obras |
| resultados.anexo_c_res | 179 | 177 | Contribuyente titular |
| resultados.deduccion_autonomica_res.andalucia_res | 21 | 21 | Para familia numerosa |
| resultados.deduccion_autonomica_res.aragon_res | 19 | 19 | Por nacimiento o adopcion del tercer hijo |
| resultados.deduccion_autonomica_res.asturias_res | 36 | 36 | Traslado domicilio fiscal al Principado |
| resultados.deduccion_autonomica_res.c_valenciana_res | 67 | 63 | Por contratar de manera indefinida |
| resultados.deduccion_autonomica_res.canarias_res | 43 | 33 | Por donaciones con finalidad ecologica |
| resultados.deduccion_autonomica_res.cantabria_res | 32 | 31 | Por gastos de guarderia |
| resultados.deduccion_autonomica_res.castilla_la_mancha_res | 29 | 28 | Por residencia habitual en zonas rurales |
| resultados.deduccion_autonomica_res.castilla_y_leon_res | 26 | 23 | Importe de la deduccion |
| resultados.deduccion_autonomica_res.catalunya_res | 16 | 16 | Por obligacion de presentar la declaracion del IRPF |
| resultados.deduccion_autonomica_res.extremadura_res | 19 | 19 | Por adquisicion o rehabilitacion vivienda habitual jovenes |
| resultados.deduccion_autonomica_res.galicia_res | 32 | 32 | Por adquisicion y rehabilitacion de viviendas |
| resultados.deduccion_autonomica_res.i_baleares_res | 29 | 26 | Por gastos derivados de la esclerosis lateral amiotrofica |
| resultados.deduccion_autonomica_res.la_rioja_res | 39 | 37 | Por donaciones para promocion y estimulo de actividades |
| resultados.deduccion_autonomica_res.madrid_res | 33 | 33 | Por nacimiento o adopcion de hijos |
| resultados.deduccion_autonomica_res.murcia_res | 41 | 41 | Por donaciones de bienes inscritos en el Inventario |
| toma_datos_ampliada.inmuebles | 128 | 119 | Propiedad (%) |
| toma_datos_ampliada.ganancias_patrimoniales | 234 | 231 | Ganancias derivadas de transmisiones |
| toma_datos_ampliada.regimenes_especiales | 203 | 199 | Produccion de mejillon en batea: Ingresos integros |
| toma_datos_ampliada.red_base_imponible | 25 | 21 | Si no tiene NIF, marque con una X |
| toma_datos_ampliada.anexo_a | 49 | 41 | Situacion. Clave |
| toma_datos_ampliada.otros | 46 | 46 | Contribuyente que obtiene los rendimientos |

**Totals: 2,235 casillas, 2,069 unroled (166 already roled in datos_identificativos
and prior NIF/monetary stubs)**

---

## Recommended audit dispatch plan

| section_family | estimated_count | recommended_scope | cross-modelo_notes |
|---|---:|---|---|
| rendimientos_trabajo | 25 | Single agent | Overlap with M111 (retenciones trabajo); reuse `retenciones_ingresos_a_cuenta` where applicable |
| rendimientos_capital_mobiliario.base_ahorro | 15 | Single agent | New `irpf_*` rendimiento roles; no cross-modelo overlap today |
| rendimientos_capital_mobiliario.base_general | 11 | Single agent (combine with base_ahorro) | — |
| rendimientos_capital_inmobiliario | 26 | Single agent | Retenciones overlap with M115 / M180 |
| rendimientos_actividades_economicas.estimacion_directa | 59 | Single agent | Overlap M130 / M131 pagos fraccionados |
| retenciones_pagos_fraccionados | 15 | **Done in Phase 2 below** | Reuses `retenciones_ingresos_a_cuenta` / `pago_fraccionado` from taxonomy |
| resultado_declaracion | 27 | Single agent | deducciones maternidad/familia/discapacidad; some roles may overlap M100 CCAA |
| resultados.base_imponible_liquidable | 47 | Single agent | `base_imponible_irpf` role already exists; extensions needed |
| resultados.calculo_impuesto_res | 110 | Single agent (dense, but linear) | cuota/minimos/NIF slots; NIFs already roled |
| resultados.minimo_per_fam_res | 14 | Single agent (combine with calculo) | — |
| resultados.integracion_ganancias | 55 | Single agent | ganancias/perdidas patrimoniales aggregate rows |
| resultados.datos_adicionales_res | 33 | Single agent | NIF slots already roled; remaining are amounts |
| resultados.datos_adicionales_anexo_b | 230 | Single agent | NIF slots (landlord, assignor) mostly roled; remaining = amounts + flags |
| resultados.compensacion_conyuges_res | 12 | Single agent | IBAN slots already roled; remaining = amounts |
| resultados.regularizacion_res | 3 | Combine with compensacion | — |
| resultados.irpf_ccaa_res | 3 | Combine with calculo | — |
| resultados.anexo_a_res | 173 | Subdivide: obras/mejoras energy (producer NIF already roled) + amounts | Overlap with `service_provider_nif`, `producer_nif` already roled |
| resultados.anexo_c_res | 179 | Single agent (contributor/property triplets) | Overlap with NIF roles already roled |
| resultados.deduccion_autonomica_res (15 CCAA) | 482 total | One agent per CCAA sub-tree | Each CCAA legally distinct; share structural triplet pattern (amount + cap + flag) |
| toma_datos_ampliada.inmuebles | 128 | Single agent | catastral/situacion/propiedad triplets; new `irpf_inmueble_*` roles |
| toma_datos_ampliada.ganancias_patrimoniales | 234 | Subdivide: acciones / derechos / fondos / inmuebles / criptomonedas / premios | NIF slots (investment_entity_nif) partially roled |
| toma_datos_ampliada.regimenes_especiales | 203 | Subdivide: estimacion_obj / estimacion_obj_agricola / regimenes_especiales | agricola has 74 casillas (crop-type rows); estimacion_obj has 39 |
| toma_datos_ampliada.red_base_imponible | 25 | Single agent | pension plan / aportaciones / NIF already partially roled |
| toma_datos_ampliada.anexo_a | 49 | Single agent | Situacion/clave triplets for inversiones empresariales |
| toma_datos_ampliada.otros | 46 | Single agent | Residual header / contributor attribution rows |

---

## Phase 2 — per-id role assignment: `retenciones_pagos_fraccionados` cluster

**Rationale for selection:** Smallest fully-unroled section family (15 casillas in
2025). All 15 ids are present across all 6 revisions. The concepts map directly to
existing canonical roles (`retenciones_ingresos_a_cuenta`, `pago_fraccionado`) or to
new narrowly-scoped IRPF line-item roles. The single semantic hazard (casilla 0598) is
clearly bounded and flagged below.

| id | section (2025) | proposed_role | label_snippet | data_type | revisions_present |
|---|---|---|---|---|---|
| 0592 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_retencion_atribuida_capital_mobiliario` | Por atribucion de retenciones de rendimientos del capital mobiliario | (empty — decimal implied) | 2020–2025 |
| 0593 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_retencion_atribuida_capital_inmobiliario` | Por atribucion de retenciones de rendimientos del capital inmobiliario | (empty — decimal implied) | 2020–2025 |
| 0594 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_retencion_atribuida_actividades_economicas` | Por atribucion de retenciones de rendimientos de actividades economicas | (empty — decimal implied) | 2020–2025 |
| 0596 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_retencion_trabajo` | Por rendimientos del trabajo | (empty — decimal implied) | 2020–2025 |
| 0597 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_retencion_capital_mobiliario` | Por rendimientos del capital mobiliario | (empty — decimal implied) | 2020–2025 |
| **0598** | retenciones_ingresos_cuenta_pagos_fraccionados (2025) / resultados.inmuebles_res (2020–2024) | **HAZARD — see below** | 2025: Por arrendamientos de inmuebles urbanos / 2020–2024: Suma de retenciones e ingresos a cuenta (capital inmobiliario aggregate) | 2025: (none/computed); 2020–2024: decimal | 2020–2025 |
| 0599 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_retencion_actividades_economicas` | Por rendimientos de actividades economicas | (empty — decimal implied) | 2020–2025 |
| 0600 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_retencion_atribuida_ganancias_patrimoniales` | Por atribucion de retenciones de ganancias y perdidas patrimoniales | (empty — decimal implied) | 2020–2025 |
| 0601 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_retencion_imputada_aie_ute` | Imputados por agrupaciones de interes economico y UTEs | (empty — decimal implied) | 2020–2025 |
| 0602 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_ingreso_cuenta_art_92_8` | Ingresos a cuenta del articulo 92.8 de la Ley del Impuesto | (empty — decimal implied) | 2020–2025 |
| 0603 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_retencion_ganancias_patrimoniales_premios` | Por ganancias patrimoniales, incluidos premios | (empty — decimal implied) | 2020–2025 |
| 0604 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_pago_fraccionado_actividades_economicas` | Pagos fraccionados ingresados por actividades economicas | (empty — computed) | 2020–2025 |
| 0605 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_cuota_irnr_imputada` | Cuotas del Impuesto sobre la Renta de no Residentes | (empty — decimal implied) | 2020–2025 |
| 0606 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_retencion_directiva_ahorro_2003_48` | Retenciones art. 11 de la Directiva 2003/48/CE devengadas antes de 2019 | (empty — decimal implied) | 2020–2025 |
| 0609 | retenciones_ingresos_cuenta_pagos_fraccionados | `irpf_total_pagos_cuenta` | Total pagos a cuenta | (empty — computed) | 2020–2025 |

**Note on data_type:** The 2025 files for casillas 0592–0607, 0609 do not declare
`data_type` explicitly (field absent). The 2020–2024 files for 0598 declare
`data_type = "decimal"`. The bulk-apply pass must confirm the inferred type before
writing roles; the cross-revision validator will catch mismatches at registry load.

**Note on canonical role reuse:** Casillas 0592–0606 are IRPF-specific line items on
the pagos a cuenta section. The existing `retenciones_ingresos_a_cuenta` role covers the
cross-modelo aggregate (M111/M115/M123/M180); these M100 casillas are per-source-type
breakdowns, not the same aggregate. New `irpf_retencion_*` roles are therefore correct
rather than overloading the cross-modelo role. Casilla 0604 (`pagos fraccionados por
actividades economicas`) could potentially share `pago_fraccionado` from the existing
taxonomy, but it is an M100-specific computed aggregate combining M130/M131 declarations
rather than the pago fraccionado amount itself — a distinct `irpf_pago_fraccionado_*`
role avoids false-positive intra-role consistency failures.

---

## New roles introduced in Phase 2

These role names are not present in the canonical taxonomy reference as of 2026-05-19:

- `irpf_retencion_atribuida_capital_mobiliario` — M100 0592; atribucion from transparencia fiscal / regimenes especiales for capital mobiliario source
- `irpf_retencion_atribuida_capital_inmobiliario` — M100 0593; same pattern, capital inmobiliario source
- `irpf_retencion_atribuida_actividades_economicas` — M100 0594; same pattern, actividades economicas source
- `irpf_retencion_trabajo` — M100 0596; direct withholding on trabajo income
- `irpf_retencion_capital_mobiliario` — M100 0597; direct withholding on capital mobiliario income
- `irpf_retencion_actividades_economicas` — M100 0599; direct withholding on actividades economicas income
- `irpf_retencion_atribuida_ganancias_patrimoniales` — M100 0600; atribucion from regimenes especiales for ganancias patrimoniales
- `irpf_retencion_imputada_aie_ute` — M100 0601; withholding imputada via AIE/UTE transparencia
- `irpf_ingreso_cuenta_art_92_8` — M100 0602; ingresos a cuenta under art. 92.8 LIRPF (specific statutory reference warrants own role)
- `irpf_retencion_ganancias_patrimoniales_premios` — M100 0603; direct withholding on ganancias patrimoniales including prizes
- `irpf_pago_fraccionado_actividades_economicas` — M100 0604; pagos fraccionados ingresados for economic activities (M130/M131 aggregate)
- `irpf_cuota_irnr_imputada` — M100 0605; IRNR cuotas credited against IRPF liability
- `irpf_retencion_directiva_ahorro_2003_48` — M100 0606; legacy Directive 2003/48/CE retenciones pre-2019 (historical artifact; single-occurrence warning expected)
- `irpf_total_pagos_cuenta` — M100 0609; total pagos a cuenta aggregate

**14 new roles total.**

---

## Cross-revision id-reuse hazards

### Critical: 0598 — section and semantic change in 2025

| revision | section | label | data_type |
|---|---|---|---|
| 2020–2024 | `resultados.inmuebles_res` | Suma de retenciones e ingresos a cuenta (suma de las casillas [0153]) | `decimal` |
| 2025 | `retenciones_ingresos_cuenta_pagos_fraccionados` | Por arrendamientos de inmuebles urbanos | (absent; computed) |

The 2020–2024 meaning is an aggregate sum of capital inmobiliario withholding
(a `resultados` computed total). The 2025 meaning is a line-item retención for
urban property rentals in the reorganised retenciones section. These are semantically
related but structurally distinct: aggregate-of-sums vs. source-type line item.
Resolution path: rename one generation following the M100/0700 legacy pattern —
`0598` in 2020–2024 takes a `-legacy` suffix role or the roles differ per revision.
The bulk-apply pass must assign different roles per revision range for 0598.

### Structural-only section drift (not semantic hazards)

Casillas 0592–0597, 0599–0606, 0609 all moved from
`resultados.calculo_impuesto_res.retenciones_res` (2020–2024) to
`retenciones_ingresos_cuenta_pagos_fraccionados` (2025) as part of the 2025 form
restructure. Label content is substantively identical (minor accent/punctuation
normalisation only). The cross-revision drift validator keys on `semantic_role`,
not `section`; these section-path changes do not block a common role assignment
across all 6 revisions.

---

## Acceptance notes

- Phase 2 role assignments cover 14 casilla ids (excluding 0598 pending hazard
  resolution); all 14 are present in all 6 revisions.
- 0598 requires a follow-up decision before bulk-apply: either a per-revision
  role assignment (distinct roles for 2020–2024 vs. 2025) or a legacy rename.
- The 14 new roles should be appended to the canonical taxonomy reference doc
  after the bulk-apply commit lands.
- The `irpf_retencion_directiva_ahorro_2003_48` role (0606) is a genuine
  single-occurrence role (pre-2019 EU Savings Directive withholding — directive
  repealed); typo-twin warning is expected and documented here.
