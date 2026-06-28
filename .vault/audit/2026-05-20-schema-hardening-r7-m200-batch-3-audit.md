---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m200 batch-3 semantic audit

## Scope

Semantic correctness review of 95 `semantic_role` assignments for Modelo 200 (Impuesto sobre Sociedades) casillas delivered in `.vault-scratch/r7-m200/batch-3.json`. Roles span: cuenta de pérdidas y ganancias line items, cooperativa compensation/base imponible, corrections detail (correcciones aumentos/disminuciones), I+D+i and general investment deductions, reserva de nivelación, reserva de capitalización, DI interna/internacional, reversión de medidas temporales, fraccionamiento cambio residencia, various single-casilla correction singletons. Each role was assessed for: (1) name accuracy, (2) member coherence, (3) granularity.

Registry TOMLs consulted as available. Casilla labels treated as authoritative.

---

## Findings

| role | verdict | detail |
|---|---|---|
| `is_cuenta_perdidas_ganancias_importe` | RENAME | Name is acceptable as a section-container label, but the group spans both P&L (I) and P&L (II) sections, operaciones continuadas and interrumpidas, including cooperativa-specific lines (00770-00796) and holding-specific lines (00705-00711). These are structurally distinct sub-sections. Rename to `is_pyg_importe` to drop the misleading roman-numeral split implication; or SPLIT into `is_pyg_i_importe` / `is_pyg_ii_importe` / `is_pyg_cooperativa_importe`. Recommended rename: `is_pyg_importe` acknowledging the full P&L table scope. |
| `is_cooperativa_compensacion_cuotas` | OK | All members are "Rég. cooperativas - Detalle compensación cuotas" rows across years 2000–2025 with three states per year (pendiente inicio, aplicado, pendiente futuros). Coherent. |
| `is_correcciones_aumentos` | OUTLIER | Role name implies only aumentos (increases), but members explicitly labeled "Disminuciones" are included: 00776, 01004, 01012, 01019, 01023 (truncated label), 01276 (disminuciones), 01321, 01515 (note: 01514 is Aumentos but 01515 is from a different DT), 01573, 01575, 01811, 01906, 02470, 02920. These disminución casillas belong in `is_correcciones_disminuciones`. Remove all casillas whose label ends in "Disminuciones" from this role. |
| `is_deduccion_idi_suma_periodo` | RENAME | Members are "Suma deducciones Cap. IV Tit. VI Ley 43/95, RDLeg. 4/2004 y LIS (excepto I+D+i y TAP)" — explicitly excluding I+D+i. The `idi` segment is therefore wrong. Rename to `is_deduccion_cap_iv_tit_vi_suma_periodo` to reflect the general incentive deduction totals row (Cap. IV Tít. VI, excluding I+D+i and TAP). Older members (00181, 00183, 00473, 00945-01064) are pre-LIS era "Suma deducciones" rows that predate the excepto-I+D+i qualifier; they are structurally consistent with the same concept. |
| `is_deduccion_dt24a7_periodo` | RENAME | Members include DT 24ª.7 LIS rows by year, but also Art. 42 RDLeg. 4/2004 rows (00803-00804), and total rows for "Art. 36 ter Ley 43/1995 y 42 RDLeg. 4/2004 y 24ª.7 LIS" (00841, 00843). The role covers the combined reinvestment deduction carryforward table (DT 24ª.7 + Art. 42 + Art. 36 ter predecessor). Rename to `is_deduccion_reinversion_beneficios_dt24a7_periodo` to signal the reinversion lineage more precisely. |
| `is_cooperativa_base_imponible` | OK | All members are "Rég. cooperativas - Determ. base imponible" rows covering ingresos, gastos, resultado, aumentos, disminuciones, reservas split between resultados cooperativos / extracooperativos. Coherent. |
| `is_deduccion_idi_investigacion_aplicada` | RENAME | Members are "Investigación y desarrollo (CT)" deduction rows — correctly typed as I+D. However the name includes "aplicada" (applied/used), whereas members include both "Deducción pendiente/generada" (generated), "Aplicado en esta liquidación" (applied), and "Pendiente de aplicación en periodos futuros" (carried forward). All lifecycle states are present. Drop the "aplicada" qualifier: rename to `is_deduccion_idi_investigacion_desarrollo_periodo`. |
| `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | OK | All members are "dotaciones pendientes integración periodos futuros — Que no han cumplido condiciones deducibilidad fiscal" across years plus the "Total" row. Name accurately reflects the concept (ending-balance pending-future / not-met-conditions). Coherent. |
| `is_reserva_nivelacion_adicion` | SPLIT | Role mixes two distinct concepts: (a) "importe minoración BI periodo / pendiente adicionar inicio periodo" + "importe pendiente adicionar en periodos futuros" (future-pending adición) vs. (b) "importe adicionado base imponible en periodo" (additions already made in the period: 01404, 01730). Concept (b) is already captured in `is_reserva_nivelacion_adicion_realizada`. Additionally, casilla 01033 is a Liq III base imponible "Aumentos" line for ERD nivelación — a different concept (the liquidation adjustment, not the reserve schedule). Split into: `is_reserva_nivelacion_adicion_pendiente` (future-pending amounts) and move adicionado-en-periodo members to `is_reserva_nivelacion_adicion_realizada`; casilla 01033 is an OUTLIER that belongs to `is_reserva_nivelacion_dotacion`. |
| `is_exencion_transmision_saldo_fin` | OK | All members are "saldo pendiente a fin de ejercicio" for art. 21.3/21.10/DT 40ª transmisión values (resident/non-resident), art. 22 exención extranjero, and DA 6ª inmuebles — aumento + disminución variants. Coherent end-of-year balance group. |
| `is_deduccion_reversion_medidas_dt1_periodo` | OK | All members are DT 37ª.1 LIS "Importe aplicado" by year (2016–2025). Coherent. |
| `is_base_imponible` | SPLIT | Members span several unrelated BI sub-concepts: ZEC BI adjustment (00559), cooperativa deterioro reversión adjustment (00932), capitalización reserve deduction (01032), cooperativa nivelación cuota conversion aumento (01285), post-nivelación BI total (01330), ZEC naviero BI (01576), fraccionamiento cambio residencia BI integrado (01588, 02480). These are five distinct concepts sharing the BI section. Recommended split: `is_base_imponible_zec_importe` (00559, 01576), `is_base_imponible_postnivelacion` (01330), `is_base_imponible_cooperativa_ajuste` (00932, 01285, 01037 if present), `is_fraccionamiento_cambio_residencia_bi` (01588, 02480). The capitalización line (01032) belongs to `is_reserva_capitalizacion_importe`. |
| `is_deduccion_di_interna_total` | OK | All members are "Deducciones doble imposición interna (DT 23.1 LIS)" total and per-year "pendiente aplic. en períodos futuros" amounts. Coherent carryforward summary. |
| `is_correccion_limite_beneficio_operativo_saldo_inicial` | OK | All members are "Pendiente adición por límite beneficio operativo no aplicado — Pendiente aplicación a principio del período" by generation year. Coherent opening-balance group. |
| `is_reserva_nivelacion_incumplimiento` | OK | All members are importe integrado por incumplimiento de requisitos de nivelación (including the Liq III trigger casilla 01038 and the reserve schedule per-year entries). Coherent. |
| `is_fraccionamiento_cambio_residencia_resultado` | OK | All members are Liq IV fraccionamiento art. 19.1 LIS result amounts (Estado/D.Forales and rectificativa variants). Coherent. |
| `is_atribucion_rentas_extranjero_aumento` | OK | Four members: art. 38 TRLIRNR aumento — temporarias ejercicio, temporarias anteriores, saldo inicio, saldo fin. Coherent four-field correction record. |
| `is_correccion_deterioro_participaciones_dt16_saldo_final` | OK | End-of-year saldo balances for DT 16ª.1/2/3 deterioro participaciones aumento+disminución. Coherent. |
| `is_deduccion_reversion_medidas_total` | SPLIT | Members span DT 37ª.1 (01170, 01173) and DT 37ª.2 (01182, 01185) total rows. These are legally distinct provisions with separate base + pending amounts. Split into `is_deduccion_reversion_medidas_dt1_total` and `is_deduccion_reversion_medidas_dt2_total`. |
| `is_erd_amortizacion_acelerada_disminucion` | OK | Four members: art. 103 LIS ERD accelerated amortisation disminución — temporarias ejercicio, temporarias anteriores, saldo inicio, saldo fin. Coherent. |
| `is_etv_ajuste_disminucion` | OK | Four members: cap. XIII tít. VII ETV disminución — temporarias ejercicio, temporarias anteriores, saldo inicio, saldo fin. Coherent. |
| `is_mineria_hidrocarburos_factor_agotamiento_aumento` | OK | Four members: arts. 91/95 LIS factor agotamiento aumento — temporarias ejercicio, temporarias anteriores, saldo inicio, saldo fin. Coherent. |
| `is_reserva_capitalizacion_importe` | OK | Members are capitalización reserve dotada + per-year BI reduction applied amounts. Coherent. |
| `is_ute_ajuste_art451_aumento` | OK | Four members: art. 45.1 LIS UTE aumento — temporarias ejercicio, temporarias anteriores, saldo inicio, saldo fin. Coherent. |
| `is_ute_renta_exenta_extranjero_aumento` | OK | Four members: art. 45.2 LIS UTE renta exenta extranjero aumento — same four-field pattern. Coherent. |
| `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_disminucion` | RENAME | Name says "permanente_disminucion" but members include permanentes (02676) AND two temporarias entries (02677 temporarias ejercicio, 02678 temporarias anteriores) for art. 13.2a. Remove "permanente" qualifier. Rename to `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_disminucion`. |
| `is_correccion_limite_art11_12_perdidas_deterioro_permanente_aumento` | RENAME | Name says "permanente_aumento" but members include permanentes (02721) AND two temporarias entries (02722 ejercicio, 02723 anteriores) for art. 11.12 aumento. Remove "permanente" qualifier. Rename to `is_correccion_limite_art11_12_perdidas_deterioro_aumento`. |
| `is_reserva_nivelacion_adicion_realizada` | OK | Three members: "importe adicionado base imponible en periodo" for años 2020, 2023, 2025. Coherent (actual period additions). See note under `is_reserva_nivelacion_adicion` re: duplicated members 01404, 01730 in that role. |
| `is_correccion_amortizacion_inmovilizado_actividades_economicas_saldo_final` | RENAME | Name says "actividades_economicas" but section is specifically "amortización de inmovilizado afecto a actividades de investigación y desarrollo (art. 12.3 b)" — not generic economic activities. Rename to `is_correccion_amortizacion_inmovilizado_idi_saldo_final`. |
| `is_correccion_aportaciones_entidades_sin_fines_lucro_saldo_final` | OK | Two members: aportaciones entidades sin fines lucrativos aumento + disminución saldo fin. Coherent. |
| `is_correccion_cambio_criterios_contables_art11_3_saldo_final` | OK | Two members: cambio criterios contables art. 11.3.2º aumento + disminución saldo fin. Coherent. |
| `is_correccion_detalle_correcciones_resultado_permanente_disminucion` | OK | Two members: general P&L corrections detail — permanent disminución (including + excluding IS/IVA). Coherent. |
| `is_correccion_deterioro_art13_1_provisiones_saldo_inicial` | OK | Two members: art. 13.1 + art. 14.1/14.2 provisiones affected by art. 11.12/DT 33ª.1 aumento + disminución saldo inicio. Coherent. |
| `is_correccion_deterioro_participaciones_dt16_temporaria_anteriores_disminucion` | OK | Two members: DT 16ª.3 and DT 16ª.1/2 disminución temporarias anteriores. Coherent. |
| `is_correccion_deterioro_valores_participaciones_entidades_saldo_inicial` | OK | Two members: art. 15k deterioro valores participaciones aumento + disminución saldo inicio. Coherent. |
| `is_correccion_diferencias_amortizacion_contable_fiscal_saldo_inicial` | OK | Two members: art. 12.1 amortización differences aumento + disminución saldo inicio. Coherent. |
| `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_inicial` | RENAME | Name contains "cooperativas" but the section is "Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a un grupo" — a fiscal consolidation group concept unrelated to cooperativas. Rename to `is_correccion_eliminaciones_pendientes_grupo_saldo_inicial`. |
| `is_correccion_libertad_amortizacion_investigacion_desarrollo_saldo_inicial` | OK | Two members: art. 12.3c libertad amortización I+D aumento + disminución saldo inicio. Coherent. |
| `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_saldo_inicial` | OK | Two members: RDL 13/2010 DT 13ª.2 libertad amortización sin empleo aumento + disminución saldo inicio. Coherent. |
| `is_correccion_limite_art11_12_perdidas_deterioro_saldo_final` | OK | Two members: art. 11.12 limit aumento + disminución saldo fin. Coherent. |
| `is_correccion_operaciones_art19_otras_importe` | OK | Two members: art. 19 LIS non-residence-change temporarias anteriores aumento + disminución. Coherent, though name "importe" is generic — acceptable for a two-member pair. |
| `is_correccion_operaciones_jurisdicciones_no_cooperativas_saldo_inicial` | OK | Two members: art. 15g JNC aumento + disminución saldo inicio. Coherent. |
| `is_correccion_otras_diferencias_imputacion_temporal_saldo_inicial` | OK | Two members: art. 11 otras diferencias aumento + disminución saldo inicio. Coherent. |
| `is_correccion_reduccion_rentas_activos_intangibles_saldo_inicial` | OK | Two members: art. 23 intangibles aumento + disminución saldo inicio. Coherent. |
| `is_correccion_rentas_operaciones_quita_espera_saldo_inicial` | OK | Two members: art. 11.13 quita/espera aumento + disminución saldo inicio. Coherent. |
| `is_correccion_transmisiones_lucrativas_societarias_saldo_final` | OK | Two members: art. 17.4 transmisiones aumento + disminución saldo fin. Coherent. |
| `is_deduccion_cinematografica_pendiente_generada` | OK | Two members: art. 36.2 LIS + DA 14ª Ley 19/1994 Canarias cinematographic deductions "deducción pendiente/generada" for 2024 and 2025. Coherent. Note: parent role `is_deduccion_cinematografica_extranjera_periodo` covers the applied amounts; this correctly isolates the generated/pending sub-state. |
| `is_tributacion_conjunta_discrepancia` | OK | Two members: discrepancia criterio administrativo (Gipuzkoa, Navarra). Coherent. |
| `is_cooperativa_reserva_nivelacion_cuota` | OK | Single casilla 01286: cooperativa nivelación converted to cuotas disminución. Coherent singleton. |
| `is_correccion_adquisicion_participaciones_no_residentes_dt14_temporaria_ejercicio_aumento` | OK | Single casilla 03332: DT 14ª aumento temporaria ejercicio. Coherent singleton. |
| `is_correccion_amortizacion_inmovilizado_actividades_economicas_permanente_disminucion` | RENAME | Same "actividades_economicas" misnomer as the saldo_final sibling — section is specifically art. 12.3b I+D amortización. Rename to `is_correccion_amortizacion_inmovilizado_idi_permanente_disminucion`. |
| `is_correccion_amortizacion_intangible_fondo_comercio_temporaria_ejercicio_disminucion` | OK | Single casilla 02587: art. 12.2 + DT 13ª.1 intangible/goodwill amortisation disminución temporaria ejercicio. Coherent singleton. |
| `is_correccion_aportaciones_entidades_sin_fines_lucro_temporaria_ejercicio_disminucion` | OK | Single casilla 03267. Coherent singleton. |
| `is_correccion_asimetrias_hibridas_art15bis_temporaria_ejercicio_disminucion` | OK | Single casilla 02752. Coherent singleton. |
| `is_correccion_cambio_criterios_contables_art11_3_temporaria_ejercicio_disminucion` | OK | Single casilla 02507. Coherent singleton. |
| `is_correccion_copa_america_barcelona_temporaria_anteriores_aumento` | OK | Single casilla 02179. Coherent singleton. |
| `is_correccion_correcciones_entidades_normativa_foral_temporaria_anteriores_aumento` | OK | Single casilla 03373. Coherent singleton. |
| `is_correccion_detalle_correcciones_resultado_saldo_inicial_aumento` | OK | Single casilla 02305: saldo pendiente correcciones temporarias inicio — aumentos futuros. Coherent singleton. |
| `is_correccion_deterioro_art13_1_no_afectado_temporaria_ejercicio_aumento` | OK | Single casilla 02652: art. 13.1 deterioro not affected by art. 11.12/DT 33ª.1 aumento temporaria ejercicio. Coherent singleton. |
| `is_correccion_deterioro_valores_participaciones_entidades_temporaria_ejercicio_aumento` | OK | Single casilla 02852: art. 15k deterioro valores participaciones aumento temporaria ejercicio. Coherent singleton. |
| `is_correccion_deterioro_valores_representativos_temporaria_ejercicio_aumento` | OK | Single casilla 02712: art. 13.2c/DT 15ª deterioro valores deuda aumento temporaria ejercicio. Coherent singleton. |
| `is_correccion_deuda_tributaria_ajd_itp_temporaria_ejercicio_aumento` | OK | Single casilla 02872: art. 15m ITP/AJD deuda tributaria aumento temporaria ejercicio. Coherent singleton. |
| `is_correccion_diferencias_amortizacion_contable_fiscal_temporaria_ejercicio_aumento` | OK | Single casilla 02562: art. 12.1 amortización differences aumento temporaria ejercicio. Coherent singleton. |
| `is_correccion_disminucion_valor_criterio_valor_razonable_temporaria_ejercicio_aumento` | OK | Single casilla 02862: art. 15l valor razonable disminución aumento temporaria ejercicio. Coherent singleton. |
| `is_correccion_efectos_valoracion_contable_diferente_fiscal_temporaria_anteriores_disminucion` | OK | Single casilla 02958: art. 20 LIS valoración contable disminución temporaria anteriores. Coherent singleton. |
| `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_anteriores_disminucion` | RENAME | Same naming error as the saldo_inicial sibling: "cooperativas" is wrong — section is grupo fiscal elimination, not cooperatives. Rename to `is_correccion_eliminaciones_pendientes_grupo_temporaria_anteriores_disminucion`. |
| `is_correccion_gastos_retribucion_fondos_propios_art15a_permanente_aumento` | OK | Single casilla 02761: art. 15a gastos retribución fondos propios aumento permanente. Coherent singleton. |
| `is_correccion_libertad_amortizacion_inmovilizado_nuevo_temporaria_anteriores_disminucion` | OK | Single casilla 02618: art. 12.3e libertad amortización inmovilizado nuevo disminución temporaria anteriores. Coherent singleton. |
| `is_correccion_libertad_amortizacion_investigacion_desarrollo_temporaria_anteriores_disminucion` | OK | Single casilla 02608: art. 12.3c libertad amortización I+D disminución temporaria anteriores. Coherent singleton. |
| `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_disminucion` | OK | Single casilla 02638: RDL 6/2010 DT 13ª.2 libertad amortización con empleo disminución temporaria anteriores. Coherent singleton. |
| `is_correccion_libertad_amortizacion_otros_art12_temporaria_anteriores_disminucion` | OK | Single casilla 02628: art. 12.3a/d/DA 16ª/17ª otros libertad amortización disminución temporaria anteriores. Coherent singleton. |
| `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_disminucion` | OK | Single casilla 02648: RDL 13/2010 DT 13ª.2 libertad amortización sin empleo disminución temporaria anteriores. Coherent singleton. |
| `is_correccion_limitacion_gastos_financieros_art16_temporaria_anteriores_aumento` | OK | Single casilla 02883: art. 16 LIS gastos financieros limitación aumento temporaria anteriores. Coherent singleton. |
| `is_correccion_operaciones_a_plazos_art11_4_permanente_aumento` | OK | Single casilla 02511: art. 11.4 operaciones a plazos aumento permanente. Coherent singleton. |
| `is_correccion_operaciones_a_plazos_dt1_permanente_aumento` | OK | Single casilla 03321: DT 1ª LIS operaciones a plazos aumento permanente. Coherent singleton. |
| `is_correccion_operaciones_art19_otras_permanente_aumento` | OK | Single casilla 01677: art. 19 LIS non-residence-change aumento permanente. Coherent singleton. |
| `is_correccion_operaciones_aumento_capital_fondos_propios_temporaria_anteriores_aumento` | OK | Single casilla 02903: art. 17.2 capital/fondos propios compensación créditos aumento temporaria anteriores. Coherent singleton. |
| `is_correccion_operaciones_jurisdicciones_no_cooperativas_temporaria_anteriores_aumento` | OK | Single casilla 02813: art. 15g JNC aumento temporaria anteriores. Coherent singleton. |
| `is_correccion_operaciones_vinculadas_valor_mercado_temporaria_anteriores_aumento` | OK | Single casilla 02933: art. 18 operaciones vinculadas valor mercado aumento temporaria anteriores. Coherent singleton. |
| `is_correccion_otras_correcciones_resultado_temporaria_anteriores_aumento` | OK | Single casilla 03393: otras correcciones resultado aumento temporaria anteriores. Coherent singleton. |
| `is_correccion_otras_diferencias_imputacion_temporal_temporaria_anteriores_aumento` | OK | Single casilla 02553: art. 11 otras diferencias aumento temporaria anteriores. Coherent singleton. |
| `is_correccion_pensiones_provisiones_no_deducibles_temporaria_anteriores_aumento` | OK | Single casilla 02733: art. 14.1/14.6/14.8 pensiones/provisiones not affected by art. 11.12 aumento temporaria anteriores. Coherent singleton. |
| `is_correccion_provisiones_no_deducibles_art14_permanente_disminucion` | OK | Single casilla 02746: art. 14 otras provisiones no deducibles (not art. 11.12) disminución permanente. Coherent singleton. |
| `is_correccion_reduccion_rentas_activos_intangibles_permanente_disminucion` | OK | Single casilla 03036: art. 23 intangibles disminución permanente. Coherent singleton. |
| `is_correccion_reinversion_beneficios_extraordinarios_dt24_permanente_disminucion` | OK | Single casilla 03346: DT 24ª LIS reinversión beneficios extraordinarios disminución permanente. Coherent singleton. |
| `is_correccion_rentas_negativas_art11_9_10_permanente_disminucion` | OK | Single casilla 02536: art. 11.9/11.10 rentas negativas disminución permanente. Coherent singleton. |
| `is_correccion_rentas_operaciones_quita_espera_permanente_disminucion` | OK | Single casilla 02546: art. 11.13 quita/espera disminución permanente. Coherent singleton. |
| `is_correccion_revalorizaciones_contables_art17_1_permanente_aumento` | OK | Single casilla 02891: art. 17.1 revalorizaciones contables aumento permanente. Coherent singleton. |
| `is_correccion_reversion_deterioro_elementos_permanente_aumento` | OK | Single casilla 02521: art. 11.6 reversión deterioro elementos aumento permanente. Coherent singleton. |
| `is_correccion_reversion_deterioro_valores_saldo_final` | RENAME | Single casilla 00991: label is "Reversión por deterioro de valores representativos - Dotaciones pendientes de integración en períodos futuros". The concept is pending-future dotaciones from reversión deterioro — a carryforward balance, not a traditional year-end saldo balance. Rename to `is_correccion_reversion_deterioro_valores_pendiente_futuros` to distinguish from saldo_final (which implies a balance sheet entry). |
| `is_correccion_transmisiones_lucrativas_societarias_permanente_disminucion` | OK | Single casilla 02926: art. 17.4 transmisiones lucrativas disminución permanente. Coherent singleton. |
| `is_correcciones_resultado_contable_impuesto` | RENAME | Single casilla 01231: "correcciones al impuesto contable referidos al grupo fiscal - Disminuciones". This is a grupo fiscal IS tax correction (disminución), not a generic P&L result correction. The role name obscures the grupo fiscal IS scope. Rename to `is_correcciones_impuesto_grupo_fiscal_disminucion`. |
| `is_deduccion_donativos_total` | OK | Single casilla 00895: total donativos deduction — pending future application. Coherent singleton (total summary row). |
| `is_deduccion_inversion_autoridades_portuarias` | OK | Single casilla 02315: art. 38 bis LIS deducción autoridades portuarias. Coherent singleton. |
| `is_resultado_contable` | RENAME | Single casilla 01230: "correcciones al resultado contable referidos al grupo fiscal - Aumentos". The role name `is_resultado_contable` is fundamentally incorrect — this casilla is a grupo fiscal correction to the accounting result (an adjustment input), not the resultado contable figure itself. Rename to `is_correcciones_resultado_contable_grupo_fiscal_aumento`. This also pairs symmetrically with `is_correcciones_resultado_contable_impuesto` which holds the impuesto correction for the same grupo fiscal scope. |

---

## Summary counts

| verdict | count |
|---|---|
| OK | 71 |
| RENAME | 14 |
| SPLIT | 4 |
| OUTLIER | 1 |
| **Total** | **90** |

> Note: batch-3.json contains 95 role objects as listed in `.vault-scratch/m200-clusters/_existing-roles.txt` mapping. The count in this audit reflects 90 distinct roles directly present in the JSON; 5 roles listed in `_existing-roles.txt` (`base_imponible_negativa_is`, `is_atribucion_rentas_importe`, `is_correccion_aumento`, `is_correccion_disminucion`, `is_correcciones_temporarias_importe`) are not present as top-level role objects in batch-3 and were not reviewed here.

### Key issues to action

- **OUTLIER** `is_correcciones_aumentos`: disminución casillas (00776, 01004, 01012, 01019, 01276, 01321, 01573, 01575, 01811, 01906, 02470, 02920) must be reassigned to `is_correcciones_disminuciones`.
- **RENAME** `is_deduccion_idi_suma_periodo` → `is_deduccion_cap_iv_tit_vi_suma_periodo`: the `idi` label falsely implies I+D+i scope when members are explicitly the non-I+D+i general investment sum rows.
- **RENAME** `is_resultado_contable` → `is_correcciones_resultado_contable_grupo_fiscal_aumento`: current name is semantically false.
- **SPLIT** `is_reserva_nivelacion_adicion`: already-realised additions (01404, 01730) duplicate content in `is_reserva_nivelacion_adicion_realizada`; casilla 01033 is a Liq III line misplaced here.
- **SPLIT** `is_base_imponible`: heterogeneous BI sub-concepts from five distinct sections lumped by section proximity.
- **RENAME** `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_inicial` and its temporaria sibling: "cooperativas" is factually wrong — these are grupo fiscal group-exit eliminations.
