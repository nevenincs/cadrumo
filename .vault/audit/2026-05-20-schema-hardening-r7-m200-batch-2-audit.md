---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m200 batch-2 semantic role audit

## Scope

Semantic correctness review of 95 `semantic_role` values from `.vault-scratch/r7-m200/batch-2.json`.
All members use `data_type: money`. Grounded against AEAT Modelo 200 (2024-y-siguientes) registry TOMLs
and section paths under `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/`.

Three axes evaluated per role: (1) name accuracy, (2) member coherence, (3) granularity.

## Findings

| role | verdict | detail |
|------|---------|--------|
| `is_conversion_aid_art130_importe` | OK | 111 members, all in `conversion_activos_impuesto_diferido_credito_exigi/activos_impuesto_diferido_aid_art_130_lis`. Covers all year-vintages of AID tracking columns (importe total, cuota líquida, pendientes inicio/fin, aplicados, convertidos). Name accurately reflects Art. 130 LIS AID amounts. |
| `is_conversion_aid_exceso_cuota_importe` | OK | 19 members, single section `conversion_activos_impuesto_diferido_credito_exigi/exceso_cuota_liquida_positiva`. All are exceso cuota líquida positiva amounts. Name accurate. |
| `is_conversion_aid_importe` | RENAME → `is_conversion_aid_conjunta_importe` | 24 members, section `tributacion_conjunta_estado_y_adm_forales/conversion_de_activos_por_impuesto_diferido_en_cre`. These are AID conversion amounts inside the tributación conjunta (joint taxation) block, not the general AID conversion schedule. The bare `importe` suffix hides the conjunta context; the role is otherwise coherent. |
| `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | RENAME → `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | 14 members, single section `dotaciones_deterioro_creditos_u_otros_activos/ejercicio_generacion`. All labels read "Dotaciones aplicadas conversión activos imp. diferido". The role is semantically precise but the name repeats "dotaciones" twice, suggesting a naming artefact. Cleaner name removes the stutter. Members are coherent (all within the deterioro-créditos AID conversion subsection, by generation year). |
| `is_deduccion_cinematografica_extranjera_periodo` | RENAME → `is_deduccion_cinematografica_extranjera_aplicado_periodo` | 69 members across 12 year-vintage sections, all in `deducciones_por_producciones_cinematograficas_extr/*`. Members represent amounts "aplicado en esta liquidación" for each year. The suffix `_periodo` is vague; `_aplicado_periodo` aligns with AEAT field nomenclature. Coherent — no outliers. |
| `is_deduccion_cinematografica_extranjera_pendiente_futuros` | OK | 21 members across 11 sections. All are "pendiente de aplicación en períodos futuros" for the cinematographic foreign deduction. Name accurate; coherent. |
| `is_correcciones_disminuciones` | RENAME → `is_correcciones_disminuciones_liquidacion_detalle` | 32 members in `liquidacion_i/detalle_correcciones` and `liquidacion_ii/detalle_correcciones`. These are the line-by-line decrease-correction rows from the liquidación I and II detail schedules, not the per-section regime-specific decrement amounts tracked by `is_correccion_disminucion`. The rename clarifies provenance. Members coherent. |
| `is_correccion_disminucion` | OK | 41 members from 23 distinct special-regime sections (capital-riesgo, exenciones, navieras, arrendamiento financiero, etc.), each tagged `/disminucion`. These are the regime-specific net-decrease adjustments at section level, distinct from the liquidación-detail rows. Name accurate; coherent across regimes as the generic regime-level decrease marker. |
| `is_deduccion_dt24a1_periodificacion` | OK | 14 members across 5 year-vintage sections of `deducciones_dt_24a_1_lis/*_periodificacion`. All are DT 24ª.1 LIS spreading-schedule amounts (generated, applied, pending). Accurate. |
| `is_deduccion_reversion_medidas_dt1_pendiente` | OK | 11 members across 10 year-vintage sections of `deduccion_por_reversion_de_medidas_temporales_d_t/*`. All are "importe pendiente" for D.T.37ª.1 LIS. Accurate. |
| `is_deduccion_reversion_medidas_dt2_pendiente` | OK | 12 members across 11 year-vintage sections. All are "importe pendiente" for D.T.37ª.2 LIS. Accurate. |
| `is_deduccion_reversion_medidas_dt2_periodo` | OK | 10 members across 10 year-vintage sections. All are "importe aplicado" for D.T.37ª.2 LIS. Name is correct (period-applied amounts for DT2). |
| `is_deduccion_idi_investigacion_pendiente` | OK | 8 members from 8 year-vintage sections of `deducc_para_incentivar_determ_actividades/*_investigacion_y_desarrollo`. All are "pendiente de aplicación en períodos futuros" for I+D. Accurate. |
| `is_deduccion_idi_total` | RENAME → `is_deduccion_actividades_total_pendiente` | Single member 00831, section `deducc_para_incentivar_determ_actividades/total`, label "Total - Deducción pendiente/generada". This is the grand total carryforward for ALL actividades incentivadas deducciones, not only IDI. The `_idi` prefix is incorrect; the section is `total` covering all activity categories. |
| `is_deduccion_copa_america_periodo` | RENAME → `is_deduccion_eventos_especiales_aplicado_periodo` | 4 members spanning Copa América Barcelona, Barcelona Mobile World Capital, Barcelona 2026 Capital Mundial de la Arquitectura, and Rally Islas Canarias (all in `deducc_para_incentivar_determ_actividades/2025_*` or `2026_*` sections). None of the 4 members is the Copa América casilla — the role name reflects only one of four distinct events. The common trait is "applied in period" for special-event deducciones of art. 27.3 Ley 49/2002 / similar. |
| `is_reserva_nivelacion_dotacion_dispuesta` | OK | 7 members, all `reserva_de_nivelacion/dotacion_de_la_reserva/*`. All are "Reserva dispuesta" amounts by year and total. Accurate. |
| `is_reserva_nivelacion_minoracion` | OK | Single member 01406, section `reserva_de_nivelacion/reduccion_base_imponible`. Label: "Importe minoración B.I. periodo/pendiente adicionar inicio periodo". Accurate; this is the base-imponible reduction amount. |
| `is_correccion_limite_beneficio_operativo_saldo_final` | RENAME → `is_correccion_limite_beneficio_operativo_pendiente` | 6 members from 5 year-vintage sections of `pendiente_adicion_por_limite_beneficio_operativo_n/*`. All are "Pendiente aplicación en periodos futuros" — they are forward-carry balances, not a closing balance (`saldo_final`). The AEAT field structure uses "pendiente" language; `_pendiente` is more accurate than `_saldo_final`. |
| `is_tributacion_conjunta_proporcion` | OK | 6 members across `tributacion_conjunta_estado_y_adm_forales/concierto_economico` and `concierto_economico_navarra`. All are proportion/volume amounts for joint-taxation apportionment. Accurate. |
| `is_capital_riesgo_ajuste_aumento` | SPLIT → `is_capital_riesgo_correccion_ejercicio_aumento` + `is_capital_riesgo_saldo_pendiente_aumento` | 4 members: 03132–03133 are "Correcciones del ejercicio – Temporarias" (flow), 03134–03135 are "Saldo pendiente a principio / fin de ejercicio" (stock). These are structurally different measure types; mixing them into one role conflates flow corrections with balance-sheet carryforward. |
| `is_entidad_sin_fines_lucrativos_aumento` | SPLIT → `is_entidad_sin_fines_lucrativos_correccion_ejercicio_aumento` + `is_entidad_sin_fines_lucrativos_saldo_pendiente_aumento` | 4 members: 03272–03273 are "Correcciones del ejercicio" (flow); 03274–03275 are "Saldo pendiente a principio / fin" (stock). Same flow/stock conflation as capital-riesgo. |
| `is_erd_libertad_amortizacion_aumento` | SPLIT → `is_erd_libertad_amortizacion_correccion_ejercicio_aumento` + `is_erd_libertad_amortizacion_saldo_pendiente_aumento` | 4 members: 03182–03183 correcciones del ejercicio, 03184–03185 saldos pendientes. Flow/stock conflation. |
| `is_hidrocarburos_amortizacion_intangibles_disminucion` | SPLIT → `is_hidrocarburos_amortizacion_intangibles_correccion_ejercicio_disminucion` + `is_hidrocarburos_amortizacion_intangibles_saldo_pendiente_disminucion` | 4 members: 03167–03168 correcciones del ejercicio (temporarias), 03169–03170 saldos inicio/fin. Flow/stock conflation. |
| `is_naviera_tonelaje_ajuste_disminucion` | SPLIT → `is_naviera_tonelaje_correccion_ejercicio_disminucion` + `is_naviera_tonelaje_saldo_pendiente_disminucion` | 4 members: 03257–03258 correcciones del ejercicio, 03259–03260 saldos inicio/fin. Same pattern. |
| `is_tfi_ajuste_aumento` | SPLIT → `is_tfi_correccion_ejercicio_aumento` + `is_tfi_saldo_pendiente_aumento` | 4 members: 03172–03173 correcciones del ejercicio (temporarias); 03174–03175 saldos inicio/fin. Flow/stock conflation. |
| `is_ute_imputacion_temporal_disminucion` | SPLIT → `is_ute_imputacion_temporal_correccion_ejercicio_disminucion` + `is_ute_imputacion_temporal_saldo_pendiente_disminucion` | 4 members: 03117–03118 correcciones del ejercicio, 03119–03120 saldos inicio/fin. Same pattern. |
| `is_correccion_bases_negativas_grupo_fiscal_permanente_aumento` | OK | 3 members (03121–03123), all "Correcciones del ejercicio" for BINs generated by transmitted entities in fiscal group (art. 62.2 LIS). Members cover permanentes + two temporarias sub-rows — all exercise-level flow, same concept. Acceptable granularity. |
| `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_aumento` | OK | 3 members (02671–02673), "Correcciones del ejercicio" for deterioro de IM/inversiones inmobiliarias (art. 13.2a + DT 15 LIS). Permanent + two temporarias sub-rows. Coherent — all current-exercise corrections for same concept. |
| `is_correccion_libertad_amortizacion_vehiculos_permanente_disminucion` | OK | 3 members (01885, 01961, 01962), "Correcciones del ejercicio" for DA 18ª LIS (RDL 4/2024 vehicles/charging infrastructure). Permanent + two temporarias. Coherent current-exercise corrections. Name is slightly misleading (`_permanente_disminucion` while 2 of 3 members are temporarias) — note: acceptable because the section primary identifier is the permanent row and temporarias are subordinate. |
| `is_liquidacion_i_importe` | OUTLIER: 02311 and 03401 misassigned | Member 00501 (`liquidacion_i/resultado_cuenta_perdidas`) is correctly the P&L result amount. Members 02311 and 03401 are detail-correction rows (`liquidacion_i/detalle_correcciones`) — specifically an increase-correction for autoridades portuarias (art. 15n LIS) and a correction for the bank interest surcharge (DF 9ª Ley 7/2024). These belong to a `is_correccion_aumento` role, not a general `is_liquidacion_i_importe` container. |
| `is_correccion_adquisicion_participaciones_no_residentes_dt14_saldo_inicial` | OK | 2 members: aumento + disminucion rows for "Saldo pendiente a principio de ejercicio" for DT 14ª participaciones. Coherent pairing: opening-balance tracking always pairs both directions. |
| `is_correccion_amortizacion_intangible_fondo_comercio_saldo_inicial` | OK | 2 members: aumento + disminucion for "Saldo pendiente a principio de ejercicio" for art. 12.2 LIS intangibles/goodwill. Coherent. |
| `is_correccion_bases_negativas_grupo_fiscal_saldo_inicial` | OK | 2 members: aumento + disminucion opening-balance rows for BINs del grupo fiscal. Coherent. |
| `is_correccion_correcciones_entidades_normativa_foral_saldo_inicial` | OK | 2 members: aumento + disminucion saldo inicio. Coherent. |
| `is_correccion_deterioro_art13_1_provisiones_saldo_final` | OK | 2 members: aumento + disminucion "saldo pendiente a fin de ejercicio" for art. 13.1 / 14.1 / 14.2 LIS deterioro and provisions. Coherent closing-balance pair. |
| `is_correccion_deterioro_participaciones_dt16_temporaria_anteriores_aumento` | OK | 2 members (01863, 02240): DT 16ª.1-2 and DT 16ª.3 temporaria-anteriores aumento rows. Both track deterioro de valores participaciones under the transitional regime. Coherent; the two DT 16ª sub-articles are structurally equivalent. |
| `is_correccion_deterioro_valores_participaciones_entidades_saldo_final` | OK | 2 members: aumento + disminucion closing-balance for art. 15k LIS participaciones. Coherent. |
| `is_correccion_diferencias_amortizacion_contable_fiscal_saldo_final` | OK | 2 members: aumento + disminucion closing-balance for art. 12.1 LIS amortization differences. Coherent. |
| `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_final` | OK | 2 members: aumento + disminucion closing-balance for cooperativa eliminations. Coherent. |
| `is_correccion_libertad_amortizacion_investigacion_desarrollo_saldo_final` | OK | 2 members: aumento + disminucion closing-balance for art. 12.3c LIS I+D free amortisation. Coherent. |
| `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_saldo_final` | OK | 2 members: aumento + disminucion closing-balance for RDL 13/2010 free amortisation without employment maintenance. Coherent. |
| `is_correccion_limitacion_gastos_financieros_art16_saldo_inicial` | OK | 2 members: aumento + disminucion opening-balance for art. 16 LIS financial expense limitation. Coherent. |
| `is_correccion_operaciones_a_plazos_dt1_saldo_inicial` | OK | 2 members: aumento + disminucion opening-balance for DT 1ª LIS instalment sales. Coherent. |
| `is_correccion_operaciones_jurisdicciones_no_cooperativas_saldo_final` | OK | 2 members: aumento + disminucion closing-balance for art. 15g LIS non-cooperative jurisdictions. Coherent. |
| `is_correccion_otras_diferencias_imputacion_temporal_saldo_final` | OK | 2 members: aumento + disminucion closing-balance for art. 11 LIS timing differences. Coherent. |
| `is_correccion_reduccion_rentas_activos_intangibles_saldo_final` | OK | 2 members: aumento + disminucion closing-balance for art. 23 LIS IP box. Coherent. |
| `is_correccion_rentas_operaciones_quita_espera_saldo_final` | OK | 2 members: aumento + disminucion closing-balance for art. 11.13 LIS debt-forgiveness/moratorium rents. Coherent. |
| `is_correccion_reversion_deterioro_valores_dotaciones_aplicadas` | OK | 2 members (00990, 02810): DT 16ª.3 and DT 16ª.1-2 "dotaciones integradas en esta liquidación" rows for reversal of deterioro de valores. Coherent — both are reversal-of-prior-dotaciones amounts under DT 16ª. |
| `is_tributacion_conjunta_cuota` | SPLIT → `is_tributacion_conjunta_cuota_diferencial` + `is_tributacion_conjunta_abono_idi` | 2 members: 00474 is "Cuota diferencial – Araba/Álava" (net tax after withholdings), 01334 is "Abono deducciones I+D+i insuf. cuota – Araba/Álava" (cash refund for excess R&D credit). These are structurally different: one is a liquidación result, the other is a cash-transfer mechanism. Both happen to be money amounts for Álava but serve different tax concepts. |
| `is_cooperativa_cuota_integra_previa` | OK | Single member 01331, `liquidacion_iii/base_imponible`, "Cuota íntegra previa después de la reserva de nivelación – sólo sociedades cooperativas". Accurate and appropriately narrow. |
| `is_correccion_adquisicion_participaciones_no_residentes_dt14_temporaria_anteriores_disminucion` | OK | Single member 03339: DT 14ª LIS disminucion temporaria-anteriores row. Name fully precise. |
| `is_correccion_amortizacion_inmovilizado_actividades_economicas_permanente_aumento` | OK | Single member, art. 12.3b LIS amortisation of I+D-dedicated fixed assets. Name accurate. |
| `is_correccion_amortizacion_intangible_fondo_comercio_temporaria_ejercicio_aumento` | OK | Single member, art. 12.2 / DT 23ª temporaria ejercicio aumento. Accurate. |
| `is_correccion_aportaciones_entidades_sin_fines_lucro_temporaria_ejercicio_aumento` | OK | Single member, colaboración entidades sin fines lucrativos temporaria ejercicio aumento. Accurate. |
| `is_correccion_asimetrias_hibridas_art15bis_temporaria_ejercicio_aumento` | OK | Single member, art. 15bis LIS (excl. 15bis.12) temporaria ejercicio aumento. Accurate. |
| `is_correccion_cambio_criterios_contables_art11_3_temporaria_ejercicio_aumento` | OK | Single member, art. 11.3.2ª LIS accounting-policy change temporaria ejercicio aumento. Accurate. |
| `is_correccion_copa_america_barcelona_permanente_disminucion` | OK | Single member 02290, "XXXVII Copa América Barcelona (Ley 31/2022) – Disminución – Permanentes". Accurately names this specific event and direction. |
| `is_correccion_correcciones_entidades_normativa_foral_permanente_disminucion` | OK | Single member, foral-regime entity permanent-decrease correction. Accurate. |
| `is_correccion_detalle_correcciones_resultado_saldo_final_disminucion` | RENAME → `is_correccion_temporarias_saldo_final_disminuciones_futuras` | Single member 02310, section `detalle_correcciones_resultado/saldo_pendiente_de_correcciones_temporarias_a_fin`. Label: "Saldo pendiente de correcciones temporarias a fin de ejercicio – Disminuciones futuras". The current role name (`detalle_correcciones_resultado_saldo_final_disminucion`) correctly places it in the liquidación detail but undersells the key semantic: this is the aggregate future-decrease residual for temporary corrections. Rename improves searchability. |
| `is_correccion_deterioro_art13_1_no_afectado_temporaria_anteriores_disminucion` | OK | Single member, art. 13.1 LIS deterioro not caught by art. 11.12 / DT 1ª disminucion anteriores. Accurate. |
| `is_correccion_deterioro_valores_participaciones_entidades_temporaria_anteriores_disminucion` | OK | Single member, art. 15k LIS participaciones temporaria-anteriores disminucion. Accurate. |
| `is_correccion_deterioro_valores_representativos_temporaria_anteriores_disminucion` | OK | Single member, art. 13.2c LIS debt securities temporaria-anteriores disminucion. Accurate. |
| `is_correccion_deuda_tributaria_ajd_itp_temporaria_anteriores_disminucion` | OK | Single member, art. 15m LIS ITP/AJD tax debt temporaria-anteriores disminucion. Accurate. |
| `is_correccion_diferencias_amortizacion_contable_fiscal_temporaria_anteriores_disminucion` | OK | Single member, art. 12.1 LIS temporaria-anteriores disminucion. Accurate. |
| `is_correccion_disminucion_valor_criterio_valor_razonable_temporaria_anteriores_disminucion` | OK | Single member, art. 15l LIS fair-value decrease temporaria-anteriores disminucion. Accurate. |
| `is_correccion_efectos_valoracion_contable_diferente_fiscal_temporaria_anteriores_aumento` | OK | Single member, art. 20 LIS tax/book valuation difference temporaria-anteriores aumento. Accurate. |
| `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_anteriores_aumento` | OK | Single member, cooperativa elimination temporaria-anteriores aumento. Accurate. |
| `is_correccion_gastos_financieros_deudas_grupo_art15h_permanente_aumento` | OK | Single member, art. 15h LIS intra-group financial expenses permanent aumento. Accurate. |
| `is_correccion_libertad_amortizacion_inmovilizado_nuevo_temporaria_anteriores_aumento` | OK | Single member, art. 12.3e LIS new fixed-asset free amortisation temporaria-anteriores aumento. Accurate. |
| `is_correccion_libertad_amortizacion_investigacion_desarrollo_temporaria_anteriores_aumento` | OK | Single member, art. 12.3c LIS I+D free amortisation temporaria-anteriores aumento. Accurate. |
| `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_aumento` | OK | Single member, RDL 6/2010 / DT 13ª.2 with employment maintenance temporaria-anteriores aumento. Accurate. |
| `is_correccion_libertad_amortizacion_otros_art12_temporaria_anteriores_aumento` | OK | Single member, art. 12.3a/d + DA 16ª/17ª LIS other free amortisation categories temporaria-anteriores aumento. Accurate; `_otros_art12` is appropriately broad for the residual category. |
| `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_aumento` | OK | Single member, RDL 13/2010 / DT 13ª.2 without employment maintenance temporaria-anteriores aumento. Accurate. |
| `is_correccion_limitacion_gastos_financieros_art16_permanente_disminucion` | OK | Single member, art. 16 LIS financial expense limitation permanent disminucion. Accurate. |
| `is_correccion_multas_sanciones_art15c_permanente_aumento` | OK | Single member, art. 15c LIS fines and penalties permanent aumento. Accurate. |
| `is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_disminucion` | OK | Single member, art. 11.4 LIS instalment sales temporaria ejercicio disminucion. Accurate. |
| `is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_disminucion` | OK | Single member, DT 1ª LIS instalment sales temporaria ejercicio disminucion. Accurate. |
| `is_correccion_operaciones_aumento_capital_fondos_propios_permanente_disminucion` | OK | Single member, capitalisation of credits / equity increases permanent disminucion. Accurate. |
| `is_correccion_operaciones_jurisdicciones_no_cooperativas_permanente_disminucion` | OK | Single member, art. 15g LIS non-cooperative jurisdictions permanent disminucion. Accurate. |
| `is_correccion_operaciones_vinculadas_valor_mercado_permanente_disminucion` | OK | Single member, art. 18 LIS related-party arm's-length permanent disminucion. Accurate. |
| `is_correccion_otras_correcciones_resultado_permanente_disminucion` | OK | Single member, other P&L corrections permanent disminucion catch-all. Accurate for a residual bucket. |
| `is_correccion_otras_diferencias_imputacion_temporal_permanente_disminucion` | OK | Single member, art. 11 LIS other timing differences permanent disminucion. Accurate. |
| `is_correccion_pensiones_provisiones_no_deducibles_permanente_disminucion` | OK | Single member, art. 14.1 / 14.2 LIS pension / non-deductible provisions not in art. 11.12 permanent disminucion. Accurate. |
| `is_correccion_provisiones_no_deducibles_art14_permanente_aumento` | OK | Single member, art. 14 LIS other non-deductible provisions not in art. 11.12 permanent aumento. Accurate. |
| `is_correccion_reduccion_rentas_activos_intangibles_permanente_aumento` | OK | Single member, art. 23 LIS IP box permanent aumento. Accurate. |
| `is_correccion_reinversion_beneficios_extraordinarios_dt24_permanente_aumento` | OK | Single member 03341, DT 24ª LIS extraordinary-gain reinvestment permanent aumento. Accurate. |
| `is_correccion_rentas_negativas_art11_9_10_permanente_aumento` | OK | Single member, art. 11.9 and 11.10 LIS negative rents permanent aumento. Accurate. |
| `is_correccion_rentas_operaciones_quita_espera_permanente_aumento` | OK | Single member, art. 11.13 LIS quita/espera rents permanent aumento. Accurate. |
| `is_correccion_rentas_transmision_inmovilizado_autoridades_portuarias_permanente_disminucion` | OK | Single member, port-authority fixed-asset transfer rents permanent disminucion. Accurate. |
| `is_correccion_revalorizaciones_contables_art17_1_temporaria_ejercicio_disminucion` | OK | Single member, art. 17.1 LIS accounting revaluations temporaria ejercicio disminucion. Accurate. |
| `is_correccion_reversion_deterioro_elementos_temporaria_ejercicio_disminucion` | OK | Single member, art. 11.6 LIS reversal of asset impairment temporaria ejercicio disminucion. Accurate. |
| `is_correccion_transmisiones_lucrativas_societarias_permanente_aumento` | OK | Single member, art. 17 LIS non-consideration transfers (arm's-length step-up) permanent aumento. Accurate. |
| `is_correccion_valoracion_bienes_derechos_regimen_especial_temporaria_ejercicio_aumento` | OK | Single member, restructuring-regime valuation of assets temporaria ejercicio aumento. Accurate. |
| `is_deduccion_amortizacion_libre_disminucion` | RENAME → `is_correccion_amortizacion_libre_30pct_saldo_pendiente` | 2 members (02579–02580), section `deduccion_del_30_importe_gastos_de_amortiz_contabl/disminucion`. These are opening- and closing-balance carry rows for the 30% accounting-amortisation deduction (art. 7 Ley 16/2012). They are not period-applied deductions; they are balance tracking. The `_disminucion` suffix accurately reflects that this is the decrease-side, but calling it `deduccion` blurs it with the deducción-de-cuota family; it is a base correction carryforward. |
| `is_deduccion_donativos_base` | OK | Single member 00974, section `deduccion_donativos_entidades_sin_fines_lucro/base_de_la_deduccion`. Label is "Base de la deducción por donaciones del período impositivo". Accurate. |

## Summary counts

| verdict | count |
|---------|-------|
| OK | 73 |
| RENAME | 10 |
| SPLIT | 8 |
| OUTLIER | 1 (members 02311 and 03401 inside `is_liquidacion_i_importe`) |
| **Total roles reviewed** | **95** |

### Key patterns

- **Flow vs stock conflation (8 SPLITs):** Seven special-regime adjustment roles (capital-riesgo, entidad sin fines lucrativos, ERD libertad amortización, hidrocarburos, navieras, TFI, UTE) bundle both "correcciones del ejercicio" (flow) and "saldo pendiente inicio/fin" (stock) into a single role. These should be separated to avoid incorrect aggregation in the calculation engine.
- **Naming precision mismatches (10 RENAMEs):** Primarily affect: (a) roles that use the generic `_importe` suffix without capturing jurisdictional context (`is_conversion_aid_importe`), (b) the misattributed IDI label on a grand-total deducción-actividades casilla, (c) Copa América naming covering four distinct events, (d) a `_saldo_final` label on forward-carry balances, and (e) minor stutter/verbosity issues.
- **Single outlier injection (1 OUTLIER):** `is_liquidacion_i_importe` contains the correct P&L result casilla (00501) but was contaminated with two detail-correction increase rows (02311, 03401) that belong to specific `is_correccion_aumento` roles.
- The majority of granular `is_correccion_*` roles (73 OK) are correctly named with directional (`aumento`/`disminucion`), temporal (`temporaria`/`permanente`), vintage (`ejercicio`/`anteriores`), and balance (`saldo_inicial`/`saldo_final`) qualifiers that map precisely to AEAT section paths.
