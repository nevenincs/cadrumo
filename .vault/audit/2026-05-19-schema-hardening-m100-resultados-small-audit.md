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

# `schema-hardening` audit: M100 resultados small-cluster role classification

## Scope

Five clusters from `resultados.*`: `resultado_declaracion` (~27),
`compensacion_conyuges_res` (~12), `regularizacion_res` (~3),
`irpf_ccaa_res` (~3), `datos_adicionales_res` (~33), plus
`minimo_per_fam_res` (~14, skip-check).

Revisions checked: 2020–2025 for every proposed id.  
Read-only: no TOML files modified.

---

## Cluster 1 — `resultado_declaracion` (27 casillas)

**Finding:** All 27 casillas already carry `semantic_role`. Zero unroled.
No further action required for this cluster.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0585 | resultado_declaracion | `irpf_cuota_liquida_estatal_incrementada` | Cuota liquida estatal incrementada | (absent/decimal implied) | 2020–2025 | already roled |
| 0586 | resultado_declaracion | `irpf_cuota_liquida_autonomica_incrementada` | Cuota liquida autonomica incrementada | (absent/decimal implied) | 2020–2025 | already roled |
| 0587 | resultado_declaracion | `irpf_cuota_liquida_total` | Cuota liquida incrementada total | (absent/decimal implied) | 2020–2025 | already roled |
| 0588 | resultado_declaracion | `irpf_deduccion_doble_imposicion_internacional` | Deduccion por doble imposicion internacional | (absent/decimal implied) | 2020–2025 | already roled |
| 0589 | resultado_declaracion | `irpf_deduccion_doble_imposicion_transparencia` | Deduccion por doble imposicion … transparencia | (absent/decimal implied) | 2020–2025 | already roled |
| 0590 | resultado_declaracion | `irpf_deduccion_doble_imposicion_imputacion_rentas` | Deduccion por doble imposicion … rentas imagen | (absent/decimal implied) | 2020–2025 | already roled |
| 0591 | resultado_declaracion | `irpf_retenciones_consideradas_practicadas` | Retenciones no practicadas deducibles | (absent/decimal implied) | 2020–2025 | already roled |
| 0595 | resultado_declaracion | `irpf_cuota_resultante_autoliquidacion` | Cuota resultante de la autoliquidacion | (absent/decimal implied) | 2020–2025 | already roled |
| 0610 | resultado_declaracion | `irpf_cuota_diferencial` | Cuota diferencial | `decimal` | 2020–2025 | already roled |
| 0611 | resultado_declaracion | `irpf_deduccion_maternidad` | Deduccion por maternidad. Importe | (absent/decimal implied) | 2020–2025 | already roled |
| 0612 | resultado_declaracion | `irpf_abono_anticipado_maternidad` | Deduccion por maternidad. Abono anticipado | (absent/decimal implied) | 2020–2025 | already roled |
| 0613 | resultado_declaracion | `irpf_incremento_maternidad_guarderia` | Incremento por gastos en guarderias | (absent/decimal implied) | 2020–2025 | already roled |
| 0414 | resultado_declaracion | — | Deduccion por obtencion de rendimientos del trabajo | (absent/decimal implied) | 2020–2025 | **UNROLED — see proposal below** |
| 0623 | resultado_declaracion | `irpf_deduccion_descendiente_discapacidad` | Deduccion por descendiente con discapacidad | (absent/decimal implied) | 2020–2025 | already roled |
| 0624 | resultado_declaracion | `irpf_abono_anticipado_descendiente_discapacidad` | Abono anticipado por descendiente discapacidad | (absent/decimal implied) | 2020–2025 | already roled |
| 0636 | resultado_declaracion | `irpf_deduccion_ascendiente_discapacidad` | Deduccion por ascendiente con discapacidad | (absent/decimal implied) | 2020–2025 | already roled |
| 0637 | resultado_declaracion | `irpf_abono_anticipado_ascendiente_discapacidad` | Abono anticipado por ascendiente discapacidad | (absent/decimal implied) | 2020–2025 | already roled |
| 0248 | resultado_declaracion | `irpf_deduccion_conyuge_discapacidad` | Deduccion por conyuge con discapacidad | (absent/decimal implied) | 2020–2025 | already roled |
| 0249 | resultado_declaracion | `irpf_abono_anticipado_conyuge_discapacidad` | Abono anticipado por conyuge discapacidad | (absent/decimal implied) | 2020–2025 | already roled |
| 0660 | resultado_declaracion | `irpf_deduccion_familia_numerosa` | Deduccion por familia numerosa | (absent/decimal implied) | 2020–2025 | already roled |
| 0661 | resultado_declaracion | `irpf_abono_anticipado_familia_numerosa` | Abono anticipado por familia numerosa | (absent/decimal implied) | 2020–2025 | already roled |
| 0662 | resultado_declaracion | `irpf_deduccion_monoparental` | Deduccion por ascendiente separado legalmente | (absent/decimal implied) | 2020–2025 | already roled |
| 0663 | resultado_declaracion | `irpf_abono_anticipado_monoparental` | Abono anticipado por ascendiente separado | (absent/decimal implied) | 2020–2025 | already roled |
| 0664 | resultado_declaracion | `irpf_regularizacion_cobro_anticipado_descendiente` | Regularizacion abono anticipado descendiente | (absent/decimal implied) | 2020–2025 | already roled |
| 0666 | resultado_declaracion | `irpf_regularizacion_cobro_anticipado_ascendiente` | Regularizacion abono anticipado ascendiente | (absent/decimal implied) | 2020–2025 | already roled |
| 0669 | resultado_declaracion | `irpf_discrepancia_criterio_administrativo` | Discrepancia de criterio administrativo | `decimal` | 2020–2025 | already roled |
| 0670 | resultado_declaracion | `irpf_resultado_declaracion` | Resultado de la declaracion | `decimal` | 2020–2025 | already roled |

### Unroled in resultado_declaracion: casilla 0414

Cross-revision check: id `0414` carries the consistent label "Deduccion por obtencion de rendimientos del trabajo" across 2020–2025 with no data_type declared (decimal implied). No semantic divergence.

**Proposed role:** `irpf_deduccion_rendimientos_trabajo`

---

## Cluster 2 — `resultados.compensacion_conyuges_res` (12 casillas)

Already roled: `1790` (`spouse_compensation_iban`), `1799` (`taxpayer_country`). 10 unroled.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1790 | compensacion_conyuges_res | `spouse_compensation_iban` | Compensacion entre conyuges: IBAN | `iban` | 2020–2025 | already roled |
| 1799 | compensacion_conyuges_res / compnosepa | `taxpayer_country` | Codigo Pais/Country code | `country_code` | 2021–2025 | already roled; absent in 2020 |
| 0693 | compensacion_conyuges_res | `irpf_compensacion_conyuges_ingresar_suspendido` | Importe del resultado a ingresar … suspension solicita | (absent/decimal implied) | 2020–2025 | **new role** |
| 0694 | compensacion_conyuges_res | `irpf_compensacion_conyuges_devolver_renunciado` | Importe del resultado a devolver … renuncia cobro | (absent/decimal implied) | 2020–2025 | **new role** |
| 0695 | compensacion_conyuges_res | `irpf_compensacion_conyuges_resto_ingresar` | Resto a ingresar del resultado … diferencia positiva | (absent/decimal implied; computed) | 2020–2025 | **new role** |
| 1791 | compensacion_conyuges_res / compsepa | `irpf_compensacion_conyuges_sepa_flag` | Compensacion entre conyuges: SEPA | `text` | 2021–2025 | **new role**; absent in 2020 |
| 1792 | compensacion_conyuges_res / compsepa | `irpf_compensacion_conyuges_swift_flag` | Compensacion entre conyuges: SWIFT | `text` | 2021–2025 | **new role**; absent in 2020 |
| 1793 | compensacion_conyuges_res / compnosepa | `irpf_compensacion_conyuges_swift_bic` | Codigo/Code SWIFT/BIC | `text` | 2021–2025 | **new role**; absent in 2020 |
| 1794 | compensacion_conyuges_res / compnosepa | `irpf_compensacion_conyuges_account_no` | Numero de cuenta / Account no. | `text` | 2021–2025 | **new role**; absent in 2020 |
| 1795 | compensacion_conyuges_res / compnosepa | `irpf_compensacion_conyuges_bank_name` | Banco/Name of the bank | `text` | 2021–2025 | **new role**; absent in 2020 |
| 1796 | compensacion_conyuges_res / compnosepa | `irpf_compensacion_conyuges_bank_address` | Direccion del Banco/Address of the bank | `text` | 2021–2025 | **new role**; absent in 2020 |
| 1797 | compensacion_conyuges_res / compnosepa | `irpf_compensacion_conyuges_bank_city` | Ciudad/City | `text` | 2021–2025 | **new role**; absent in 2020 |

**Note on 1791–1797:** These are international banking detail fields (SEPA/non-SEPA branch) first introduced in 2021. Their data_type is `text` — consistent across 2021–2025. They carry no declared `data_type` that would conflict. New roles use `irpf_compensacion_conyuges_*` prefix to group them under the spouse compensation banking sub-tree.

---

## Cluster 3 — `resultados.regularizacion_res` (3 casillas)

All 3 are unroled. Labels are semantically stable across 2020–2025 (only the exercise year reference in the label changes; core meaning is identical).

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0676 | regularizacion_res | `irpf_regularizacion_autoliquidaciones_anteriores_ingresar` | Resultado a ingresar … tramitacion autoliquidaciones anteriores | (absent/decimal implied) | 2020–2025 | **new role** |
| 0677 | regularizacion_res | `irpf_regularizacion_autoliquidaciones_anteriores_devolver` | Devolucion acordada … tramitacion autoliquidaciones anteriores | (absent/decimal implied) | 2020–2025 | **new role** |
| 0685 | regularizacion_res | `irpf_regularizacion_resultado` | Resultado (de la rectificacion de autoliquidacion) | `decimal` | 2020–2025 | **new role**; label in 2020–2023 is "Resultado de la solicitud de rectificación de autoliquidación"; in 2024–2025 shortened to "Resultado" — same semantic identity |

**Note on 0685:** Label abbreviated in 2024. `data_type = "decimal"` declared consistently in all revisions. Safe to assign one role.

---

## Cluster 4 — `resultados.irpf_ccaa_res` (3 casillas)

All 3 already carry `semantic_role`. Zero unroled.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0671 | irpf_ccaa_res | `irpf_cuota_liquida_autonomica_ccaa` | Cuota liquida autonomica incrementada (passthrough) | (absent/decimal implied) | 2020–2025 | already roled |
| 0672 | irpf_ccaa_res | `irpf_deduccion_doble_imposicion_autonomica_50pct` | 50 por 100 … deducciones por doble imposicion | (absent/decimal implied) | 2020–2025 | already roled |
| 0675 | irpf_ccaa_res | `irpf_cuota_ccaa_residencia` | Importe del IRPF que corresponde a la CCAA | (absent/decimal implied) | 2020–2025 | already roled |

---

## Cluster 5 — `resultados.datos_adicionales_res` (33 casillas)

Already roled (NIF/identity slots): 0456, 0458, 0742, 0745, 0747, 0750, 0752, 0755, 0757, 0760, 1742, 1745, 1750, 1755, 1760, 1762, 1786, 1787, 1788, 1789 (all NIF roles). Also roled: 1744, 1749, 1754, 1759 (carry `irpf_anexo_c_*` roles — **see ID-reuse hazard below**).

**Genuinely unroled in 2025:** 0457, 0459, 0525, 0526, 0527, 1741, 1743, 1746, 1748, 1751, 1753, 1756, 1758, 1761.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0457 | datos_adicionales_res / anualidades_alimentos_res | `irpf_datos_adicionales_nif_ausente_flag` | Hijo/Hija 1: Si no tiene NIF o NIE, marque X | `boolean` | 2020–2025 | **new role**; consistent boolean, no-NIF-flag companion to descendant_nif |
| 0459 | datos_adicionales_res / anualidades_alimentos_res | `irpf_datos_adicionales_nif_ausente_flag` | Hijo/Hija 2: Si no tiene NIF o NIE, marque X | `boolean` | 2020–2025 | same role as 0457; consistent |
| 0525 | datos_adicionales_res / rentas_exentas_res | `irpf_rentas_exentas_base_general` | Correspondientes a la base liquidable general | (absent/decimal implied) | 2020–2025 | **new role** |
| 0526 | datos_adicionales_res / rentas_exentas_res | `irpf_rentas_exentas_base_ahorro` | Correspondientes a la base liquidable del ahorro | (absent/decimal implied) | 2020–2025 | **new role** |
| 0527 | datos_adicionales_res / anualidades_alimentos_res | `irpf_anualidades_alimentos_total` | Importe de las anualidades por alimentos … hijos (suma) | (absent/decimal implied; computed) | 2020–2025 | **new role** |
| 1741 | datos_adicionales_res / anualidades_alimentos_res | `irpf_anualidades_alimentos_hijo_importe` | Hijo/Hija 1: Importe de las anualidades satisfechas | (absent/decimal implied) | 2022–2025 | **new role**; absent in 2020–2021 where id held anexo_c role — see hazard below |
| 1743 | datos_adicionales_res / anualidades_alimentos_res | `irpf_datos_adicionales_nif_ausente_flag` | Hijo/Hija 1: Si no tiene NIF o NIE, marque X | `boolean` | 2022–2025 | reuses existing NIF-flag role; absent 2020–2021 |
| 1746 | datos_adicionales_res / anualidades_alimentos_res | `irpf_datos_adicionales_nif_ausente_flag` | Hijo/Hija 2: Si no tiene NIF o NIE, marque X | `boolean` | 2022–2025 | reuses NIF-flag role |
| 1748 | datos_adicionales_res / anualidades_alimentos_res | `irpf_datos_adicionales_nif_ausente_flag` | Hijo/Hija 3: Si no tiene NIF o NIE, marque X | `boolean` | 2022–2025 | reuses NIF-flag role |
| 1751 | datos_adicionales_res / anualidades_alimentos_res | `irpf_datos_adicionales_nif_ausente_flag` | Hijo/Hija 3: Si no tiene NIF o NIE, marque X | `boolean` | 2022–2025 | reuses NIF-flag role |
| 1753 | datos_adicionales_res / anualidades_alimentos_res | `irpf_datos_adicionales_nif_ausente_flag` | Hijo/Hija 4: Si no tiene NIF o NIE, marque X | `boolean` | 2022–2025 | reuses NIF-flag role |
| 1756 | datos_adicionales_res / anualidades_alimentos_res | `irpf_datos_adicionales_nif_ausente_flag` | Hijo/Hija 4: Si no tiene NIF o NIE, marque X | `boolean` | 2022–2025 | reuses NIF-flag role |
| 1758 | datos_adicionales_res / anualidades_alimentos_res | `irpf_datos_adicionales_nif_ausente_flag` | Hijo/Hija 5: Si no tiene NIF o NIE, marque X | `boolean` | 2022–2025 | reuses NIF-flag role |
| 1761 | datos_adicionales_res / anualidades_alimentos_res | `irpf_datos_adicionales_nif_ausente_flag` | Hijo/Hija 5: Si no tiene NIF o NIE, marque X | `boolean` | 2022–2025 | reuses NIF-flag role |

---

## Cluster 6 — `resultados.minimo_per_fam_res` (14 casillas)

**All 14 casillas already carry `semantic_role`** (confirmed by checking all files in 2025). These were assigned in the `calculo_impuesto` cluster. Skipped per task instructions.

---

## New roles introduced

The following role names are proposed for this cluster set and are not present in the canonical taxonomy as of this audit:

- `irpf_deduccion_rendimientos_trabajo` — M100 0414; deduccion por obtencion de rendimientos del trabajo against cuota liquida. Appears in resultado_declaracion across all 6 revisions.
- `irpf_compensacion_conyuges_ingresar_suspendido` — M100 0693; amount of the positive result whose payment is suspended under spouse compensation.
- `irpf_compensacion_conyuges_devolver_renunciado` — M100 0694; amount of the refund whose collection is waived under spouse compensation.
- `irpf_compensacion_conyuges_resto_ingresar` — M100 0695; residual amount to pay after suspension (0670 - 0693); computed.
- `irpf_compensacion_conyuges_sepa_flag` — M100 1791; SEPA routing flag for the spouse-compensation payment (text/boolean-equivalent flag).
- `irpf_compensacion_conyuges_swift_flag` — M100 1792; SWIFT routing flag.
- `irpf_compensacion_conyuges_swift_bic` — M100 1793; SWIFT/BIC code for non-SEPA bank.
- `irpf_compensacion_conyuges_account_no` — M100 1794; bank account number for non-SEPA transfer.
- `irpf_compensacion_conyuges_bank_name` — M100 1795; bank name for non-SEPA transfer.
- `irpf_compensacion_conyuges_bank_address` — M100 1796; bank address for non-SEPA transfer.
- `irpf_compensacion_conyuges_bank_city` — M100 1797; bank city for non-SEPA transfer.
- `irpf_regularizacion_autoliquidaciones_anteriores_ingresar` — M100 0676; prior-period autoliquidacion net amount to pay in regularizacion context.
- `irpf_regularizacion_autoliquidaciones_anteriores_devolver` — M100 0677; prior-period autoliquidacion net refund in regularizacion context.
- `irpf_regularizacion_resultado` — M100 0685; net result of the rectification autoliquidacion (`decimal`, signed).
- `irpf_datos_adicionales_nif_ausente_flag` — M100 0457, 0459, 1743, 1746, 1748, 1751, 1753, 1756, 1758, 1761; companion boolean flag indicating no valid NIF/NIE is available for the accompanying descendant slot.
- `irpf_rentas_exentas_base_general` — M100 0525; exempt-income amount attributable to the base liquidable general.
- `irpf_rentas_exentas_base_ahorro` — M100 0526; exempt-income amount attributable to the base liquidable del ahorro.
- `irpf_anualidades_alimentos_total` — M100 0527; total court-ordered alimony paid across all child slots (computed sum).
- `irpf_anualidades_alimentos_hijo_importe` — M100 1741; per-child alimony amount paid in the tax year (input row).

**19 new roles total.**

---

## ID-reuse hazards

### Critical: 1741, 1744, 1749, 1754, 1759 — section and semantic change between 2021 and 2022

In 2021, these ids belong to `resultados.datos_adicionales_res` but hold **anexo_c excess pension-contributions carry-forward** rows (already roled with `irpf_anexo_c_*` roles). In 2022–2025, these same ids were reassigned to the `anualidades_alimentos_res` subsection and hold **alimony per-child amounts** for hijo/hija 1–5.

| id | 2021 label | 2021 role | 2022–2025 label | 2022–2025 role |
|---|---|---|---|---|
| 1741 | Contribuyente con derecho a reduccion | `irpf_anexo_c_contribuyente_con_derecho_reduccion` | Hijo/Hija 1: Importe anualidades por alimentos | `irpf_anualidades_alimentos_hijo_importe` (proposed) |
| 1744 | Ejercicio 2017: Pendiente de aplicacion al principio | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Hijo/Hija 2: Importe anualidades por alimentos | conflicts with existing role (see below) |
| 1749 | Ejercicio 2018: Pendiente de aplicacion en ejercicios futuros | `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | Hijo/Hija 3: Importe anualidades por alimentos | conflicts with existing role |
| 1754 | Ejercicio 2020: Aplicado en esta declaracion | `irpf_anexo_c_exceso_sps_rt_aplicado` | Hijo/Hija 4: Importe anualidades por alimentos | conflicts with existing role |
| 1759 | Ejercicio 2021: Aportaciones pendientes de aplicacion | `irpf_anexo_c_exceso_sps_rg_aportaciones_pendiente_fin` | Hijo/Hija 5: Importe anualidades por alimentos | conflicts with existing role |

**Note on 2020:** Ids 1741–1761 are entirely absent from the 2020 revision. The hazard is bounded to 2021 vs. 2022–2025.

**Resolution required before bulk-apply:**
- Ids 1744, 1749, 1754, 1759 currently carry `irpf_anexo_c_*` roles in 2021 (assigned in a prior pass) and **different semantics** in 2022–2025 (alimony amounts). The cross-revision constraint prohibits assigning one role across divergent revisions.
- Recommended path: assign revision-scoped roles. In 2021, retain the existing `irpf_anexo_c_*` roles. For 2022–2025, assign `irpf_anualidades_alimentos_hijo_importe` via a revision-scoped override (do NOT overwrite the 2021 TOML files).
- Id 1741 in 2021 carries `irpf_anexo_c_contribuyente_con_derecho_reduccion`; in 2022–2025 it is an alimony amount — same revision-scoped treatment applies.

**Do not apply a single cross-revision role to 1741, 1744, 1749, 1754, 1759 until revision-scoped role assignment is implemented.**

### Structural-only: 1791–1797 absent in 2020

Ids 1791–1797 first appear in 2021. This is a form-addition, not a semantic reuse. Labels are consistent 2021–2025. Safe to assign proposed `irpf_compensacion_conyuges_*` roles across 2021–2025 only.

---

## Decimal/money divergences

All proposed roles in this audit bind `decimal` (no `data_type` declaration means decimal is inferred for IRPF intermediate fields, consistent with the taxonomy note). No proposed role spans `decimal` and `money`.

- `irpf_regularizacion_resultado` (0685): explicitly `data_type = "decimal"` in all revisions. Signed (can be positive or negative depending on rectification direction). Consistent.
- Compensacion amounts 0693–0695: no `data_type` declared; decimal implied. Consistent across 2020–2025.
- Text fields 1791–1797: `data_type = "text"`. No monetary divergence concern.
- Boolean flags (0457, 0459, 1743, 1746, 1748, 1751, 1753, 1756, 1758, 1761): `data_type = "boolean"`. No monetary concern.

---

## Acceptance notes

- **resultado_declaracion:** 1 unroled id (0414), 26 already roled. Proposed `irpf_deduccion_rendimientos_trabajo` is safe for all 6 revisions.
- **compensacion_conyuges_res:** 10 unroled. 8 new roles (3 decimal amounts + 7 text banking fields). Revision presence for 1791–1797 is 2021–2025 only.
- **regularizacion_res:** 3 unroled. 3 new roles. Cross-revision semantics are stable (label wording varies only by year-reference).
- **irpf_ccaa_res:** 0 unroled. No action.
- **datos_adicionales_res:** 14 genuinely unroled in 2025. 5 new roles proposed. `irpf_datos_adicionales_nif_ausente_flag` covers 9 boolean slots. ID-reuse hazard on 1741/1744/1749/1754/1759 blocks their cross-revision assignment.
- **minimo_per_fam_res:** 0 unroled. Skipped.
- Total proposed new roles: **19**.
- Ids blocked from bulk-apply: **1741, 1744, 1749, 1754, 1759** (revision-scoped role assignment required).
