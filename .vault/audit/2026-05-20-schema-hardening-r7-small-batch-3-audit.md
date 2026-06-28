---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7-small batch-3 semantic audit

## Scope

45 semantic roles from `.vault-scratch/r7-small/batch-3.json`, covering modelos 036, 111, 115, 123, 130, 131, 180, 184, 190, 202, 232, 303, 308, 309, 322, 347, 349, 353, 360, 369, 390, 720, 840. Registry TOMLs consulted: `modelos/131/revisions/2019-2023.toml`, `modelos/202/revisions/2019-2022/revision.toml`, both manifests.

## Findings

| role | verdict | detail |
|---|---|---|
| `perceptor_count` | OK | Coherent across M111 (all income categories), M115 (rental), M123 (capital). Integer count of payees per category — acceptable breadth for a shared presentation role. |
| `pago_fraccionado` | SPLIT | Members span two distinct tax regimes: M130 casillas 04/09 are IRPF quarterly instalments (RD 439/2007 art. 110, estimación directa / agrícola); M202 casillas 22/25/63/66 are IS corporate-tax fractional payments under LIS art. 40.3 B2. Different legal bases, different declarants, different computation chains. Split into `irpf_pf_importe` (M130) and `is_pf_mod_40_3_b2_importe_pago_fraccionado` (M202). |
| `pago_fraccionado_previo` | SPLIT | Same cross-regime mixing as above. M130 casilla 05 = IRPF prior-period instalments (estimación directa); M131 casilla 07 = IRPF prior-period instalments (estimación objetiva); M202 casilla 30 = IS prior-period payments in Territorio Común under LIS art. 40.3. The registry TOML confirms M131/07 carries `semantic_role = "pago_fraccionado_previo"` — the role exists, but M202/30 is a distinct IS concept. Split: keep `pago_fraccionado_previo` for IRPF (M130, M131) and introduce `is_pf_mod_40_3_pagos_previos_territorio_comun` for M202/30. |
| `filing_period` | OK | M303 (quarterly), M322/353 (monthly), M369 (all three OSS schemes) all share `decl.periodo` with `period_code` type. Cross-modelo and cross-revision span is normal for a presentation header field. |
| `tipo_declaracion` | OUTLIER | M840 member (id `decl.tipo-declaracion`, label "alta / variacion / baja") is an IAE census lifecycle event (registration, amendment, deregistration), not a filing amendment type. The other four members (M184, M347, M390, M720) carry the standard amendment-type triplet (originaria / sustitutiva / complementaria). M840 belongs in a separate role such as `tipo_evento_censal_iae` or under the existing `tipo_evento_censal` role (M036). Remove M840 `decl.tipo-declaracion` from `tipo_declaracion`. |
| `irpf_pf_modulos_diferencia` | OK | M131 casilla 10 across four annual revisions. Single modelo, single concept (diferencia en estimación objetiva). Revision repetition is normal. |
| `irpf_pf_modulos_suma_rendimientos` | OK | M131 casilla 01 — confirmed by registry TOML (`semantic_role = "irpf_pf_modulos_suma_rendimientos"`). Coherent. |
| `irpf_pf_modulos_volumen_sin_datos_base` | OK | M131 casilla 03 — confirmed by registry TOML (`semantic_role = "irpf_pf_modulos_volumen_sin_datos_base"`). Coherent. |
| `iva_cuota_repercutida_super_reducido` | OK | M303/322/353 are periodic super-reduced output tax (4%); M390 is the annual reconciliation equivalent — same tax concept, different filing cadence. Standard annual-vs-periodic coexistence. |
| `pago_fraccionado_previo_agrario` | OK | M131 casilla 06 — confirmed by registry TOML (`semantic_role = "pago_fraccionado_previo_agrario"`). Single concept across four annual revisions. |
| `prestamo_vivienda_habitual` | OK | M131 casilla 12 across four revisions. The housing-loan deduction from total liquidation is a stable IRPF concept (transitional regime, RD 439/2007 art. 110). Coherent. |
| `is_pf_mod_40_2_resultado_declaracion_anterior` | OK | M202 casilla 02 across three revisions. IS art. 40.2 prior-declaration result (complementaria). Single concept, revision repetition normal. |
| `is_pf_mod_40_3_b1_compensacion_cuotas_neg_coop` | OK | M202 casilla 40 — IS art. 40.3 B1 cooperative negative-quota offset. Consistent across revisions (2025 label is more explicit but conceptually identical). |
| `is_pf_mod_40_3_b1_reserva_nivelacion_convertida_aum` | OK | M202 casilla 48 — levelling reserve converted to quotas, increases side. 2025 label refinement ("convertida en cuotas") is cosmetic. Coherent. |
| `is_pf_mod_40_3_b2_base_pago_fraccionado` | OK | M202 casilla 19 — B2 specific-cases fractional payment base. Coherent across three revisions. |
| `is_pf_mod_40_3_b2_compensacion_cuotas_neg_coop` | OK | M202 casilla 42 — B2 cooperative negative-quota offset, parallel to B1 casilla 40. All three revisions identical. |
| `is_pf_mod_40_3_b2_porcentaje_2` | OK | M202 casilla 24, `decimal` type. IS art. 40.3 B2 percentage slot 2. Coherent. |
| `is_pf_mod_40_3_b2_resultado_previo` | OK | M202 casilla 26 — B2 preliminary result (sum of pago-fraccionado amounts). 2025 label adds formula hint but concept is unchanged. Coherent. |
| `is_pf_mod_40_3_cantidad_a_ingresar` | OK | M202 casilla 34 — IS art. 40.3 amount payable (max of [32],[33]). Coherent. |
| `is_pf_mod_40_3_correcciones_is_disminuciones` | OK | M202 casilla 06 — accounting result corrections (IS decreases). Coherent across three revisions. |
| `is_pf_mod_40_3_reserva_nivelacion_aumentos` | OK | M202 casilla 45 — levelling reserve (art. 105 LIS) increases. Coherent. |
| `is_pf_mod_40_3_resto_correcciones_disminuciones` | OK | M202 casilla 08 — remaining corrections decreases, parallel to casilla 06. Coherent. |
| `is_pf_mod_40_3_resultado_declaracion_anterior` | OK | M202 casilla 31 — IS art. 40.3 prior-declaration result (complementaria). Coherent. |
| `is_pf_mod_40_3_volumen_territorio_comun_pct` | OK | M202 casilla 29 — % volume in Territorio Común, `decimal` type. Coherent. |
| `iva_resultado_regimen_general` | OK | M303 (individual periodic), M322 (individual in VAT group), M353 (group aggregate). Different scopes but identical tax concept and formula semantics. Acceptable shared role. |
| `actividad_cnae` | OK | M232 `decl.cnae` across two revisions (2016-2017, 2018+). Single-field census code, same section, `text` type. Coherent. |
| `devengo_year` | OK | M180 `perc.ejercicio-devengo` across two revisions. `year` type, payee accrual year field. Coherent. |
| `payee_immueble_municipality_code` | RENAME | Role name uses `immueble` (double-m, anglicised spelling) while the AEAT field id and all other payee roles use `inmueble`. Rename to `payee_inmueble_municipality_code`. Members are correct M180 municipality-code fields. |
| `payee_inmueble_bloque` | OK | M180 block-address component. Coherent two-revision pair. |
| `payee_inmueble_escalera` | OK | M180 stairwell-address component. Coherent. |
| `payee_inmueble_nombre_via` | OK | M180 street-name component. Coherent. |
| `payee_inmueble_portal` | OK | M180 building-entrance component. Coherent. |
| `payee_inmueble_situacion` | OK | M180 property-situation code (e.g. immueble type classification). Coherent. |
| `payee_modalidad_renta` | OK | M180 income-modality classification for the payee. Coherent. |
| `payee_representative_nif` | OK | M180 legal-representative NIF. `nif` type, coherent two-revision pair. |
| `suma_retenciones_regularizacion` | OK | M123 casillas 06-legacy (2019-2023) and 12 (2024+). Same concept across revision boundary — total withholdings including regularisation adjustment. Cross-revision tracking is correct. |
| `base_rentas_total` | OK | M123 casilla 06 (2024+) — total base for all income categories. Single-member singleton, coherent. |
| `deduccion_vivienda_habitual` | OK | M130 casilla 16 — primary-residence investment deduction (IRPF estimación directa). Single-member singleton, coherent. |
| `intracomunitario_importe_operaciones` | OK | M349 summary total of intra-EU transactions. Singleton, coherent. |
| `intracomunitario_numero_operadores` | OK | M349 count of EU operators. `integer`, singleton, coherent. |
| `irpf_pf_diferencia` | OK | M130 casilla 17 (estimación directa diferencia). Distinct from `irpf_pf_modulos_diferencia` (M131 estimación objetiva) — correct separation. |
| `irpf_pf_minoracion_rendimientos` | OK | M130 casilla 13 — net-income reduction in quarterly settlement. Single-member singleton. |
| `irpf_pf_resultado_final` | OK | M130 casilla 19 — final result of IRPF quarterly instalment. Singleton. |
| `irpf_pf_resultados_negativos_anteriores` | OK | M130 casilla 15 — prior-quarter negative results carried forward (estimación directa). Singleton; the M131 equivalent uses `irpf_pf_modulos_resultados_negativos_anteriores`. |
| `is_pf_mod_40_3_b2_base_tipo_3` | OK | M202 casilla 61, 2025+ only. New base amount for third rate tier added by 2025 reform. Singleton. |
| `is_pf_mod_40_3_b2_porcentaje_4` | OK | M202 casilla 65, 2025+ only. `decimal` percentage for fourth rate tier. Singleton. |
| `iva_anual_compensacion_ultimo_periodo` | OK | M390 `iva.anual.compensacion-ultimo-periodo-97` — annual carry-forward from last quarterly period. Singleton, coherent. |
| `iva_anual_reconciliacion_deducible_303` | OK | M390 reconciliation of deductible quota from four M303 periods. Singleton, coherent. |
| `iva_anual_resultado_regimen_general` | OK | M390 annual general-regime result. Singleton, the annual counterpart of `iva_resultado_regimen_general`. |
| `iva_compensacion_generada_periodo` | OK | M303 compensation balance generated in the period. Singleton. |
| `iva_cuota_no_periodica_total` | OK | M309 non-periodic VAT total (self-billed + recargo). Singleton. |
| `iva_ioss_importacion_low_value_cuota` | OK | M369 IOSS import scheme (DE destination, ≤150 EUR goods). Singleton, correctly scoped to importacion schema. |
| `iva_oss_union_cuota_total` | OK | M369 OSS Union scheme total output tax. Singleton. |
| `iva_prorrata_volumen_con_derecho` | OK | M303 pro-rata deductible-operation volume. Singleton, `money` type consistent with LIVA art. 104. Note: label has a UTF-8 encoding artifact ("deducciÃ³n") — cosmetic, not a semantic issue. |
| `iva_resultado_autoliquidacion` | OK | M303 final self-assessment result. Singleton. |
| `numero_rentas_total` | OK | M123 total income count (2024+). Singleton, `integer`. |
| `tipo_evento_censal` | OK | M036 census declaration event kind. Singleton. Correctly distinct from `tipo_declaracion`. |
| `tipo_solicitud` | OK | M308 request type (recargo de equivalencia / art 30 bis etc). Singleton, `text` enumeration. |
| `total_percepciones_count` | OK | M190 total number of receipts in the annual summary. Singleton, `integer`, 2025+ revision. |

## Summary counts

| verdict | count |
|---|---|
| OK | 40 |
| RENAME | 1 |
| SPLIT | 2 |
| OUTLIER | 1 |
| **Total** | **45** |

### Action items

- **`pago_fraccionado`** — split into `irpf_pf_importe` (M130/04, M130/09) and `is_pf_mod_40_3_b2_importe_pago_fraccionado` (all M202 members). The IS role name aligns with the existing `is_pf_mod_40_3_b2_*` cluster.
- **`pago_fraccionado_previo`** — retain for IRPF (M130/05, M131/07 all revisions); extract M202/30 into `is_pf_mod_40_3_pagos_previos_territorio_comun`.
- **`tipo_declaracion`** — remove M840 `decl.tipo-declaracion`; assign it to `tipo_evento_censal` (alongside M036) or to a dedicated `tipo_evento_censal_iae` role, since the M840 values (alta/variacion/baja) describe IAE census lifecycle events, not amendment types.
- **`payee_immueble_municipality_code`** — rename to `payee_inmueble_municipality_code` (drop double-m typo).
