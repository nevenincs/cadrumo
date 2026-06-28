---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 small modelos — semantic role review batch 1

## Scope

Semantic-correctness review of all roles appearing in
`.vault-scratch/r7-small/batch-1.json`. Covers 24 smaller modelos
(036, 111, 115, 123, 130, 131, 180, 184, 190, 193, 202, 232, 303, 308,
309, 322, 347, 349, 353, 360, 369, 390, 720, 840). Structural type
consistency is assumed correct; this pass judges whether role names
accurately describe the tax concept and whether all members belong to
the same semantic concept.

Read-only. No TOML or source files were modified.

## Findings

| role | verdict | detail |
|---|---|---|
| `retenciones_ingresos_a_cuenta` | OK | Name is the standard Spanish statutory label used verbatim across M111, M115, M123, M130, M131, M180, M190, M193, M202. All members are withholding/payment-on-account amounts (both cash withholding and non-cash ingreso a cuenta). M202/28 belongs: it is the retenciones credit line within the Mod. 40.3 LIS liquidation, a legitimate retenciones amount deducted against the fractional payment obligation. Cross-modelo and cross-revision span is expected for this settled role. |
| `gross_cash_payment_amount` | RENAME → `importe_percepciones_dinerario` | All five M111 members are "importe de percepciones" (gross cash amount paid to recipients) for distinct income categories (trabajo dinerario, actividades económicas dinerarias, premios dinerarios, ganancias forestales dinerarias, cesión derechos imagen contraprestaciones). The English-language name "gross_cash_payment_amount" mixes English with the established Spanish-term convention used throughout this registry. The correct stable tax label is `importe_percepciones_dinerario`, mirroring the companion role for in-kind values. |
| `iva_cuota_autorepercutida_intracomunitaria` | OK | Name matches precisely: cuota IVA autorepercutida in intra-community acquisitions under reverse-charge (LIVA art. 84.Uno.2), appearing in M303, M309, M322, M353, M390. M390 carries the annual aggregate variant; the `anual` qualifier in its casilla ID is implementation-level, not a different concept. All members are coherent. |
| `in_kind_payment_value` | RENAME → `valor_percepciones_especie` | Four M111 members covering "valor de percepciones en especie" (trabajo especie, actividades económicas especie, premios especie, ganancias forestales especie). Same naming-convention problem as `gross_cash_payment_amount`: English is inconsistent with all surrounding roles. Correct stable label is `valor_percepciones_especie`. |
| `irpf_pf_modulos_resultados_negativos_anteriores` | OK | Four M131 revisions (2019-2023, 2024, 2025, 2026) for casilla 11 "Resultados negativos de trimestres anteriores". Name is accurate: IRPF objective-method (módulos) negative quarterly results carried forward in the fractional-payment liquidation. Multiple-revision span is normal. |
| `irpf_pf_modulos_volumen_agrario` | OK | Four M131 revisions for casilla 05 "Volumen de ingresos agrarios del trimestre". Name is accurate: agricultural/livestock/forestry income volume for the objective-method fractional payment. |
| `iva_cuota_repercutida_reducido` | OK | M303, M322, M353, M390 — cuota IVA at the reduced rate (10%). M390 is the annual reconciliation aggregate of the same concept. All coherent. |
| `minoracion_rendimientos_actividades_economicas` | OK | Four M131 revisions for casilla 09 "Minoración por rendimientos netos de actividades económicas". Name is accurate: the statutory reduction applied against the net income from economic activities in the módulos fractional payment. |
| `pago_fraccionado_previo_sin_datos_base` | OK | Four M131 revisions for casilla 04 "Pago fraccionado previo sin datos-base". Name accurately describes the fractional payment amount for activities without a base datum (volume-based substitute computation). |
| `is_pf_mod_40_3_amortizacion_30pct_dism` | OK | M202 casilla 37 across three revisions: "30% gastos amortización — Disminuciones" within the Mod. 40.3 LIS accounting-result corrections block. Name accurately encodes: IS (corporate tax), pago fraccionado, modalidad 40.3, amortisation 30%, decreases. |
| `is_pf_mod_40_3_b1_dotaciones_art_11_12` | OK | M202 casilla 47: "Dotaciones del art. 11.12 LIS" in the B1 general-case sub-block. The 2025 revision appends "DF 4a LIS" in its label; this is a label clarification not a concept change. Role name is accurate. |
| `is_pf_mod_40_3_b1_reserva_nivelacion_convertida_dis` | OK | M202 casilla 49: "Reserva de nivelación convertida — Disminuciones" in B1. The 2025 label elaborates to "convertida en cuotas" but the concept (levelling reserve converted, decreases) is unchanged. |
| `is_pf_mod_40_3_b2_base_tipo_1` | OK | M202 casilla 20: "Base a tipo 1" in B2 special-cases block. Accurate; "tipo 1" is the first rate band. |
| `is_pf_mod_40_3_b2_dotaciones_art_11_12_coop` | OK | M202 casilla 50: dotaciones art. 11.12 LIS for cooperatives in B2. The `_coop` suffix correctly distinguishes this from the B1 general-case dotaciones (casilla 47). |
| `is_pf_mod_40_3_b2_reserva_nivelacion_aumentos` | OK | M202 casilla 51: "Reserva de nivelación (art. 105 LIS) — Aumentos" in B2. Accurate. |
| `is_pf_mod_40_3_base_imponible_previa` | OK | M202 casilla 13: "Base imponible previa" in the Mod. 40.3 base-imponible block. Accurate: the pre-offset taxable base before negative-base compensation. |
| `is_pf_mod_40_3_compensacion_bases_negativas` | OK | M202 casilla 14: "Compensación de bases negativas de ejercicios anteriores". Accurate: prior-year loss set-off in Mod. 40.3. |
| `is_pf_mod_40_3_minimo_a_ingresar` | OK | M202 casilla 33: "Mínimo a ingresar (CN >= 10 millones euros)". Accurate: the statutory floor payment applicable to large taxpayers under Mod. 40.3 LIS. |
| `is_pf_mod_40_3_reserva_nivelacion_disminuciones` | OK | M202 casilla 46: "Reserva de nivelación (art. 105 LIS) — Disminuciones" in the dedicated `reserva_nivelacion` section. Accurate. |
| `is_pf_mod_40_3_resultado` | OK | M202 casilla 32: "Resultado" — the net payable result of the Mod. 40.3 LIS computation. Accurate. |
| `is_pf_mod_40_3_total_correcciones_aumentos` | OK | M202 casilla 38: "TOTAL correcciones — Aumentos". Accurate: aggregate of all accounting-result increases within Mod. 40.3. |
| `iva_cuota_deducible_total` | OK | M303, M322, M353: total deductible IVA quota (soportado + autorepercutido deducible). Note: M390 has a separately-named role `iva_anual_cuota_deducible_total` for its annual aggregate. No cross-modelo mismatch here because M390 is correctly excluded from this role. All members coherent. |
| `payee_nif` | OUTLIER → M184/tipo2.miembro-nif | M180 `perc.nif` (both revisions) = NIF of the arrendamiento recipient (perceptor). That correctly fits `payee_nif`. However, M184 `tipo2.miembro-nif` = NIF of the member (socio, comunero, heredero, partícipe) of an income-attributing entity — a different legal role (miembro of a régimen de atribución de rentas, not a payee in a retención context). Suggest either split to a new role `miembro_entidad_atribucion_nif` or move M184's member to `declarado_miembro_nif`. |
| `ingresos_ejercicios_anteriores` | OK | M123 casilla 04-legacy (2019-2023) and casilla 10 (2024+): "Ingresos de ejercicios anteriores" in the periodificación section. Name is accurate: prior-year income regularisation for withholding accounting. The ID change between revisions reflects a renumbering, not a concept change. |
| `payee_immueble_postal_code` | RENAME → `payee_inmueble_codigo_postal` | Typo: "immueble" (double-m) should be "inmueble". Both M180 members are correctly scoped (postal code of the leased property). The concept is correct; only the name has a spelling error. |
| `payee_inmueble_calificador_numero` | OK | M180 casilla `perc.inmueble-calificador-numero` (both revisions): address qualifier of the property's number (e.g., "BIS", "DPDO"). Name is accurate. |
| `payee_inmueble_localidad` | OK | M180: locality (town/city) of the leased property. Accurate. |
| `payee_inmueble_numero_casa` | OK | M180: house number of the leased property. Accurate. |
| `payee_inmueble_puerta` | OK | M180: door identifier of the leased property. Accurate. |
| `payee_inmueble_tipo_numeracion` | OK | M180: type of numbering (KM, S/N, NUM, etc.) of the leased property address. Accurate. |
| `payee_name` | OK | M180 `perc.nombre` (both revisions): full name or business name of the perceptor. Accurate. |
| `porcentaje_retencion` | OK | M180: "Porcentaje de retención aplicado" — the withholding rate applied per recipient. Accurate. Note: `data_type = text` is consistent with AEAT's free-form percentage field. |
| `tipo_ejercicio_232` | OK | M232 (2016-2017 and 2018+): "Tipo de ejercicio" — coded integer distinguishing 12 natural months / 12 × 365-day months / less than 12 months. The `_232` suffix appropriately scopes it to M232 where this concept appears. Accurate. |
| `complementaria_period` | RENAME → `periodo_rectificado` | M349 `rect.periodo-rectificado`: the period code of the rectified (corrected) prior declaration. The name `complementaria_period` mixes English with the context, and more importantly is semantically imprecise — this is a *rectificación* period (period being corrected), not a *complementaria* declaration period. `periodo_rectificado` matches the TOML id and AEAT label directly. |
| `estado_miembro_devolucion` | OK | M360 `decl.estado-miembro`: the EU member state where the IVA quotas were borne (for the IVA refund procedure). Accurate. |
| `intracomunitario_importe_rectificaciones` | OK | M349: total monetary amount of intra-community corrections declared. Accurate and consistent with sibling role `intracomunitario_numero_rectificaciones`. |
| `intracomunitario_numero_rectificaciones` | OK | M349: count of intra-community operators with rectifications. Accurate. |
| `irpf_pf_gastos` | OK | M130 casilla 02: "Gastos" in the direct-estimation section. Accurate: deductible expenses for the IRPF quarterly fractional payment under direct estimation. |
| `irpf_pf_neto_tras_minoracion` | OK | M130 casilla 14: "Neto tras minoración" in the total liquidation block. Accurate: net amount after applying the applicable reductions in the M130 fractional payment. |
| `irpf_pf_resultado_parcial_agraria` | OK | M130 casilla 11: "Resultado parcial apartado II" under actividades agrícolas/ganaderas/forestales/pesqueras. The label is generic but the section scoping makes the concept clear. The role name accurately reflects its domain. |
| `irpf_pf_suma_resultados_parciales` | OK | M130 casilla 12: "Suma de resultados parciales" in the total liquidation section. Accurate: sum of partial results (direct estimation + agricultural activities) before further adjustments. |
| `is_pf_mod_40_3_b2_base_tipo_4` | OK | M202/64 (2025+ only): "Base a tipo 4" — fourth rate band in B2, singleton deliberately. The `semantic_role_cardinality = intentional_singleton` annotation in the TOML confirms this is a new band introduced in 2025 with no prior-revision equivalent. Accurate. |
| `is_pf_mod_40_3_correcciones_impuesto_complementario` | OK | M202/67 (2025+ only): "Correcciones por Impuesto Complementario (IC) — Aumentos". Accurate: the Pillar 2 global minimum tax supplementary adjustments introduced in the 2025 revision of M202. |
| `iva_anual_cuota_deducible_total` | OK | M390: "Total cuota IVA deducible anual (soportado + autorepercutido)". Correctly distinguished from `iva_cuota_deducible_total` (periodic modelos). Accurate. |
| `iva_anual_reconciliacion_devengada_303` | OK | M390: "Cuota devengada anual reconciliada desde los cuatro Modelos 303 trimestrales". Accurate: the annual reconciliation field that aggregates the four quarterly M303 devengado totals. |
| `iva_compensacion_aplicada_periodo` | OK | M303: "Cuotas a compensar de periodos anteriores aplicadas en este periodo". Accurate: prior-period IVA credit applied in the current period. |
| `iva_compensacion_pendiente_anteriores` | OK | M303: "Cuotas a compensar pendientes de periodos anteriores". Accurate: unspent carry-forward IVA credit balance. |
| `iva_cuota_soportada_recargo_equivalencia` | OK | M309: "Cuota IVA soportado por minoristas en recargo de equivalencia (devolución a viajeros)". Accurate: input IVA borne by retailers under the recargo de equivalencia special regime in the non-periodic declaration context. |
| `iva_oss_exterior_cuota_total` | OK | M369 exterior scheme: total IVA quota repercutida under the non-Union OSS (Exterior) scheme. Accurate. |
| `iva_oss_union_goods_destino_cuota` | OK | M369 Union scheme: IVA quota for distance sales and electronic interface supplies destined for DE (Germany). The DE-specific nature is encoded in the casilla ID (`destino_de`); at role level this represents the per-destination IVA quota concept under the Union OSS scheme. Acceptable granularity given OSS destination-country design. |
| `iva_prorrata_volumen_total` | OK | M303: "Volumen anual total de operaciones" in the prorrata section. Accurate: total annual turnover used as denominator in the pro-rata IVA deduction calculation. |
| `numero_rentas_dividendos` | OK | M123/01 (2024+): "Número de rentas dividendos y participaciones". Accurate: count of dividend/profit-share income lines declared. |
| `payee_country` | RENAME → `operador_codigo_pais` | M349 `op.codigo-pais` is the country code of the EU intra-community *operator* (the counterparty in the intra-community operation), not a payee in the retención/perceptor sense. The section is `operador/identificacion`, not any payee context. `payee_country` imports the wrong semantic frame. Correct role: `operador_codigo_pais`. |
| `tipo_renta_atribuida_clave` | OK | M184 `tipo2.clave`: the key code classifying the type of attributed income (A=capital mobiliario, C=capital inmobiliario, D=actividades económicas, F=ganancias/pérdidas non-transfer, G=transfer gains/losses, I=IRPF deductions, J=IS deductions, K=withheld retenciones, L=excess negative income from non-treaty countries). Name is accurate. |
| `tipo_trigger` | RENAME → `motivo_declaracion_no_periodica` | M309 `decl.tipo-trigger`: the coded indicator distinguishing which non-periodic IVA obligation has been triggered (medios de transporte nuevos / régimen agrícola / recargo de equivalencia / ejecución forzosa). "trigger" is an informal English implementation term; the statutory concept is the grounds or motivo that makes a non-periodic (ad-hoc) Mod. 309 declaration mandatory. Suggest `motivo_declaracion_no_periodica`. |
| `vigencia_normativa` | OK | M036 `decl.vigencia-2025`: a textual field recording the normative effectivity date (vigencia normativa desde 3 de febrero de 2025). The role name accurately describes the concept; the singleton cardinality is expected for a version-stamp field specific to a single effective-date revision. |

## Summary counts

| verdict | count |
|---|---|
| OK | 45 |
| RENAME | 5 |
| SPLIT | 0 |
| OUTLIER | 1 |
| **Total** | **51** |

### Roles requiring action

- **RENAME** `gross_cash_payment_amount` → `importe_percepciones_dinerario` (English name, inconsistent with registry convention)
- **RENAME** `in_kind_payment_value` → `valor_percepciones_especie` (English name, inconsistent with registry convention)
- **RENAME** `payee_immueble_postal_code` → `payee_inmueble_codigo_postal` (typo: "immueble" → "inmueble")
- **RENAME** `complementaria_period` → `periodo_rectificado` (misnomer: this is a rectificación period, not a complementaria; English hybrid)
- **RENAME** `payee_country` → `operador_codigo_pais` (wrong semantic frame: M349 entity is an intra-community operator, not a payee/perceptor)
- **OUTLIER** `payee_nif` — M184/`tipo2.miembro-nif` belongs to a different legal role (miembro of a régimen de atribución de rentas); suggest separate role `miembro_entidad_atribucion_nif` or `declarado_miembro_nif`
