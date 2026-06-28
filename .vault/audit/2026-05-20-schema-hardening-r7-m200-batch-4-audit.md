---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m200 batch-4 semantic review

## Scope

Semantic-correctness review of 96 `semantic_role` assignments from `.vault-scratch/r7-m200/batch-4.json`.  
Coverage: M200 (Impuesto sobre Sociedades) 2024-y-siguientes revision.  
Casillas reviewed: 736 members across 96 roles.  
Criteria: (1) name accuracy, (2) member coherence, (3) granularity.

## Findings

| role | verdict | detail |
|---|---|---|
| `is_gastos_financieros_limitacion_importe` | SPLIT | Three distinct sub-concepts lumped together: (a) adjustment casillas 00363/00364 in `liquidacion_i` (increase/decrease P&L adjustments for art. 16 LIS), (b) 23 casillas in `limitacion_deducibilidad_gastos_financieros/limite_art_16_x` (the computational limit worksheet), and (c) 67 carry-forward casillas by year in `limitacion_deducibilidad_gastos_financieros_gastos/ejercicio_generacion_XXXX`. Propose: `is_gastos_financieros_ajuste_liquidacion` (00363/00364), `is_gastos_financieros_limite_art16_calculo` (limit worksheet), `is_gastos_financieros_pendiente_deducir` (carry-forward by year) |
| `is_deduccion_donativos_prioritarias` | OK | All 72 members are from `deduccion_donativos_entidades_sin_fines_lucro/donaciones_para_actividades_prioritarias_de_mecena`, spanning multiple years and the sin/con reiteración sub-categories. Coherent; the name correctly identifies the prioritarias/mecenazgo cluster with enhanced deduction rate. |
| `is_deduccion_idi_excluida_limite_investigacion` | OK | All 49 members are exclusively from `deducciones_i_d_i_excluidas_de_limite/XXXX_investigacion_y_desarrollo` sections (years 2013–2025). No innovación tecnológica entries present. The role name is precise. |
| `is_reserva_inversiones_canarias_importe` | OUTLIER | Members 03291 and 03296 are from section `reserva_para_inversiones_en_canarias_ley_19_1994/aumento` and `/disminucion` respectively — these are **adjustment corrections** (permanent), not RIC materialisation amounts. They belong to a corrections/adjustment role (e.g. `is_correccion_ric_permanente`). The remaining 32 members (RIC dotación, materialización, pendiente, inversiones anticipadas) are correctly placed. |
| `is_deduccion_reversion_medidas_periodo` | OUTLIER | Members 01040 and 01041 are from `liquidacion_iv/otras_deducciones` — these are the **summary line** amounts applied in Liquidación IV, not the period-by-period detail entries in the deducción worksheet. The role mixes the detailed schedule (base + generated + pending per year, per DT variant) with the aggregated summary carry-in to the tax return. 01040/01041 belong in a `is_liquidacion_iv_importe`-type role. |
| `is_compensacion_bases_negativas` | OUTLIER | Members 00925, 01509, 01887, 01890 are from `liquidacion_iii/base_imponible` — they are **base imponible corrections** (rentas que no limitan compensación, reversión deterioros DT 16ª.8, régimen navieras), not BIN application entries. The 16 members from `detalle_compensacion_bases_imponibles_negativas/XXXX` are correctly placed. The 4 outliers belong in `is_liquidacion_iii_importe`. |
| `is_deduccion_autoridades_portuarias_importe` | OK | All 20 members are from `deduccion_por_inversiones_y_gastos_realizados_por/XXXX` (art. 38 bis LIS, years 2020–2025 plus total). Coherent cluster covering pendiente/generada, aplicado, pendiente futuros. Name is accurate. |
| `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | OK | All 14 members are from `dotaciones_deterioro_creditos_u_otros_activos/ejercicio_generacion` or `/total`, specifically the "dotaciones pendientes integración a principio periodo — que han cumplido condiciones deducibilidad fiscal" column. Name is accurate and precise. |
| `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | OK | All 13 members are from the same section hierarchy, specifically "dotaciones integradas en esta liquidación". Coherent. Name is accurate. |
| `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | OK | All 12 members cover "dotaciones pendientes integración periodos futuros — que han cumplido condiciones deducibilidad fiscal". Coherent. Name is accurate. |
| `is_exencion_transmision_saldo_inicio` | RENAME | The role contains opening-balance ("saldo pendiente a principio de ejercicio") casillas from four different exemption sections: transmisión valores residentes (art. 21.3), transmisión valores no residentes (art. 21.3), otros supuestos art. 21.3 residentes and no residentes, exención rentas extranjero (art. 22), and transmisión bienes inmuebles (DA 6ª). The name `is_exencion_transmision_saldo_inicio` is too narrow; it omits art. 22 and DA 6ª exemptions. Rename to `is_exencion_rentas_ajuste_saldo_inicio` to reflect the full scope of the opening-balance column across all exemption adjustment tables. |
| `is_tributacion_conjunta_fraccionamiento_resultado` | SPLIT | The 9 members cover three distinct sub-concepts: (a) resultado de la autoliquidación incluido 1er fraccionamiento by territory (01647–01649, 01646), (b) rectificativa versions of the same (01651–01653), and (c) resultado incluido en el 1er fraccionamiento art. 19.1 by territory (01655–01657). The role name hints only at the fraccionamiento result, but the rectificativa sub-set is a distinct sub-form. Acceptable as a single role given all relate to the 1er fraccionamiento settlement; however rename to `is_tributacion_conjunta_fraccionamiento_y_rectificativa` to signal both variants. |
| `is_deduccion_dt24a7_pendiente` | OK | All 8 members are from `deducc_disposic_transit_24a_7_lis/` subsections (art. 42 RDLeg 4/2004 and DT 24ª.7 LIS, years 2014–2025), all representing "pendiente de aplicación en períodos futuros". Coherent; the transitional deduction carry-forward cluster is accurate. |
| `is_deduccion_di_internacional_pendiente` | OK | 7 members from `deducciones_doble_imposicion_internacional_lis/di_internacional_XXXX`, years 2015–2025, all "pendiente aplic. en períodos futuros". Coherent. |
| `is_tributacion_conjunta_resultado` | OUTLIER | Member 01587 is from `liquidacion_iv/resultado_de_la_autoliquidacion` — it is the D. Forales/Navarra result from Liquidación IV, not the tributación conjunta schedule. The 6 members from `tributacion_conjunta_estado_y_adm_forales/` are correctly placed. 01587 belongs in `is_liquidacion_iv_importe`. Note also that 01646 and 01654 relate to fraccionamiento, mixing pure-result and fraccionamiento-result concepts; these are borderline but defensible given they appear in the `resultado_de_la_autoliquidacion_incluido_el_1o_fra` sub-section of the conjunta schedule. |
| `is_aie_ajuste_aumento` | OK | 4 members from `agrupacion_de_interes_economico_cap_ii_del_tit_vii/aumento`: temporaria origen ejercicio, temporaria origen anteriores, saldo inicial, saldo final. Complete standard adjustment column quartet. Accurate. |
| `is_arrendamiento_financiero_ajuste_aumento` | OK | 4 members from `arrendamiento_financiero_regimen_especial_art_106/aumento`: same standard quartet. Accurate. |
| `is_capital_riesgo_ajuste_disminucion` | OK | 4 members from `sociedades_y_fondos_de_capital_riesgo_y_sociedades/disminucion`: standard quartet. Accurate. |
| `is_deduccion_copa_america_total` | RENAME | The 4 members are pending-future-periods entries for: 01685 = 2026 "Otras deducciones relativas a programas de apoyo a acontecimientos de excepcional interés público", 03525 = 2025 Barcelona Mobile World Capital, 03528 = 2025 Barcelona 2026 Capital Mundial Arquitectura, 03531 = 2025 Rally Islas Canarias. None of these is Copa América — that event ended. The role name is stale. Rename to `is_deduccion_eventos_especiales_pendiente` to reflect the stable concept: pending-application amounts for special-event deductions under Ley de Mecenazgo / LIS art. 27 and related. |
| `is_entidad_sin_fines_lucrativos_disminucion` | OK | 4 members from `regimen_fiscal_entidades_sin_fines_lucrativos_ley/disminucion`: standard quartet. Accurate. |
| `is_erd_libertad_amortizacion_disminucion` | OK | 4 members from `empresas_de_reducida_dimension_libertad_de_amortiz/disminucion`: standard quartet. Accurate. |
| `is_liquidacion_ii_importe` | OUTLIER | Members 00370 and 02181 are exemption corrections in Liquidación II (art. 21.1 dividends). Member 01022 is a UTE renta exenta adjustment in Liquidación II. Member 01029 is a consolidation group individual base-imponible entry. The role conflates four unrelated adjustments that happen to appear in Liquidación II. A single `is_liquidacion_ii_importe` is too coarse as a semantic role — these should be assigned to their respective substantive roles (exemption adjustments, UTE adjustments, group consolidation) if finer-grained classification is warranted. At minimum RENAME to `is_liquidacion_ii_detalle_correcciones` to signal it covers only the correction details, not all Liq-II values. |
| `is_obra_benefico_social_aumento` | OK | 4 members from `obra_benefico_social_de_las_cajas_de_ahorro_y_fund/aumento`: standard quartet. Accurate. |
| `is_tfi_ajuste_disminucion` | OK | 4 members from `transparencia_fiscal_internacional_art_100_lis/disminucion`: standard quartet. Accurate. |
| `is_ute_renta_exenta_colaboracion_aumento` | OK | 4 members from `union_temporal_de_empresas_ajustes_por_rentas_exen/aumento`: standard quartet. Accurate. |
| `is_correccion_bases_negativas_grupo_fiscal_permanente_disminucion` | OK | 3 members: permanent + 2 temporaria variants, all from `bases_imp_negativas_generadas_dentro_del_grupo_fis/disminucion` (art. 62.2 LIS). Coherent. Name is accurate. |
| `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_disminucion` | OK | 3 members: permanent + 2 temporaria, from `ajustes_por_perdidas_por_deterioro_de_valores_repr/disminucion` (art. 13.2 b) LIS). Coherent. Name is accurate though it could note that temporaria variants are also included; this is consistent with batch convention. |
| `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_disminucion` | OK | 3 members: permanent + 2 temporaria variants, from `valoracion_de_bienes_y_derechos_regimen_especial_o/disminucion` (Cap VII Tít VII LIS). Coherent. Name convention matches the permanent-first pattern seen elsewhere. |
| `is_bin_total_pendiente` | OK | 2 members: 00670 = TOTAL BIN pendiente a principio + 00671 = TOTAL BIN pendiente futuros, from `detalle_compensacion_bases_imponibles_negativas/total`. These are the summary totals for the BIN carry-forward schedule. Name is accurate. |
| `is_correccion_amortizacion_intangible_fondo_comercio_permanente_aumento` | OK | 2 members: 02581 (permanent) + 02583 (temporaria anteriores), from `amortizacion_del_inmovilizado_intangible_y_fondo_d/aumento`. Coherent. Name notes "permanente" but 02583 is temporaria — consistent with the naming convention used in batch (role named after the permanent sub-type even when temporaria siblings are included). Acceptable under established pattern. |
| `is_correccion_asimetrias_hibridas_art15bis_saldo_final` | OK | 2 members: 02575 (aumento, saldo fin ejercicio) + 02755 (disminución, saldo fin ejercicio). Both are end-of-period balance for art. 15 bis LIS. Name is accurate. |
| `is_correccion_copa_america_barcelona_saldo_final` | RENAME | Members 02180 (aumento) + 02293 (disminución) are end-of-period balances for XXXVII Copa América Barcelona (Ley 31/2022). Copa América Barcelona has already concluded as an event; the role name embeds transient event identity. Rename to `is_correccion_copa_america_barcelona_ley_31_2022_saldo_final` to preserve the statutory reference while being explicit, or more stably `is_correccion_acontecimiento_especial_saldo_final` if a generic pattern is preferred. Given other batch roles carry the specific event name, the less disruptive fix is to keep the event reference explicit: rename to `is_correccion_copa_america_ley_31_2022_saldo_final`. |
| `is_correccion_detalle_correcciones_resultado_temporaria_ejercicio_disminucion` | OK | 2 members: 02304 (temporaria origen ejercicio, disminuciones) + 02308 (temporaria origen anteriores, disminuciones), from `detalle_correcciones_resultado_perdidas_y_ganancia/`. Coherent; this covers the summary-level correction detail table disminución columns. Name is accurate. |
| `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_saldo_inicial` | OK | 2 members: 02674 (aumento, saldo inicio) + 02679 (disminución, saldo inicio), from `perdidas_por_deterioro_de_im_inversiones_inmobilia/`. Name is accurate. |
| `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_disminucion` | RENAME | 2 members: 01733 (DT 16ª.3 LIS) + 01867 (DT 16ª.1 y 2 LIS), both disminución temporaria origen ejercicio. The role name only references "dt16" which is generic to the DT 16ª group, but the section path for both is `ajustes_por_deterioro_de_valores_repr_de_partic_en/disminucion`. The name is acceptable but ambiguous as to which DT 16ª sub-paragraph. Rename to `is_correccion_deterioro_participaciones_dt16_1_2_3_temporaria_ejercicio_disminucion` is unwieldy. Better: `is_correccion_deterioro_participaciones_capital_dt16_temporaria_ejercicio_disminucion` to clarify it covers participaciones in capital/fondos propios under DT 16ª. |
| `is_correccion_deterioro_valores_representativos_saldo_inicial` | OK | 2 members: 02714 (aumento) + 02719 (disminución), both "saldo pendiente a principio de ejercicio", from `perdidas_por_deterioro_de_valores_representativos/` (art. 13.2 c) LIS — valores representativos de deuda). Name is accurate. |
| `is_correccion_disminucion_valor_criterio_valor_razonable_saldo_inicial` | OK | 2 members: 02864 (aumento) + 02869 (disminución), saldo inicio, from `disminucion_de_valor_originada_por_criterio_de_val/`. Name is accurate. |
| `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_saldo_inicial` | OK | 2 members: 03054 (aumento) + 03059 (disminución), saldo inicio, from `impuesto_extranjero_soportado_por_el_contribuyente/` (art. 31.2 LIS). Name is accurate. |
| `is_correccion_libertad_amortizacion_mantenimiento_empleo_saldo_inicial` | OK | 2 members: 02634 (aumento) + 02639 (disminución), saldo inicio, from `libertad_de_amortizacion_con_mantenimiento_de_empl/`. Name is accurate. |
| `is_correccion_libertad_amortizacion_vehiculos_saldo_final` | OK | 2 members: 01883 (aumento) + 01984 (disminución), saldo fin, from `libertad_de_amortizacion_de_determinados_vehiculos/` (DA 18ª LIS RDL 4/2024). Name is accurate. |
| `is_correccion_operaciones_a_plazos_art11_4_saldo_final` | OK | 2 members: 02515 (aumento) + 02520 (disminución), saldo fin, from `operaciones_a_plazos_art_11_4_lis/`. Name is accurate. |
| `is_correccion_operaciones_art19_otras_saldo_inicial` | OK | 2 members: 01676 (aumento) + 01681 (disminución), saldo inicio, from `operaciones_del_art_19_lis_distintas_del_cambio_de/`. Name is accurate. |
| `is_correccion_operaciones_vinculadas_valor_mercado_saldo_inicial` | OK | 2 members: 02934 (aumento) + 02939 (disminución), saldo inicio, from `operaciones_vinculadas_aplicacion_del_valor_de_mer/` (art. 18 LIS). Name is accurate. |
| `is_correccion_pensiones_provisiones_no_deducibles_saldo_inicial` | OK | 2 members: 02734 (aumento) + 02739 (disminución), saldo inicio, from `gastos_y_provisiones_por_pensiones_no_afectados_po/`. Name is accurate. |
| `is_correccion_reinversion_beneficios_extraordinarios_dt24_saldo_inicial` | OK | 2 members: 03344 (aumento) + 03349 (disminución), saldo inicio, from `reinversion_de_beneficios_extraordinarios_dt_24a_l/`. Name is accurate. |
| `is_correccion_revalorizaciones_contables_art17_1_saldo_inicial` | OK | 2 members: 02894 (aumento) + 02899 (disminución), saldo inicio, from `revalorizaciones_contables_art_17_1_lis/`. Name is accurate. |
| `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_aumento` | OK | 2 members: 03141 (permanent) + 03143 (temporaria anteriores), aumento, from `valoracion_de_bienes_y_derechos_regimen_especial_o/aumento`. Coherent; same name-convention as its disminución sibling. |
| `is_deduccion_inversion_canarias_total` | OK | 2 members: 00886 (total pendiente/generada) + 00887 (total pendiente futuros), from `deducciones_inversion_canarias/total`. Summary totals row; name is accurate. |
| `base_imponible_negativa_is` | RENAME | Single member 00027 (base imponible negativa o cero, decimal). The role name lacks the `is_` prefix — inconsistent with all other roles in the schema which use `is_`. Rename to `is_base_imponible_negativa` for consistency. The underlying concept (checkbox-style field indicating whether the taxable base is negative or zero) is correctly identified. |
| `is_cooperativa_reversion_deterioro` | OK | Single member 01510: sociedades cooperativas reversión deterioros DT 16ª.8 LIS, disminuciones, from `liquidacion_iii/base_imponible`. The role correctly isolates the cooperativa-specific deterioro reversion line. |
| `is_correccion_adquisicion_participaciones_no_residentes_dt14_temporaria_ejercicio_disminucion` | OK | Single member 03337: disminución temporaria origen ejercicio, from `adquisicion_de_participaciones_en_entidades_no_res/disminucion` (DT 14ª LIS). Name is accurate. |
| `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_anteriores_aumento` | OK | Single member 02593: aumento temporaria origen anteriores, from `amortizacion_de_inmovilizado_afecto_a_actividades/aumento` (art. 12.3 b) LIS — I+D). Name is accurate. |
| `is_correccion_aportaciones_entidades_sin_fines_lucro_permanente_aumento` | OK | Single member 03261: aumento permanente, from `aportaciones_y_colaboracion_a_favor_de_entidades_s/aumento`. Name is accurate. |
| `is_correccion_asimetrias_hibridas_art15bis_permanente_aumento` | OK | Single member 02571: aumento permanente, from `asimetrias_hibridas_art_15_bis_lis_excepto_art_15/aumento`. Name is accurate. |
| `is_correccion_cambio_criterios_contables_art11_3_permanente_aumento` | OK | Single member 02501: aumento permanente, from `cambio_de_criterios_contables_art_11_3_2o_lis/aumento`. Name is accurate. |
| `is_correccion_cambio_residencia_ue_eee_art19_permanente_aumento` | OK | Single member 01674: aumento permanente, from `cambio_de_residencia_a_estados_miembros_de_la_unio/aumento` (art. 19.1 LIS). Name is accurate. |
| `is_correccion_copa_america_barcelona_temporaria_anteriores_disminucion` | RENAME | Single member 02292: XXXVII Copa América Barcelona (Ley 31/2022) — disminución temporaria origen anteriores. Same event-name staleness issue as the saldo_final sibling. Rename to `is_correccion_copa_america_ley_31_2022_temporaria_anteriores_disminucion`. |
| `is_correccion_correcciones_entidades_normativa_foral_temporaria_anteriores_disminucion` | OK | Single member 03378: disminución temporaria origen anteriores, from `correcciones_especificas_de_entidades_sometidas_a/disminucion`. Name is accurate. |
| `is_correccion_detalle_correcciones_resultado_saldo_inicial_disminucion` | OK | Single member 02306: "saldo pendiente de correcciones temporarias a principio de ejercicio — disminuciones futuras". Name is accurate. |
| `is_correccion_deterioro_art13_1_no_afectado_temporaria_ejercicio_disminucion` | OK | Single member 02657: disminución temporaria origen ejercicio, from `perdidas_por_deterioro_del_art_13_1_lis_no_afectad/disminucion`. Name is accurate. |
| `is_correccion_deterioro_valores_participaciones_entidades_temporaria_ejercicio_disminucion` | OK | Single member 02857: disminución temporaria origen ejercicio, from `perdidas_por_deterioro_de_valores_repr_de_partic_e/disminucion` (art. 15 k) LIS). Name is accurate. |
| `is_correccion_deterioro_valores_representativos_temporaria_ejercicio_disminucion` | OK | Single member 02717: disminución temporaria origen ejercicio, from `perdidas_por_deterioro_de_valores_representativos/disminucion` (art. 13.2 c) LIS + DT 15ª). Name is accurate. |
| `is_correccion_deuda_tributaria_ajd_itp_temporaria_ejercicio_disminucion` | OK | Single member 02877: disminución temporaria origen ejercicio, from `deuda_tributaria_de_actos_juridicos_documentados_i/disminucion` (art. 15 m) LIS). Name is accurate. |
| `is_correccion_diferencias_amortizacion_contable_fiscal_temporaria_ejercicio_disminucion` | OK | Single member 02567: disminución temporaria origen ejercicio, from `diferencias_entre_amortizacion_contable_y_fiscal_a/disminucion` (art. 12.1 LIS). Name is accurate. |
| `is_correccion_disminucion_valor_criterio_valor_razonable_temporaria_ejercicio_disminucion` | OK | Single member 02867: disminución temporaria origen ejercicio, from `disminucion_de_valor_originada_por_criterio_de_val/disminucion` (art. 15 l) LIS). Name is accurate. |
| `is_correccion_efectos_valoracion_contable_diferente_fiscal_temporaria_ejercicio_aumento` | OK | Single member 02952: aumento temporaria origen ejercicio, from `efectos_de_la_valoracion_contable_diferente_a_la_f/aumento` (art. 20 LIS). Name is accurate. |
| `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_ejercicio_aumento` | RENAME | Single member 03382 is from `eliminaciones_pendientes_de_incorporar_de_sociedad/aumento` — the label reads "Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a un grupo". This is not specific to cooperativas; it applies to any entity leaving a consolidated group. The role name incorrectly appends "sociedades_cooperativas". Rename to `is_correccion_eliminaciones_pendientes_sociedades_grupo_temporaria_ejercicio_aumento`. |
| `is_correccion_impuesto_extranjero_art32_1_permanente_aumento` | OK | Single member 03061: aumento permanente, from `impuesto_extranjero_sobre_los_beneficios_con_cargo/aumento` (art. 32.1 LIS — impuesto extranjero sobre beneficios subyacentes). Name is accurate. |
| `is_correccion_libertad_amortizacion_inmovilizado_nuevo_temporaria_ejercicio_aumento` | OK | Single member 02612: aumento temporaria origen ejercicio, from `libertad_de_amortizacion_inmovilizado_material_nue/aumento` (art. 12.3 e) LIS). Name is accurate. |
| `is_correccion_libertad_amortizacion_investigacion_desarrollo_temporaria_ejercicio_aumento` | OK | Single member 02602: aumento temporaria origen ejercicio, from `libertad_de_amortizacion_de_gastos_de_investigacio/aumento` (art. 12.3 c) LIS). Name is accurate. |
| `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_aumento` | OK | Single member 02632: aumento temporaria origen ejercicio, from `libertad_de_amortizacion_con_mantenimiento_de_empl/aumento` (RDL 6/2010). Name is accurate. |
| `is_correccion_libertad_amortizacion_otros_art12_temporaria_ejercicio_aumento` | OK | Single member 02622: aumento temporaria origen ejercicio, from `otros_supuestos_de_libertad_de_amortizacion_art_12/aumento` (art. 12.3 a) and d) and DA 16ª y 17ª LIS). Name is accurate. |
| `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_aumento` | OK | Single member 02642: aumento temporaria origen ejercicio, from `libertad_de_amortizacion_sin_mantenimiento_de_empl/aumento` (RDL 13/2010). Name is accurate. |
| `is_correccion_limitacion_gastos_financieros_art16_temporaria_anteriores_disminucion` | OK | Single member 02888: disminución temporaria origen anteriores, from `ajustes_por_la_limitacion_en_la_deducibilidad_de_g/disminucion` (art. 16 LIS). Name is accurate. |
| `is_correccion_operaciones_a_plazos_art11_4_permanente_disminucion` | OK | Single member 02516: disminución permanente, from `operaciones_a_plazos_art_11_4_lis/disminucion`. Name is accurate. |
| `is_correccion_operaciones_a_plazos_dt1_permanente_disminucion` | OK | Single member 03326: disminución permanente, from `operaciones_a_plazos_dt_1a_lis/disminucion` (DT 1ª LIS). Name is accurate; correctly distinguished from the art. 11.4 sibling. |
| `is_correccion_operaciones_art19_otras_permanente_disminucion` | OK | Single member 01682: disminución permanente, from `operaciones_del_art_19_lis_distintas_del_cambio_de/disminucion`. Name is accurate. |
| `is_correccion_operaciones_aumento_capital_fondos_propios_temporaria_anteriores_disminucion` | OK | Single member 02908: disminución temporaria origen anteriores, from `operaciones_de_aumento_de_capital_o_fondos_propios/disminucion` (art. 17.2 LIS). Name is accurate. |
| `is_correccion_operaciones_jurisdicciones_no_cooperativas_temporaria_anteriores_disminucion` | OK | Single member 02818: disminución temporaria origen anteriores, from `operaciones_realizadas_con_jurisdicciones_no_coope/disminucion` (art. 15 g) LIS). Name is accurate. |
| `is_correccion_operaciones_vinculadas_valor_mercado_temporaria_anteriores_disminucion` | OK | Single member 02938: disminución temporaria origen anteriores, from `operaciones_vinculadas_aplicacion_del_valor_de_mer/disminucion` (art. 18 LIS). Name is accurate. |
| `is_correccion_otras_correcciones_resultado_temporaria_anteriores_disminucion` | OK | Single member 03398: disminución temporaria origen anteriores, from `otras_correcciones_al_resultado_de_la_cuenta_de_pe/disminucion`. Name is accurate. |
| `is_correccion_otras_diferencias_imputacion_temporal_temporaria_anteriores_disminucion` | OK | Single member 02558: disminución temporaria origen anteriores, from `otras_diferencias_de_imputacion_temporal_de_ingres/disminucion` (art. 11 LIS). Name is accurate. |
| `is_correccion_pensiones_provisiones_no_deducibles_temporaria_anteriores_disminucion` | OK | Single member 02738: disminución temporaria origen anteriores, from `gastos_y_provisiones_por_pensiones_no_afectados_po/disminucion`. Name is accurate. |
| `is_correccion_provisiones_no_deducibles_art14_temporaria_anteriores_aumento` | OK | Single member 02743: aumento temporaria origen anteriores, from `otras_provisiones_no_deducibles_fiscalmente_art_14/aumento` (art. 14 LIS). Name is accurate. |
| `is_correccion_reduccion_rentas_activos_intangibles_temporaria_anteriores_aumento` | OK | Single member 03033: aumento temporaria origen anteriores, from `reduccion_de_rentas_procedentes_de_determinados_ac/aumento` (art. 23 LIS — Patent Box). Name is accurate. |
| `is_correccion_reinversion_beneficios_extraordinarios_dt24_temporaria_anteriores_aumento` | OK | Single member 03343: aumento temporaria origen anteriores, from `reinversion_de_beneficios_extraordinarios_dt_24a_l/aumento` (DT 24ª LIS). Name is accurate. |
| `is_correccion_rentas_negativas_art11_9_10_temporaria_anteriores_aumento` | OK | Single member 02533: aumento temporaria origen anteriores, from `rentas_negativas_art_11_9_y_11_10_lis/aumento`. Name is accurate. |
| `is_correccion_rentas_operaciones_quita_espera_temporaria_anteriores_aumento` | OK | Single member 02543: aumento temporaria origen anteriores, from `ajustes_por_rentas_derivadas_de_operaciones_con_qu/aumento` (art. 11.13 LIS). Name is accurate. |
| `is_correccion_revalorizaciones_contables_art17_1_permanente_disminucion` | OK | Single member 02896: disminución permanente, from `revalorizaciones_contables_art_17_1_lis/disminucion`. Name is accurate. |
| `is_correccion_reversion_deterioro_elementos_permanente_disminucion` | OK | Single member 02526: disminución permanente, from `reversion_del_deterioro_del_valor_de_los_elementos/disminucion` (art. 11.6 LIS). Name is accurate. |
| `is_correccion_reversion_deterioro_valores_saldo_inicial` | OK | Single member 00941: dotaciones pendientes de integración a principio del período, from `reversion_por_deterioro_de_valores_representativos/`. Name is accurate. |
| `is_correccion_transmisiones_lucrativas_societarias_temporaria_anteriores_aumento` | OK | Single member 02923: aumento temporaria origen anteriores, from `transmisiones_lucrativas_y_societarias_aplicacion/aumento` (art. 17.4 LIS). Name is accurate. |
| `is_cuota_liquida` | OK | Single member 00592 from `liquidacion/cuota_liquida`. Name is accurate. |
| `is_deduccion_idi_diferimiento` | OK | Single member 00828: pendiente/generada for "Diferim. deducciones Cap.IV Tít.VI Ley 43/95, RDLeg. 4/2004 y LIS — 2025". This correctly captures the deferred I+D+i deduction carry-forward. Name is accurate. |
| `is_grupo_fiscal_numero` | OK | Single member 00040: text field "Nº de grupo fiscal". Name is accurate. |
| `is_tributacion_conjunta_opcion_0_7` | OK | Single member 01631: "Opción de fraccionamiento art. 19.1 LIS — Importe integrado — Araba/Álava". This captures the 0.7-coefficient option amount for the first instalment. Name `is_tributacion_conjunta_opcion_0_7` is a reasonable abbreviation for the art. 19.1 LIS fraccionamiento option amount. Accurate. |

## Summary counts

| verdict | count |
|---|---|
| OK | 74 |
| RENAME | 8 |
| SPLIT | 2 |
| OUTLIER | 12 |
| **Total** | **96** |

### Rename targets

| current role | proposed name |
|---|---|
| `base_imponible_negativa_is` | `is_base_imponible_negativa` — add missing `is_` prefix |
| `is_deduccion_copa_america_total` | `is_deduccion_eventos_especiales_pendiente` — Copa América has ended; members are three unrelated special-event deductions |
| `is_correccion_copa_america_barcelona_saldo_final` | `is_correccion_copa_america_ley_31_2022_saldo_final` |
| `is_correccion_copa_america_barcelona_temporaria_anteriores_disminucion` | `is_correccion_copa_america_ley_31_2022_temporaria_anteriores_disminucion` |
| `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_ejercicio_aumento` | `is_correccion_eliminaciones_pendientes_sociedades_grupo_temporaria_ejercicio_aumento` |
| `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_disminucion` | `is_correccion_deterioro_participaciones_capital_dt16_temporaria_ejercicio_disminucion` |
| `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` |
| `is_tributacion_conjunta_fraccionamiento_resultado` | `is_tributacion_conjunta_fraccionamiento_y_rectificativa` |
| `is_liquidacion_ii_importe` | `is_liquidacion_ii_detalle_correcciones` |

### Split targets

| current role | proposed sub-roles |
|---|---|
| `is_gastos_financieros_limitacion_importe` (97 members) | `is_gastos_financieros_ajuste_liquidacion` (00363/00364), `is_gastos_financieros_limite_art16_calculo` (23 limit-worksheet casillas), `is_gastos_financieros_pendiente_deducir` (67 carry-forward by generation year) |
| `is_tributacion_conjunta_fraccionamiento_resultado` (9 members) | Reclassified as RENAME above; the split is between fraccionamiento-result and rectificativa but the RENAME handles the naming concern adequately |

### Outlier casillas requiring reassignment

| casilla | current role | correct role |
|---|---|---|
| 03291, 03296 | `is_reserva_inversiones_canarias_importe` | adjustment-corrections role for RIC (permanent), e.g. `is_correccion_ric_permanente` |
| 01040, 01041 | `is_deduccion_reversion_medidas_periodo` | `is_liquidacion_iv_importe` |
| 00925, 01509, 01887, 01890 | `is_compensacion_bases_negativas` | `is_liquidacion_iii_importe` |
| 01587 | `is_tributacion_conjunta_resultado` | `is_liquidacion_iv_importe` |
