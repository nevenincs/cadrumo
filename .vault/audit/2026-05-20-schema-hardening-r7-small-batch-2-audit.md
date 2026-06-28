---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7-small batch-2 semantic role audit

## Scope

Semantic correctness review of 48 roles from `.vault-scratch/r7-small/batch-2.json`,
covering small AEAT modelos (111, 115, 123, 130, 131, 180, 184, 190, 193, 202,
232, 303, 308, 309, 322, 347, 349, 353, 360, 369, 390, 720, 840). Registry TOMLs read
for verification: 115, 303, 390, 349/2020-y-siguientes, 131, 123/2019-2023, 202
manifest. Structural validators confirm type-consistency; this pass verifies semantic
name accuracy, member coherence, and role granularity.

## Findings

| role | verdict | detail |
|------|---------|--------|
| `filing_year` | OK | 16 members across 13 modelos. All are `decl.ejercicio` / `year`. Consistent cross-modelo identity role. Label variance ("ejercicio de devengo" in 232) is acceptable — 232 aligns to IS accrual year; the underlying concept is the fiscal year the filing refers to. |
| `resultado_anteriores_autoliquidaciones` | OK | 9 members across 111/115/123/130/131. Covers the complementaria adjustment field for prior-period self-assessments. 115 casilla 04 label reads "anteriores declaraciones" but the registry assigns it this role and the semantic concept is the same. |
| `base_retenciones_ingresos_a_cuenta` | OK | 7 members across 115/123/180/193. Taxable base for withholdings and account payments. 180 contributes both per-payee (`perc.base`) and declarant summary (`decl.base-total`) entries — both are the same semantic role at different aggregation levels within an informative return. Coherent. |
| `irpf_pf_saldo_negativo_fin_periodo` | OK | 5 members across 130/131. Computed carry-forward negative balances. `irpf_pf` prefix correctly scopes to IRPF instalment modelos. |
| `cuota_a_ingresar` | OK | 4 members across 111/115/123. Final net-to-pay result in quarterly withholding/instalment returns. Precise. |
| `irpf_pf_modulos_resultado_declaracion` | OK | 4 members (131, 4 revisions). Casilla 15 "resultado de la declaracion". Single modelo; revisions are the expected pattern. |
| `irpf_pf_modulos_total` | OK | 4 members (131, 4 revisions). Casilla 13 "Total" in `total_liquidacion`. Pre-complementaria subtotal in estimacion objetiva. Accurate. |
| `iva_cuota_repercutida_general` | OK | 4 members across 303/322/353/390. Registry confirms `semantic_role = "iva_cuota_repercutida_general"` on all. 390 entry uses an `anual` section path — correct, 390 is the annual summary. Coherent cross-modelo identity. |
| `iva_cuota_soportada_interiores` | OK | 4 members across 303/322/353/390. Same pattern as `iva_cuota_repercutida_general`. Registry-confirmed. |
| `pago_fraccionado_previo_datos_base` | OK | 4 members (131, 4 revisions). Casilla 02 in estimacion objetiva. Stable concept across annual revisions. |
| `base_intracomunitaria` | OK | 3 members (349). Includes original operation base (`op.base-imponible`) and rectification amounts (`rect.base-rectificada`, `rect.base-anterior`). Registry assigns all three to this role. Contextual distinction is captured by section and casilla ID; the shared role is acceptable granularity. |
| `is_pf_mod_40_2_base_pago_fraccionado` | OK | 3 members (202, 3 revisions). Casilla 01, art. 40.2 LIS modalidad base. Stable across revisions. |
| `is_pf_mod_40_3_b1_base_pago_fraccionado` | OK | 3 members (202, 3 revisions). Casilla 16, art. 40.3 LIS B1 caso general base. |
| `is_pf_mod_40_3_b1_porcentaje` | OK | 3 members (202, 3 revisions). Casilla 17, rate field (`decimal`). Correct. |
| `is_pf_mod_40_3_b1_resultado_previo` | OK | 3 members (202, 3 revisions). Casilla 18, intermediate result before deductions. |
| `is_pf_mod_40_3_b2_base_tipo_2` | OK | 3 members (202, 3 revisions). Casilla 23, B2 second-type base. |
| `is_pf_mod_40_3_b2_porcentaje_1` | OK | 3 members (202, 3 revisions). Casilla 21, first percentage in B2 block. |
| `is_pf_mod_40_3_b2_reserva_nivelacion_disminuciones` | OK | 3 members (202, 3 revisions). Casilla 52, levelling reserve decreases (art. 105 LIS). |
| `is_pf_mod_40_3_bonificaciones` | OK | 3 members (202, 3 revisions). Casilla 27, period bonificaciones. |
| `is_pf_mod_40_3_correcciones_is_aumentos` | OK | 3 members (202, 3 revisions). Casilla 05, IS increases in accounting result corrections. |
| `is_pf_mod_40_3_remanente_reserva_capitalizacion` | OK | 3 members (202, 3 revisions). Casilla 44, capitalisation reserve remainder unused due to insufficient base. |
| `is_pf_mod_40_3_resto_correcciones_aumentos` | OK | 3 members (202, 3 revisions). Casilla 07, remaining corrections increases. |
| `is_pf_mod_40_3_resultado_contable` | OK | 3 members (202, 3 revisions). Casilla 04. 2025+ label adds "e IC" (Impuesto Complementario, Pillar Two); the underlying concept is unchanged. Label drift is registry-documented across revisions. |
| `is_pf_mod_40_3_total_correcciones_disminuciones` | OK | 3 members (202, 3 revisions). Casilla 39, total corrections decreases. |
| `iva_cuota_devengada_total` | OK | 3 members across 303/322/353. Periodic total devengada only. 390 correctly uses the separate `iva_anual_cuota_devengada_total` role. |
| `total_perceptores_count` | OK | 3 members across 180/193. Count of payees in informative withholding returns. `integer` type correct. |
| `iva_oss_union_servicios_destino_cuota` | SPLIT | Two members in the same modelo/revision with different destination countries: `iva.union.de.services-cuota` (DE) and `iva.union.fr.services-cuota` (FR). These are distinct destination-specific OSS VAT slots — not the same casilla across different revisions. Grouping two structurally parallel but country-distinct entries under one role is incorrect. Suggested resolution: introduce a generic per-destination-slot role (`iva_oss_union_servicios_cuota`) applied per country-destination row, or split into `iva_oss_union_servicios_destino_de_cuota` / `iva_oss_union_servicios_destino_fr_cuota`. |
| `payee_immueble_province` | RENAME | Typo: "immueble" should be "inmueble" (Spanish). Corrected name: `payee_inmueble_provincia`. Aligns with all sibling roles (`payee_inmueble_complemento`, `payee_inmueble_municipio`, `payee_inmueble_planta`, `payee_inmueble_referencia_catastral`, `payee_inmueble_tipo_via`) which spell the word correctly. |
| `payee_inmueble_complemento` | OK | 2 members (180, 2 revisions). Address complement of rented property. |
| `payee_inmueble_municipio` | OK | 2 members (180, 2 revisions). Municipality of rented property. |
| `payee_inmueble_planta` | OK | 2 members (180, 2 revisions). Floor/storey of rented property. |
| `payee_inmueble_referencia_catastral` | OK | 2 members (180, 2 revisions). Cadastral reference. |
| `payee_inmueble_tipo_via` | OK | 2 members (180, 2 revisions). Street-type code for property address. |
| `payee_province` | OK | 2 members (180, 2 revisions). Province code of payee domicile. Distinct from `payee_inmueble_provincia` (property location). |
| `regularizacion` | OK | 2 members (123, 2 revisions). Casilla 05-legacy / 11 "Regularizacion" in `periodificacion` section. Periodic accrual regularisation in Modelo 123 withholding returns. Accurate. |
| `base_rentas_dividendos` | OK | 1 member (123/2024+). Casilla 04, dividend/participation income base. |
| `base_rentas_resto` | OK | 1 member (123/2024+). Casilla 05, remaining income base. |
| `complementaria_year` | RENAME | Member is `rect.ejercicio-rectificado` in Modelo 349 — the year of the period being rectified in a rectification row, not the year of a complementaria declaration. A rectificacion in 349 is an amendment of a previously reported intracomunitario operation. Corrected name: `intracomunitario_rectificacion_ejercicio`. Consistent with sibling roles `intracomunitario_clave_operacion`, `intracomunitario_nif_iva`, `intracomunitario_operador_nombre`. |
| `intracomunitario_clave_operacion` | OK | 1 member (349). Operation type key in per-operator detail record. |
| `intracomunitario_nif_iva` | OK | 1 member (349). EU-VAT NIF of community operator. |
| `intracomunitario_operador_nombre` | OK | 1 member (349). Name or company name of community operator. |
| `irpf_pf_ingresos` | OK | 1 member (130). Casilla 01 "Ingresos" in estimacion directa section. |
| `irpf_pf_rendimiento_neto` | OK | 1 member (130). Casilla 03 net income. |
| `irpf_pf_resultado_parcial_directa` | OK | 1 member (130). Casilla 07, partial result for estimacion directa block. |
| `irpf_pf_volumen_ingresos_trimestre` | OK | 1 member (130). Casilla 08, quarterly income volume in agricultural/forestry activities section. |
| `is_pf_mod_40_3_b2_porcentaje_3` | OK | 1 member (202/2025+). Casilla 62, third percentage in B2 block added in 2025 revision. Singleton is expected — new field not present in prior revisions. |
| `iva_anual_compensacion_generada_ejercicio` | OK | 1 member (390). Casilla 662, compensation credits generated in the exercise excluding casilla 97. Specific and accurate. |
| `iva_anual_cuota_devengada_total` | OK | 1 member (390). Annual total devengada. Correctly distinct from periodic `iva_cuota_devengada_total`. |
| `iva_anual_reconciliacion_resultado_303` | OK | 1 member (390). Reconciliation of annual result aggregated from four quarterly 303 filings. |
| `iva_compensacion_disponible_fin_periodo` | OK | 1 member (303). End-of-period compensation balance available for forward carry. |
| `iva_compensacion_pendiente_posteriores` | OK | 1 member (303). Prior-period compensation not yet applied, carried forward. Distinct from `iva_compensacion_disponible_fin_periodo`. |
| `iva_ioss_importacion_cuota_total` | OK | 1 member (369/esquema-importacion). IOSS total VAT for Import scheme. |
| `iva_oss_exterior_servicios_destino_cuota` | OK | 1 member (369/esquema-exterior). Single destination (DE) in Exterior scheme. Singleton is coherent — single destination present in batch. |
| `iva_prorrata_porcentaje` | OK | 1 member (303). Prorrata general percentage (`ratio` type). Registry formula confirmed (LIVA art. 104.4, rounded up). |
| `iva_regularizacion_inversiones` | OK | 1 member (303). Capital goods regularisation per LIVA arts. 107-110. |
| `numero_rentas_resto` | OK | 1 member (123/2024+). Count of remaining-income rents. `integer` type correct. |
| `renta_atribuible_importe` | OK | 1 member (184). Attribution income amount in entity-member detail record. |
| `tipo_renta_atribuida_subclave` | OK | 1 member (184). Sub-key classifying attributed income by geographic origin, applicable reductions, etc. `text` type appropriate for an enumeration code. |
| `total_percepciones_amount` | OK | 1 member (190/2025+). Total perceptions amount in declarant summary. |

## Summary counts

- Total roles reviewed: **48**
- OK: **44**
- RENAME: **2**
- SPLIT: **1**
- OUTLIER: **0**

### Rename actions

- `payee_immueble_province` → `payee_inmueble_provincia`: fix typo and align with Spanish terminology. Affects 180 revisions 2019-2022 and 2023-y-siguientes.
- `complementaria_year` → `intracomunitario_rectificacion_ejercicio`: the casilla is the rectified year in a 349 amendment row, not a complementaria declaration year. Affects 349/2020-y-siguientes.

### Split action

- `iva_oss_union_servicios_destino_cuota`: split into a per-destination-slot role or two country-specific roles. The current grouping conflates DE and FR destination entries from the same revision into one role. Preferred resolution is a generic parameterised slot (`iva_oss_union_servicios_cuota`) applied individually per country row, consistent with how OSS per-country entries are structured in 369.
