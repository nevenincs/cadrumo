---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# `schema-hardening` audit: M100 rendimientos clusters role classification

## Scope

Three `toma_datos_ampliada` rendimientos clusters in M100 IRPF, 77 casillas
total across 6 revisions (2020–2025). All cross-revision checks performed
against every revision. Section paths changed in 2025 (AEAT form restructure);
semantic content is consistent across all revisions within each cluster unless
noted as a hazard.

**Data-type note (corpus-wide):** Casillas in 2020–2024 declare
`data_type = "decimal"` explicitly on monetary fields. The 2025 files leave
`data_type` absent (same pattern as the retenciones cluster documented in
Phase 2). This is a uniform inferred-decimal pattern, not a decimal/money
divergence. No money/decimal split was found in any of the three clusters.

---

## Cluster A — rendimientos del trabajo (25 casillas)

Section path 2020–2024: `["toma_datos_ampliada", "rdto_trabajo"]` (ids 0003–0017, 0024)
and `["resultados", "rdto_trabajo_res"]` (ids 0018–0023, 0025).
Section path 2025: `["rendimientos_trabajo"]` for all 25 ids.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0003 | rendimientos_trabajo | `irpf_rendimiento_trabajo_importe_integro_dinerario` | Retribuciones dinerarias. Importe integro | decimal (absent 2025) | 2020–2025 | Input; dinerarias component of importe integro |
| 0004 | rendimientos_trabajo | `irpf_rendimiento_trabajo_especie_valoracion` | Rendimientos del trabajo en especie. Valoracion | decimal (absent 2025) | 2020–2025 | Input; in-kind remuneration valuation |
| 0005 | rendimientos_trabajo | `irpf_rendimiento_trabajo_especie_ingreso_cuenta` | Rendimientos del trabajo en especie. Ingresos a cuenta | decimal (absent 2025) | 2020–2025 | Input; ingresos a cuenta on in-kind benefit |
| 0006 | rendimientos_trabajo | `irpf_rendimiento_trabajo_especie_ingreso_cuenta_repercutido` | Rendimientos del trabajo en especie. Ingresos a cuenta repercutidos | decimal (absent 2025) | 2020–2025 | Input; repercuted ingresos a cuenta on in-kind benefit |
| 0007 | rendimientos_trabajo | `irpf_rendimiento_trabajo_especie_importe_integro` | Rendimientos del trabajo en especie. Importe integro | decimal (absent 2025) | 2020–2025 | Computed; especie gross total (0004+0005) |
| 0008 | rendimientos_trabajo | `irpf_rendimiento_trabajo_contribucion_empresarial_prevision` | Contribuciones empresariales a planes de pensiones y prevision social | decimal (absent 2025) | 2020–2025 | Input; employer pension/prevision contributions (LIRPF art.17) |
| 0009 | rendimientos_trabajo | `irpf_rendimiento_trabajo_contribucion_empresarial_seguro_dependencia` | Contribuciones empresariales a seguros colectivos de dependencia | decimal (absent 2025) | 2020–2025 | Input; employer dependency insurance contributions |
| 0010 | rendimientos_trabajo | `irpf_rendimiento_trabajo_aportacion_patrimonio_protegido` | Aportaciones al patrimonio protegido de personas discapacitadas | decimal (absent 2025) | 2020–2025 | Input; contributions to protected patrimony of disabled persons |
| 0011 | rendimientos_trabajo | `irpf_rendimiento_trabajo_reduccion` | Reducciones de rendimientos del trabajo | decimal (absent 2025) | 2020–2025 | Input; irregulares/plurianual reductions (LIRPF art.18) |
| 0012 | rendimientos_trabajo | `irpf_rendimiento_trabajo_total_ingresos_integros` | Total ingresos integros computables del trabajo | decimal (absent 2025) | 2020–2025 | Computed aggregate of all trabajo income sources |
| 0013 | rendimientos_trabajo | `irpf_rendimiento_trabajo_gasto_ss_mutualidad` | Cotizaciones a la Seguridad Social o mutualidades obligatorias | decimal (absent 2025) | 2020–2025 | Input; SS/mutualidad cotizaciones (LIRPF art.19) |
| 0014 | rendimientos_trabajo | `irpf_rendimiento_trabajo_gasto_sindicato` | Cuotas satisfechas a sindicatos | decimal (absent 2025) | 2020–2025 | Input; union dues (LIRPF art.19) |
| 0015 | rendimientos_trabajo | `irpf_rendimiento_trabajo_gasto_colegio_profesional` | Cuotas satisfechas a colegios profesionales | decimal (absent 2025) | 2020–2025 | Input; professional association dues (LIRPF art.19) |
| 0016 | rendimientos_trabajo | `irpf_rendimiento_trabajo_gasto_defensa_juridica` | Gastos de defensa juridica derivados de litigios con el empleador | decimal (absent 2025) | 2020–2025 | Input; legal defence costs against employer (LIRPF art.19) |
| 0017 | rendimientos_trabajo | `irpf_rendimiento_trabajo_rendimiento_neto_previo` | Rendimiento neto previo del trabajo | decimal (absent 2025) | 2020–2025 | Computed; neto before gastos generales reduction |
| 0018 | rendimientos_trabajo | `irpf_rendimiento_trabajo_suma_rendimientos_netos_previos` | Suma de rendimientos netos previos del trabajo | decimal (absent 2025) | 2020–2025 | Computed aggregate; section changed 2025 (resultados→rendimientos_trabajo); semantic unchanged |
| 0019 | rendimientos_trabajo | `irpf_rendimiento_trabajo_gasto_otros` | Otros gastos deducibles del trabajo | decimal (absent 2025) | 2020–2025 | Input; art.19 otros gastos; section changed 2025; semantic unchanged |
| 0020 | rendimientos_trabajo | `irpf_rendimiento_trabajo_incremento_traslado_residencia` | Incremento para contribuyentes desempleados que acepten traslado | decimal (absent 2025) | 2020–2025 | Input; art.19 increment for relocated unemployed; section changed 2025 |
| 0021 | rendimientos_trabajo | `irpf_rendimiento_trabajo_incremento_discapacitado_activo` | Incremento para trabajadores activos con discapacidad | decimal (absent 2025) | 2020–2025 | Input; art.19 increment for active disabled workers; section changed 2025 |
| 0022 | rendimientos_trabajo | `irpf_rendimiento_trabajo_rendimiento_neto` | Rendimiento neto del trabajo | decimal (absent 2025) | 2020–2025 | Computed; section changed 2025; semantic unchanged |
| 0023 | rendimientos_trabajo | `irpf_rendimiento_trabajo_reduccion_gastos_generales` | Cuantia aplicable con caracter general | decimal (absent 2025) | 2020–2025 | Input; art.20 reduccion general del trabajo; section changed 2025 |
| 0024 | rendimientos_trabajo | `irpf_rendimiento_trabajo_aportacion_empresa_decision_trabajador` | Cantidades aportadas por la empresa a sistemas de prevision social por decision del trabajador | decimal (absent 2025) | 2022–2025 | Input; introduced in 2022; not present in 2020–2021 |
| 0025 | rendimientos_trabajo | `irpf_rendimiento_trabajo_rendimiento_neto_reducido` | Rendimiento neto reducido del trabajo | decimal (absent 2025) | 2020–2025 | Computed; section changed 2025; semantic unchanged |
| 0057 | rendimientos_trabajo | **HAZARD — see below** | Reduccion de rendimientos acogidos al regimen fiscal del acontecimiento XXXVII Copa America Barcelona | decimal (absent 2025) | 2023–2025 | Section changed: resultados.rdto_trabajo_res (2023–2024) → rendimientos_trabajo (2025) |
| 0058 | rendimientos_trabajo | `irpf_rendimiento_trabajo_reduccion_actividades_artisticas_excepcional` | Reduccion por rendimientos de actividades artisticas obtenidos de manera excepcional | (absent) | 2025 only | New in 2025; single-revision — typo-twin warning expected |

---

## Cluster B — rendimientos del capital mobiliario base_ahorro + base_general (26 casillas)

Section path 2020–2024: `["toma_datos_ampliada", "rdto_capital_mobiliario", "rdto_capital_mobiliario_ahorro"]`
/ `["toma_datos_ampliada", "rdto_capital_mobiliario", "rdto_capital_mobiliario_general"]`
and `["resultados", "rdto_capital_mobiliario_res", "rdto_capital_mobiliario_ahorro_res"]`
/ `["resultados", "rdto_capital_mobiliario_res", "rdto_capital_mobiliario_general_res"]` (ids 0041, 0060).
Section path 2025: `["rendimientos_capital_mobiliario", "base_ahorro"]` or `["rendimientos_capital_mobiliario", "base_general"]`.

### base_ahorro sub-section (15 casillas)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0027 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_intereses_cuentas` | Intereses de cuentas, depositos y activos financieros en general | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.25.2 |
| 0028 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_intereses_bonificados` | Intereses de activos financieros con derecho a bonificacion | decimal (absent 2025) | 2020–2025 | Input; transitional bonification interest |
| 0029 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_dividendos` | Dividendos y rendimientos por participacion en fondos propios | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.25.1 equity participation |
| 0030 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_letras_tesoro` | Rendimientos de transmision o amortizacion de Letras del Tesoro | decimal (absent 2025) | 2020–2025 | Input; Treasury bills |
| 0031 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_otros_activos_financieros` | Rendimientos de otros activos financieros | decimal (absent 2025) | 2020–2025 | Input; bonds/other financial assets (transmision/amortizacion/reembolso) |
| 0032 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_seguros_capitalizacion` | Rendimientos de seguros de vida o invalidez y operaciones de capitalizacion | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.25.3 |
| 0033 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_rentas_imposicion_capitales` | Rentas por imposicion de capitales y otros rendimientos en base del ahorro | decimal (absent 2025) | 2020–2025 | Input; capitalization rents |
| 0034 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_deuda_subordinada_preferentes` | Rendimientos derivados de deuda subordinada o participaciones preferentes | decimal (absent 2025) | 2020–2025 | Input; subordinated debt / preference shares |
| 0035 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_palp` | Rendimientos de Planes de Ahorro a Largo Plazo | decimal (absent 2025) | 2020–2025 | Input; PALP (Planes de Ahorro a Largo Plazo) |
| 0036 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_total_ingresos_integros` | Total ingresos integros del capital mobiliario en base del ahorro | decimal (absent 2025) | 2020–2025 | Computed aggregate |
| 0037 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_gastos_deducibles` | Gastos fiscalmente deducibles de capital mobiliario en base del ahorro | decimal (absent 2025) | 2020–2025 | Input; admin/deposito de valores negociables (LIRPF art.26) |
| 0038 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_rendimiento_neto` | Rendimiento neto del capital mobiliario en base del ahorro | decimal (absent 2025) | 2020–2025 | Computed (0036 − 0037) |
| 0039 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_reduccion_seguros_antiguos` | Reduccion aplicable a determinados contratos de seguro | decimal (absent 2025) | 2020–2025 | Input; DT 4ª LIRPF transitional reduction for pre-1994 insurance |
| 0040 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_rendimiento_neto_reducido` | Rendimiento neto reducido del capital mobiliario en base del ahorro | decimal (absent 2025) | 2020–2025 | Computed (0038 − 0039) |
| 0041 | rendimientos_capital_mobiliario.base_ahorro | `irpf_rendimiento_capital_mobiliario_ahorro_suma_rendimientos_reducidos` | Suma de rendimientos reducidos del capital mobiliario en base del ahorro | decimal (absent 2025) | 2020–2025 | Computed aggregate; section changed 2025 (resultados→rendimientos_capital_mobiliario); semantic unchanged |

### base_general sub-section (11 casillas)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0046 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_arrendamiento_bienes_muebles` | Arrendamiento de bienes muebles, negocios o minas y subarrendamientos | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.25.4.a |
| 0047 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_asistencia_tecnica` | Prestacion de asistencia tecnica | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.25.4.b |
| 0048 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_propiedad_intelectual_no_autor` | Propiedad intelectual cuando el contribuyente no sea autor | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.25.4.c non-author |
| 0050 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_propiedad_industrial` | Propiedad industrial no afecta a una actividad economica | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.25.4.d |
| 0051 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_otros` | Otros rendimientos del capital mobiliario en base general | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.25.4 residual |
| 0052 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_total_ingresos_integros` | Total ingresos integros del capital mobiliario en base general | decimal (absent 2025) | 2020–2025 | Computed aggregate |
| 0053 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_gastos_deducibles` | Gastos fiscalmente deducibles de capital mobiliario en base general | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.26 deducible expenses |
| 0054 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_rendimiento_neto` | Rendimiento neto del capital mobiliario en base general | decimal (absent 2025) | 2020–2025 | Computed (0052 − 0053) |
| 0055 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_reduccion` | Reducciones de rendimientos del capital mobiliario de base general | decimal (absent 2025) | 2020–2025 | Input; irregulares/plurianual reduction |
| 0056 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_rendimiento_neto_reducido` | Rendimiento neto reducido del capital mobiliario en base general | decimal (absent 2025) | 2020–2025 | Computed (0054 − 0055) |
| 0060 | rendimientos_capital_mobiliario.base_general | `irpf_rendimiento_capital_mobiliario_general_suma_rendimientos_reducidos` | Suma de rendimientos reducidos del capital mobiliario en base general | decimal (absent 2025) | 2020–2025 | Computed aggregate; section changed 2025 (resultados→rendimientos_capital_mobiliario); semantic unchanged |

---

## Cluster C — rendimientos del capital inmobiliario (26 casillas)

Section path 2020–2024: `["toma_datos_ampliada", "inmuebles", "inmueble"]` (ids 0089, 0102,
0104, 0107, 0109–0117, 0131–0132, 0146–0154) and `["resultados", "inmuebles_res"]`
(ids 0155, 0156).
Section path 2025: `["rendimientos_capital_inmobiliario", "<sub-section>"]`.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0089 | rendimientos_capital_inmobiliario.imputacion_rentas_inmobiliarias | `irpf_rendimiento_capital_inmobiliario_renta_imputada` | Renta inmobiliaria imputada | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.85 per-inmueble imputed rent |
| 0102 | rendimientos_capital_inmobiliario | `irpf_rendimiento_capital_inmobiliario_ingresos_integros` | Ingresos integros computables del capital inmobiliario | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.22 gross rental income |
| 0104 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gastos_pendientes` | Gastos pendientes aplicados en esta declaracion | decimal (absent 2025) | 2020–2025 | Input; prior-year pending expenses applied in current period |
| 0107 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gasto_intereses_reparacion` | Intereses y reparacion/conservacion aplicados en esta declaracion | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.23.1 interest + repair/conservation cap |
| 0109 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gasto_comunidad` | Gastos de comunidad | decimal (absent 2025) | 2020–2025 | Input; community charges (LIRPF art.23) |
| 0110 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gasto_formalizacion_contrato` | Gastos de formalizacion del contrato | decimal (absent 2025) | 2020–2025 | Input; lease formalisation costs |
| 0111 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gasto_defensa_juridica` | Gastos de defensa juridica | decimal (absent 2025) | 2020–2025 | Input; legal defence costs |
| 0112 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gasto_servicios_personales_terceros` | Otras cantidades devengadas por terceros por servicios personales | decimal (absent 2025) | 2020–2025 | Input; third-party personal services (property management etc.) |
| 0113 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gasto_servicios_suministros` | Servicios y suministros | decimal (absent 2025) | 2020–2025 | Input; utilities (electricity, water, internet, gas) |
| 0114 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gasto_primas_seguro` | Primas de contratos de seguro | decimal (absent 2025) | 2020–2025 | Input; insurance premiums |
| 0115 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gasto_tributos` | Tributos recargos y tasas | decimal (absent 2025) | 2020–2025 | Input; IBI and other property taxes/levies |
| 0116 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gasto_saldos_dudoso_cobro` | Saldos de dudoso cobro | decimal (absent 2025) | 2020–2025 | Input; doubtful-debt deduction (LIRPF art.23) |
| 0117 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_amortizacion_bienes_muebles` | Amortizacion de bienes muebles | decimal (absent 2025) | 2020–2025 | Input; moveable property amortisation (furniture/fittings) |
| 0131 | rendimientos_capital_inmobiliario.amortizacion | `irpf_rendimiento_capital_inmobiliario_amortizacion_inmueble` | Amortizacion del inmueble y la mejora | decimal (absent 2025) | 2020–2025 | Input; immoveable property + improvements amortisation |
| 0132 | rendimientos_capital_inmobiliario.amortizacion | `irpf_rendimiento_capital_inmobiliario_amortizacion_casos_especiales` | Amortizacion en casos especiales | decimal (absent 2025) | 2020–2025 | Input; special-case amortisation on main inmueble — see label-twin note below |
| 0146 | rendimientos_capital_inmobiliario.amortizacion | `irpf_rendimiento_capital_inmobiliario_amortizacion_inmueble_accesorio` | Amortizacion del inmueble accesorio y mejoras | decimal (absent 2025) | 2020–2025 | Input; accessory property + improvements amortisation |
| 0147 | rendimientos_capital_inmobiliario.amortizacion | `irpf_rendimiento_capital_inmobiliario_amortizacion_casos_especiales_accesorio` | Amortizacion en casos especiales del inmueble accesorio | decimal (absent 2025) | 2020–2025 | Input; special-case amortisation on accessory inmueble — see label-twin note below |
| 0148 | rendimientos_capital_inmobiliario.gastos_deducibles | `irpf_rendimiento_capital_inmobiliario_gasto_otros` | Otros gastos fiscalmente deducibles | decimal (absent 2025) | 2020–2025 | Input; residual deductible expenses |
| 0149 | rendimientos_capital_inmobiliario | `irpf_rendimiento_capital_inmobiliario_rendimiento_neto` | Rendimiento neto del capital inmobiliario | decimal (absent 2025) | 2020–2025 | Computed; ingresos minus total gastos |
| 0150 | rendimientos_capital_inmobiliario.reducciones | `irpf_rendimiento_capital_inmobiliario_reduccion_arrendamiento_vivienda` | Reduccion por arrendamiento de inmuebles destinados a vivienda | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.23.2 vivienda habitual rental reduction |
| 0151 | rendimientos_capital_inmobiliario.reducciones | `irpf_rendimiento_capital_inmobiliario_reduccion_rendimientos_irregulares` | Reduccion por rendimientos irregulares del capital inmobiliario | decimal (absent 2025) | 2020–2025 | Input; 30% reduction for plurianual/irregular income (LIRPF art.23.3) |
| 0152 | rendimientos_capital_inmobiliario | `irpf_rendimiento_capital_inmobiliario_rendimiento_minimo_parentesco` | Rendimiento minimo computable en caso de parentesco | decimal (absent 2025) | 2020–2025 | Input; LIRPF art.24 related-party minimum imputed rent |
| 0153 | rendimientos_capital_inmobiliario.retenciones | `retenciones_ingresos_a_cuenta` | Retenciones e ingresos a cuenta de capital inmobiliario | decimal (absent 2025) | 2020–2025 | Reuses canonical cross-modelo role; withholding on rental income (M115/M180 overlap) |
| 0154 | rendimientos_capital_inmobiliario | `irpf_rendimiento_capital_inmobiliario_rendimiento_neto_reducido` | Rendimiento neto reducido del capital inmobiliario | decimal (absent 2025) | 2020–2025 | Computed; max(rendimiento_neto, rendimiento_minimo_parentesco) - reducciones |
| 0155 | rendimientos_capital_inmobiliario.imputacion_rentas_inmobiliarias | `irpf_rendimiento_capital_inmobiliario_suma_rentas_imputadas` | Suma de rentas inmobiliarias imputadas | decimal (absent 2025) | 2020–2025 | Computed aggregate; section changed 2025 (resultados→rendimientos_capital_inmobiliario); semantic unchanged |
| 0156 | rendimientos_capital_inmobiliario | `irpf_rendimiento_capital_inmobiliario_suma_rendimientos_netos_reducidos` | Suma de rendimientos netos reducidos del capital inmobiliario | decimal (absent 2025) | 2020–2025 | Computed aggregate; section changed 2025 (resultados→rendimientos_capital_inmobiliario); semantic unchanged |

---

## New roles introduced

All roles below are new and not present in the canonical taxonomy as of
2026-05-19. They should be appended to the taxonomy reference after the
bulk-apply commit lands.

### Cluster A — rendimientos del trabajo (24 new roles)

- `irpf_rendimiento_trabajo_importe_integro_dinerario`
- `irpf_rendimiento_trabajo_especie_valoracion`
- `irpf_rendimiento_trabajo_especie_ingreso_cuenta`
- `irpf_rendimiento_trabajo_especie_ingreso_cuenta_repercutido`
- `irpf_rendimiento_trabajo_especie_importe_integro`
- `irpf_rendimiento_trabajo_contribucion_empresarial_prevision`
- `irpf_rendimiento_trabajo_contribucion_empresarial_seguro_dependencia`
- `irpf_rendimiento_trabajo_aportacion_patrimonio_protegido`
- `irpf_rendimiento_trabajo_reduccion`
- `irpf_rendimiento_trabajo_total_ingresos_integros`
- `irpf_rendimiento_trabajo_gasto_ss_mutualidad`
- `irpf_rendimiento_trabajo_gasto_sindicato`
- `irpf_rendimiento_trabajo_gasto_colegio_profesional`
- `irpf_rendimiento_trabajo_gasto_defensa_juridica`
- `irpf_rendimiento_trabajo_rendimiento_neto_previo`
- `irpf_rendimiento_trabajo_suma_rendimientos_netos_previos`
- `irpf_rendimiento_trabajo_gasto_otros`
- `irpf_rendimiento_trabajo_incremento_traslado_residencia`
- `irpf_rendimiento_trabajo_incremento_discapacitado_activo`
- `irpf_rendimiento_trabajo_rendimiento_neto`
- `irpf_rendimiento_trabajo_reduccion_gastos_generales`
- `irpf_rendimiento_trabajo_aportacion_empresa_decision_trabajador`
- `irpf_rendimiento_trabajo_rendimiento_neto_reducido`
- `irpf_rendimiento_trabajo_reduccion_actividades_artisticas_excepcional` (2025 only; typo-twin warning expected)

### Cluster B — rendimientos del capital mobiliario (25 new roles)

- `irpf_rendimiento_capital_mobiliario_ahorro_intereses_cuentas`
- `irpf_rendimiento_capital_mobiliario_ahorro_intereses_bonificados`
- `irpf_rendimiento_capital_mobiliario_ahorro_dividendos`
- `irpf_rendimiento_capital_mobiliario_ahorro_letras_tesoro`
- `irpf_rendimiento_capital_mobiliario_ahorro_otros_activos_financieros`
- `irpf_rendimiento_capital_mobiliario_ahorro_seguros_capitalizacion`
- `irpf_rendimiento_capital_mobiliario_ahorro_rentas_imposicion_capitales`
- `irpf_rendimiento_capital_mobiliario_ahorro_deuda_subordinada_preferentes`
- `irpf_rendimiento_capital_mobiliario_ahorro_palp`
- `irpf_rendimiento_capital_mobiliario_ahorro_total_ingresos_integros`
- `irpf_rendimiento_capital_mobiliario_ahorro_gastos_deducibles`
- `irpf_rendimiento_capital_mobiliario_ahorro_rendimiento_neto`
- `irpf_rendimiento_capital_mobiliario_ahorro_reduccion_seguros_antiguos`
- `irpf_rendimiento_capital_mobiliario_ahorro_rendimiento_neto_reducido`
- `irpf_rendimiento_capital_mobiliario_ahorro_suma_rendimientos_reducidos`
- `irpf_rendimiento_capital_mobiliario_general_arrendamiento_bienes_muebles`
- `irpf_rendimiento_capital_mobiliario_general_asistencia_tecnica`
- `irpf_rendimiento_capital_mobiliario_general_propiedad_intelectual_no_autor`
- `irpf_rendimiento_capital_mobiliario_general_propiedad_industrial`
- `irpf_rendimiento_capital_mobiliario_general_otros`
- `irpf_rendimiento_capital_mobiliario_general_total_ingresos_integros`
- `irpf_rendimiento_capital_mobiliario_general_gastos_deducibles`
- `irpf_rendimiento_capital_mobiliario_general_rendimiento_neto`
- `irpf_rendimiento_capital_mobiliario_general_reduccion`
- `irpf_rendimiento_capital_mobiliario_general_rendimiento_neto_reducido`
- `irpf_rendimiento_capital_mobiliario_general_suma_rendimientos_reducidos`

### Cluster C — rendimientos del capital inmobiliario (24 new roles; 1 reuse)

- `irpf_rendimiento_capital_inmobiliario_renta_imputada`
- `irpf_rendimiento_capital_inmobiliario_ingresos_integros`
- `irpf_rendimiento_capital_inmobiliario_gastos_pendientes`
- `irpf_rendimiento_capital_inmobiliario_gasto_intereses_reparacion`
- `irpf_rendimiento_capital_inmobiliario_gasto_comunidad`
- `irpf_rendimiento_capital_inmobiliario_gasto_formalizacion_contrato`
- `irpf_rendimiento_capital_inmobiliario_gasto_defensa_juridica`
- `irpf_rendimiento_capital_inmobiliario_gasto_servicios_personales_terceros`
- `irpf_rendimiento_capital_inmobiliario_gasto_servicios_suministros`
- `irpf_rendimiento_capital_inmobiliario_gasto_primas_seguro`
- `irpf_rendimiento_capital_inmobiliario_gasto_tributos`
- `irpf_rendimiento_capital_inmobiliario_gasto_saldos_dudoso_cobro`
- `irpf_rendimiento_capital_inmobiliario_amortizacion_bienes_muebles`
- `irpf_rendimiento_capital_inmobiliario_amortizacion_inmueble`
- `irpf_rendimiento_capital_inmobiliario_amortizacion_casos_especiales`
- `irpf_rendimiento_capital_inmobiliario_amortizacion_inmueble_accesorio`
- `irpf_rendimiento_capital_inmobiliario_amortizacion_casos_especiales_accesorio`
- `irpf_rendimiento_capital_inmobiliario_gasto_otros`
- `irpf_rendimiento_capital_inmobiliario_rendimiento_neto`
- `irpf_rendimiento_capital_inmobiliario_reduccion_arrendamiento_vivienda`
- `irpf_rendimiento_capital_inmobiliario_reduccion_rendimientos_irregulares`
- `irpf_rendimiento_capital_inmobiliario_rendimiento_minimo_parentesco`
- `irpf_rendimiento_capital_inmobiliario_rendimiento_neto_reducido`
- `irpf_rendimiento_capital_inmobiliario_suma_rentas_imputadas`
- `irpf_rendimiento_capital_inmobiliario_suma_rendimientos_netos_reducidos`
- **Reused:** `retenciones_ingresos_a_cuenta` — id 0153; withholding on capital
  inmobiliario income is the canonical M115/M180 cross-modelo withholding role.

**Total new roles: 73** (24 + 25 + 24). 1 canonical role reuse (0153).

---

## Id-reuse hazards

### Critical: 0057 — section change between 2023/2024 and 2025

| revision | section | label |
|---|---|---|
| 2023–2024 | `resultados.rdto_trabajo_res` | Reducción de rendimientos acogidos al régimen fiscal del acontecimiento "XXXVII Copa América Barcelona" |
| 2025 | `rendimientos_trabajo` | Reduccion de rendimientos acogidos al regimen fiscal del acontecimiento XXXVII Copa America Barcelona |

The semantic concept is identical (the same Copa América Barcelona reduction
introduced by Ley 31/2022 DT 36ª). The section path changed from `resultados`
to `rendimientos_trabajo` as part of the 2025 restructure. This is a
**structural drift only** — the same pattern as the other ids that moved from
`resultados.*` to `rendimientos_*` (ids 0018–0025, 0041, 0060, 0155, 0156).
The cross-revision validator keys on `semantic_role`, not `section`; a single
common role is safe to assign across 2023–2025.

**Proposed resolution:** Assign
`irpf_rendimiento_trabajo_reduccion_copa_america_barcelona` for 2023–2025.
Pre-2023 (2020–2022) the id does not exist; not present in those revisions.

### Warning: 0132 and 0147 — identical labels in 2020–2024

Both ids carry `label = "Amortización en casos especiales"` and identical
`section = ["toma_datos_ampliada", "inmuebles", "inmueble"]` in all revisions
2020–2024. In 2025 they diverge:

- `0132` → `"Amortizacion en casos especiales"` (main property)
- `0147` → `"Amortizacion en casos especiales del inmueble accesorio"` (accessory property)

These are structurally distinct casillas (different registry positions, different
per-inmueble context in the toma_datos_ampliada grid), so distinct roles are
correct. The 2025 labels confirm the semantic distinction. The 2020–2024
label collision is a source-data labelling gap — the differentiation was always
structural, not label-based. The two roles assigned above correctly disambiguate.

### Informational: 0058 — single-revision (2025 only)

Id `0058` (Reduccion por rendimientos de actividades artisticas obtenidos de
manera excepcional) was introduced in the 2025 revision only. The role
`irpf_rendimiento_trabajo_reduccion_actividades_artisticas_excepcional` will
emit a typo-twin warning at registry load; this is expected and documented here.

---

## Decimal/money divergences

None found in these three clusters. All monetary casillas use `data_type =
"decimal"` in 2020–2024 (consistent with IRPF intermediate-precision fields per
the taxonomy reference) or `data_type` absent in 2025 (same pattern as the
retenciones cluster documented in Phase 2 and accepted as inferred-decimal). No
casilla in any of the three clusters carries `data_type = "money"`. No
decimal/money split exists.

---

## Section-path structural drift (non-hazard)

The following ids moved from `resultados.*` or deeper `toma_datos_ampliada`
sub-trees to the flat `rendimientos_*` section hierarchy in 2025 as part of
the form restructure. Labels are substantively identical across all revisions
(minor accent/punctuation normalisation only). These are **not** semantic
hazards; role assignments are common across all revisions.

- Cluster A: 0018, 0019, 0020, 0021, 0022, 0023, 0025 (resultados→rendimientos_trabajo)
- Cluster B: 0041 (resultados→rendimientos_capital_mobiliario.base_ahorro);
  0060 (resultados→rendimientos_capital_mobiliario.base_general)
- Cluster C: 0155, 0156 (resultados→rendimientos_capital_inmobiliario)

---

## Acceptance notes

- 74 casilla ids covered (25 trabajo + 26 capital mobiliario + 26 capital inmobiliario
  = 77 rows; minus 0153 reuse = 73 new roles + 1 reuse; minus 0057 pending
  resolution = 72 clean assignments + 1 hazard).
- 0057 requires a follow-up decision before bulk-apply: the resolution above
  (assign `irpf_rendimiento_trabajo_reduccion_copa_america_barcelona` for
  2023–2025, absent for 2020–2022) is recommended.
- 0058 is 2025-only; typo-twin warning is expected and documented.
- 0153 reuses the canonical `retenciones_ingresos_a_cuenta` role; no new role needed.
- All 73 new role names must be appended to the taxonomy reference document
  after the bulk-apply commit lands.
