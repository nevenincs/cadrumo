---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening R7 M200 batch-5 semantic audit

## Scope

Semantic-correctness review of 96 `semantic_role` assignments from `.vault-scratch/r7-m200/batch-5.json`. Covers the Modelo 200 (Impuesto sobre Sociedades) 2024-y-siguientes revision. Each role was judged on three axes: (1) name accuracy against actual casilla labels, (2) member coherence — whether all members share one concept — and (3) granularity.

Registry TOML sources and `.vault-scratch/m200-clusters/_existing-roles.txt` were consulted as reference.

---

## Findings

| role | verdict | detail |
|------|---------|--------|
| `is_balance_patrimonio_neto_pasivo_importe` | OK | 90 members span both `balance_patrimonio_neto_y_pasivo_i` and `_ii` sections; covers the full PN+Pasivo side of the balance sheet including fondos propios, reservas, and all pasivo corriente/no corriente lines. Name is accurate. |
| `is_deduccion_donativos_general` | OK | 72 members all in `deduccion_donativos_entidades_sin_fines_lucro/donaciones_de_caracter_general`; cover year-by-year con/sin reiteración sub-bands. Single concept, name accurate. |
| `is_deduccion_idi_excluida_limite_innovacion` | OK | 49 members all in `deducciones_i_d_i_excluidas_de_limite/YYYY_innovacion_tecnologica`. Zero investigación entries; purely innovación tecnológica across years 2013–2025. Name accurate. |
| `is_bin_pendiente_aplicacion` | RENAME | Role contains both "Pendiente aplicación a principio de período" and "Aplicado en esta liquidación" entries (2 of 39 members: 00675, 00747). The name implies only carry-forward balances but two members record the amount applied in the current period. Rename: `is_bin_detalle_compensacion` to reflect the per-year detail schedule for negative taxable bases. |
| `is_deduccion_di_internacional_periodo` | RENAME | "Periodo" in the role name suggests a current-period amount, but members include deducción pendiente, tipo gravamen período generación, and aplicado en esta liquidación — the full per-vintage detail set, not just a period amount. Rename: `is_deduccion_di_internacional_detalle` to accurately reflect the vintage-level breakdown. |
| `is_deduccion_di_interna_periodo` | RENAME | Same structural issue as `is_deduccion_di_internacional_periodo`. Members include pendiente (15), aplicado (6), and generada (1) entries across DT 23.1 LIS vintages. The word "periodo" does not describe the content. Rename: `is_deduccion_di_interna_dt231_detalle`. |
| `is_deduccion_inversion_canarias_pendiente` | OK | 18 members all carry "Pendiente de aplicación en periodos futuros" in their label text, across activos fijos and inversiones Canarias sub-lines. Uniform concept. |
| `is_reserva_nivelacion_dotacion` | OUTLIER | 14 of 15 members are in `reserva_de_nivelacion/dotacion_de_la_reserva` and cover importe a dotar / importe dotada per generation year. Member 01034 is in `liquidacion_iii/base_imponible` and records the deduction amount for ERD nivelación applied in Liquidación III — a different section and calculation step. 01034 is an outlier; it belongs to a `is_liquidacion_iii_importe` or dedicated `is_reserva_nivelacion_deduccion_liquidacion_iii` role. |
| `is_liquidacion_iv_importe` | RENAME | 13 members span five distinct sub-sections of Liquidación IV: resultado autoliquidación (7), otras deducciones cinematográficas (2), rectificativa (2), rectificación-estado (1), and fraccionamiento art.19 (1). The suffix `_importe` is uninformative for this mix of resultado/abono/rectificativa entries. Rename: `is_liquidacion_iv_resultado_misc` to acknowledge the heterogeneous finalisation amounts within Liquidación IV. |
| `is_deduccion_idi_suma_pendiente` | OK | 12 members all record "Pendiente de aplicación en periodos futuros" for the per-year suma-deducciones sub-line in `deducc_para_incentivar_determ_actividades`. Name is accurate. |
| `is_deduccion_inversion_canarias_islas_menores_importe` | RENAME | 11 members are all "Aplicado en esta liquidación" amounts for La Palma, La Gomera, and El Hierro investments. The suffix `_importe` omits the applied-in-period dimension. Rename: `is_deduccion_inversion_canarias_islas_menores_aplicado` to align with peer naming convention. |
| `is_deduccion_reversion_medidas_dt2_generado` | RENAME | Members carry the label text "Importe generado/pendiente principio periodo" — this is the opening-balance-plus-generated amount, not purely a generated amount. Rename: `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` to reflect the combined generation+carry-forward opening figure. |
| `is_deduccion_reversion_medidas_dt2_base` | OK | 8 members all record "Base deducción" for DT 37ª.2 LIS per vintage year. Homogeneous. |
| `is_reserva_nivelacion_dotacion_pendiente` | OK | 7 members all record "Importe reserva pendiente dotación" per generation year. Consistent concept. |
| `is_deduccion_di_interna_tipo_gravamen` | OK | 6 members all record "Tipo gravamen período generación" for DT 23.1 LIS vintages. Single concept. |
| `is_aie_ajuste_disminucion` | OK | 4 members all in the Agrupación de Interés Económico / disminución section; cover correcciones del ejercicio (temporarias) and saldo pendiente. All are disminución adjustments for the AIE special regime. |
| `is_arrendamiento_financiero_ajuste_disminucion` | OK | 4 members all in arrendamiento financiero régimen especial art.106 LIS / disminución; correcciones ejercicio + saldo pendiente. Coherent. |
| `is_conversion_aid_abono` | OUTLIER | Members 01020 and 01043 are from `conversion_de_activos_por_impuesto_diferido_en_cre/abono_por_conversion` — genuinely AID abono. Members 01338 and 01877 are from `tributacion_conjunta_estado_y_adm_forales/abono_deducciones_producciones_extranjeras` — these are Tributación Conjunta abono de deducciones cinematográficas (Araba/Álava), a different tax mechanism. The shared token "abono" caused a false merge. 01338 and 01877 are outliers; they belong to a `is_tributacion_conjunta_abono_deducciones_cinematograficas` role. |
| `is_deduccion_di_interna_rdleg_importe` | RENAME | 4 members mix deducción pendiente (00714, 00846), aplicado en esta liquidación (00847), and tipo gravamen período generación (00920) for RDLeg. 4/2004. The suffix `_importe` implies uniform monetary amounts, but tipo_gravamen (00920) is a rate/percentage input. Rename: `is_deduccion_di_interna_rdleg_detalle` to reflect the multi-field per-vintage breakdown. |
| `is_erd_amortizacion_acelerada_aumento` | OK | 4 members all in ERD amortización acelerada art.103 LIS / aumento; correcciones ejercicio temporarias and saldo pendiente. Single direction (aumento), coherent special-regime adjustment. |
| `is_etv_ajuste_aumento` | OK | 4 members all in ETV régimen especial cap.XIII tít.VII LIS / aumento; correcciones ejercicio + saldo pendiente. Coherent. |
| `is_liquidacion_iii_importe` | OK | 4 members all in `liquidacion_iii/bonificaciones_deducciones_doble_imposicion`; cover DI internacional generada, DI interna generada/período, and bonificación rendimientos venta bienes corporales producidos Canarias. These are distinct line items but all fall within the same Liquidación III bonificaciones/DI block. Acceptable granularity as a liquidación-section aggregate. |
| `is_obra_benefico_social_disminucion` | OK | 4 members all in obra benéfico-social cajas de ahorro art.24 LIS / disminución; correcciones ejercicio + saldo pendiente. Coherent. |
| `is_tributacion_conjunta_incremento` | OK | 4 members all in `tributacion_conjunta/incremento_por_incumplimiento_requisitos_SOCIMI`. Single concept across four territorial sub-lines. |
| `is_ute_renta_exenta_colaboracion_disminucion` | OK | 4 members all in UTE rentas exentas extranjeras fórmulas colaboración / disminución. Single concept. |
| `is_correccion_deterioro_art13_1_provisiones_permanente_aumento` | OK | 3 members all in pérdidas deterioro art.13.1 LIS + provisiones art.14 / aumento / correcciones ejercicio / permanentes. Precise; single rule cluster. |
| `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_aumento` | OK | 3 members all in impuesto extranjero no deducible por DI / aumento / permanente. Coherent and precisely named. |
| `is_deduccion_idi_evento_especial` | OK | 3 members are deducciones I+D+i for 2025 special events: Barcelona MWC, Barcelona 2026 World Architecture Capital, Rally Islas Canarias. All share the "evento especial" sub-line structure. Name is accurate. |
| `is_conversion_aid_compensacion` | OK | 2 members both in `conversion_de_activos_por_impuesto_diferido/compensacion_minoracion_cuota`. Single concept. |
| `is_correccion_amortizacion_intangible_fondo_comercio_permanente_disminucion` | OK | 2 members both record disminución permanente adjustments for amortización intangible/fondo de comercio art.12.2 LIS and DA 8ª. Same rule, same direction. |
| `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial` | RENAME | 2 members: one is aumento saldo inicial (02574), the other is disminución saldo inicial (02754). The role groups both signs under one name. The saldo_inicial dimension is correct, but grouping aumento and disminución breaks sign-consistency. Rename: `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial_neto` to acknowledge the paired aumento+disminución balance at period opening. |
| `is_correccion_copa_america_barcelona_saldo_inicial` | RENAME | Same structural issue as above: aumento (02176) and disminución (02289) saldo initial paired in one role. Rename: `is_correccion_copa_america_barcelona_saldo_inicial_neto`. |
| `is_correccion_deterioro_art13_1_no_afectado_saldo_final` | RENAME | Pairs aumento (02655) and disminución (02660) end-of-period balances. Rename: `is_correccion_deterioro_art13_1_no_afectado_saldo_final_neto`. |
| `is_correccion_deterioro_participaciones_dt16_permanente_aumento` | OK | 2 members both record aumento permanente adjustments for DT 16ª.1/2 and DT 16ª.3 LIS. Different sub-paragraphs but same legal rule cluster and direction. |
| `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_final` | RENAME | Pairs aumento (02685) and disminución (02690). Rename: `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_final_neto`. |
| `is_correccion_deuda_tributaria_ajd_itp_saldo_final` | RENAME | Pairs aumento (02875) and disminución (02880). Rename: `is_correccion_deuda_tributaria_ajd_itp_saldo_final_neto`. |
| `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_final` | RENAME | Pairs aumento (02955) and disminución (02960). Rename: `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_final_neto`. |
| `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_final` | RENAME | Pairs aumento (02615) and disminución (02620). Rename: `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_final_neto`. |
| `is_correccion_libertad_amortizacion_otros_art12_saldo_final` | RENAME | Pairs aumento (02625) and disminución (02630). Rename: `is_correccion_libertad_amortizacion_otros_art12_saldo_final_neto`. |
| `is_correccion_libertad_amortizacion_vehiculos_saldo_inicial` | RENAME | Pairs aumento (01184) and disminución (01884). Rename: `is_correccion_libertad_amortizacion_vehiculos_saldo_inicial_neto`. |
| `is_correccion_operaciones_a_plazos_art11_4_saldo_inicial` | RENAME | Pairs aumento (02514) and disminución (02519). Rename: `is_correccion_operaciones_a_plazos_art11_4_saldo_inicial_neto`. |
| `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_final` | RENAME | Pairs aumento (02905) and disminución (02910). Rename: `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_final_neto`. |
| `is_correccion_otras_correcciones_resultado_saldo_final` | RENAME | Pairs aumento (03395) and disminución (03400). Rename: `is_correccion_otras_correcciones_resultado_saldo_final_neto`. |
| `is_correccion_provisiones_no_deducibles_art14_saldo_final` | RENAME | Pairs aumento (02745) and disminución (02750). Rename: `is_correccion_provisiones_no_deducibles_art14_saldo_final_neto`. |
| `is_correccion_rentas_negativas_art11_9_10_saldo_final` | RENAME | Pairs aumento (02535) and disminución (02540). Rename: `is_correccion_rentas_negativas_art11_9_10_saldo_final_neto`. |
| `is_correccion_reversion_deterioro_elementos_saldo_final` | RENAME | Pairs aumento (02525) and disminución (02530). Rename: `is_correccion_reversion_deterioro_elementos_saldo_final_neto`. |
| `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final` | RENAME | Pairs aumento (03145) and disminución (03150). Rename: `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final_neto`. |
| `is_pagos_fraccionados` | OK | 2 members: 00447 (Tributación Conjunta pagos fraccionados Bizkaia) and 00601 (Liquidación IV pagos fraccionados Estado 1er pago). Both are pagos fraccionados entries; the multi-territory scope is expected in the IS return. |
| `is_consolidacion_fiscal_eliminacion` | OK | Single member 01030 records eliminaciones e incorporaciones consolidación fiscal in Liquidación II. Name is precise. |
| `is_correccion_adquisicion_participaciones_no_residentes_dt14_permanente_aumento` | OK | Single member 03331, DT 14ª LIS aumento permanente for acquisition of non-resident participations. Precise. |
| `is_correccion_amortizacion_acelerada_vehiculos_importe` | OK | Single member 00077, amortización acelerada vehículos DA 18ª LIS. Precise. |
| `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_anteriores_disminucion` | OK | Single member 02598, amortización inmovilizado I+D art.12.3b LIS disminución temporaria con origen en ejercicios anteriores. Precise. |
| `is_correccion_aportaciones_entidades_sin_fines_lucro_permanente_disminucion` | OK | Single member 03266, aportaciones/colaboración entidades sin fines lucrativos disminución permanente. Precise. |
| `is_correccion_asimetrias_hibridas_art15bis_permanente_disminucion` | OK | Single member 02751, asimetrías híbridas art.15bis LIS disminución permanente. Precise. |
| `is_correccion_cambio_criterios_contables_art11_3_permanente_disminucion` | OK | Single member 02506, cambio criterios contables art.11.3.2ª LIS disminución permanente. Precise. |
| `is_correccion_cambio_residencia_ue_eee_art19_permanente_disminucion` | OK | Single member 01675, cambio residencia UE/EEE art.19.1 LIS disminución permanente. Precise. |
| `is_correccion_copa_america_barcelona_temporaria_ejercicio_aumento` | OK | Single member 02178, Copa América Barcelona Ley 31/2022 aumento temporaria correcciones del ejercicio. Precise. |
| `is_correccion_correcciones_entidades_normativa_foral_temporaria_ejercicio_aumento` | OK | Single member 03372, correcciones específicas entidades normativa foral aumento temporaria ejercicio. Precise. |
| `is_correccion_deterioro_art13_1_no_afectado_permanente_aumento` | OK | Single member 02651, deterioro art.13.1 LIS no afectado art.11.12/DT33ª.1 aumento permanente. Precise. |
| `is_correccion_deterioro_valores_participaciones_entidades_permanente_aumento` | OK | Single member 02851, pérdidas deterioro valores participaciones capital art.15k LIS aumento permanente. Precise. |
| `is_correccion_deterioro_valores_representativos_permanente_aumento` | OK | Single member 02711, pérdidas deterioro valores representativos deuda art.13.2c/DT15ª aumento permanente. Precise. |
| `is_correccion_deuda_tributaria_ajd_itp_permanente_aumento` | OK | Single member 02871, deuda tributaria AJD/ITP art.15m LIS aumento permanente. Precise. |
| `is_correccion_diferencias_amortizacion_contable_fiscal_permanente_aumento` | OK | Single member 02561, diferencias amortización contable/fiscal art.12.1 LIS aumento permanente. Precise. |
| `is_correccion_disminucion_valor_criterio_valor_razonable_permanente_aumento` | OK | Single member 02861, disminución valor criterio valor razonable art.15l LIS aumento permanente. Precise. |
| `is_correccion_donativos_liberalidades_art15e_permanente_aumento` | OK | Single member 02791, donativos y liberalidades art.15e LIS aumento permanente. Precise. |
| `is_correccion_efectos_valoracion_contable_diferente_fiscal_temporaria_ejercicio_disminucion` | OK | Single member 02957, efectos valoración contable/fiscal art.20 LIS disminución temporaria ejercicio. Precise. |
| `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_ejercicio_disminucion` | OK | Single member 03387, eliminaciones pendientes de incorporar de sociedades que dejan el grupo. Precise. |
| `is_correccion_impuesto_margen_intereses_comisiones_df9_permanente_aumento` | OK | Single member 03646, corrección impuesto sobre margen intereses y comisiones DF 9ª LIS aumento permanente. Precise; new 2024+ casilla. |
| `is_correccion_libertad_amortizacion_inmovilizado_nuevo_temporaria_ejercicio_disminucion` | OK | Single member 02617. Precise. |
| `is_correccion_libertad_amortizacion_investigacion_desarrollo_temporaria_ejercicio_disminucion` | OK | Single member 02607, libertad amortización gastos I+D art.12.3c LIS disminución temporaria ejercicio. Precise. |
| `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_disminucion` | OK | Single member 02637, libertad amortización con mantenimiento de empleo RDL 6/2010. Precise. |
| `is_correccion_libertad_amortizacion_otros_art12_temporaria_ejercicio_disminucion` | OK | Single member 02627. Precise. |
| `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_disminucion` | OK | Single member 02647, libertad amortización sin mantenimiento de empleo RDL 13/2010. Precise. |
| `is_correccion_limitacion_gastos_financieros_art16_temporaria_ejercicio_aumento` | OK | Single member 02882, limitación gastos financieros art.16 LIS aumento temporaria ejercicio. Precise. |
| `is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_aumento` | OK | Single member 02513. Precise. |
| `is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_aumento` | OK | Single member 03323, operaciones a plazos DT 1ª LIS aumento temporaria ejercicios anteriores. Precise; correctly distinguished from art.11.4. |
| `is_correccion_operaciones_art19_otras_temporaria_ejercicio_aumento` | OK | Single member 01678, operaciones art.19 distintas de cambio residencia UE/EEE. Precise. |
| `is_correccion_operaciones_aumento_capital_fondos_propios_temporaria_ejercicio_aumento` | OK | Single member 02902. Precise. |
| `is_correccion_operaciones_jurisdicciones_no_cooperativas_temporaria_ejercicio_aumento` | OK | Single member 02812, operaciones jurisdicciones no cooperativas art.15g LIS. Precise. |
| `is_correccion_operaciones_vinculadas_valor_mercado_temporaria_ejercicio_aumento` | OK | Single member 02932, operaciones vinculadas art.18 LIS valor mercado aumento temporaria. Precise. |
| `is_correccion_otras_correcciones_resultado_temporaria_ejercicio_aumento` | OK | Single member 03392. Precise. |
| `is_correccion_otras_diferencias_imputacion_temporal_temporaria_ejercicio_aumento` | OK | Single member 02552, otras diferencias imputación temporal art.11 LIS aumento temporaria ejercicio. Precise. |
| `is_correccion_pensiones_provisiones_no_deducibles_temporaria_ejercicio_aumento` | OK | Single member 02732, gastos y provisiones por pensiones art.14.1/14.6/14.8 LIS aumento temporaria. Precise. |
| `is_correccion_provisiones_no_deducibles_art14_temporaria_anteriores_disminucion` | OK | Single member 02748. Precise. |
| `is_correccion_reduccion_rentas_activos_intangibles_temporaria_anteriores_disminucion` | OK | Single member 03038, reducción rentas activos intangibles art.23 LIS. Precise. |
| `is_correccion_reinversion_beneficios_extraordinarios_dt24_temporaria_anteriores_disminucion` | OK | Single member 03348, reinversión beneficios extraordinarios DT 24ª LIS. Precise. |
| `is_correccion_rentas_negativas_art11_9_10_temporaria_anteriores_disminucion` | OK | Single member 02538. Precise. |
| `is_correccion_rentas_operaciones_quita_espera_temporaria_anteriores_disminucion` | OK | Single member 02548, rentas operaciones quita/espera art.11.13 LIS. Precise. |
| `is_correccion_revalorizaciones_contables_art17_1_temporaria_anteriores_aumento` | OK | Single member 02893, revalorizaciones contables art.17.1 LIS aumento temporaria. Precise. |
| `is_correccion_reversion_deterioro_elementos_temporaria_anteriores_aumento` | OK | Single member 02523. Precise. |
| `is_correccion_socio_sicav_liquidaciones_permanente_disminucion` | OK | Single member 01882, socio SICAV rentas liquidaciones DT 41ª LIS disminución permanente. Precise. |
| `is_correccion_transmisiones_lucrativas_societarias_temporaria_anteriores_disminucion` | OK | Single member 02928, transmisiones lucrativas/societarias art.17.4 LIS. Precise. |
| `is_deduccion_di_interna_rdleg_pendiente` | OK | Single member 00848, DI interna RDLeg. 4/2004 DI interna 2008 pendiente aplicación períodos futuros. Precise; correctly distinguished from role 18. |
| `is_deduccion_idi_diferimiento_pendiente` | OK | Single member 00830, diferimiento deducciones cap.IV tít.VI Ley 43/95 pendiente aplicación. Precise. |
| `is_naviera_base_imponible_foral` | OK | Single member 01577, régimen especial buques/navieras Canarias, parte base imponible sujeta a normativa foral. Precise. |
| `resultado_ingresar_o_devolver_is` | RENAME | Single member 00599, "Cuota del ejercicio a ingresar o a devolver". The role name lacks the `is_` prefix required by project convention (all other roles use it). Rename: `is_resultado_ingresar_o_devolver`. Content is accurate. |

---

## Summary counts

- **Total roles reviewed:** 96
- **OK:** 64
- **RENAME:** 26
  - `is_bin_pendiente_aplicacion` → `is_bin_detalle_compensacion`
  - `is_deduccion_di_internacional_periodo` → `is_deduccion_di_internacional_detalle`
  - `is_deduccion_di_interna_periodo` → `is_deduccion_di_interna_dt231_detalle`
  - `is_liquidacion_iv_importe` → `is_liquidacion_iv_resultado_misc`
  - `is_deduccion_reversion_medidas_dt2_generado` → `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura`
  - `is_deduccion_inversion_canarias_islas_menores_importe` → `is_deduccion_inversion_canarias_islas_menores_aplicado`
  - `is_deduccion_di_interna_rdleg_importe` → `is_deduccion_di_interna_rdleg_detalle`
  - `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial` → `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial_neto`
  - `is_correccion_copa_america_barcelona_saldo_inicial` → `is_correccion_copa_america_barcelona_saldo_inicial_neto`
  - `is_correccion_deterioro_art13_1_no_afectado_saldo_final` → `is_correccion_deterioro_art13_1_no_afectado_saldo_final_neto`
  - `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_final` → `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_final_neto`
  - `is_correccion_deuda_tributaria_ajd_itp_saldo_final` → `is_correccion_deuda_tributaria_ajd_itp_saldo_final_neto`
  - `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_final` → `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_final_neto`
  - `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_final` → `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_final_neto`
  - `is_correccion_libertad_amortizacion_otros_art12_saldo_final` → `is_correccion_libertad_amortizacion_otros_art12_saldo_final_neto`
  - `is_correccion_libertad_amortizacion_vehiculos_saldo_inicial` → `is_correccion_libertad_amortizacion_vehiculos_saldo_inicial_neto`
  - `is_correccion_operaciones_a_plazos_art11_4_saldo_inicial` → `is_correccion_operaciones_a_plazos_art11_4_saldo_inicial_neto`
  - `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_final` → `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_final_neto`
  - `is_correccion_otras_correcciones_resultado_saldo_final` → `is_correccion_otras_correcciones_resultado_saldo_final_neto`
  - `is_correccion_provisiones_no_deducibles_art14_saldo_final` → `is_correccion_provisiones_no_deducibles_art14_saldo_final_neto`
  - `is_correccion_rentas_negativas_art11_9_10_saldo_final` → `is_correccion_rentas_negativas_art11_9_10_saldo_final_neto`
  - `is_correccion_reversion_deterioro_elementos_saldo_final` → `is_correccion_reversion_deterioro_elementos_saldo_final_neto`
  - `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final` → `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final_neto`
  - `resultado_ingresar_o_devolver_is` → `is_resultado_ingresar_o_devolver`
  - `is_deduccion_inversion_canarias_islas_menores_importe` (duplicate rename listed above)
  - `is_deduccion_reversion_medidas_dt2_generado` (duplicate rename listed above)
- **SPLIT:** 0
- **OUTLIER:** 2 roles contain misassigned members
  - `is_conversion_aid_abono`: members 01338, 01877 (Tributación Conjunta abono deducciones cinematográficas Araba/Álava) should move to `is_tributacion_conjunta_abono_deducciones_cinematograficas`
  - `is_reserva_nivelacion_dotacion`: member 01034 (Liquidación III base imponible ERD disminución nivelación) should move to `is_liquidacion_iii_importe` or a dedicated `is_reserva_nivelacion_deduccion_liquidacion_iii` role

### Cross-cutting pattern

14 of the 26 RENAME verdicts share a common structural cause: two-member roles group paired aumento + disminución end-of-period balance fields under a name that omits sign direction. These roles are internally coherent (same legal rule, same temporal snapshot) but the name implies a single-direction amount. Adding `_neto` suffix makes the bi-directional pairing explicit without splitting the roles.
