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

# M100 actividad-est-directa cluster — semantic role classification

## Scope

This audit classifies every casilla in the `actividad-est-directa` cluster of Modelo 100 (IRPF). The cluster covers direct-estimate economic activity income (`estimación directa normal` and `estimación directa simplificada`), spanning sections `toma_datos_ampliada/reg_estima_directa/actividad_est_directa`, `rendimientos_actividades_economicas/estimacion_directa`, and `resultados/reg_estima_directa_res` across revisions 2020–2025. All 47 casilla ids in `.vault-scratch/m100-clusters/actividad-est-directa.json` are classified. No `irpf_ed_*` roles existed in the 1333-entry existing-roles registry prior to this audit; every role below is new. The `irpf_ed_*` prefix mirrors the established `irpf_eo_*` (estimación objetiva) convention.

## Role assignments

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|--------------|-----------|-------------------|-------|
| 0166 | `irpf_ed_actividad_tipo_clave` | Tipo de actividad/es realizada/s: clave indicativa | text | 2020-2025 | Activity-type key code for the direct-estimate activity block |
| 0167 | `irpf_ed_actividad_iae_code` | Grupo o epígrafe I.A.E. | text | 2020-2025 | IAE heading/group code for the principal activity |
| 0168 | `irpf_ed_modalidad_clave` | Modalidad aplicable del método de estimación directa (N/S) | text | 2020-2025 | N=normal / S=simplificada flag |
| 0169 | `irpf_ed_cobros_pagos_flag` | Si para la imputación temporal de los rendimientos opta por criterio de cobros y pagos | boolean | 2020-2025 | Temporal-imputation criterion election |
| 0170 | `irpf_ed_derechos_imagen_cessation_flag` | En el caso de rendimientos derivados de la cesión de explotación de los derechos de imagen | boolean | 2020-2025 | Image-rights cessation regime election flag |
| 0171 | `irpf_ed_ingresos_explotacion` | Ingresos de explotación | money(default) | 2020-2025 | Operating revenue (turnover) |
| 0172 | `irpf_ed_ingresos_financieros_aplazamiento` | Ingresos financieros derivados del aplazamiento o fraccionamiento | money(default) | 2020-2025 | Financial income from deferred/instalment operations |
| 0173 | `irpf_ed_ingresos_subvenciones_corrientes` | Ingresos por subvenciones corrientes | money(default) | 2020-2025 | Current (revenue) subsidies |
| 0174 | `irpf_ed_ingresos_subvenciones_capital` | Imputación de ingresos por subvenciones de capital | money(default) | 2020-2025 | Capital-subsidy income imputation |
| 0175 | `irpf_ed_autoconsumo` | Autoconsumo de bienes y servicios | money(default) | 2020-2025 | Own-consumption of goods and services |
| 0176 | `irpf_ed_iva_devengado` | IVA devengado | money(default) | 2020-2025 | VAT accrued (equiv/agri compensation schemes) |
| 0177 | `irpf_ed_variacion_existencias_incremento` | Variación de existencias (incremento de existencias finales) | money(default) | 2020-2025 | Stock variation — increase in closing stock |
| 0178 | `irpf_ed_otros_ingresos` | Otros ingresos | money(default) | 2020-2025 | Other operating income |
| 0179 | `irpf_ed_exceso_amortizacion_libertad` | Transmisión elementos patrimoniales con libertad amortización: exceso amortiz. | money(default) | 2020-2025 | Excess amortisation on assets that enjoyed accelerated/free depreciation |
| 0180 | `irpf_ed_total_ingresos_computables` | Total ingresos computables | money(default) | 2020-2025 | Computed total of all countable revenues (sum 0171–0179) |
| 0181 | `irpf_ed_compra_existencias` | Compra de existencias | money(default) | 2020-2025 | Purchases of stock/inventory |
| 0182 | `irpf_ed_variacion_existencias_disminucion` | Variación de existencias (disminución de existencias finales) | money(default) | 2020-2025 | Stock variation — decrease in closing stock |
| 0183 | `irpf_ed_otros_consumos_explotacion` | Otros consumos de explotación | money(default) | 2020-2025 | Other operating consumption |
| 0184 | `irpf_ed_sueldos_salarios` | Sueldos y salarios | money(default) | 2020-2025 | Wages and salaries |
| 0185 | `irpf_ed_seguridad_social_empresa` | Seguridad Social a cargo de la empresa | money(default) | 2020-2025 | Employer social-security contributions |
| 0186 | `irpf_ed_seguridad_social_titular` | Seguridad Social del titular de la actividad | money(default) | 2020-2025 | Activity-holder own SS contributions (or mutualidad alternativa prior to 2023) |
| 0187 | `irpf_ed_indemnizaciones` | Indemnizaciones | money(default) | 2020-2025 | Severance/indemnification payments |
| 0188 | `irpf_ed_dietas_viajes_personal` | Dietas y asignaciones de viajes del personal empleado | money(default) | 2020-2025 | Subsistence and travel allowances for employees |
| 0189 | `irpf_ed_aportaciones_prevision_social_personal` | Aportaciones a sistemas de previsión social imputadas al personal empleado | money(default) | 2020-2025 | Pension/social-provision contributions allocated to employees |
| 0190 | `irpf_ed_otros_gastos_personal` | Otros gastos de personal | money(default) | 2020-2025 | Other personnel expenses |
| 0191 | `irpf_ed_gastos_manutencion_contribuyente` | Gastos de manutención del contribuyente | money(default) | 2020-2025 | Taxpayer subsistence expenses (art 30.2.5ª.c LIRPF) |
| 0192 | `irpf_ed_arrendamientos_canones` | Arrendamientos y cánones | money(default) | 2020-2025 | Rents and royalties |
| 0193 | `irpf_ed_reparaciones_conservacion` | Reparaciones y conservación | money(default) | 2020-2025 | Repairs and maintenance |
| 0194 | `irpf_ed_suministros` | Suministros (electricidad, agua, gas, telefonía e internet) | money(default) | 2020-2025 | Utility supplies (electricity, water, gas, phone, internet) |
| 0195 | `irpf_ed_mutualidades_alternativas_titular` | Aportaciones a mutualidades alternativas del titular de la actividad | money(default) | 2023-2025 | Alternative-mutuality contributions by activity holder (split from 0186 from 2023) |
| 0196 | `irpf_ed_regularizacion_reta_ingresar` | Regularización cuotas RETA a ingresar | money(default) | 2025 | RETA quota regularisation — amount payable (2025 only) |
| 0197 | `irpf_ed_regularizacion_reta_devolver` | Regularización cuotas RETA a devolver | money(default) | 2025 | RETA quota regularisation — amount refundable (2025 only) |
| 0198 | `irpf_ed_otros_suministros` | Otros suministros | money(default) | 2020-2025 | Other supplies not itemised in 0194 |
| 0199 | `irpf_ed_servicios_profesionales_independientes` | Servicios de profesionales independientes | money(default) | 2020-2025 | Fees for independent professional services |
| 0200 | `irpf_ed_primas_seguros` | Primas de seguros | money(default) | 2020-2025 | Insurance premiums |
| 0202 | `irpf_ed_otros_servicios_exteriores` | Otros servicios exteriores | money(default) | 2020-2025 | Other external services |
| 0203 | `irpf_ed_gastos_financieros` | Gastos financieros | money(default) | 2020-2025 | Financial costs/interest expense |
| 0205 | `irpf_ed_iva_soportado` | IVA soportado | money(default) | 2020-2025 | Input VAT borne (equiv/agri compensation schemes) |
| 0206 | `irpf_ed_otros_tributos_deducibles` | Otros tributos fiscalmente deducibles | money(default) | 2020-2025 | Other tax-deductible levies |
| 0208 | `irpf_ed_amortizacion_inmovilizado_material` | Dotaciones del ejercicio para amortización de inmovilizado material | money(default) | 2020-2025 | Depreciation of tangible fixed assets |
| 0214 | `irpf_ed_perdidas_insolvencias_deudores` | Pérdidas por insolvencias de deudores | money(default) | 2020-2025 | Bad-debt losses |
| 0215 | `irpf_ed_mecenazgo_convenios_colaboracion` | Incentivos al mecenazgo — convenios de colaboración en actividades de interés general | money(default) | 2020-2025 | Patronage incentives via collaboration agreements |
| 0216 | `irpf_ed_mecenazgo_actividades_interes_general` | Incentivos al mecenazgo — gastos en actividades de interés general | money(default) | 2020-2025 | Patronage incentives for general-interest activity expenditure |
| 0217 | `irpf_ed_otros_conceptos_deducibles` | Otros conceptos fiscalmente deducibles (excepto provisiones) | money(default) | 2020-2025 | Other tax-deductible concepts excluding provisions |
| 0218 | `irpf_ed_suma_gastos_previos` | Suma de gastos previos de estimación directa | money(default) | 2020-2025 | Sub-total of deductible expenses before provisions (computed) |
| 0219 | `irpf_ed_provisiones_deducibles` | Provisiones fiscalmente deducibles | money(default) | 2020-2025 | Tax-deductible provisions (normal mode only) |
| 0220 | `irpf_ed_total_gastos_deducibles_normal` | Total gastos deducibles — estimación directa normal | money(default) | 2020-2025 | Total deductible expenses under normal direct estimation |
| 0221 | `irpf_ed_diferencia_ingresos_gastos_previos` | Diferencia entre ingresos y gastos previos | money(default) | 2020-2025 | Difference: total revenues minus pre-provision expenses; data_type diverges across revisions (see below) |
| 0222 | `irpf_ed_provisiones_gastos_dificil_justificacion` | Conjunto de provisiones deducibles y gastos de difícil justificación | money(default) | 2020-2025 | Provisions and hard-to-justify expenses (simplified mode) |
| 0223 | `irpf_ed_total_gastos_deducibles_simplificada` | Total gastos deducibles — estimación directa simplificada | money(default) | 2020-2025 | Total deductible expenses under simplified direct estimation |
| 0224 | `irpf_ed_rdto_neto` | Rendimiento neto ([0180] - [0220] o [0180] - [0223]) | decimal | 2020 | Per-activity net income result (actividad_est_directa section); id reused in 2021–2025 as aggregate — see id-reuse hazards |
| 0225 | `irpf_ed_reduccion_rendimientos_irregulares` | Reducciones de rendimientos generados en más de 2 años u obtenidos de forma notoriamente irregular | money(default) | 2020-2025 | Reduction for irregular income (multi-year or exceptionally irregular); data_type diverges (see below) |
| 0226 | `irpf_ed_rdto_neto_reducido` | Rendimiento neto reducido | money(default) | 2020-2025 | Net income after applying irregularity reductions; data_type diverges (see below) |
| 0227 | `irpf_ed_amortizacion_inmovilizado_inmaterial` | Dotaciones del ejercicio para amortización del inmovilizado inmaterial | money(default) | 2020-2025 | Amortisation of intangible fixed assets |
| 0231 | `irpf_ed_suma_rdtos_netos_reducidos` | Suma de rendimientos netos reducidos de las actividades económicas en estimación directa | money(default) | 2020-2025 | Aggregate of per-activity reduced net incomes across all direct-estimate activities; data_type diverges (see below) |
| 0232 | `irpf_ed_reduccion_art_32_2_1` | Reducción por el ejercicio de determinadas actividades económicas (art 32.2.1º LIRPF) | money(default) | 2020-2025 | Reduction for qualifying economic activities under art 32.2.1º |
| 0233 | `irpf_ed_reduccion_art_32_2_3` | Reducción por el ejercicio de determinadas actividades económicas (art 32.2.3º LIRPF) | money(default) | 2020-2025 | Reduction for qualifying economic activities under art 32.2.3º |
| 0234 | `irpf_ed_reduccion_inicio_actividad` | Reducción por inicio de una actividad económica (art 32.3 LIRPF) | money(default) | 2020-2025 | Start-up reduction for new economic activities |
| 0235 | `irpf_ed_rdto_neto_reducido_total` | Rendimiento neto reducido total de las actividades económicas en estimación directa | money(default) | 2020-2025 | Final aggregate net income after all statutory reductions; data_type diverges (see below) |
| 0236 | `irpf_ed_reduccion_copa_america` | Reducción de rendimientos acogidos al régimen fiscal del acontecimiento Copa América Barcelona | money(default) | 2023-2025 | Event-specific reduction (XXXVII Copa América Barcelona 2024 fiscal regime); data_type diverges (see below) |
| 0237 | `irpf_ed_reduccion_rendimientos_artisticos_excepcionales` | Reducción por rendimientos de actividades artísticas obtenidos de manera excepcional | money(default) | 2025 | Reduction for exceptionally obtained artistic-activity income (2025 only) |

## Id-reuse hazards

### Casilla 0224 — per-activity result vs. aggregate summary

Casilla `0224` carries two distinct concepts across the revision range:

- **2020** (`actividad_est_directa` section, `decimal`): Per-activity direct-estimate net income computed within the individual activity block as `[0180] − [0220]` or `[0180] − [0223]`. Label: "Rendimiento neto ([0180] - [0220] o [0180] - [0223])". Role: `irpf_ed_rdto_neto`.
- **2021–2025** (section `rendimientos_actividades_economicas` at the top level, not inside `actividad_est_directa`): Aggregate "Rendimiento neto de actividades económicas en estimación directa" — a cross-activity total. This concept belongs to the summary layer, not to this cluster. The 2020 TOML confirms the 2020 id sits in `toma_datos_ampliada/reg_estima_directa/actividad_est_directa` while the 2025 TOML places it in `rendimientos_actividades_economicas` only.

**Classification action**: `0224` is classified as `irpf_ed_rdto_neto` for revision 2020 only. The 2021–2025 incarnation of this id represents a different aggregate role that should be classified separately when the summary-results cluster is processed.

### No other id-reuse hazards detected

All other casillas in this cluster carry consistent labels and concepts across their active revision ranges. Label variation is orthographic only (accent normalisation, parenthetical formula text).

## Data_type divergences

Several casillas show `["decimal", "money(default)"]` in the aggregated `data_types` list. Investigation of 2020 TOMLs confirms these were declared `decimal` in 2020 and migrated to `money(default)` from 2021 onwards. The `money(default)` data_type is the canonical production type; the `decimal` variant reflects the 2020 schema before the money-type hardening campaign.

| id | data_types observed | canonical role data_type | divergence note |
|----|---------------------|--------------------------|-----------------|
| 0221 | decimal (2020), money(default) (2021–2025) | money(default) | Schema migration; use money(default) as canonical |
| 0224 | decimal (2020 only) | decimal | Single-revision id (2020); only decimal data_type applicable |
| 0225 | decimal (2020), money(default) (2021–2025) | money(default) | Schema migration |
| 0226 | decimal (2020), money(default) (2021–2025) | money(default) | Schema migration |
| 0231 | decimal (2020), money(default) (2021–2025) | money(default) | Schema migration |
| 0235 | decimal (2020), money(default) (2021–2025) | money(default) | Schema migration |
| 0236 | decimal (2023), money(default) (2024–2025) | money(default) | Introduced in 2023 as decimal; corrected to money(default) in 2024 |
