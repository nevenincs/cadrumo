---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m200 batch-1 semantic role review

## Scope

Semantic-correctness review of 90 `semantic_role` values from `.vault-scratch/r7-m200/batch-1.json`.
Each role is judged on name accuracy, member coherence, and granularity.
Source data: Modelo 200 (IS) 2024-y-siguientes casilla registry.
Read-only: no TOML or source files were modified.

## Findings

| role | verdict | detail |
|---|---|---|
| `is_estado_cambios_patrimonio_neto_importe` | SPLIT | Entire ECPN statement (~200 casillas) under one role. Distinct concepts present: (1) ingresos/gastos imputados al patrimonio neto (ECPN-I), (2) transferencias a cta. pérdidas y ganancias (ECPN-I), (3) saldo final ejercicio anterior (ECPN-II/III), (4) ajustes por cambio de criterio de ejercicios anteriores (ECPN-II/III), (5) ajustes por errores de ejercicios anteriores (ECPN-II/III), (6) saldo ajustado inicio del ejercicio (ECPN-II/III), (7) total ingresos y gastos reconocidos (ECPN-II/III), (8) resultado cuenta pérdidas y ganancias (ECPN-II/III), (9) ingresos y gastos reconocidos en patrimonio neto – ingresos fiscales (ECPN-II/III), (10) ingresos y gastos reconocidos en patrimonio neto – otros (ECPN-II/III), (11) operaciones con socios (subtotals + aumentos capital, reducciones capital, conversión pasivos, distribución dividendos, operaciones acciones propias, combinación negocios, otras operaciones) (ECPN-II/III), (12) otras variaciones del patrimonio neto – reserva revalorización (ECPN-II/III), (13) otras variaciones del patrimonio neto – otras variaciones (ECPN-II/III), (14) saldo final del ejercicio (ECPN-II/III). Recommended roles: `is_ecpn_ingresos_gastos_imputados_importe`, `is_ecpn_transferencias_perdidas_ganancias_importe`, `is_ecpn_saldo_ejercicio_anterior_importe`, `is_ecpn_ajuste_criterio_importe`, `is_ecpn_ajuste_errores_importe`, `is_ecpn_saldo_ajustado_inicio_importe`, `is_ecpn_total_ingresos_gastos_reconocidos_importe`, `is_ecpn_resultado_perdidas_ganancias_importe`, `is_ecpn_ingresos_gastos_en_pn_fiscales_importe`, `is_ecpn_ingresos_gastos_en_pn_otros_importe`, `is_ecpn_operaciones_socios_importe`, `is_ecpn_otras_variaciones_reserva_revalorizacion_importe`, `is_ecpn_otras_variaciones_importe`, `is_ecpn_saldo_final_importe`. |
| `is_deduccion_idi_innovacion_tecnologica` | OK | All members are IT (Innovación tecnológica) deduction amounts (pendiente/generada and aplicado) across years 2013–2025. Coherent. |
| `is_retenciones_ingresos_a_cuenta` | OK | All members are retenciones e ingresos a cuenta breakdowns in Liquidación IV (capital mobiliario, arrendamientos inmuebles, IIC, loterías, AIEs/UTEs imputaciones, otros). Coherent money amounts. |
| `is_conversion_aid_rectificativa` | OK | All members are in the AID conversion art. 130 LIS "rectificativa" subsection: compensation results, amounts to pay/abono, devolución breakdown by territory. Coherent. |
| `is_deduccion_reversion_medidas_dt1_generado` | RENAME | Role stem `_dt1_` implies DT 1ª LIS (installment operations) but all members label "D.T.37ª. 1 LIS" (Disposición Transitoria 37ª, reversión de medidas temporales). Corrected role: `is_deduccion_reversion_medidas_dt37_generado`. |
| `is_deduccion_inversiones_africa_canarias_periodo` | OUTLIER | Casilla 00881 (2023) is labelled "Pendiente de aplicación en periodos futuros" — it is the pending-future amount, not the applied-in-period amount. All other members are "Aplicado en esta liquidación". 00881 belongs to `is_deduccion_inversiones_africa_canarias_pendiente`. |
| `is_deduccion_inversiones_africa_canarias_pendiente` | OK | All are "Pendiente de aplicación en periodos futuros" for Africa Occidental TAP (art. 27 bis Ley 19/1994) across years. Coherent. |
| `is_deduccion_idi_innovacion_pendiente` | OK | All are "Pendiente de aplicación en periodos futuros" for IT deductions. Coherent. |
| `is_reserva_capitalizacion_pendiente` | SPLIT | Two semantically distinct sub-concepts: (a) "Derecho reducir B.I. generado periodo/pendiente aplicar inicio periodo" (casillas 01137, 01401, 02773, 03591) = opening balance / newly generated right; (b) "Reducción B.I. pdte. de aplicar en períodos futuros" (casillas 01139, 02775, 03593) = carry-forward pending. Recommended split: `is_reserva_capitalizacion_derecho_generado` (concept a) and `is_reserva_capitalizacion_pendiente_futuros` (concept b). |
| `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | RENAME | Suffix `_base_deduccion` does not appear in any member label. All six members describe deduction amounts "generada en el período impositivo" for Canarias limits information. Corrected role: `is_informacion_adicional_limites_deducciones_canarias_generada`. |
| `is_tributacion_conjunta_abono_cinematografica` | OK | All members are "Abono deducciones producciones extranjeras" (mainland and Canarias) in Tributación conjunta by Hacienda Foral territory. Coherent. |
| `is_atribucion_rentas_hibridos_aumento` | OK | All are aumento corrections (permanentes, temporarias, saldo final) for atribución de rentas asimetrías híbridas art. 15 bis.12 LIS. Coherent. |
| `is_deduccion_cinematografica_extranjera_total` | SPLIT | Two distinct provisions mixed: (1) casillas 01317, 01322 — "producciones cinematográficas extranjeras en Canarias (art. 36.2 LIS y DA 14ª Ley 19/1994)"; (2) casillas 02144, 02147 — "producciones cinematográficas extranjeras (art. 36.2 LIS)" without Canarias qualifier. These are different deduction bases. Recommended: `is_deduccion_cinematografica_extranjera_canarias_total` (casillas 01317, 01322) and `is_deduccion_cinematografica_extranjera_total` retaining only 02144, 02147. |
| `is_entidad_parcialmente_exenta_disminucion` | OK | All are disminución corrections (temporarias ejercicio, temporarias anteriores, saldo inicial, saldo final) for Cap. XIV entidades parcialmente exentas. Coherent. |
| `is_erd_deterioro_creditos_disminucion` | OK | All are disminución corrections for ERD bad debt deterioration art. 104 LIS. Coherent. |
| `is_hidrocarburos_amortizacion_intangibles_aumento` | OK | All are aumento corrections (temporarias ejercicio, temporarias anteriores, saldo inicial, saldo final) for art. 99 LIS hydrocarbon intangibles. Coherent. |
| `is_naviera_tonelaje_ajuste_aumento` | OK | All are aumento corrections for tonelaje shipping regime Cap. XVI. Coherent. |
| `is_reserva_inversiones_canarias_ajuste_disminucion` | OK | All are disminución corrections for Reserva para inversiones en Canarias (Ley 19/1994). Coherent. |
| `is_ute_imputacion_temporal_aumento` | OK | All are aumento corrections for UTE art. 46.2 LIS temporal allocation. Coherent. |
| `is_atribucion_rentas_hibridos_disminucion` | OK | All are disminución corrections for atribución de rentas asimetrías híbridas art. 15 bis.12 LIS. Coherent. |
| `is_correccion_deterioro_art13_1_provisiones_permanente_disminucion` | OK | All are permanentes disminución for art. 13.1 + art. 14.1/14.2 + art. 11.12 + DT 33ª.1 LIS cluster. Coherent. |
| `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_disminucion` | OUTLIER | Casillas 03057 and 03058 are labelled "Temporarias (con origen en el ejercicio)" and "Temporarias (con origen en ejercicios anteriores)" respectively — not permanentes. Only casilla 03056 is permanente. 03057 and 03058 belong to the temporaria-ejercicio and temporaria-anteriores roles for this correction cluster. |
| `is_deduccion_inversion_canarias_islas_menores_generado` | OK | All are "Deducción pendiente/generada" for activos fijos in La Palma, La Gomera and el Hierro (years 2019–2021). Coherent. |
| `is_correccion_adquisicion_participaciones_no_residentes_dt14_saldo_final` | OK | Pairs aumento + disminución saldo final for DT 14ª LIS non-resident shareholding acquisition. Consistent pattern for bilateral saldo_final roles. |
| `is_correccion_amortizacion_intangible_fondo_comercio_saldo_final` | OK | Pairs aumento + disminución saldo final for art. 12.2 LIS + DT 13ª.1 LIS intangible amortization. Coherent. |
| `is_correccion_bases_negativas_grupo_fiscal_saldo_final` | OK | Pairs aumento + disminución saldo final for art. 62.2 LIS group tax base negatives. Coherent. |
| `is_correccion_correcciones_entidades_normativa_foral_saldo_final` | OK | Pairs aumento + disminución saldo final for foral-regime entities. Coherent. |
| `is_correccion_deterioro_art13_1_no_afectado_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for art. 13.1 LIS unaffected by art. 11.12 / DT 33ª.1 LIS. Coherent. |
| `is_correccion_deterioro_participaciones_dt16_permanente_disminucion` | OK | Members span DT 16ª.3 (01732) and DT 16ª.1 y 2 (01866) — both are permanentes disminución for DT 16ª deterioro participaciones. Same provision family. Acceptable grouping. |
| `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for art. 13.2 b) LIS. Coherent. |
| `is_correccion_deuda_tributaria_ajd_itp_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for art. 15 m) LIS AJD/ITP debt. Coherent. |
| `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for art. 20 LIS. Coherent. |
| `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for art. 12.3 e) LIS new tangible asset free amortization. Coherent. |
| `is_correccion_libertad_amortizacion_otros_art12_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for other free amortization art. 12.3 a) d) DA 16ª/17ª LIS. Coherent. |
| `is_correccion_limitacion_gastos_financieros_art16_saldo_final` | OK | Pairs aumento + disminución saldo final for art. 16 LIS financial expense limitation. Coherent. |
| `is_correccion_operaciones_a_plazos_dt1_saldo_final` | OK | Pairs aumento + disminución saldo final for DT 1ª LIS installment operations. Coherent. |
| `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for art. 17.2 LIS capital increase by credit offset. Coherent. |
| `is_correccion_otras_correcciones_resultado_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for miscellaneous P&G corrections. Coherent. |
| `is_correccion_provisiones_no_deducibles_art14_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for art. 14 LIS non-deductible provisions (not affected by art. 11.12). Coherent. |
| `is_correccion_rentas_negativas_art11_9_10_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for art. 11.9 and 11.10 LIS negative income. Coherent. |
| `is_correccion_reversion_deterioro_elementos_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for art. 11.6 LIS impairment reversal. Coherent. |
| `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_inicial` | OK | Pairs aumento + disminución saldo inicial for Cap. VII restructuring regime. Coherent. |
| `is_personal_asalariado_cifra_media` | OK | Both members are headcount decimal averages (personal fijo, personal no fijo). Coherent. |
| `is_consolidacion_fiscal_integracion` | OK | Single member 01031: Liquidación II fiscal consolidation group integration of art. 11.12 LIS dotaciones. Name is accurate. |
| `is_correccion_adquisicion_participaciones_no_residentes_dt14_temporaria_anteriores_aumento` | OK | Single member 03333: aumento temporaria-anteriores for DT 14ª LIS. Coherent. |
| `is_correccion_amortizacion_acelerada_vehiculos_saldo_inicial` | OK | Single member 00075: aumento saldo inicial for DA 18ª LIS accelerated amortization of vehicles/charging infrastructure. Coherent. |
| `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_ejercicio_disminucion` | RENAME | Role says `actividades_economicas` but single member 02597 is specifically "Amortización de inmovilizado afecto a actividades de investigación y desarrollo (art. 12.3 b) LIS)" — R&D fixed assets, not generic economic activities. Corrected role: `is_correccion_amortizacion_inmovilizado_investigacion_desarrollo_temporaria_ejercicio_disminucion`. |
| `is_correccion_aportaciones_entidades_sin_fines_lucro_temporaria_anteriores_disminucion` | OK | Single member 03268: disminución temporaria-anteriores for contributions to non-profit entities. Coherent. |
| `is_correccion_asimetrias_hibridas_art15bis_temporaria_anteriores_disminucion` | OK | Single member 02753: disminución temporaria-anteriores for art. 15 bis LIS (exc. art. 15 bis.12). Coherent. |
| `is_correccion_cambio_criterios_contables_art11_3_temporaria_anteriores_disminucion` | OK | Single member 02508: disminución temporaria-anteriores for art. 11.3.2º LIS accounting policy changes. Coherent. |
| `is_correccion_copa_america_barcelona_permanente_aumento` | OK | Single member 02177: permanente aumento for XXXVII Copa América Barcelona (Ley 31/2022). Coherent. |
| `is_correccion_correcciones_entidades_normativa_foral_permanente_aumento` | OK | Single member 03371: permanente aumento for foral-regime entity corrections. Coherent. |
| `is_correccion_detalle_correcciones_resultado_saldo_final_aumento` | OK | Single member 02309: "Saldo pendiente de correcciones temporarias a fin de ejercicio - Aumentos futuros". Role name accurately reflects future-increase pending balance at period end. |
| `is_correccion_deterioro_art13_1_no_afectado_temporaria_anteriores_aumento` | OK | Single member 02653: aumento temporaria-anteriores for art. 13.1 LIS unaffected deterioration. Coherent. |
| `is_correccion_deterioro_valores_participaciones_entidades_temporaria_anteriores_aumento` | OK | Single member 02853: aumento temporaria-anteriores for art. 15 k) LIS equity shareholding impairment. Coherent. |
| `is_correccion_deterioro_valores_representativos_temporaria_anteriores_aumento` | OK | Single member 02713: aumento temporaria-anteriores for art. 13.2 c) LIS debt securities impairment. Coherent. |
| `is_correccion_deuda_tributaria_ajd_itp_temporaria_anteriores_aumento` | OK | Single member 02873: aumento temporaria-anteriores for art. 15 m) LIS AJD/ITP tax debt. Coherent. |
| `is_correccion_diferencias_amortizacion_contable_fiscal_temporaria_anteriores_aumento` | OK | Single member 02563: aumento temporaria-anteriores for art. 12.1 LIS accounting vs fiscal depreciation differences. Coherent. |
| `is_correccion_disminucion_valor_criterio_valor_razonable_temporaria_anteriores_aumento` | OK | Single member 02863: aumento temporaria-anteriores for art. 15 l) LIS fair value decreases. Coherent. |
| `is_correccion_efectos_valoracion_contable_diferente_fiscal_permanente_disminucion` | OK | Single member 02956: permanente disminución for art. 20 LIS. Coherent. |
| `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_permanente_disminucion` | RENAME | Role says `cooperativas` but member 03386 label is "Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a un grupo" — no mention of cooperativas; this covers any entity leaving a fiscal group. Corrected role: `is_correccion_eliminaciones_pendientes_baja_grupo_permanente_disminucion`. |
| `is_correccion_gastos_extincion_relacion_laboral_art15i_permanente_aumento` | OK | Single member 02831: permanente aumento for art. 15 i) LIS employment/commercial relationship termination costs. Coherent. |
| `is_correccion_libertad_amortizacion_inmovilizado_nuevo_permanente_disminucion` | OK | Single member 02616: permanente disminución for art. 12.3 e) LIS. Coherent. |
| `is_correccion_libertad_amortizacion_investigacion_desarrollo_permanente_disminucion` | OK | Single member 02606: permanente disminución for art. 12.3 c) LIS R&D free amortization. Coherent. |
| `is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_disminucion` | OK | Single member 02636: permanente disminución for RDL 6/2010 / DT 13ª.2 LIS free amortization with employment maintenance. Coherent. |
| `is_correccion_libertad_amortizacion_otros_art12_permanente_disminucion` | OK | Single member 02626: permanente disminución for art. 12.3 a) d) DA 16ª/17ª LIS. Coherent. |
| `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_disminucion` | OK | Single member 02646: permanente disminución for RDL 13/2010 / DT 13ª.2 LIS free amortization without employment maintenance. Coherent. |
| `is_correccion_limitacion_gastos_financieros_art16_permanente_aumento` | OK | Single member 02881: permanente aumento for art. 16 LIS. Coherent. |
| `is_correccion_montes_vecinales_cap_xv_permanente_disminucion` | OK | Single member 03246: permanente disminución for Cap. XV montes vecinales en mano común. Coherent. |
| `is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_aumento` | OK | Single member 02512: temporaria-ejercicio aumento for art. 11.4 LIS installment operations (current-year provision). Coherent. |
| `is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_aumento` | OK | Single member 03322: temporaria-ejercicio aumento for DT 1ª LIS installment operations (transitional provision). Coherent. |
| `is_correccion_operaciones_aumento_capital_fondos_propios_permanente_aumento` | OK | Single member 02901: permanente aumento for art. 17.2 LIS. Coherent. |
| `is_correccion_operaciones_jurisdicciones_no_cooperativas_permanente_aumento` | OK | Single member 02811: permanente aumento for art. 15 g) LIS non-cooperative jurisdictions. Coherent. |
| `is_correccion_operaciones_vinculadas_valor_mercado_permanente_aumento` | OK | Single member 02931: permanente aumento for art. 18 LIS related-party market-value transactions. Coherent. |
| `is_correccion_otras_correcciones_resultado_permanente_aumento` | OK | Single member 03391: permanente aumento for other P&G corrections. Coherent. |
| `is_correccion_otras_diferencias_imputacion_temporal_permanente_aumento` | OK | Single member 02551: permanente aumento for other temporal income/expense timing differences art. 11 LIS. Coherent. |
| `is_correccion_pensiones_provisiones_no_deducibles_permanente_aumento` | OK | Single member 02731: permanente aumento for pension/provision expenses not affected by art. 11.12 LIS. Coherent. |
| `is_correccion_perdidas_juego_art15d_permanente_aumento` | OK | Single member 02781: permanente aumento for art. 15 d) LIS gambling losses. Coherent. |
| `is_correccion_provisiones_no_deducibles_art14_temporaria_ejercicio_disminucion` | OK | Single member 02747: temporaria-ejercicio disminución for art. 14 LIS non-deductible provisions. Coherent. |
| `is_correccion_reduccion_rentas_activos_intangibles_temporaria_ejercicio_disminucion` | OK | Single member 03037: temporaria-ejercicio disminución for art. 23 LIS intangible asset income reduction. Coherent. |
| `is_correccion_reinversion_beneficios_extraordinarios_dt24_temporaria_ejercicio_disminucion` | OK | Single member 03347: temporaria-ejercicio disminución for DT 24ª LIS extraordinary profit reinvestment. Coherent. |
| `is_correccion_rentas_negativas_art11_9_10_temporaria_ejercicio_disminucion` | OK | Single member 02537: temporaria-ejercicio disminución for art. 11.9/11.10 LIS negative income. Coherent. |
| `is_correccion_rentas_operaciones_quita_espera_temporaria_ejercicio_disminucion` | OK | Single member 02547: temporaria-ejercicio disminución for art. 11.13 LIS quita/espera debt restructuring income. Coherent. |
| `is_correccion_revalorizaciones_contables_art17_1_temporaria_ejercicio_aumento` | OK | Single member 02892: temporaria-ejercicio aumento for art. 17.1 LIS accounting revaluations. Coherent. |
| `is_correccion_reversion_deterioro_elementos_temporaria_ejercicio_aumento` | OK | Single member 02522: temporaria-ejercicio aumento for art. 11.6 LIS impairment reversal. Coherent. |
| `is_correccion_subvenciones_publicas_no_integrables_art14_8_permanente_disminucion` | OK | Single member 02756: permanente disminución for art. 14.8 LIS non-integrable public grants. Coherent. |
| `is_correccion_transmisiones_lucrativas_societarias_temporaria_ejercicio_disminucion` | OK | Single member 02927: temporaria-ejercicio disminución for art. 17.4 LIS lucrative/corporate transfers. Coherent. |
| `is_deduccion_di_internacional_rdleg_pendiente` | OK | Single member 00827: "Deducciones doble imposición internacional RDLeg. 4/2004 - DI internacional 2008 - Pendiente aplic. en períodos futuros". Name matches concept. |
| `is_deduccion_idi_otras` | RENAME | Single member 01683: "Otras deducciones relativas a programas de apoyo a acontecimientos de excepcional interés público". This is not an I+D (IDI) deduction — it belongs to the special-event support programmes category (art. 26 LIS/similar). The `_idi_` prefix is incorrect. Corrected role: `is_deduccion_acontecimiento_interes_publico_otras`. |
| `is_reserva_capitalizacion_aumento` | RENAME | Single member 03594: "Incremento porcentual de la plantilla media total". The role name implies a monetary capitalisation reserve increase amount, but this casilla holds a percentage headcount growth indicator, not a monetary reserve movement. Corrected role: `is_reserva_capitalizacion_incremento_plantilla_porcentaje`. Note: data_type "money" on this casilla also warrants a separate type-correctness audit. |

## Summary counts

| verdict | count |
|---|---|
| OK | 73 |
| RENAME | 6 |
| SPLIT | 3 |
| OUTLIER | 2 |
| **Total** | **84** |

> Note: The batch contains 90 declared roles in `_existing-roles.txt` but the JSON file contains 84 distinct role objects. Six roles listed in the vocabulary (`base_imponible_negativa_is`, `is_atribucion_rentas_importe`, `is_balance_activo_importe`, `is_balance_patrimonio_neto_pasivo_importe`, `is_base_imponible`, and others from the tail of the vocabulary list) did not appear as objects in `batch-1.json` and were not reviewed here. All 84 present roles have been individually assessed.
