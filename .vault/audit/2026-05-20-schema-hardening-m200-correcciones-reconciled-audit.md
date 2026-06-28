---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# M200 correcciones al resultado — schema-hardening role reconciliation

## Post-application correction (2026-05-20)

64 of the 695 casillas in this audit were **misrouted** into the
correcciones cluster by the section-to-cluster router and are NOT
result-corrections: 60 entity-identification checkboxes, 2
employee-headcount fields, the negative-base indicator `00027`, and
the fiscal-group number `00018`. Their `is_correccion_*` rows below
were applied then **reverted** to their correct pre-existing roles
(`is_identificacion_flag`, `is_personal_asalariado_cifra_media`,
`base_imponible_negativa_is`, `is_grupo_fiscal_numero`). The 631
genuine-correction casillas carry the reconciled scheme. Drift gate
green after the revert.

## Scope

This document reconciles the `correcciones al resultado contable` cluster of Modelo 200.
Two parallel agents produced incompatible role schemes: one using coarse generic roles
(`is_correccion_aumento` shared across unrelated casillas) and one using 214 hyper-specific
roles with no shared tokens. This audit assigns every one of the 695 casillas a single
canonical role under the scheme `is_correccion_<concepto>_<eje>`.

- Total casillas classified: **695**
- Distinct roles assigned: **395**
- Distinct concept slugs: **72**
- Distinct axis tokens: **24**
- Data-type divergences within any role: **0**

## Axis vocabulary

The following `<eje>` tokens are used across all 695 casillas. Every casilla in every
adjustment block that expresses the same field role uses the same token.

| eje token | definition |
|---|---|
| `dotaciones_aplicadas` | Dotaciones integrated (applied) into this tax return settlement |
| `dotaciones_conversion_activo_diferido` | Dotaciones applied via conversion to a deferred tax asset |
| `flag_regimen` | Boolean/decimal checkbox indicating the entity belongs to a particular tax regime or category (header identification field, not a monetary adjustment) |
| `importe` | General monetary amount (used for sub-sections with a single amount field not covered by the above axes) |
| `importe_base_deduccion` | Base amount used to calculate a deduction limit (informational monetary field within the additional-limits section) |
| `numero_grupo_fiscal` | Text field holding the fiscal group number (non-monetary identifier) |
| `permanente_aumento` | Permanent correction — increase to the accounting result (no future reversal expected) |
| `permanente_disminucion` | Permanent correction — decrease to the accounting result (no future reversal expected) |
| `personal_fijo` | Average headcount of permanent (fixed) employees during the period |
| `personal_no_fijo` | Average headcount of temporary (non-fixed) employees during the period |
| `saldo_final` | Outstanding balance at the end of the period (pending future integration) |
| `saldo_final_aumento` | Outstanding balance of pending future increases at the end of the period |
| `saldo_final_cumplido_condiciones` | Pending-integration balance at period end — dotaciones that have met deductibility conditions |
| `saldo_final_disminucion` | Outstanding balance of pending future decreases at the end of the period |
| `saldo_final_no_cumplido_condiciones` | Pending-integration balance at period end — dotaciones that have not yet met deductibility conditions |
| `saldo_inicial` | Outstanding balance at the beginning of the period (pending future integration) |
| `saldo_inicial_aumento` | Outstanding balance of pending future increases at the beginning of the period |
| `saldo_inicial_cumplido_condiciones` | Pending-integration balance at period start — dotaciones that have met deductibility conditions |
| `saldo_inicial_disminucion` | Outstanding balance of pending future decreases at the beginning of the period |
| `saldo_inicial_no_cumplido_condiciones` | Pending-integration balance at period start — dotaciones that have not yet met deductibility conditions |
| `temporaria_anteriores_aumento` | Temporary correction originating in a prior period — increase reversal in current period |
| `temporaria_anteriores_disminucion` | Temporary correction originating in a prior period — decrease reversal in current period |
| `temporaria_ejercicio_aumento` | Temporary correction originating in the current period — increase (will reverse in a future period) |
| `temporaria_ejercicio_disminucion` | Temporary correction originating in the current period — decrease (will reverse in a future period) |

## Concept slugs

Each `<concepto>` slug is derived from the casilla section path. One slug covers all
casillas in the same LIS adjustment block, regardless of axis.

| section key | concepto slug |
|---|---|
| `entidad_parcialmente_exenta` | `identificacion_entidad` |
| `sociedad_de_inversion_de_capital_variable_o_fondo` | `identificacion_entidad` |
| `sociedad_de_inversion_inmobiliaria_o_fondo_de_inve` | `identificacion_entidad` |
| `comunidades_titulares_de_montes_vecinales_en_mano` | `identificacion_entidad` |
| `incentivos_entidad_de_reducida_dimension_cap_xi_ti` | `identificacion_entidad` |
| `imputacion_en_base_imponible_rentas_positivas_art` | `identificacion_entidad` |
| `sociedad_de_inversion_de_capital_variable_que_no_c` | `identificacion_entidad` |
| `entidad_dominante_de_grupo_fiscal` | `identificacion_entidad` |
| `entidad_dependiente_de_grupo_fiscal` | `identificacion_entidad` |
| `entidad_de_tenencia_de_valores_extranjeros` | `identificacion_entidad` |
| `socimi` | `identificacion_entidad` |
| `agrupacion_europea_de_interes_economico` | `identificacion_entidad` |
| `entidad_zec_sin_consolidacion_fiscal` | `identificacion_entidad` |
| `cooperativa_protegida` | `identificacion_entidad` |
| `cooperativa_especialmente_protegida` | `identificacion_entidad` |
| `resto_cooperativas` | `identificacion_entidad` |
| `otros_regimenes_especiales` | `identificacion_entidad` |
| `establecimiento_permanente` | `identificacion_entidad` |
| `gran_empresa` | `identificacion_entidad` |
| `entidad_de_credito` | `identificacion_entidad` |
| `entidad_aseguradora` | `identificacion_entidad` |
| `entidad_inactiva` | `identificacion_entidad` |
| `base_imponible_negativa_o_cero` | `identificacion_entidad` |
| `regimen_especial_canarias` | `identificacion_entidad` |
| `transmision_elementos_patrimoniales_arts_27_2_d_y` | `identificacion_entidad` |
| `sociedades_desarrollo_industrial_regional` | `identificacion_entidad` |
| `regimen_especial_fusiones_escisiones_aportaciones` | `identificacion_entidad` |
| `sociedad_de_garantia_reciproca_o_de_reafianzamient` | `identificacion_entidad` |
| `opcion_de_fraccionamiento_art_19_1_lis` | `identificacion_entidad` |
| `entidad_dedicada_al_arrend_viviendas` | `identificacion_entidad` |
| `entidad_que_forma_parte_de_un_grupo_mercantil_art` | `identificacion_entidad` |
| `grupo_fiscal/claves_00009_o_00010` | `identificacion_entidad` |
| `obligacion_informacion_dt_5a_ris` | `identificacion_entidad` |
| `inversiones_anticipadas/reserva_inversiones_en_canarias_art_27_11_ley_19_1` | `identificacion_entidad` |
| `entidad_en_reg_atribuc_de_rentas_constituida_en_el` | `identificacion_entidad` |
| `entidades_sometidas_a_normativa_foral` | `identificacion_entidad` |
| `fondo_de_pensiones_real_decreto_legislativo_1_2002` | `identificacion_entidad` |
| `regimenes_especiales_de_normativa_foral` | `identificacion_entidad` |
| `mutua_de_seguros_o_mutualidad_de_prevision_social` | `identificacion_entidad` |
| `opcion_art_39_2_lis` | `identificacion_entidad` |
| `fondos_o_activos_de_titulizacion` | `identificacion_entidad` |
| `estados_de_cuentas_de_instituciones_de_inversion_c/entidades_que_utilicen_los_estados_de_cuentas_apli` | `identificacion_entidad` |
| `reg_fiscal_de_operac_de_aportacion_de_activos_a_sd` | `identificacion_entidad` |
| `tipo_de_gravamen_reducido_para_entidades_de_nueva` | `identificacion_entidad` |
| `bonificacion_personal_investigador_rd_475_2014` | `identificacion_entidad` |
| `entidad_patrimonial` | `identificacion_entidad` |
| `estados_de_cuentas_de_entidades_de_credito/entidades_que_sin_ser_entidades_de_credito_utilice` | `identificacion_entidad` |
| `tipo_gravamen_reducido_para_entidades_de_nueva_cre` | `identificacion_entidad` |
| `extincion_de_entidad` | `identificacion_entidad` |
| `opcion_del_0_7_de_la_cuota_integra_para_fines_soci` | `identificacion_entidad` |
| `contribuyente_que_financia_producciones_con_derech` | `identificacion_entidad` |
| `diocesis_provincia_religiosa_o_entidad_eclesiastic` | `identificacion_entidad` |
| `entidad_zec_en_consolidacion_fiscal` | `identificacion_entidad` |
| `uniones_federaciones_y_confederaciones_de_cooperat` | `identificacion_entidad` |
| `filial_grupo_multinacional_o_grupo_nacional_de_gra` | `identificacion_entidad` |
| `sociedad_matriz_ultima_grupo_multinacional_o_grupo` | `identificacion_entidad` |
| `tipo_gravamen_reducido_para_empresa_emergente` | `identificacion_entidad` |
| `regimen_especial_de_disolucion_y_liquidacion_de_si` | `identificacion_entidad` |
| `regimen_especial_illes_balears` | `identificacion_entidad` |
| `inversiones_anticipadas_reserva_inversiones_en_ill` | `identificacion_entidad` |
| `tipo_gravamen_reducido_para_entidades_con_incn_per` | `identificacion_entidad` |
| `opcion_art_39_3_lis` | `identificacion_entidad` |
| `personal_asalariado_cifra_media_del_ejercicio_pers` | `personal_asalariado` |
| `amortizacion_acelerada_de_determinados_vehiculos_y/aumento` | `amortizacion_acelerada_vehiculos` |
| `reversion_por_deterioro_de_valores_representativos/dotaciones_pendientes_de_integracion_a_principio_d` | `reversion_deterioro_valores` |
| `reversion_por_deterioro_de_valores_representativos/dotaciones_integradas_en_esta_liquidacion_dt_16a_3` | `reversion_deterioro_valores` |
| `reversion_por_deterioro_de_valores_representativos/dotaciones_pendientes_de_integracion_en_periodos_f` | `reversion_deterioro_valores` |
| `reversion_por_deterioro_de_valores_representativos/dotaciones_integradas_en_esta_liquidacion_dt_16a_1` | `reversion_deterioro_valores` |
| `ajustes_por_deterioro_de_valores_repr_de_partic_en/disminucion` | `deterioro_participaciones_dt16` |
| `ajustes_por_deterioro_de_valores_repr_de_partic_en/aumento` | `deterioro_participaciones_dt16` |
| `pendiente_adicion_por_limite_beneficio_operativo_n/ejercicio_generacion_2022` | `limite_beneficio_operativo` |
| `pendiente_adicion_por_limite_beneficio_operativo_n/ejercicio_generacion_2023` | `limite_beneficio_operativo` |
| `pendiente_adicion_por_limite_beneficio_operativo_n/ejercicio_generacion_2020` | `limite_beneficio_operativo` |
| `pendiente_adicion_por_limite_beneficio_operativo_n/ejercicio_generacion_2021` | `limite_beneficio_operativo` |
| `pendiente_adicion_por_limite_beneficio_operativo_n/ejercicio_generacion_2025` | `limite_beneficio_operativo` |
| `pendiente_adicion_por_limite_beneficio_operativo_n/ejercicio_generacion_2024` | `limite_beneficio_operativo` |
| `dotaciones_deterioro_creditos_u_otros_activos/ejercicio_generacion` | `dotaciones_deterioro_creditos` |
| `dotaciones_deterioro_creditos_u_otros_activos/total` | `dotaciones_deterioro_creditos` |
| `libertad_de_amortizacion_de_determinados_vehiculos/aumento` | `libertad_amortizacion_vehiculos` |
| `libertad_de_amortizacion_de_determinados_vehiculos/disminucion` | `libertad_amortizacion_vehiculos` |
| `cambio_de_residencia_a_estados_miembros_de_la_unio/aumento` | `cambio_residencia_ue_eee_art19` |
| `cambio_de_residencia_a_estados_miembros_de_la_unio/disminucion` | `cambio_residencia_ue_eee_art19` |
| `operaciones_del_art_19_lis_distintas_del_cambio_de/saldo_pendiente_a_principio_de_ejercicio` | `operaciones_art19_otras` |
| `operaciones_del_art_19_lis_distintas_del_cambio_de/aumento` | `operaciones_art19_otras` |
| `operaciones_del_art_19_lis_distintas_del_cambio_de/disminucion` | `operaciones_art19_otras` |
| `socio_sicav_rentas_derivadas_de_liquidaciones_de_s/disminucion` | `socio_sicav_liquidaciones` |
| `informacion_adicional_para_el_calculo_de_limites_d/2025_financiador_deduccion_por_producciones_cinema` | `info_adicional_limites_deducciones` |
| `informacion_adicional_para_el_calculo_de_limites_d/2025_financiador_deduccion_por_espectaculos_en_viv` | `info_adicional_limites_deducciones` |
| `informacion_adicional_para_el_calculo_de_limites_d/2025_deduccion_por_investigacion_y_desarrollo_en_c` | `info_adicional_limites_deducciones` |
| `informacion_adicional_para_el_calculo_de_limites_d/2025_deduccion_por_innovacion_tecnologica_en_canar` | `info_adicional_limites_deducciones` |
| `informacion_adicional_para_el_calculo_de_limites_d/2025_productor_deduccion_por_producciones_cinemato` | `info_adicional_limites_deducciones` |
| `informacion_adicional_para_el_calculo_de_limites_d/2025_productor_deduccion_por_espectaculos_en_vivo` | `info_adicional_limites_deducciones` |
| `xxxvii_copa_america_barcelona_ley_31_2022/aumento` | `copa_america_barcelona` |
| `xxxvii_copa_america_barcelona_ley_31_2022/disminucion` | `copa_america_barcelona` |
| `detalle_correcciones_resultado_perdidas_y_ganancia/correcciones_al_resultado_de_la_cuenta_de_perdidas` | `detalle_correcciones_resultado` |
| `detalle_correcciones_resultado_perdidas_y_ganancia/saldo_pendiente_de_correcciones_temporarias_a_prin` | `detalle_correcciones_resultado` |
| `detalle_correcciones_resultado_perdidas_y_ganancia/saldo_pendiente_de_correcciones_temporarias_a_fin` | `detalle_correcciones_resultado` |
| `cambio_de_criterios_contables_art_11_3_2o_lis/aumento` | `cambio_criterios_contables_art11_3` |
| `cambio_de_criterios_contables_art_11_3_2o_lis/disminucion` | `cambio_criterios_contables_art11_3` |
| `operaciones_a_plazos_art_11_4_lis/aumento` | `operaciones_a_plazos_art11_4` |
| `operaciones_a_plazos_art_11_4_lis/disminucion` | `operaciones_a_plazos_art11_4` |
| `reversion_del_deterioro_del_valor_de_los_elementos/aumento` | `reversion_deterioro_elementos` |
| `reversion_del_deterioro_del_valor_de_los_elementos/disminucion` | `reversion_deterioro_elementos` |
| `rentas_negativas_art_11_9_y_11_10_lis/aumento` | `rentas_negativas_art11_9_10` |
| `rentas_negativas_art_11_9_y_11_10_lis/disminucion` | `rentas_negativas_art11_9_10` |
| `ajustes_por_rentas_derivadas_de_operaciones_con_qu/aumento` | `rentas_operaciones_quita_espera` |
| `ajustes_por_rentas_derivadas_de_operaciones_con_qu/disminucion` | `rentas_operaciones_quita_espera` |
| `otras_diferencias_de_imputacion_temporal_de_ingres/aumento` | `otras_diferencias_imputacion_temporal` |
| `otras_diferencias_de_imputacion_temporal_de_ingres/disminucion` | `otras_diferencias_imputacion_temporal` |
| `diferencias_entre_amortizacion_contable_y_fiscal_a/aumento` | `diferencias_amortizacion_contable_fiscal` |
| `diferencias_entre_amortizacion_contable_y_fiscal_a/disminucion` | `diferencias_amortizacion_contable_fiscal` |
| `asimetrias_hibridas_art_15_bis_lis_excepto_art_15/aumento` | `asimetrias_hibridas_art15bis` |
| `asimetrias_hibridas_art_15_bis_lis_excepto_art_15/disminucion` | `asimetrias_hibridas_art15bis` |
| `amortizacion_del_inmovilizado_intangible_y_fondo_d/aumento` | `amortizacion_intangible_fondo_comercio` |
| `amortizacion_del_inmovilizado_intangible_y_fondo_d/disminucion` | `amortizacion_intangible_fondo_comercio` |
| `amortizacion_de_inmovilizado_afecto_a_actividades/aumento` | `amortizacion_inmovilizado_actividades_economicas` |
| `amortizacion_de_inmovilizado_afecto_a_actividades/disminucion` | `amortizacion_inmovilizado_actividades_economicas` |
| `libertad_de_amortizacion_de_gastos_de_investigacio/aumento` | `libertad_amortizacion_investigacion_desarrollo` |
| `libertad_de_amortizacion_de_gastos_de_investigacio/disminucion` | `libertad_amortizacion_investigacion_desarrollo` |
| `libertad_de_amortizacion_inmovilizado_material_nue/aumento` | `libertad_amortizacion_inmovilizado_nuevo` |
| `libertad_de_amortizacion_inmovilizado_material_nue/disminucion` | `libertad_amortizacion_inmovilizado_nuevo` |
| `otros_supuestos_de_libertad_de_amortizacion_art_12/aumento` | `libertad_amortizacion_otros_art12` |
| `otros_supuestos_de_libertad_de_amortizacion_art_12/disminucion` | `libertad_amortizacion_otros_art12` |
| `libertad_de_amortizacion_con_mantenimiento_de_empl/aumento` | `libertad_amortizacion_mantenimiento_empleo` |
| `libertad_de_amortizacion_con_mantenimiento_de_empl/disminucion` | `libertad_amortizacion_mantenimiento_empleo` |
| `libertad_de_amortizacion_sin_mantenimiento_de_empl/aumento` | `libertad_amortizacion_sin_mantenimiento_empleo` |
| `libertad_de_amortizacion_sin_mantenimiento_de_empl/disminucion` | `libertad_amortizacion_sin_mantenimiento_empleo` |
| `perdidas_por_deterioro_del_art_13_1_lis_no_afectad/aumento` | `deterioro_art13_1_no_afectado` |
| `perdidas_por_deterioro_del_art_13_1_lis_no_afectad/disminucion` | `deterioro_art13_1_no_afectado` |
| `perdidas_por_deterioro_del_art_13_1_lis_y_provisio/aumento` | `deterioro_art13_1_provisiones` |
| `perdidas_por_deterioro_del_art_13_1_lis_y_provisio/disminucion` | `deterioro_art13_1_provisiones` |
| `perdidas_por_deterioro_de_im_inversiones_inmobilia/aumento` | `deterioro_inmovilizado_inversiones_inmobiliarias` |
| `perdidas_por_deterioro_de_im_inversiones_inmobilia/disminucion` | `deterioro_inmovilizado_inversiones_inmobiliarias` |
| `ajustes_por_perdidas_por_deterioro_de_valores_repr/aumento` | `deterioro_valores_participaciones_art13_2b` |
| `ajustes_por_perdidas_por_deterioro_de_valores_repr/disminucion` | `deterioro_valores_participaciones_art13_2b` |
| `perdidas_por_deterioro_de_valores_representativos/aumento` | `deterioro_valores_representativos` |
| `perdidas_por_deterioro_de_valores_representativos/disminucion` | `deterioro_valores_representativos` |
| `aplicacion_del_limite_del_art_11_12_lis_a_las_perd/aumento` | `limite_art11_12_perdidas_deterioro` |
| `aplicacion_del_limite_del_art_11_12_lis_a_las_perd/disminucion` | `limite_art11_12_perdidas_deterioro` |
| `gastos_y_provisiones_por_pensiones_no_afectados_po/aumento` | `pensiones_provisiones_no_deducibles` |
| `gastos_y_provisiones_por_pensiones_no_afectados_po/disminucion` | `pensiones_provisiones_no_deducibles` |
| `otras_provisiones_no_deducibles_fiscalmente_art_14/aumento` | `provisiones_no_deducibles_art14` |
| `otras_provisiones_no_deducibles_fiscalmente_art_14/disminucion` | `provisiones_no_deducibles_art14` |
| `subvenciones_publicas_incluidas_en_el_resultado_de/disminucion` | `subvenciones_publicas_no_integrables_art14_8` |
| `gastos_no_deducibles_por_considerarse_retribucion/aumento` | `gastos_retribucion_fondos_propios_art15a` |
| `multas_sanciones_y_otros_art_15_c_lis/aumento` | `multas_sanciones_art15c` |
| `perdidas_del_juego_art_15_d_lis/aumento` | `perdidas_juego_art15d` |
| `gastos_por_donativos_y_liberalidades_art_15_e_lis/aumento` | `donativos_liberalidades_art15e` |
| `gastos_de_actuaciones_contrarias_al_ordenamiento_j/aumento` | `gastos_contrarios_ordenamiento_art15f` |
| `operaciones_realizadas_con_jurisdicciones_no_coope/aumento` | `operaciones_jurisdicciones_no_cooperativas` |
| `operaciones_realizadas_con_jurisdicciones_no_coope/disminucion` | `operaciones_jurisdicciones_no_cooperativas` |
| `gastos_financieros_derivados_de_deudas_con_entidad/aumento` | `gastos_financieros_deudas_grupo_art15h` |
| `gastos_derivados_de_la_extincion_de_la_relacion_la/aumento` | `gastos_extincion_relacion_laboral_art15i` |
| `perdidas_por_deterioro_de_valores_repr_de_partic_e/aumento` | `deterioro_valores_participaciones_entidades` |
| `perdidas_por_deterioro_de_valores_repr_de_partic_e/disminucion` | `deterioro_valores_participaciones_entidades` |
| `disminucion_de_valor_originada_por_criterio_de_val/aumento` | `disminucion_valor_criterio_valor_razonable` |
| `disminucion_de_valor_originada_por_criterio_de_val/disminucion` | `disminucion_valor_criterio_valor_razonable` |
| `deuda_tributaria_de_actos_juridicos_documentados_i/aumento` | `deuda_tributaria_ajd_itp` |
| `deuda_tributaria_de_actos_juridicos_documentados_i/disminucion` | `deuda_tributaria_ajd_itp` |
| `ajustes_por_la_limitacion_en_la_deducibilidad_de_g/aumento` | `limitacion_gastos_financieros_art16` |
| `ajustes_por_la_limitacion_en_la_deducibilidad_de_g/disminucion` | `limitacion_gastos_financieros_art16` |
| `revalorizaciones_contables_art_17_1_lis/aumento` | `revalorizaciones_contables_art17_1` |
| `revalorizaciones_contables_art_17_1_lis/disminucion` | `revalorizaciones_contables_art17_1` |
| `operaciones_de_aumento_de_capital_o_fondos_propios/aumento` | `operaciones_aumento_capital_fondos_propios` |
| `operaciones_de_aumento_de_capital_o_fondos_propios/disminucion` | `operaciones_aumento_capital_fondos_propios` |
| `socio_sicav_reducciones_de_capital_y_distribucion/aumento` | `socio_sicav_reducciones_capital` |
| `transmisiones_lucrativas_y_societarias_aplicacion/aumento` | `transmisiones_lucrativas_societarias` |
| `transmisiones_lucrativas_y_societarias_aplicacion/disminucion` | `transmisiones_lucrativas_societarias` |
| `operaciones_vinculadas_aplicacion_del_valor_de_mer/aumento` | `operaciones_vinculadas_valor_mercado` |
| `operaciones_vinculadas_aplicacion_del_valor_de_mer/disminucion` | `operaciones_vinculadas_valor_mercado` |
| `efectos_de_la_valoracion_contable_diferente_a_la_f/aumento` | `efectos_valoracion_contable_diferente_fiscal` |
| `efectos_de_la_valoracion_contable_diferente_a_la_f/disminucion` | `efectos_valoracion_contable_diferente_fiscal` |
| `reduccion_de_rentas_procedentes_de_determinados_ac/aumento` | `reduccion_rentas_activos_intangibles` |
| `reduccion_de_rentas_procedentes_de_determinados_ac/disminucion` | `reduccion_rentas_activos_intangibles` |
| `impuesto_extranjero_soportado_por_el_contribuyente/aumento` | `impuesto_extranjero_deduccion_doble_imposicion` |
| `impuesto_extranjero_soportado_por_el_contribuyente/disminucion` | `impuesto_extranjero_deduccion_doble_imposicion` |
| `impuesto_extranjero_sobre_los_beneficios_con_cargo/aumento` | `impuesto_extranjero_art32_1` |
| `bases_imp_negativas_generadas_dentro_del_grupo_fis/aumento` | `bases_negativas_grupo_fiscal` |
| `bases_imp_negativas_generadas_dentro_del_grupo_fis/disminucion` | `bases_negativas_grupo_fiscal` |
| `valoracion_de_bienes_y_derechos_regimen_especial_o/aumento` | `valoracion_bienes_derechos_regimen_especial` |
| `valoracion_de_bienes_y_derechos_regimen_especial_o/disminucion` | `valoracion_bienes_derechos_regimen_especial` |
| `montes_vecinales_en_mano_comun_capitulo_xv_del_tit/disminucion` | `montes_vecinales_cap_xv` |
| `aportaciones_y_colaboracion_a_favor_de_entidades_s/aumento` | `aportaciones_entidades_sin_fines_lucro` |
| `aportaciones_y_colaboracion_a_favor_de_entidades_s/disminucion` | `aportaciones_entidades_sin_fines_lucro` |
| `cooperativas_fondo_de_reserva_obligatorio_ley_20_1/disminucion` | `cooperativas_fondo_reserva_obligatorio` |
| `rentas_procedentes_de_transmision_de_inmovilizado/disminucion` | `rentas_transmision_inmovilizado_autoridades_portuarias` |
| `operaciones_a_plazos_dt_1a_lis/aumento` | `operaciones_a_plazos_dt1` |
| `operaciones_a_plazos_dt_1a_lis/disminucion` | `operaciones_a_plazos_dt1` |
| `adquisicion_de_participaciones_en_entidades_no_res/aumento` | `adquisicion_participaciones_no_residentes_dt14` |
| `adquisicion_de_participaciones_en_entidades_no_res/disminucion` | `adquisicion_participaciones_no_residentes_dt14` |
| `reinversion_de_beneficios_extraordinarios_dt_24a_l/aumento` | `reinversion_beneficios_extraordinarios_dt24` |
| `reinversion_de_beneficios_extraordinarios_dt_24a_l/disminucion` | `reinversion_beneficios_extraordinarios_dt24` |
| `correcciones_especificas_de_entidades_sometidas_a/aumento` | `correcciones_entidades_normativa_foral` |
| `correcciones_especificas_de_entidades_sometidas_a/disminucion` | `correcciones_entidades_normativa_foral` |
| `eliminaciones_pendientes_de_incorporar_de_sociedad/aumento` | `eliminaciones_pendientes_sociedades_cooperativas` |
| `eliminaciones_pendientes_de_incorporar_de_sociedad/disminucion` | `eliminaciones_pendientes_sociedades_cooperativas` |
| `otras_correcciones_al_resultado_de_la_cuenta_de_pe/aumento` | `otras_correcciones_resultado` |
| `otras_correcciones_al_resultado_de_la_cuenta_de_pe/disminucion` | `otras_correcciones_resultado` |
| `correccion_por_el_impuesto_sobre_el_margen_de_inte/aumento` | `impuesto_margen_intereses_comisiones_df9` |

## Role assignments

All 695 casillas. `label_snippet` is the first 80 characters of the full label.

| id | role | label_snippet | data_type | notes |
|---|---|---|---|---|
| 00002 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad parcialmente exenta [00002] | decimal |  |
| 00003 | `is_correccion_identificacion_entidad_flag_regimen` | Sociedad de inversiÃ³n de capital variable o fondo de inversiÃ³n de carÃ¡cter fi | decimal |  |
| 00004 | `is_correccion_identificacion_entidad_flag_regimen` | Sociedad de inversiÃ³n inmobiliaria o fondo de inversiÃ³n inmobiliaria [00004] | decimal |  |
| 00005 | `is_correccion_identificacion_entidad_flag_regimen` | Comunidades titulares de montes vecinales en mano comÃºn [00005] | decimal |  |
| 00006 | `is_correccion_identificacion_entidad_flag_regimen` | Incentivos entidad de reducida dimensiÃ³n ( cap XI, tÃ­t. VII LIS ) [00006] | decimal |  |
| 00007 | `is_correccion_identificacion_entidad_flag_regimen` | ImputaciÃ³n en base imponible rentas positivas art. 100 LIS [00007] | decimal |  |
| 00008 | `is_correccion_identificacion_entidad_flag_regimen` | Sociedad de inversiÃ³n de capital variable que no cumpla los requisitos del art. | decimal |  |
| 00009 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad dominante de grupo fiscal [00009] | decimal |  |
| 00010 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad dependiente de grupo fiscal [00010] | decimal |  |
| 00011 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad de tenencia de valores extranjeros [00011] | decimal |  |
| 00012 | `is_correccion_identificacion_entidad_flag_regimen` | SOCIMI [00012] | decimal |  |
| 00014 | `is_correccion_identificacion_entidad_flag_regimen` | AgrupaciÃ³n europea de interÃ©s econÃ³mico [00014] | decimal |  |
| 00015 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad ZEC (sin consolidaciÃ³n fiscal) [00015] | decimal |  |
| 00017 | `is_correccion_identificacion_entidad_flag_regimen` | Cooperativa protegida [00017] | decimal |  |
| 00018 | `is_correccion_identificacion_entidad_flag_regimen` | Cooperativa especialmente protegida [00018] | decimal |  |
| 00019 | `is_correccion_identificacion_entidad_flag_regimen` | Resto cooperativas [00019] | decimal |  |
| 00020 | `is_correccion_identificacion_entidad_flag_regimen` | Otros regÃ­menes especiales [00020] | decimal |  |
| 00021 | `is_correccion_identificacion_entidad_flag_regimen` | Establecimiento permanente [00021] | decimal |  |
| 00023 | `is_correccion_identificacion_entidad_flag_regimen` | Gran empresa [00023] | decimal |  |
| 00024 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad de crÃ©dito [00024] | decimal |  |
| 00025 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad aseguradora [00025] | decimal |  |
| 00026 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad inactiva [00026] | decimal |  |
| 00027 | `is_correccion_identificacion_entidad_flag_regimen` | Base imponible negativa o cero [00027] | decimal |  |
| 00029 | `is_correccion_identificacion_entidad_flag_regimen` | RÃ©gimen especial Canarias [00029] | decimal |  |
| 00030 | `is_correccion_identificacion_entidad_flag_regimen` | TransmisiÃ³n elementos patrimoniales arts. 27.2.d) y 77.1 L.I.S. [00030] | decimal |  |
| 00032 | `is_correccion_identificacion_entidad_flag_regimen` | Sociedades desarrollo industrial regional [00032] | decimal |  |
| 00035 | `is_correccion_identificacion_entidad_flag_regimen` | RÃ©gimen especial fusiones, escisiones, aportaciones activos y canjes valores (C | decimal |  |
| 00036 | `is_correccion_identificacion_entidad_flag_regimen` | Sociedad de garantÃ­a recÃ­proca o de reafianzamiento [00036] | decimal |  |
| 00037 | `is_correccion_identificacion_entidad_flag_regimen` | OpciÃ³n de fraccionamiento art. 19.1 LIS [00037] | decimal |  |
| 00038 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad dedicada al arrend. viviendas [00038] | decimal |  |
| 00039 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad que forma parte de un grupo mercantil (art. 42 del CÃ³d. Comercio) [0003 | decimal |  |
| 00040 | `is_correccion_identificacion_entidad_numero_grupo_fiscal` | Grupo fiscal - Claves 00009 Ã³ 00010 - NÂº de grupo fiscal [00040] | text |  |
| 00041 | `is_correccion_personal_asalariado_personal_fijo` | Personal asalariado (cifra media del ejercicio) Personal fijo [00041] | decimal |  |
| 00042 | `is_correccion_personal_asalariado_personal_no_fijo` | Personal asalariado (cifra media del ejercicio) Personal no fijo [00042] | decimal |  |
| 00043 | `is_correccion_identificacion_entidad_flag_regimen` | ObligaciÃ³n informaciÃ³n DT 5Âª RIS [00043] | decimal |  |
| 00045 | `is_correccion_identificacion_entidad_flag_regimen` | Inversiones anticipadas - reserva inversiones en Canarias (art. 27.11 Ley 19/199 | decimal |  |
| 00046 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad en rÃ©g. Atribuc. de rentas constituida en el extranjero con presencia e | decimal |  |
| 00047 | `is_correccion_identificacion_entidad_flag_regimen` | Entidades sometidas a normativa foral [00047] | decimal |  |
| 00048 | `is_correccion_identificacion_entidad_flag_regimen` | Fondo de Pensiones Real Decreto Legislativo 1/2002 de 29 de noviembre [00048] | decimal |  |
| 00049 | `is_correccion_identificacion_entidad_flag_regimen` | RegÃ­menes especiales de normativa foral [00049] | decimal |  |
| 00058 | `is_correccion_identificacion_entidad_flag_regimen` | Mutua de seguros o Mutualidad de previsiÃ³n social [00058] | decimal |  |
| 00059 | `is_correccion_identificacion_entidad_flag_regimen` | OpciÃ³n art. 39.2 LIS [00059] | decimal |  |
| 00060 | `is_correccion_identificacion_entidad_flag_regimen` | Fondos o activos de titulizaciÃ³n [00060] | decimal |  |
| 00061 | `is_correccion_identificacion_entidad_flag_regimen` | Estados de cuentas de Instituciones de InversiÃ³n Colectiva: Entidades que utili | decimal |  |
| 00062 | `is_correccion_identificacion_entidad_flag_regimen` | Reg.fiscal de operac.de aportaciÃ³n de activos a sdades. para la gestiÃ³n de act | decimal |  |
| 00063 | `is_correccion_identificacion_entidad_flag_regimen` | Tipo de gravamen reducido para entidades de nueva creaciÃ³n (DT 22Âª LIS) [00063 | decimal |  |
| 00065 | `is_correccion_identificacion_entidad_flag_regimen` | BonificaciÃ³n personal investigador (RD 475/2014) [00065] | decimal |  |
| 00066 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad patrimonial [00066] | decimal |  |
| 00068 | `is_correccion_identificacion_entidad_flag_regimen` | Estados de cuentas de Entidades de CrÃ©dito: Entidades que sin ser Entidades de  | decimal |  |
| 00071 | `is_correccion_identificacion_entidad_flag_regimen` | Tipo gravamen reducido para entidades de nueva creaciÃ³n (art. 29.1 LIS) [00071] | decimal |  |
| 00072 | `is_correccion_identificacion_entidad_flag_regimen` | ExtinciÃ³n de entidad [00072] | decimal |  |
| 00073 | `is_correccion_identificacion_entidad_flag_regimen` | OpciÃ³n del 0,7% de la cuota Ã­ntegra para fines sociales [00073] | decimal |  |
| 00074 | `is_correccion_identificacion_entidad_flag_regimen` | Contribuyente que financia producciones con derecho a la deducciÃ³n del art. 36. | decimal |  |
| 00075 | `is_correccion_amortizacion_acelerada_vehiculos_saldo_inicial` | AmortizaciÃ³n acelerada de determinados vehÃ­culos y de nuevas infraestructuras  | money |  |
| 00076 | `is_correccion_amortizacion_acelerada_vehiculos_permanente_aumento` | AmortizaciÃ³n acelerada de determinados vehÃ­culos y de nuevas infraestructuras  | money |  |
| 00077 | `is_correccion_amortizacion_acelerada_vehiculos_importe` | AmortizaciÃ³n acelerada de determinados vehÃ­culos y de nuevas infraestructuras  | money |  |
| 00078 | `is_correccion_identificacion_entidad_flag_regimen` | DiÃ³cesis, provincia religiosa o entidad eclesiÃ¡stica que integra entidades men | decimal |  |
| 00079 | `is_correccion_identificacion_entidad_flag_regimen` | Entidad ZEC en consolidaciÃ³n fiscal [00079] | decimal |  |
| 00080 | `is_correccion_identificacion_entidad_flag_regimen` | Uniones, federaciones y confederaciones de cooperativas [00080] | decimal |  |
| 00081 | `is_correccion_identificacion_entidad_flag_regimen` | Filial grupo multinacional o grupo nacional de gran magnitud [00081] | decimal |  |
| 00082 | `is_correccion_identificacion_entidad_flag_regimen` | Sociedad matriz Ãºltima grupo multinacional o grupo nacional de gran magnitud [0 | decimal |  |
| 00083 | `is_correccion_identificacion_entidad_flag_regimen` | Tipo gravamen reducido para empresa emergente [00083] | decimal |  |
| 00084 | `is_correccion_identificacion_entidad_flag_regimen` | RÃ©gimen especial de disoluciÃ³n y liquidaciÃ³n de SICAV (DT 41Âª LIS) [00084] | decimal |  |
| 00086 | `is_correccion_identificacion_entidad_flag_regimen` | RÃ©gimen especial Illes Balears [00086] | decimal |  |
| 00087 | `is_correccion_identificacion_entidad_flag_regimen` | Inversiones anticipadas-reserva inversiones en Illes Balears (DA 70Âª.Cuatro.10  | decimal |  |
| 00088 | `is_correccion_identificacion_entidad_flag_regimen` | Tipo gravamen reducido para entidades con INCN periodo anterior inferior a 1 mil | decimal |  |
| 00090 | `is_correccion_identificacion_entidad_flag_regimen` | OpciÃ³n art. 39.3 LIS [00090] | decimal |  |
| 00941 | `is_correccion_reversion_deterioro_valores_saldo_inicial` | ReversiÃ³n por deterioro de valores representativos - Dotaciones pendientes de i | money |  |
| 00990 | `is_correccion_reversion_deterioro_valores_dotaciones_aplicadas` | ReversiÃ³n por deterioro de valores representativos - Dotaciones integradas en e | money |  |
| 00991 | `is_correccion_reversion_deterioro_valores_saldo_final` | ReversiÃ³n por deterioro de valores representativos - Dotaciones pendientes de i | money |  |
| 01009 | `is_correccion_deterioro_participaciones_dt16_saldo_inicial` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01103 | `is_correccion_limite_beneficio_operativo_saldo_inicial` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 01104 | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 01105 | `is_correccion_limite_beneficio_operativo_saldo_final` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 01143 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2021 -  | money |  |
| 01148 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2021 -  | money |  |
| 01162 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2022 -  | money |  |
| 01163 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2022 -  | money |  |
| 01164 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2022 -  | money |  |
| 01184 | `is_correccion_libertad_amortizacion_vehiculos_saldo_inicial` | Libertad de amortizaciÃ³n de determinados vehÃ­culos y de nuevas infraestructura | money |  |
| 01192 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2021 -  | money |  |
| 01217 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2024 -  | money |  |
| 01218 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2024 -  | money |  |
| 01219 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2024 -  | money |  |
| 01398 | `is_correccion_limite_beneficio_operativo_saldo_inicial` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 01399 | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 01400 | `is_correccion_limite_beneficio_operativo_saldo_final` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 01408 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2007 y  | money |  |
| 01409 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2007 y  | money |  |
| 01470 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2022 -  | money |  |
| 01471 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2022 -  | money |  |
| 01473 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2007 y  | money |  |
| 01474 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2007 y  | money |  |
| 01475 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2007 y  | money |  |
| 01476 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2007 y  | money |  |
| 01477 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2008 a  | money |  |
| 01478 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2008 a  | money |  |
| 01479 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2023 -  | money |  |
| 01480 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2023 -  | money |  |
| 01481 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2008 a  | money |  |
| 01482 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2008 a  | money |  |
| 01483 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2008 a  | money |  |
| 01484 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2008 a  | money |  |
| 01485 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2016 -  | money |  |
| 01486 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2016 -  | money |  |
| 01487 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2016 -  | money |  |
| 01488 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2016 -  | money |  |
| 01489 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2016 -  | money |  |
| 01490 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2016 -  | money |  |
| 01491 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2017 -  | money |  |
| 01492 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2017 -  | money |  |
| 01493 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2017 -  | money |  |
| 01494 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Total - Dotaciones pendientes i | money |  |
| 01495 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Total - Dotaciones pendientes i | money |  |
| 01496 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Total - Dotaciones integradas e | money |  |
| 01497 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Total - Dotaciones aplicadas co | money |  |
| 01498 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Total - Dotaciones pendientes i | money |  |
| 01499 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Total - Dotaciones pendientes i | money |  |
| 01500 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2023 -  | money |  |
| 01602 | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_aumento` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01626 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2025(*) | money |  |
| 01627 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2025(*) | money |  |
| 01628 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2025(*) | money |  |
| 01674 | `is_correccion_cambio_residencia_ue_eee_art19_permanente_aumento` | Cambio de residencia a Estados miembros de la UniÃ³n Europea o EEE (art. 19.1 LI | money |  |
| 01675 | `is_correccion_cambio_residencia_ue_eee_art19_permanente_disminucion` | Cambio de residencia a Estados miembros de la UniÃ³n Europea o EEE (art. 19.1 LI | money |  |
| 01676 | `is_correccion_operaciones_art19_otras_saldo_inicial` | Operaciones del art. 19 LIS distintas del cambio de residencia a Estados miembro | money |  |
| 01677 | `is_correccion_operaciones_art19_otras_permanente_aumento` | Operaciones del art. 19 LIS distintas del cambio de residencia a Estados miembro | money |  |
| 01678 | `is_correccion_operaciones_art19_otras_temporaria_ejercicio_aumento` | Operaciones del art. 19 LIS distintas del cambio de residencia a Estados miembro | money |  |
| 01679 | `is_correccion_operaciones_art19_otras_importe` | Operaciones del art. 19 LIS distintas del cambio de residencia a Estados miembro | money |  |
| 01680 | `is_correccion_operaciones_art19_otras_saldo_final` | Operaciones del art. 19 LIS distintas del cambio de residencia a Estados miembro | money |  |
| 01681 | `is_correccion_operaciones_art19_otras_saldo_inicial` | Operaciones del art. 19 LIS distintas del cambio de residencia a Estados miembro | money |  |
| 01682 | `is_correccion_operaciones_art19_otras_permanente_disminucion` | Operaciones del art. 19 LIS distintas del cambio de residencia a Estados miembro | money |  |
| 01686 | `is_correccion_operaciones_art19_otras_temporaria_ejercicio_disminucion` | Operaciones del art. 19 LIS distintas del cambio de residencia a Estados miembro | money |  |
| 01687 | `is_correccion_operaciones_art19_otras_importe` | Operaciones del art. 19 LIS distintas del cambio de residencia a Estados miembro | money |  |
| 01688 | `is_correccion_operaciones_art19_otras_saldo_final` | Operaciones del art. 19 LIS distintas del cambio de residencia a Estados miembro | money |  |
| 01732 | `is_correccion_deterioro_participaciones_dt16_permanente_disminucion` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01733 | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_disminucion` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01734 | `is_correccion_deterioro_participaciones_dt16_temporaria_anteriores_disminucion` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01735 | `is_correccion_deterioro_participaciones_dt16_saldo_final` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01741 | `is_correccion_libertad_amortizacion_vehiculos_permanente_aumento` | Libertad de amortizaciÃ³n de determinados vehÃ­culos y de nuevas infraestructura | money |  |
| 01742 | `is_correccion_libertad_amortizacion_vehiculos_temporaria_ejercicio_aumento` | Libertad de amortizaciÃ³n de determinados vehÃ­culos y de nuevas infraestructura | money |  |
| 01747 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2017 -  | money |  |
| 01748 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2017 -  | money |  |
| 01749 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2017 -  | money |  |
| 01750 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2018 -  | money |  |
| 01751 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2018 -  | money |  |
| 01752 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2018 -  | money |  |
| 01820 | `is_correccion_libertad_amortizacion_vehiculos_permanente_aumento` | Libertad de amortizaciÃ³n de determinados vehÃ­culos y de nuevas infraestructura | money |  |
| 01860 | `is_correccion_deterioro_participaciones_dt16_saldo_inicial` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01861 | `is_correccion_deterioro_participaciones_dt16_permanente_aumento` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01862 | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_aumento` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01863 | `is_correccion_deterioro_participaciones_dt16_temporaria_anteriores_aumento` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01864 | `is_correccion_deterioro_participaciones_dt16_saldo_final` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01865 | `is_correccion_deterioro_participaciones_dt16_saldo_inicial` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01866 | `is_correccion_deterioro_participaciones_dt16_permanente_disminucion` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01867 | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_disminucion` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01868 | `is_correccion_deterioro_participaciones_dt16_temporaria_anteriores_disminucion` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01869 | `is_correccion_deterioro_participaciones_dt16_saldo_final` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01882 | `is_correccion_socio_sicav_liquidaciones_permanente_disminucion` | Socio SICAV: rentas derivadas de liquidaciones de SICAV (DT 41Âª LIS) - Disminuc | money |  |
| 01883 | `is_correccion_libertad_amortizacion_vehiculos_saldo_final` | Libertad de amortizaciÃ³n de determinados vehÃ­culos y de nuevas infraestructura | money |  |
| 01884 | `is_correccion_libertad_amortizacion_vehiculos_saldo_inicial` | Libertad de amortizaciÃ³n de determinados vehÃ­culos y de nuevas infraestructura | money |  |
| 01885 | `is_correccion_libertad_amortizacion_vehiculos_permanente_disminucion` | Libertad de amortizaciÃ³n de determinados vehÃ­culos y de nuevas infraestructura | money |  |
| 01915 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2022 -  | money |  |
| 01961 | `is_correccion_libertad_amortizacion_vehiculos_permanente_disminucion` | Libertad de amortizaciÃ³n de determinados vehÃ­culos y de nuevas infraestructura | money |  |
| 01962 | `is_correccion_libertad_amortizacion_vehiculos_permanente_disminucion` | Libertad de amortizaciÃ³n de determinados vehÃ­culos y de nuevas infraestructura | money |  |
| 01984 | `is_correccion_libertad_amortizacion_vehiculos_saldo_final` | Libertad de amortizaciÃ³n de determinados vehÃ­culos y de nuevas infraestructura | money |  |
| 01988 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2018 -  | money |  |
| 01989 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2018 -  | money |  |
| 01990 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2018 -  | money |  |
| 01991 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2019 -  | money |  |
| 01992 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2019 -  | money |  |
| 01993 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2019 -  | money |  |
| 01995 | `is_correccion_deterioro_participaciones_dt16_saldo_inicial` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 01996 | `is_correccion_deterioro_participaciones_dt16_permanente_aumento` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 02079 | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | InformaciÃ³n adicional para el cÃ¡lculo de lÃ­mites de deducciones - 2025: Finan | money |  |
| 02080 | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | InformaciÃ³n adicional para el cÃ¡lculo de lÃ­mites de deducciones - 2025: Finan | money |  |
| 02176 | `is_correccion_copa_america_barcelona_saldo_inicial` | XXXVII Copa AmÃ©rica Barcelona (Ley 31/2022) - Aumento - Saldo pendiente a princ | money |  |
| 02177 | `is_correccion_copa_america_barcelona_permanente_aumento` | XXXVII Copa AmÃ©rica Barcelona (Ley 31/2022) - Aumento - Correcciones del ejerci | money |  |
| 02178 | `is_correccion_copa_america_barcelona_temporaria_ejercicio_aumento` | XXXVII Copa AmÃ©rica Barcelona (Ley 31/2022) - Aumento - Correcciones del ejerci | money |  |
| 02179 | `is_correccion_copa_america_barcelona_temporaria_anteriores_aumento` | XXXVII Copa AmÃ©rica Barcelona (Ley 31/2022) - Aumento - Correcciones del ejerci | money |  |
| 02180 | `is_correccion_copa_america_barcelona_saldo_final` | XXXVII Copa AmÃ©rica Barcelona (Ley 31/2022) - Aumento - Saldo pendiente a fin d | money |  |
| 02240 | `is_correccion_deterioro_participaciones_dt16_temporaria_anteriores_aumento` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 02258 | `is_correccion_limite_beneficio_operativo_saldo_inicial` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 02259 | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 02261 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2019 -  | money |  |
| 02262 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2019 -  | money |  |
| 02263 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2019 -  | money |  |
| 02264 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2020 -  | money |  |
| 02265 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2020 -  | money |  |
| 02266 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2020 -  | money |  |
| 02287 | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | InformaciÃ³n adicional para el cÃ¡lculo de lÃ­mites de deducciones - 2025: Deduc | money |  |
| 02288 | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | InformaciÃ³n adicional para el cÃ¡lculo de lÃ­mites de deducciones - 2025: Deduc | money |  |
| 02289 | `is_correccion_copa_america_barcelona_saldo_inicial` | XXXVII Copa AmÃ©rica Barcelona (Ley 31/2022) - DisminuciÃ³n - Saldo pendiente a  | money |  |
| 02290 | `is_correccion_copa_america_barcelona_permanente_disminucion` | XXXVII Copa AmÃ©rica Barcelona (Ley 31/2022) - DisminuciÃ³n - Correcciones del e | money |  |
| 02291 | `is_correccion_copa_america_barcelona_temporaria_ejercicio_disminucion` | XXXVII Copa AmÃ©rica Barcelona (Ley 31/2022) - DisminuciÃ³n - Correcciones del e | money |  |
| 02292 | `is_correccion_copa_america_barcelona_temporaria_anteriores_disminucion` | XXXVII Copa AmÃ©rica Barcelona (Ley 31/2022) - DisminuciÃ³n - Correcciones del e | money |  |
| 02293 | `is_correccion_copa_america_barcelona_saldo_final` | XXXVII Copa AmÃ©rica Barcelona (Ley 31/2022) - DisminuciÃ³n - Saldo pendiente a  | money |  |
| 02301 | `is_correccion_detalle_correcciones_resultado_permanente_disminucion` | Detalle correcciones resultado pÃ©rdidas y ganancias - Correcciones al resultado | money |  |
| 02302 | `is_correccion_detalle_correcciones_resultado_permanente_disminucion` | Detalle correcciones resultado pÃ©rdidas y ganancias - Correcciones al resultado | money |  |
| 02303 | `is_correccion_detalle_correcciones_resultado_temporaria_ejercicio_aumento` | Detalle correcciones resultado pÃ©rdidas y ganancias - Correcciones al resultado | money |  |
| 02304 | `is_correccion_detalle_correcciones_resultado_temporaria_ejercicio_disminucion` | Detalle correcciones resultado pÃ©rdidas y ganancias - Correcciones al resultado | money |  |
| 02305 | `is_correccion_detalle_correcciones_resultado_saldo_inicial_aumento` | Detalle correcciones resultado pÃ©rdidas y ganancias - Saldo pendiente de correc | money |  |
| 02306 | `is_correccion_detalle_correcciones_resultado_saldo_inicial_disminucion` | Detalle correcciones resultado pÃ©rdidas y ganancias - Saldo pendiente de correc | money |  |
| 02307 | `is_correccion_detalle_correcciones_resultado_temporaria_ejercicio_aumento` | Detalle correcciones resultado pÃ©rdidas y ganancias - Correcciones al resultado | money |  |
| 02308 | `is_correccion_detalle_correcciones_resultado_temporaria_ejercicio_disminucion` | Detalle correcciones resultado pÃ©rdidas y ganancias - Correcciones al resultado | money |  |
| 02309 | `is_correccion_detalle_correcciones_resultado_saldo_final_aumento` | Detalle correcciones resultado pÃ©rdidas y ganancias - Saldo pendiente de correc | money |  |
| 02310 | `is_correccion_detalle_correcciones_resultado_saldo_final_disminucion` | Detalle correcciones resultado pÃ©rdidas y ganancias - Saldo pendiente de correc | money |  |
| 02375 | `is_correccion_deterioro_participaciones_dt16_saldo_final` | Ajustes por deterioro de valores repr. de partic. en el capital o fondos propios | money |  |
| 02404 | `is_correccion_limite_beneficio_operativo_saldo_inicial` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 02405 | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 02406 | `is_correccion_limite_beneficio_operativo_saldo_final` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 02431 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2020 -  | money |  |
| 02432 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2020 -  | money |  |
| 02433 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2020 -  | money |  |
| 02434 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2021 -  | money |  |
| 02435 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2021 -  | money |  |
| 02436 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2021 -  | money |  |
| 02447 | `is_correccion_limite_beneficio_operativo_saldo_inicial` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 02465 | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 02495 | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | InformaciÃ³n adicional para el cÃ¡lculo de lÃ­mites de deducciones - 2025: Produ | money |  |
| 02496 | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | InformaciÃ³n adicional para el cÃ¡lculo de lÃ­mites de deducciones - 2025: Produ | money |  |
| 02501 | `is_correccion_cambio_criterios_contables_art11_3_permanente_aumento` | Cambio de criterios contables (art. 11.3.2Âº LIS) - Aumento - Correcciones del e | money |  |
| 02502 | `is_correccion_cambio_criterios_contables_art11_3_temporaria_ejercicio_aumento` | Cambio de criterios contables (art. 11.3.2Âº LIS) - Aumento - Correcciones del e | money |  |
| 02503 | `is_correccion_cambio_criterios_contables_art11_3_temporaria_anteriores_aumento` | Cambio de criterios contables (art. 11.3.2Âº LIS) - Aumento - Correcciones del e | money |  |
| 02504 | `is_correccion_cambio_criterios_contables_art11_3_saldo_inicial` | Cambio de criterios contables (art. 11.3.2Âº LIS) - Aumento - Saldo pendiente a  | money |  |
| 02505 | `is_correccion_cambio_criterios_contables_art11_3_saldo_final` | Cambio de criterios contables (art. 11.3.2Âº LIS) - Aumento - Saldo pendiente a  | money |  |
| 02506 | `is_correccion_cambio_criterios_contables_art11_3_permanente_disminucion` | Cambio de criterios contables (art. 11.3.2Âº LIS) - DisminuciÃ³n - Correcciones  | money |  |
| 02507 | `is_correccion_cambio_criterios_contables_art11_3_temporaria_ejercicio_disminucion` | Cambio de criterios contables (art. 11.3.2Âº LIS) - DisminuciÃ³n - Correcciones  | money |  |
| 02508 | `is_correccion_cambio_criterios_contables_art11_3_temporaria_anteriores_disminucion` | Cambio de criterios contables (art. 11.3.2Âº LIS) - DisminuciÃ³n - Correcciones  | money |  |
| 02509 | `is_correccion_cambio_criterios_contables_art11_3_saldo_inicial` | Cambio de criterios contables (art. 11.3.2Âº LIS) - DisminuciÃ³n - Saldo pendien | money |  |
| 02510 | `is_correccion_cambio_criterios_contables_art11_3_saldo_final` | Cambio de criterios contables (art. 11.3.2Âº LIS) - DisminuciÃ³n - Saldo pendien | money |  |
| 02511 | `is_correccion_operaciones_a_plazos_art11_4_permanente_aumento` | Operaciones a plazos (art. 11.4 LIS) - Aumento - Correcciones del ejercicio - Pe | money |  |
| 02512 | `is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_aumento` | Operaciones a plazos (art. 11.4 LIS) - Aumento - Correcciones del ejercicio - Te | money |  |
| 02513 | `is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_aumento` | Operaciones a plazos (art. 11.4 LIS) - Aumento - Correcciones del ejercicio - Te | money |  |
| 02514 | `is_correccion_operaciones_a_plazos_art11_4_saldo_inicial` | Operaciones a plazos (art. 11.4 LIS) - Aumento - Saldo pendiente a principio de  | money |  |
| 02515 | `is_correccion_operaciones_a_plazos_art11_4_saldo_final` | Operaciones a plazos (art. 11.4 LIS) - Aumento - Saldo pendiente a fin de ejerci | money |  |
| 02516 | `is_correccion_operaciones_a_plazos_art11_4_permanente_disminucion` | Operaciones a plazos (art. 11.4 LIS) - DisminuciÃ³n - Correcciones del ejercicio | money |  |
| 02517 | `is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_disminucion` | Operaciones a plazos (art. 11.4 LIS) - DisminuciÃ³n - Correcciones del ejercicio | money |  |
| 02518 | `is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_disminucion` | Operaciones a plazos (art. 11.4 LIS) - DisminuciÃ³n - Correcciones del ejercicio | money |  |
| 02519 | `is_correccion_operaciones_a_plazos_art11_4_saldo_inicial` | Operaciones a plazos (art. 11.4 LIS) - DisminuciÃ³n - Saldo pendiente a principi | money |  |
| 02520 | `is_correccion_operaciones_a_plazos_art11_4_saldo_final` | Operaciones a plazos (art. 11.4 LIS) - DisminuciÃ³n - Saldo pendiente a fin de e | money |  |
| 02521 | `is_correccion_reversion_deterioro_elementos_permanente_aumento` | ReversiÃ³n del deterioro del valor de los elementos patrimoniales (art. 11.6 LIS | money |  |
| 02522 | `is_correccion_reversion_deterioro_elementos_temporaria_ejercicio_aumento` | ReversiÃ³n del deterioro del valor de los elementos patrimoniales (art. 11.6 LIS | money |  |
| 02523 | `is_correccion_reversion_deterioro_elementos_temporaria_anteriores_aumento` | ReversiÃ³n del deterioro del valor de los elementos patrimoniales (art. 11.6 LIS | money |  |
| 02524 | `is_correccion_reversion_deterioro_elementos_saldo_inicial` | ReversiÃ³n del deterioro del valor de los elementos patrimoniales (art. 11.6 LIS | money |  |
| 02525 | `is_correccion_reversion_deterioro_elementos_saldo_final` | ReversiÃ³n del deterioro del valor de los elementos patrimoniales (art. 11.6 LIS | money |  |
| 02526 | `is_correccion_reversion_deterioro_elementos_permanente_disminucion` | ReversiÃ³n del deterioro del valor de los elementos patrimoniales (art. 11.6 LIS | money |  |
| 02527 | `is_correccion_reversion_deterioro_elementos_temporaria_ejercicio_disminucion` | ReversiÃ³n del deterioro del valor de los elementos patrimoniales (art. 11.6 LIS | money |  |
| 02528 | `is_correccion_reversion_deterioro_elementos_temporaria_anteriores_disminucion` | ReversiÃ³n del deterioro del valor de los elementos patrimoniales (art. 11.6 LIS | money |  |
| 02529 | `is_correccion_reversion_deterioro_elementos_saldo_inicial` | ReversiÃ³n del deterioro del valor de los elementos patrimoniales (art. 11.6 LIS | money |  |
| 02530 | `is_correccion_reversion_deterioro_elementos_saldo_final` | ReversiÃ³n del deterioro del valor de los elementos patrimoniales (art. 11.6 LIS | money |  |
| 02531 | `is_correccion_rentas_negativas_art11_9_10_permanente_aumento` | Rentas negativas (art. 11.9 y 11.10 LIS) - Aumento - Correcciones del ejercicio  | money |  |
| 02532 | `is_correccion_rentas_negativas_art11_9_10_temporaria_ejercicio_aumento` | Rentas negativas (art. 11.9 y 11.10 LIS) - Aumento - Correcciones del ejercicio  | money |  |
| 02533 | `is_correccion_rentas_negativas_art11_9_10_temporaria_anteriores_aumento` | Rentas negativas (art. 11.9 y 11.10 LIS) - Aumento - Correcciones del ejercicio  | money |  |
| 02534 | `is_correccion_rentas_negativas_art11_9_10_saldo_inicial` | Rentas negativas (art. 11.9 y 11.10 LIS) - Aumento - Saldo pendiente a principio | money |  |
| 02535 | `is_correccion_rentas_negativas_art11_9_10_saldo_final` | Rentas negativas (art. 11.9 y 11.10 LIS) - Aumento - Saldo pendiente a fin de ej | money |  |
| 02536 | `is_correccion_rentas_negativas_art11_9_10_permanente_disminucion` | Rentas negativas (art. 11.9 y 11.10 LIS) - DisminuciÃ³n - Correcciones del ejerc | money |  |
| 02537 | `is_correccion_rentas_negativas_art11_9_10_temporaria_ejercicio_disminucion` | Rentas negativas (art. 11.9 y 11.10 LIS) - DisminuciÃ³n - Correcciones del ejerc | money |  |
| 02538 | `is_correccion_rentas_negativas_art11_9_10_temporaria_anteriores_disminucion` | Rentas negativas (art. 11.9 y 11.10 LIS) - DisminuciÃ³n - Correcciones del ejerc | money |  |
| 02539 | `is_correccion_rentas_negativas_art11_9_10_saldo_inicial` | Rentas negativas (art. 11.9 y 11.10 LIS) - DisminuciÃ³n - Saldo pendiente a prin | money |  |
| 02540 | `is_correccion_rentas_negativas_art11_9_10_saldo_final` | Rentas negativas (art. 11.9 y 11.10 LIS) - DisminuciÃ³n - Saldo pendiente a fin  | money |  |
| 02541 | `is_correccion_rentas_operaciones_quita_espera_permanente_aumento` | Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS)  | money |  |
| 02542 | `is_correccion_rentas_operaciones_quita_espera_temporaria_ejercicio_aumento` | Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS)  | money |  |
| 02543 | `is_correccion_rentas_operaciones_quita_espera_temporaria_anteriores_aumento` | Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS)  | money |  |
| 02544 | `is_correccion_rentas_operaciones_quita_espera_saldo_inicial` | Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS)  | money |  |
| 02545 | `is_correccion_rentas_operaciones_quita_espera_saldo_final` | Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS)  | money |  |
| 02546 | `is_correccion_rentas_operaciones_quita_espera_permanente_disminucion` | Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS)  | money |  |
| 02547 | `is_correccion_rentas_operaciones_quita_espera_temporaria_ejercicio_disminucion` | Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS)  | money |  |
| 02548 | `is_correccion_rentas_operaciones_quita_espera_temporaria_anteriores_disminucion` | Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS)  | money |  |
| 02549 | `is_correccion_rentas_operaciones_quita_espera_saldo_inicial` | Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS)  | money |  |
| 02550 | `is_correccion_rentas_operaciones_quita_espera_saldo_final` | Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS)  | money |  |
| 02551 | `is_correccion_otras_diferencias_imputacion_temporal_permanente_aumento` | Otras diferencias de imputaciÃ³n temporal de ingresos y gastos (art. 11 LIS) - A | money |  |
| 02552 | `is_correccion_otras_diferencias_imputacion_temporal_temporaria_ejercicio_aumento` | Otras diferencias de imputaciÃ³n temporal de ingresos y gastos (art. 11 LIS) - A | money |  |
| 02553 | `is_correccion_otras_diferencias_imputacion_temporal_temporaria_anteriores_aumento` | Otras diferencias de imputaciÃ³n temporal de ingresos y gastos (art. 11 LIS) - A | money |  |
| 02554 | `is_correccion_otras_diferencias_imputacion_temporal_saldo_inicial` | Otras diferencias de imputaciÃ³n temporal de ingresos y gastos (art. 11 LIS) - A | money |  |
| 02555 | `is_correccion_otras_diferencias_imputacion_temporal_saldo_final` | Otras diferencias de imputaciÃ³n temporal de ingresos y gastos (art. 11 LIS) - A | money |  |
| 02556 | `is_correccion_otras_diferencias_imputacion_temporal_permanente_disminucion` | Otras diferencias de imputaciÃ³n temporal de ingresos y gastos (art. 11 LIS) - D | money |  |
| 02557 | `is_correccion_otras_diferencias_imputacion_temporal_temporaria_ejercicio_disminucion` | Otras diferencias de imputaciÃ³n temporal de ingresos y gastos (art. 11 LIS) - D | money |  |
| 02558 | `is_correccion_otras_diferencias_imputacion_temporal_temporaria_anteriores_disminucion` | Otras diferencias de imputaciÃ³n temporal de ingresos y gastos (art. 11 LIS) - D | money |  |
| 02559 | `is_correccion_otras_diferencias_imputacion_temporal_saldo_inicial` | Otras diferencias de imputaciÃ³n temporal de ingresos y gastos (art. 11 LIS) - D | money |  |
| 02560 | `is_correccion_otras_diferencias_imputacion_temporal_saldo_final` | Otras diferencias de imputaciÃ³n temporal de ingresos y gastos (art. 11 LIS) - D | money |  |
| 02561 | `is_correccion_diferencias_amortizacion_contable_fiscal_permanente_aumento` | Diferencias entre amortizaciÃ³n contable y fiscal (art. 12.1 LIS) - Aumento - Co | money |  |
| 02562 | `is_correccion_diferencias_amortizacion_contable_fiscal_temporaria_ejercicio_aumento` | Diferencias entre amortizaciÃ³n contable y fiscal (art. 12.1 LIS) - Aumento - Co | money |  |
| 02563 | `is_correccion_diferencias_amortizacion_contable_fiscal_temporaria_anteriores_aumento` | Diferencias entre amortizaciÃ³n contable y fiscal (art. 12.1 LIS) - Aumento - Co | money |  |
| 02564 | `is_correccion_diferencias_amortizacion_contable_fiscal_saldo_inicial` | Diferencias entre amortizaciÃ³n contable y fiscal (art. 12.1 LIS) - Aumento - Sa | money |  |
| 02565 | `is_correccion_diferencias_amortizacion_contable_fiscal_saldo_final` | Diferencias entre amortizaciÃ³n contable y fiscal (art. 12.1 LIS) - Aumento - Sa | money |  |
| 02566 | `is_correccion_diferencias_amortizacion_contable_fiscal_permanente_disminucion` | Diferencias entre amortizaciÃ³n contable y fiscal (art. 12.1 LIS) - DisminuciÃ³n | money |  |
| 02567 | `is_correccion_diferencias_amortizacion_contable_fiscal_temporaria_ejercicio_disminucion` | Diferencias entre amortizaciÃ³n contable y fiscal (art. 12.1 LIS) - DisminuciÃ³n | money |  |
| 02568 | `is_correccion_diferencias_amortizacion_contable_fiscal_temporaria_anteriores_disminucion` | Diferencias entre amortizaciÃ³n contable y fiscal (art. 12.1 LIS) - DisminuciÃ³n | money |  |
| 02569 | `is_correccion_diferencias_amortizacion_contable_fiscal_saldo_inicial` | Diferencias entre amortizaciÃ³n contable y fiscal (art. 12.1 LIS) - DisminuciÃ³n | money |  |
| 02570 | `is_correccion_diferencias_amortizacion_contable_fiscal_saldo_final` | Diferencias entre amortizaciÃ³n contable y fiscal (art. 12.1 LIS) - DisminuciÃ³n | money |  |
| 02571 | `is_correccion_asimetrias_hibridas_art15bis_permanente_aumento` | AsimetrÃ­as hÃ­bridas (art. 15 bis LIS, excepto art. 15 bis.12 LIS) - Aumento -  | money |  |
| 02572 | `is_correccion_asimetrias_hibridas_art15bis_temporaria_ejercicio_aumento` | AsimetrÃ­as hÃ­bridas (art. 15 bis LIS, excepto art. 15 bis.12 LIS) - Aumento -  | money |  |
| 02573 | `is_correccion_asimetrias_hibridas_art15bis_temporaria_anteriores_aumento` | AsimetrÃ­as hÃ­bridas (art. 15 bis LIS, excepto art. 15 bis.12 LIS) - Aumento -  | money |  |
| 02574 | `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial` | AsimetrÃ­as hÃ­bridas (art. 15 bis LIS, excepto art. 15 bis.12 LIS) - Aumento -  | money |  |
| 02575 | `is_correccion_asimetrias_hibridas_art15bis_saldo_final` | AsimetrÃ­as hÃ­bridas (art. 15 bis LIS, excepto art. 15 bis.12 LIS) - Aumento -  | money |  |
| 02581 | `is_correccion_amortizacion_intangible_fondo_comercio_permanente_aumento` | AmortizaciÃ³n del inmovilizado intangible y fondo de comercio (art. 12.2 LIS) y  | money |  |
| 02582 | `is_correccion_amortizacion_intangible_fondo_comercio_temporaria_ejercicio_aumento` | AmortizaciÃ³n del inmovilizado intangible y fondo de comercio (art. 12.2 LIS) y  | money |  |
| 02583 | `is_correccion_amortizacion_intangible_fondo_comercio_permanente_aumento` | AmortizaciÃ³n del inmovilizado intangible y fondo de comercio (art. 12.2 LIS) y  | money |  |
| 02584 | `is_correccion_amortizacion_intangible_fondo_comercio_saldo_inicial` | AmortizaciÃ³n del inmovilizado intangible y fondo de comercio (art. 12.2 LIS) y  | money |  |
| 02585 | `is_correccion_amortizacion_intangible_fondo_comercio_saldo_final` | AmortizaciÃ³n del inmovilizado intangible y fondo de comercio (art. 12.2 LIS) y  | money |  |
| 02586 | `is_correccion_amortizacion_intangible_fondo_comercio_permanente_disminucion` | AmortizaciÃ³n del inmovilizado intangible y fondo de comercio (art. 12.2 LIS) y  | money |  |
| 02587 | `is_correccion_amortizacion_intangible_fondo_comercio_temporaria_ejercicio_disminucion` | AmortizaciÃ³n del inmovilizado intangible y fondo de comercio (art. 12.2 LIS) y  | money |  |
| 02588 | `is_correccion_amortizacion_intangible_fondo_comercio_permanente_disminucion` | AmortizaciÃ³n del inmovilizado intangible y fondo de comercio (art. 12.2 LIS) y  | money |  |
| 02589 | `is_correccion_amortizacion_intangible_fondo_comercio_saldo_inicial` | AmortizaciÃ³n del inmovilizado intangible y fondo de comercio (art. 12.2 LIS) y  | money |  |
| 02590 | `is_correccion_amortizacion_intangible_fondo_comercio_saldo_final` | AmortizaciÃ³n del inmovilizado intangible y fondo de comercio (art. 12.2 LIS) y  | money |  |
| 02591 | `is_correccion_amortizacion_inmovilizado_actividades_economicas_permanente_aumento` | AmortizaciÃ³n de inmovilizado afecto a actividades de investigaciÃ³n y desarroll | money |  |
| 02592 | `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_ejercicio_aumento` | AmortizaciÃ³n de inmovilizado afecto a actividades de investigaciÃ³n y desarroll | money |  |
| 02593 | `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_anteriores_aumento` | AmortizaciÃ³n de inmovilizado afecto a actividades de investigaciÃ³n y desarroll | money |  |
| 02594 | `is_correccion_amortizacion_inmovilizado_actividades_economicas_saldo_inicial` | AmortizaciÃ³n de inmovilizado afecto a actividades de investigaciÃ³n y desarroll | money |  |
| 02595 | `is_correccion_amortizacion_inmovilizado_actividades_economicas_saldo_final` | AmortizaciÃ³n de inmovilizado afecto a actividades de investigaciÃ³n y desarroll | money |  |
| 02596 | `is_correccion_amortizacion_inmovilizado_actividades_economicas_permanente_disminucion` | AmortizaciÃ³n de inmovilizado afecto a actividades de investigaciÃ³n y desarroll | money |  |
| 02597 | `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_ejercicio_disminucion` | AmortizaciÃ³n de inmovilizado afecto a actividades de investigaciÃ³n y desarroll | money |  |
| 02598 | `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_anteriores_disminucion` | AmortizaciÃ³n de inmovilizado afecto a actividades de investigaciÃ³n y desarroll | money |  |
| 02599 | `is_correccion_amortizacion_inmovilizado_actividades_economicas_saldo_inicial` | AmortizaciÃ³n de inmovilizado afecto a actividades de investigaciÃ³n y desarroll | money |  |
| 02600 | `is_correccion_amortizacion_inmovilizado_actividades_economicas_saldo_final` | AmortizaciÃ³n de inmovilizado afecto a actividades de investigaciÃ³n y desarroll | money |  |
| 02601 | `is_correccion_libertad_amortizacion_investigacion_desarrollo_permanente_aumento` | Libertad de amortizaciÃ³n de gastos de investigaciÃ³n y desarrollo (art. 12.3 c) | money |  |
| 02602 | `is_correccion_libertad_amortizacion_investigacion_desarrollo_temporaria_ejercicio_aumento` | Libertad de amortizaciÃ³n de gastos de investigaciÃ³n y desarrollo (art. 12.3 c) | money |  |
| 02603 | `is_correccion_libertad_amortizacion_investigacion_desarrollo_temporaria_anteriores_aumento` | Libertad de amortizaciÃ³n de gastos de investigaciÃ³n y desarrollo (art. 12.3 c) | money |  |
| 02604 | `is_correccion_libertad_amortizacion_investigacion_desarrollo_saldo_inicial` | Libertad de amortizaciÃ³n de gastos de investigaciÃ³n y desarrollo (art. 12.3 c) | money |  |
| 02605 | `is_correccion_libertad_amortizacion_investigacion_desarrollo_saldo_final` | Libertad de amortizaciÃ³n de gastos de investigaciÃ³n y desarrollo (art. 12.3 c) | money |  |
| 02606 | `is_correccion_libertad_amortizacion_investigacion_desarrollo_permanente_disminucion` | Libertad de amortizaciÃ³n de gastos de investigaciÃ³n y desarrollo (art. 12.3 c) | money |  |
| 02607 | `is_correccion_libertad_amortizacion_investigacion_desarrollo_temporaria_ejercicio_disminucion` | Libertad de amortizaciÃ³n de gastos de investigaciÃ³n y desarrollo (art. 12.3 c) | money |  |
| 02608 | `is_correccion_libertad_amortizacion_investigacion_desarrollo_temporaria_anteriores_disminucion` | Libertad de amortizaciÃ³n de gastos de investigaciÃ³n y desarrollo (art. 12.3 c) | money |  |
| 02609 | `is_correccion_libertad_amortizacion_investigacion_desarrollo_saldo_inicial` | Libertad de amortizaciÃ³n de gastos de investigaciÃ³n y desarrollo (art. 12.3 c) | money |  |
| 02610 | `is_correccion_libertad_amortizacion_investigacion_desarrollo_saldo_final` | Libertad de amortizaciÃ³n de gastos de investigaciÃ³n y desarrollo (art. 12.3 c) | money |  |
| 02611 | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_permanente_aumento` | Libertad de amortizaciÃ³n inmovilizado material nuevo (art. 12.3 e) LIS) - Aumen | money |  |
| 02612 | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_temporaria_ejercicio_aumento` | Libertad de amortizaciÃ³n inmovilizado material nuevo (art. 12.3 e) LIS) - Aumen | money |  |
| 02613 | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_temporaria_anteriores_aumento` | Libertad de amortizaciÃ³n inmovilizado material nuevo (art. 12.3 e) LIS) - Aumen | money |  |
| 02614 | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_inicial` | Libertad de amortizaciÃ³n inmovilizado material nuevo (art. 12.3 e) LIS) - Aumen | money |  |
| 02615 | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_final` | Libertad de amortizaciÃ³n inmovilizado material nuevo (art. 12.3 e) LIS) - Aumen | money |  |
| 02616 | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_permanente_disminucion` | Libertad de amortizaciÃ³n inmovilizado material nuevo (art. 12.3 e) LIS) - Dismi | money |  |
| 02617 | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_temporaria_ejercicio_disminucion` | Libertad de amortizaciÃ³n inmovilizado material nuevo (art. 12.3 e) LIS) - Dismi | money |  |
| 02618 | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_temporaria_anteriores_disminucion` | Libertad de amortizaciÃ³n inmovilizado material nuevo (art. 12.3 e) LIS) - Dismi | money |  |
| 02619 | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_inicial` | Libertad de amortizaciÃ³n inmovilizado material nuevo (art. 12.3 e) LIS) - Dismi | money |  |
| 02620 | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_final` | Libertad de amortizaciÃ³n inmovilizado material nuevo (art. 12.3 e) LIS) - Dismi | money |  |
| 02621 | `is_correccion_libertad_amortizacion_otros_art12_permanente_aumento` | Otros supuestos de libertad de amortizaciÃ³n (art. 12.3 a) y d) y DA 16Âª y 17Âª | money |  |
| 02622 | `is_correccion_libertad_amortizacion_otros_art12_temporaria_ejercicio_aumento` | Otros supuestos de libertad de amortizaciÃ³n (art. 12.3 a) y d) y DA 16Âª y 17Âª | money |  |
| 02623 | `is_correccion_libertad_amortizacion_otros_art12_temporaria_anteriores_aumento` | Otros supuestos de libertad de amortizaciÃ³n (art. 12.3 a) y d) y DA 16Âª y 17Âª | money |  |
| 02624 | `is_correccion_libertad_amortizacion_otros_art12_saldo_inicial` | Otros supuestos de libertad de amortizaciÃ³n (art. 12.3 a) y d) y DA 16Âª y 17Âª | money |  |
| 02625 | `is_correccion_libertad_amortizacion_otros_art12_saldo_final` | Otros supuestos de libertad de amortizaciÃ³n (art. 12.3 a) y d) y DA 16Âª y 17Âª | money |  |
| 02626 | `is_correccion_libertad_amortizacion_otros_art12_permanente_disminucion` | Otros supuestos de libertad de amortizaciÃ³n (art. 12.3 a) y d) y DA 16Âª y 17Âª | money |  |
| 02627 | `is_correccion_libertad_amortizacion_otros_art12_temporaria_ejercicio_disminucion` | Otros supuestos de libertad de amortizaciÃ³n (art. 12.3 a) y d) y DA 16Âª y 17Âª | money |  |
| 02628 | `is_correccion_libertad_amortizacion_otros_art12_temporaria_anteriores_disminucion` | Otros supuestos de libertad de amortizaciÃ³n (art. 12.3 a) y d) y DA 16Âª y 17Âª | money |  |
| 02629 | `is_correccion_libertad_amortizacion_otros_art12_saldo_inicial` | Otros supuestos de libertad de amortizaciÃ³n (art. 12.3 a) y d) y DA 16Âª y 17Âª | money |  |
| 02630 | `is_correccion_libertad_amortizacion_otros_art12_saldo_final` | Otros supuestos de libertad de amortizaciÃ³n (art. 12.3 a) y d) y DA 16Âª y 17Âª | money |  |
| 02631 | `is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento` | Libertad de amortizaciÃ³n con mantenimiento de empleo (RDL 6/2010 y DT 13Âª.2 LI | money |  |
| 02632 | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_aumento` | Libertad de amortizaciÃ³n con mantenimiento de empleo (RDL 6/2010 y DT 13Âª.2 LI | money |  |
| 02633 | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_aumento` | Libertad de amortizaciÃ³n con mantenimiento de empleo (RDL 6/2010 y DT 13Âª.2 LI | money |  |
| 02634 | `is_correccion_libertad_amortizacion_mantenimiento_empleo_saldo_inicial` | Libertad de amortizaciÃ³n con mantenimiento de empleo (RDL 6/2010 y DT 13Âª.2 LI | money |  |
| 02635 | `is_correccion_libertad_amortizacion_mantenimiento_empleo_saldo_final` | Libertad de amortizaciÃ³n con mantenimiento de empleo (RDL 6/2010 y DT 13Âª.2 LI | money |  |
| 02636 | `is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_disminucion` | Libertad de amortizaciÃ³n con mantenimiento de empleo (RDL 6/2010 y DT 13Âª.2 LI | money |  |
| 02637 | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_disminucion` | Libertad de amortizaciÃ³n con mantenimiento de empleo (RDL 6/2010 y DT 13Âª.2 LI | money |  |
| 02638 | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_disminucion` | Libertad de amortizaciÃ³n con mantenimiento de empleo (RDL 6/2010 y DT 13Âª.2 LI | money |  |
| 02639 | `is_correccion_libertad_amortizacion_mantenimiento_empleo_saldo_inicial` | Libertad de amortizaciÃ³n con mantenimiento de empleo (RDL 6/2010 y DT 13Âª.2 LI | money |  |
| 02640 | `is_correccion_libertad_amortizacion_mantenimiento_empleo_saldo_final` | Libertad de amortizaciÃ³n con mantenimiento de empleo (RDL 6/2010 y DT 13Âª.2 LI | money |  |
| 02641 | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento` | Libertad de amortizaciÃ³n sin mantenimiento de empleo (RDL 13/2010 y DT 13Âª.2 L | money |  |
| 02642 | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_aumento` | Libertad de amortizaciÃ³n sin mantenimiento de empleo (RDL 13/2010 y DT 13Âª.2 L | money |  |
| 02643 | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_aumento` | Libertad de amortizaciÃ³n sin mantenimiento de empleo (RDL 13/2010 y DT 13Âª.2 L | money |  |
| 02644 | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_saldo_inicial` | Libertad de amortizaciÃ³n sin mantenimiento de empleo (RDL 13/2010 y DT 13Âª.2 L | money |  |
| 02645 | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_saldo_final` | Libertad de amortizaciÃ³n sin mantenimiento de empleo (RDL 13/2010 y DT 13Âª.2 L | money |  |
| 02646 | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_disminucion` | Libertad de amortizaciÃ³n sin mantenimiento de empleo (RDL 13/2010 y DT 13Âª.2 L | money |  |
| 02647 | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_disminucion` | Libertad de amortizaciÃ³n sin mantenimiento de empleo (RDL 13/2010 y DT 13Âª.2 L | money |  |
| 02648 | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_disminucion` | Libertad de amortizaciÃ³n sin mantenimiento de empleo (RDL 13/2010 y DT 13Âª.2 L | money |  |
| 02649 | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_saldo_inicial` | Libertad de amortizaciÃ³n sin mantenimiento de empleo (RDL 13/2010 y DT 13Âª.2 L | money |  |
| 02650 | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_saldo_final` | Libertad de amortizaciÃ³n sin mantenimiento de empleo (RDL 13/2010 y DT 13Âª.2 L | money |  |
| 02651 | `is_correccion_deterioro_art13_1_no_afectado_permanente_aumento` | PÃ©rdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 ni por D | money |  |
| 02652 | `is_correccion_deterioro_art13_1_no_afectado_temporaria_ejercicio_aumento` | PÃ©rdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 ni por D | money |  |
| 02653 | `is_correccion_deterioro_art13_1_no_afectado_temporaria_anteriores_aumento` | PÃ©rdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 ni por D | money |  |
| 02654 | `is_correccion_deterioro_art13_1_no_afectado_saldo_inicial` | PÃ©rdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 ni por D | money |  |
| 02655 | `is_correccion_deterioro_art13_1_no_afectado_saldo_final` | PÃ©rdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 ni por D | money |  |
| 02656 | `is_correccion_deterioro_art13_1_no_afectado_permanente_disminucion` | PÃ©rdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 ni por D | money |  |
| 02657 | `is_correccion_deterioro_art13_1_no_afectado_temporaria_ejercicio_disminucion` | PÃ©rdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 ni por D | money |  |
| 02658 | `is_correccion_deterioro_art13_1_no_afectado_temporaria_anteriores_disminucion` | PÃ©rdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 ni por D | money |  |
| 02659 | `is_correccion_deterioro_art13_1_no_afectado_saldo_inicial` | PÃ©rdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 ni por D | money |  |
| 02660 | `is_correccion_deterioro_art13_1_no_afectado_saldo_final` | PÃ©rdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 ni por D | money |  |
| 02661 | `is_correccion_deterioro_art13_1_provisiones_permanente_aumento` | PÃ©rdidas por deterioro del art. 13.1 LIS y provisiones y gastos (art. 14.1 y 14 | money |  |
| 02662 | `is_correccion_deterioro_art13_1_provisiones_permanente_aumento` | PÃ©rdidas por deterioro del art. 13.1 LIS y provisiones y gastos (art. 14.1 y 14 | money |  |
| 02663 | `is_correccion_deterioro_art13_1_provisiones_permanente_aumento` | PÃ©rdidas por deterioro del art. 13.1 LIS y provisiones y gastos (art. 14.1 y 14 | money |  |
| 02664 | `is_correccion_deterioro_art13_1_provisiones_saldo_inicial` | PÃ©rdidas por deterioro del art. 13.1 LIS y provisiones y gastos (art. 14.1 y 14 | money |  |
| 02665 | `is_correccion_deterioro_art13_1_provisiones_saldo_final` | PÃ©rdidas por deterioro del art. 13.1 LIS y provisiones y gastos (art. 14.1 y 14 | money |  |
| 02666 | `is_correccion_deterioro_art13_1_provisiones_permanente_disminucion` | PÃ©rdidas por deterioro del art. 13.1 LIS y provisiones y gastos (art. 14.1 y 14 | money |  |
| 02667 | `is_correccion_deterioro_art13_1_provisiones_permanente_disminucion` | PÃ©rdidas por deterioro del art. 13.1 LIS y provisiones y gastos (art. 14.1 y 14 | money |  |
| 02668 | `is_correccion_deterioro_art13_1_provisiones_permanente_disminucion` | PÃ©rdidas por deterioro del art. 13.1 LIS y provisiones y gastos (art. 14.1 y 14 | money |  |
| 02669 | `is_correccion_deterioro_art13_1_provisiones_saldo_inicial` | PÃ©rdidas por deterioro del art. 13.1 LIS y provisiones y gastos (art. 14.1 y 14 | money |  |
| 02670 | `is_correccion_deterioro_art13_1_provisiones_saldo_final` | PÃ©rdidas por deterioro del art. 13.1 LIS y provisiones y gastos (art. 14.1 y 14 | money |  |
| 02671 | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_aumento` | PÃ©rdidas por deterioro de IM, inversiones inmobiliarias e II, incluido el fondo | money |  |
| 02672 | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_aumento` | PÃ©rdidas por deterioro de IM, inversiones inmobiliarias e II, incluido el fondo | money |  |
| 02673 | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_aumento` | PÃ©rdidas por deterioro de IM, inversiones inmobiliarias e II, incluido el fondo | money |  |
| 02674 | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_saldo_inicial` | PÃ©rdidas por deterioro de IM, inversiones inmobiliarias e II, incluido el fondo | money |  |
| 02675 | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_saldo_final` | PÃ©rdidas por deterioro de IM, inversiones inmobiliarias e II, incluido el fondo | money |  |
| 02676 | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_disminucion` | PÃ©rdidas por deterioro de IM, inversiones inmobiliarias e II, incluido el fondo | money |  |
| 02677 | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_disminucion` | PÃ©rdidas por deterioro de IM, inversiones inmobiliarias e II, incluido el fondo | money |  |
| 02678 | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_disminucion` | PÃ©rdidas por deterioro de IM, inversiones inmobiliarias e II, incluido el fondo | money |  |
| 02679 | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_saldo_inicial` | PÃ©rdidas por deterioro de IM, inversiones inmobiliarias e II, incluido el fondo | money |  |
| 02680 | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_saldo_final` | PÃ©rdidas por deterioro de IM, inversiones inmobiliarias e II, incluido el fondo | money |  |
| 02681 | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_aumento` | Ajustes por pÃ©rdidas por deterioro de valores representativos de la participaci | money |  |
| 02682 | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_aumento` | Ajustes por pÃ©rdidas por deterioro de valores representativos de la participaci | money |  |
| 02683 | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_aumento` | Ajustes por pÃ©rdidas por deterioro de valores representativos de la participaci | money |  |
| 02684 | `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_inicial` | Ajustes por pÃ©rdidas por deterioro de valores representativos de la participaci | money |  |
| 02685 | `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_final` | Ajustes por pÃ©rdidas por deterioro de valores representativos de la participaci | money |  |
| 02686 | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_disminucion` | Ajustes por pÃ©rdidas por deterioro de valores representativos de la participaci | money |  |
| 02687 | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_disminucion` | Ajustes por pÃ©rdidas por deterioro de valores representativos de la participaci | money |  |
| 02688 | `is_correccion_deterioro_valores_participaciones_art13_2b_permanente_disminucion` | Ajustes por pÃ©rdidas por deterioro de valores representativos de la participaci | money |  |
| 02689 | `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_inicial` | Ajustes por pÃ©rdidas por deterioro de valores representativos de la participaci | money |  |
| 02690 | `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_final` | Ajustes por pÃ©rdidas por deterioro de valores representativos de la participaci | money |  |
| 02711 | `is_correccion_deterioro_valores_representativos_permanente_aumento` | PÃ©rdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y  | money |  |
| 02712 | `is_correccion_deterioro_valores_representativos_temporaria_ejercicio_aumento` | PÃ©rdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y  | money |  |
| 02713 | `is_correccion_deterioro_valores_representativos_temporaria_anteriores_aumento` | PÃ©rdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y  | money |  |
| 02714 | `is_correccion_deterioro_valores_representativos_saldo_inicial` | PÃ©rdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y  | money |  |
| 02715 | `is_correccion_deterioro_valores_representativos_saldo_final` | PÃ©rdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y  | money |  |
| 02716 | `is_correccion_deterioro_valores_representativos_permanente_disminucion` | PÃ©rdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y  | money |  |
| 02717 | `is_correccion_deterioro_valores_representativos_temporaria_ejercicio_disminucion` | PÃ©rdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y  | money |  |
| 02718 | `is_correccion_deterioro_valores_representativos_temporaria_anteriores_disminucion` | PÃ©rdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y  | money |  |
| 02719 | `is_correccion_deterioro_valores_representativos_saldo_inicial` | PÃ©rdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y  | money |  |
| 02720 | `is_correccion_deterioro_valores_representativos_saldo_final` | PÃ©rdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y  | money |  |
| 02721 | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_aumento` | AplicaciÃ³n del lÃ­mite del art. 11.12 LIS a las pÃ©rdidas por deterioro del art | money |  |
| 02722 | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_aumento` | AplicaciÃ³n del lÃ­mite del art. 11.12 LIS a las pÃ©rdidas por deterioro del art | money |  |
| 02723 | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_aumento` | AplicaciÃ³n del lÃ­mite del art. 11.12 LIS a las pÃ©rdidas por deterioro del art | money |  |
| 02724 | `is_correccion_limite_art11_12_perdidas_deterioro_saldo_inicial` | AplicaciÃ³n del lÃ­mite del art. 11.12 LIS a las pÃ©rdidas por deterioro del art | money |  |
| 02725 | `is_correccion_limite_art11_12_perdidas_deterioro_saldo_final` | AplicaciÃ³n del lÃ­mite del art. 11.12 LIS a las pÃ©rdidas por deterioro del art | money |  |
| 02726 | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_disminucion` | AplicaciÃ³n del lÃ­mite del art. 11.12 LIS a las pÃ©rdidas por deterioro del art | money |  |
| 02727 | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_disminucion` | AplicaciÃ³n del lÃ­mite del art. 11.12 LIS a las pÃ©rdidas por deterioro del art | money |  |
| 02728 | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_disminucion` | AplicaciÃ³n del lÃ­mite del art. 11.12 LIS a las pÃ©rdidas por deterioro del art | money |  |
| 02729 | `is_correccion_limite_art11_12_perdidas_deterioro_saldo_inicial` | AplicaciÃ³n del lÃ­mite del art. 11.12 LIS a las pÃ©rdidas por deterioro del art | money |  |
| 02730 | `is_correccion_limite_art11_12_perdidas_deterioro_saldo_final` | AplicaciÃ³n del lÃ­mite del art. 11.12 LIS a las pÃ©rdidas por deterioro del art | money |  |
| 02731 | `is_correccion_pensiones_provisiones_no_deducibles_permanente_aumento` | Gastos y provisiones por pensiones no afectados por el art. 11.12 LIS (art. 14.1 | money |  |
| 02732 | `is_correccion_pensiones_provisiones_no_deducibles_temporaria_ejercicio_aumento` | Gastos y provisiones por pensiones no afectados por el art. 11.12 LIS (art. 14.1 | money |  |
| 02733 | `is_correccion_pensiones_provisiones_no_deducibles_temporaria_anteriores_aumento` | Gastos y provisiones por pensiones no afectados por el art. 11.12 LIS (art. 14.1 | money |  |
| 02734 | `is_correccion_pensiones_provisiones_no_deducibles_saldo_inicial` | Gastos y provisiones por pensiones no afectados por el art. 11.12 LIS (art. 14.1 | money |  |
| 02735 | `is_correccion_pensiones_provisiones_no_deducibles_saldo_final` | Gastos y provisiones por pensiones no afectados por el art. 11.12 LIS (art. 14.1 | money |  |
| 02736 | `is_correccion_pensiones_provisiones_no_deducibles_permanente_disminucion` | Gastos y provisiones por pensiones no afectados por el art. 11.12 LIS (art. 14.1 | money |  |
| 02737 | `is_correccion_pensiones_provisiones_no_deducibles_temporaria_ejercicio_disminucion` | Gastos y provisiones por pensiones no afectados por el art. 11.12 LIS (art. 14.1 | money |  |
| 02738 | `is_correccion_pensiones_provisiones_no_deducibles_temporaria_anteriores_disminucion` | Gastos y provisiones por pensiones no afectados por el art. 11.12 LIS (art. 14.1 | money |  |
| 02739 | `is_correccion_pensiones_provisiones_no_deducibles_saldo_inicial` | Gastos y provisiones por pensiones no afectados por el art. 11.12 LIS (art. 14.1 | money |  |
| 02740 | `is_correccion_pensiones_provisiones_no_deducibles_saldo_final` | Gastos y provisiones por pensiones no afectados por el art. 11.12 LIS (art. 14.1 | money |  |
| 02741 | `is_correccion_provisiones_no_deducibles_art14_permanente_aumento` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no afectadas por el ar | money |  |
| 02742 | `is_correccion_provisiones_no_deducibles_art14_temporaria_ejercicio_aumento` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no afectadas por el ar | money |  |
| 02743 | `is_correccion_provisiones_no_deducibles_art14_temporaria_anteriores_aumento` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no afectadas por el ar | money |  |
| 02744 | `is_correccion_provisiones_no_deducibles_art14_saldo_inicial` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no afectadas por el ar | money |  |
| 02745 | `is_correccion_provisiones_no_deducibles_art14_saldo_final` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no afectadas por el ar | money |  |
| 02746 | `is_correccion_provisiones_no_deducibles_art14_permanente_disminucion` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no afectadas por el ar | money |  |
| 02747 | `is_correccion_provisiones_no_deducibles_art14_temporaria_ejercicio_disminucion` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no afectadas por el ar | money |  |
| 02748 | `is_correccion_provisiones_no_deducibles_art14_temporaria_anteriores_disminucion` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no afectadas por el ar | money |  |
| 02749 | `is_correccion_provisiones_no_deducibles_art14_saldo_inicial` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no afectadas por el ar | money |  |
| 02750 | `is_correccion_provisiones_no_deducibles_art14_saldo_final` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no afectadas por el ar | money |  |
| 02751 | `is_correccion_asimetrias_hibridas_art15bis_permanente_disminucion` | AsimetrÃ­as hÃ­bridas (art. 15 bis LIS, excepto art. 15 bis.12 LIS) - DisminuciÃ | money |  |
| 02752 | `is_correccion_asimetrias_hibridas_art15bis_temporaria_ejercicio_disminucion` | AsimetrÃ­as hÃ­bridas (art. 15 bis LIS, excepto art. 15 bis.12 LIS) - DisminuciÃ | money |  |
| 02753 | `is_correccion_asimetrias_hibridas_art15bis_temporaria_anteriores_disminucion` | AsimetrÃ­as hÃ­bridas (art. 15 bis LIS, excepto art. 15 bis.12 LIS) - DisminuciÃ | money |  |
| 02754 | `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial` | AsimetrÃ­as hÃ­bridas (art. 15 bis LIS, excepto art. 15 bis.12 LIS) - DisminuciÃ | money |  |
| 02755 | `is_correccion_asimetrias_hibridas_art15bis_saldo_final` | AsimetrÃ­as hÃ­bridas (art. 15 bis LIS, excepto art. 15 bis.12 LIS) - DisminuciÃ | money |  |
| 02756 | `is_correccion_subvenciones_publicas_no_integrables_art14_8_permanente_disminucion` | Subvenciones pÃºblicas incluidas en el resultado del ejercicio, no integrables e | money |  |
| 02761 | `is_correccion_gastos_retribucion_fondos_propios_art15a_permanente_aumento` | Gastos no deducibles por considerarse retribuciÃ³n de fondos propios (art. 15 a) | money |  |
| 02769 | `is_correccion_limite_beneficio_operativo_saldo_inicial` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 02770 | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 02771 | `is_correccion_multas_sanciones_art15c_permanente_aumento` | Multas, sanciones y otros (art. 15 c) LIS) - Aumento - Correcciones del ejercici | money |  |
| 02772 | `is_correccion_limite_beneficio_operativo_saldo_final` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 02781 | `is_correccion_perdidas_juego_art15d_permanente_aumento` | PÃ©rdidas del juego (art. 15 d) LIS) - Aumento - Correcciones del ejercicio - Pe | money |  |
| 02791 | `is_correccion_donativos_liberalidades_art15e_permanente_aumento` | Gastos por donativos y liberalidades (art. 15 e) LIS) - Aumento - Correcciones d | money |  |
| 02800 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2023 -  | money |  |
| 02801 | `is_correccion_gastos_contrarios_ordenamiento_art15f_permanente_aumento` | Gastos de actuaciones contrarias al ordenamiento jurÃ­dico (art. 15 f) LIS) - Au | money |  |
| 02802 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2023 -  | money |  |
| 02803 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2023 -  | money |  |
| 02804 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2024 -  | money |  |
| 02805 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2024 -  | money |  |
| 02806 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2024 -  | money |  |
| 02810 | `is_correccion_reversion_deterioro_valores_dotaciones_aplicadas` | ReversiÃ³n por deterioro de valores representativos - Dotaciones integradas en e | money |  |
| 02811 | `is_correccion_operaciones_jurisdicciones_no_cooperativas_permanente_aumento` | Operaciones realizadas con jurisdicciones no cooperativas (art. 15 g) LIS) - Aum | money |  |
| 02812 | `is_correccion_operaciones_jurisdicciones_no_cooperativas_temporaria_ejercicio_aumento` | Operaciones realizadas con jurisdicciones no cooperativas (art. 15 g) LIS) - Aum | money |  |
| 02813 | `is_correccion_operaciones_jurisdicciones_no_cooperativas_temporaria_anteriores_aumento` | Operaciones realizadas con jurisdicciones no cooperativas (art. 15 g) LIS) - Aum | money |  |
| 02814 | `is_correccion_operaciones_jurisdicciones_no_cooperativas_saldo_inicial` | Operaciones realizadas con jurisdicciones no cooperativas (art. 15 g) LIS) - Aum | money |  |
| 02815 | `is_correccion_operaciones_jurisdicciones_no_cooperativas_saldo_final` | Operaciones realizadas con jurisdicciones no cooperativas (art. 15 g) LIS) - Aum | money |  |
| 02816 | `is_correccion_operaciones_jurisdicciones_no_cooperativas_permanente_disminucion` | Operaciones realizadas con jurisdicciones no cooperativas (art. 15 g) LIS) - Dis | money |  |
| 02817 | `is_correccion_operaciones_jurisdicciones_no_cooperativas_temporaria_ejercicio_disminucion` | Operaciones realizadas con jurisdicciones no cooperativas (art. 15 g) LIS) - Dis | money |  |
| 02818 | `is_correccion_operaciones_jurisdicciones_no_cooperativas_temporaria_anteriores_disminucion` | Operaciones realizadas con jurisdicciones no cooperativas (art. 15 g) LIS) - Dis | money |  |
| 02819 | `is_correccion_operaciones_jurisdicciones_no_cooperativas_saldo_inicial` | Operaciones realizadas con jurisdicciones no cooperativas (art. 15 g) LIS) - Dis | money |  |
| 02820 | `is_correccion_operaciones_jurisdicciones_no_cooperativas_saldo_final` | Operaciones realizadas con jurisdicciones no cooperativas (art. 15 g) LIS) - Dis | money |  |
| 02821 | `is_correccion_gastos_financieros_deudas_grupo_art15h_permanente_aumento` | Gastos financieros derivados de deudas con entidades del grupo (art. 15 h) LIS)  | money |  |
| 02831 | `is_correccion_gastos_extincion_relacion_laboral_art15i_permanente_aumento` | Gastos derivados de la extinciÃ³n de la relaciÃ³n laboral o mercantil (art. 15 i | money |  |
| 02851 | `is_correccion_deterioro_valores_participaciones_entidades_permanente_aumento` | PÃ©rdidas por deterioro de valores repr. de partic. en el capital o fondos propi | money |  |
| 02852 | `is_correccion_deterioro_valores_participaciones_entidades_temporaria_ejercicio_aumento` | PÃ©rdidas por deterioro de valores repr. de partic. en el capital o fondos propi | money |  |
| 02853 | `is_correccion_deterioro_valores_participaciones_entidades_temporaria_anteriores_aumento` | PÃ©rdidas por deterioro de valores repr. de partic. en el capital o fondos propi | money |  |
| 02854 | `is_correccion_deterioro_valores_participaciones_entidades_saldo_inicial` | PÃ©rdidas por deterioro de valores repr. de partic. en el capital o fondos propi | money |  |
| 02855 | `is_correccion_deterioro_valores_participaciones_entidades_saldo_final` | PÃ©rdidas por deterioro de valores repr. de partic. en el capital o fondos propi | money |  |
| 02856 | `is_correccion_deterioro_valores_participaciones_entidades_permanente_disminucion` | PÃ©rdidas por deterioro de valores repr. de partic. en el capital o fondos propi | money |  |
| 02857 | `is_correccion_deterioro_valores_participaciones_entidades_temporaria_ejercicio_disminucion` | PÃ©rdidas por deterioro de valores repr. de partic. en el capital o fondos propi | money |  |
| 02858 | `is_correccion_deterioro_valores_participaciones_entidades_temporaria_anteriores_disminucion` | PÃ©rdidas por deterioro de valores repr. de partic. en el capital o fondos propi | money |  |
| 02859 | `is_correccion_deterioro_valores_participaciones_entidades_saldo_inicial` | PÃ©rdidas por deterioro de valores repr. de partic. en el capital o fondos propi | money |  |
| 02860 | `is_correccion_deterioro_valores_participaciones_entidades_saldo_final` | PÃ©rdidas por deterioro de valores repr. de partic. en el capital o fondos propi | money |  |
| 02861 | `is_correccion_disminucion_valor_criterio_valor_razonable_permanente_aumento` | DisminuciÃ³n de valor originada por criterio de valor razonable (art. 15 l) LIS) | money |  |
| 02862 | `is_correccion_disminucion_valor_criterio_valor_razonable_temporaria_ejercicio_aumento` | DisminuciÃ³n de valor originada por criterio de valor razonable (art. 15 l) LIS) | money |  |
| 02863 | `is_correccion_disminucion_valor_criterio_valor_razonable_temporaria_anteriores_aumento` | DisminuciÃ³n de valor originada por criterio de valor razonable (art. 15 l) LIS) | money |  |
| 02864 | `is_correccion_disminucion_valor_criterio_valor_razonable_saldo_inicial` | DisminuciÃ³n de valor originada por criterio de valor razonable (art. 15 l) LIS) | money |  |
| 02865 | `is_correccion_disminucion_valor_criterio_valor_razonable_saldo_final` | DisminuciÃ³n de valor originada por criterio de valor razonable (art. 15 l) LIS) | money |  |
| 02866 | `is_correccion_disminucion_valor_criterio_valor_razonable_permanente_disminucion` | DisminuciÃ³n de valor originada por criterio de valor razonable (art. 15 l) LIS) | money |  |
| 02867 | `is_correccion_disminucion_valor_criterio_valor_razonable_temporaria_ejercicio_disminucion` | DisminuciÃ³n de valor originada por criterio de valor razonable (art. 15 l) LIS) | money |  |
| 02868 | `is_correccion_disminucion_valor_criterio_valor_razonable_temporaria_anteriores_disminucion` | DisminuciÃ³n de valor originada por criterio de valor razonable (art. 15 l) LIS) | money |  |
| 02869 | `is_correccion_disminucion_valor_criterio_valor_razonable_saldo_inicial` | DisminuciÃ³n de valor originada por criterio de valor razonable (art. 15 l) LIS) | money |  |
| 02870 | `is_correccion_disminucion_valor_criterio_valor_razonable_saldo_final` | DisminuciÃ³n de valor originada por criterio de valor razonable (art. 15 l) LIS) | money |  |
| 02871 | `is_correccion_deuda_tributaria_ajd_itp_permanente_aumento` | Deuda tributaria de actos jurÃ­dicos documentados (ITP y AJD) (art. 15 m) LIS) - | money |  |
| 02872 | `is_correccion_deuda_tributaria_ajd_itp_temporaria_ejercicio_aumento` | Deuda tributaria de actos jurÃ­dicos documentados (ITP y AJD) (art. 15 m) LIS) - | money |  |
| 02873 | `is_correccion_deuda_tributaria_ajd_itp_temporaria_anteriores_aumento` | Deuda tributaria de actos jurÃ­dicos documentados (ITP y AJD) (art. 15 m) LIS) - | money |  |
| 02874 | `is_correccion_deuda_tributaria_ajd_itp_saldo_inicial` | Deuda tributaria de actos jurÃ­dicos documentados (ITP y AJD) (art. 15 m) LIS) - | money |  |
| 02875 | `is_correccion_deuda_tributaria_ajd_itp_saldo_final` | Deuda tributaria de actos jurÃ­dicos documentados (ITP y AJD) (art. 15 m) LIS) - | money |  |
| 02876 | `is_correccion_deuda_tributaria_ajd_itp_permanente_disminucion` | Deuda tributaria de actos jurÃ­dicos documentados (ITP y AJD) (art. 15 m) LIS) - | money |  |
| 02877 | `is_correccion_deuda_tributaria_ajd_itp_temporaria_ejercicio_disminucion` | Deuda tributaria de actos jurÃ­dicos documentados (ITP y AJD) (art. 15 m) LIS) - | money |  |
| 02878 | `is_correccion_deuda_tributaria_ajd_itp_temporaria_anteriores_disminucion` | Deuda tributaria de actos jurÃ­dicos documentados (ITP y AJD) (art. 15 m) LIS) - | money |  |
| 02879 | `is_correccion_deuda_tributaria_ajd_itp_saldo_inicial` | Deuda tributaria de actos jurÃ­dicos documentados (ITP y AJD) (art. 15 m) LIS) - | money |  |
| 02880 | `is_correccion_deuda_tributaria_ajd_itp_saldo_final` | Deuda tributaria de actos jurÃ­dicos documentados (ITP y AJD) (art. 15 m) LIS) - | money |  |
| 02881 | `is_correccion_limitacion_gastos_financieros_art16_permanente_aumento` | Ajustes por la limitaciÃ³n en la deducibilidad de gastos financieros (art. 16 LI | money |  |
| 02882 | `is_correccion_limitacion_gastos_financieros_art16_temporaria_ejercicio_aumento` | Ajustes por la limitaciÃ³n en la deducibilidad de gastos financieros (art. 16 LI | money |  |
| 02883 | `is_correccion_limitacion_gastos_financieros_art16_temporaria_anteriores_aumento` | Ajustes por la limitaciÃ³n en la deducibilidad de gastos financieros (art. 16 LI | money |  |
| 02884 | `is_correccion_limitacion_gastos_financieros_art16_saldo_inicial` | Ajustes por la limitaciÃ³n en la deducibilidad de gastos financieros (art. 16 LI | money |  |
| 02885 | `is_correccion_limitacion_gastos_financieros_art16_saldo_final` | Ajustes por la limitaciÃ³n en la deducibilidad de gastos financieros (art. 16 LI | money |  |
| 02886 | `is_correccion_limitacion_gastos_financieros_art16_permanente_disminucion` | Ajustes por la limitaciÃ³n en la deducibilidad de gastos financieros (art. 16 LI | money |  |
| 02887 | `is_correccion_limitacion_gastos_financieros_art16_temporaria_ejercicio_disminucion` | Ajustes por la limitaciÃ³n en la deducibilidad de gastos financieros (art. 16 LI | money |  |
| 02888 | `is_correccion_limitacion_gastos_financieros_art16_temporaria_anteriores_disminucion` | Ajustes por la limitaciÃ³n en la deducibilidad de gastos financieros (art. 16 LI | money |  |
| 02889 | `is_correccion_limitacion_gastos_financieros_art16_saldo_inicial` | Ajustes por la limitaciÃ³n en la deducibilidad de gastos financieros (art. 16 LI | money |  |
| 02890 | `is_correccion_limitacion_gastos_financieros_art16_saldo_final` | Ajustes por la limitaciÃ³n en la deducibilidad de gastos financieros (art. 16 LI | money |  |
| 02891 | `is_correccion_revalorizaciones_contables_art17_1_permanente_aumento` | Revalorizaciones contables (art. 17.1 LIS) - Aumento - Correcciones del ejercici | money |  |
| 02892 | `is_correccion_revalorizaciones_contables_art17_1_temporaria_ejercicio_aumento` | Revalorizaciones contables (art. 17.1 LIS) - Aumento - Correcciones del ejercici | money |  |
| 02893 | `is_correccion_revalorizaciones_contables_art17_1_temporaria_anteriores_aumento` | Revalorizaciones contables (art. 17.1 LIS) - Aumento - Correcciones del ejercici | money |  |
| 02894 | `is_correccion_revalorizaciones_contables_art17_1_saldo_inicial` | Revalorizaciones contables (art. 17.1 LIS) - Aumento - Saldo pendiente a princip | money |  |
| 02895 | `is_correccion_revalorizaciones_contables_art17_1_saldo_final` | Revalorizaciones contables (art. 17.1 LIS) - Aumento - Saldo pendiente a fin de  | money |  |
| 02896 | `is_correccion_revalorizaciones_contables_art17_1_permanente_disminucion` | Revalorizaciones contables (art. 17.1 LIS) - DisminuciÃ³n - Correcciones del eje | money |  |
| 02897 | `is_correccion_revalorizaciones_contables_art17_1_temporaria_ejercicio_disminucion` | Revalorizaciones contables (art. 17.1 LIS) - DisminuciÃ³n - Correcciones del eje | money |  |
| 02898 | `is_correccion_revalorizaciones_contables_art17_1_temporaria_anteriores_disminucion` | Revalorizaciones contables (art. 17.1 LIS) - DisminuciÃ³n - Correcciones del eje | money |  |
| 02899 | `is_correccion_revalorizaciones_contables_art17_1_saldo_inicial` | Revalorizaciones contables (art. 17.1 LIS) - DisminuciÃ³n - Saldo pendiente a pr | money |  |
| 02900 | `is_correccion_revalorizaciones_contables_art17_1_saldo_final` | Revalorizaciones contables (art. 17.1 LIS) - DisminuciÃ³n - Saldo pendiente a fi | money |  |
| 02901 | `is_correccion_operaciones_aumento_capital_fondos_propios_permanente_aumento` | Operaciones de aumento de capital o fondos propios por compensaciÃ³n de crÃ©dito | money |  |
| 02902 | `is_correccion_operaciones_aumento_capital_fondos_propios_temporaria_ejercicio_aumento` | Operaciones de aumento de capital o fondos propios por compensaciÃ³n de crÃ©dito | money |  |
| 02903 | `is_correccion_operaciones_aumento_capital_fondos_propios_temporaria_anteriores_aumento` | Operaciones de aumento de capital o fondos propios por compensaciÃ³n de crÃ©dito | money |  |
| 02904 | `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_inicial` | Operaciones de aumento de capital o fondos propios por compensaciÃ³n de crÃ©dito | money |  |
| 02905 | `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_final` | Operaciones de aumento de capital o fondos propios por compensaciÃ³n de crÃ©dito | money |  |
| 02906 | `is_correccion_operaciones_aumento_capital_fondos_propios_permanente_disminucion` | Operaciones de aumento de capital o fondos propios por compensaciÃ³n de crÃ©dito | money |  |
| 02907 | `is_correccion_operaciones_aumento_capital_fondos_propios_temporaria_ejercicio_disminucion` | Operaciones de aumento de capital o fondos propios por compensaciÃ³n de crÃ©dito | money |  |
| 02908 | `is_correccion_operaciones_aumento_capital_fondos_propios_temporaria_anteriores_disminucion` | Operaciones de aumento de capital o fondos propios por compensaciÃ³n de crÃ©dito | money |  |
| 02909 | `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_inicial` | Operaciones de aumento de capital o fondos propios por compensaciÃ³n de crÃ©dito | money |  |
| 02910 | `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_final` | Operaciones de aumento de capital o fondos propios por compensaciÃ³n de crÃ©dito | money |  |
| 02911 | `is_correccion_socio_sicav_reducciones_capital_permanente_aumento` | Socio SICAV: Reducciones de capital y distribuciÃ³n de la prima de emisiÃ³n (art | money |  |
| 02921 | `is_correccion_transmisiones_lucrativas_societarias_permanente_aumento` | Transmisiones lucrativas y societarias: aplicaciÃ³n del valor de mercado (art. 1 | money |  |
| 02922 | `is_correccion_transmisiones_lucrativas_societarias_temporaria_ejercicio_aumento` | Transmisiones lucrativas y societarias: aplicaciÃ³n del valor de mercado (art. 1 | money |  |
| 02923 | `is_correccion_transmisiones_lucrativas_societarias_temporaria_anteriores_aumento` | Transmisiones lucrativas y societarias: aplicaciÃ³n del valor de mercado (art. 1 | money |  |
| 02924 | `is_correccion_transmisiones_lucrativas_societarias_saldo_inicial` | Transmisiones lucrativas y societarias: aplicaciÃ³n del valor de mercado (art. 1 | money |  |
| 02925 | `is_correccion_transmisiones_lucrativas_societarias_saldo_final` | Transmisiones lucrativas y societarias: aplicaciÃ³n del valor de mercado (art. 1 | money |  |
| 02926 | `is_correccion_transmisiones_lucrativas_societarias_permanente_disminucion` | Transmisiones lucrativas y societarias: aplicaciÃ³n del valor de mercado (art. 1 | money |  |
| 02927 | `is_correccion_transmisiones_lucrativas_societarias_temporaria_ejercicio_disminucion` | Transmisiones lucrativas y societarias: aplicaciÃ³n del valor de mercado (art. 1 | money |  |
| 02928 | `is_correccion_transmisiones_lucrativas_societarias_temporaria_anteriores_disminucion` | Transmisiones lucrativas y societarias: aplicaciÃ³n del valor de mercado (art. 1 | money |  |
| 02929 | `is_correccion_transmisiones_lucrativas_societarias_saldo_inicial` | Transmisiones lucrativas y societarias: aplicaciÃ³n del valor de mercado (art. 1 | money |  |
| 02930 | `is_correccion_transmisiones_lucrativas_societarias_saldo_final` | Transmisiones lucrativas y societarias: aplicaciÃ³n del valor de mercado (art. 1 | money |  |
| 02931 | `is_correccion_operaciones_vinculadas_valor_mercado_permanente_aumento` | Operaciones vinculadas: aplicaciÃ³n del valor de mercado (art. 18 LIS ) - Aument | money |  |
| 02932 | `is_correccion_operaciones_vinculadas_valor_mercado_temporaria_ejercicio_aumento` | Operaciones vinculadas: aplicaciÃ³n del valor de mercado (art. 18 LIS ) - Aument | money |  |
| 02933 | `is_correccion_operaciones_vinculadas_valor_mercado_temporaria_anteriores_aumento` | Operaciones vinculadas: aplicaciÃ³n del valor de mercado (art. 18 LIS ) - Aument | money |  |
| 02934 | `is_correccion_operaciones_vinculadas_valor_mercado_saldo_inicial` | Operaciones vinculadas: aplicaciÃ³n del valor de mercado (art. 18 LIS ) - Aument | money |  |
| 02935 | `is_correccion_operaciones_vinculadas_valor_mercado_saldo_final` | Operaciones vinculadas: aplicaciÃ³n del valor de mercado (art. 18 LIS ) - Aument | money |  |
| 02936 | `is_correccion_operaciones_vinculadas_valor_mercado_permanente_disminucion` | Operaciones vinculadas: aplicaciÃ³n del valor de mercado (art. 18 LIS ) - Dismin | money |  |
| 02937 | `is_correccion_operaciones_vinculadas_valor_mercado_temporaria_ejercicio_disminucion` | Operaciones vinculadas: aplicaciÃ³n del valor de mercado (art. 18 LIS ) - Dismin | money |  |
| 02938 | `is_correccion_operaciones_vinculadas_valor_mercado_temporaria_anteriores_disminucion` | Operaciones vinculadas: aplicaciÃ³n del valor de mercado (art. 18 LIS ) - Dismin | money |  |
| 02939 | `is_correccion_operaciones_vinculadas_valor_mercado_saldo_inicial` | Operaciones vinculadas: aplicaciÃ³n del valor de mercado (art. 18 LIS ) - Dismin | money |  |
| 02940 | `is_correccion_operaciones_vinculadas_valor_mercado_saldo_final` | Operaciones vinculadas: aplicaciÃ³n del valor de mercado (art. 18 LIS ) - Dismin | money |  |
| 02951 | `is_correccion_efectos_valoracion_contable_diferente_fiscal_permanente_aumento` | Efectos de la valoraciÃ³n contable diferente a la fiscal (art. 20 LIS) - Aumento | money |  |
| 02952 | `is_correccion_efectos_valoracion_contable_diferente_fiscal_temporaria_ejercicio_aumento` | Efectos de la valoraciÃ³n contable diferente a la fiscal (art. 20 LIS) - Aumento | money |  |
| 02953 | `is_correccion_efectos_valoracion_contable_diferente_fiscal_temporaria_anteriores_aumento` | Efectos de la valoraciÃ³n contable diferente a la fiscal (art. 20 LIS) - Aumento | money |  |
| 02954 | `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_inicial` | Efectos de la valoraciÃ³n contable diferente a la fiscal (art. 20 LIS) - Aumento | money |  |
| 02955 | `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_final` | Efectos de la valoraciÃ³n contable diferente a la fiscal (art. 20 LIS) - Aumento | money |  |
| 02956 | `is_correccion_efectos_valoracion_contable_diferente_fiscal_permanente_disminucion` | Efectos de la valoraciÃ³n contable diferente a la fiscal (art. 20 LIS) - Disminu | money |  |
| 02957 | `is_correccion_efectos_valoracion_contable_diferente_fiscal_temporaria_ejercicio_disminucion` | Efectos de la valoraciÃ³n contable diferente a la fiscal (art. 20 LIS) - Disminu | money |  |
| 02958 | `is_correccion_efectos_valoracion_contable_diferente_fiscal_temporaria_anteriores_disminucion` | Efectos de la valoraciÃ³n contable diferente a la fiscal (art. 20 LIS) - Disminu | money |  |
| 02959 | `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_inicial` | Efectos de la valoraciÃ³n contable diferente a la fiscal (art. 20 LIS) - Disminu | money |  |
| 02960 | `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_final` | Efectos de la valoraciÃ³n contable diferente a la fiscal (art. 20 LIS) - Disminu | money |  |
| 02972 | `is_correccion_limite_beneficio_operativo_saldo_final` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 03031 | `is_correccion_reduccion_rentas_activos_intangibles_permanente_aumento` | ReducciÃ³n de rentas procedentes de determinados activos intangibles (art. 23 LI | money |  |
| 03032 | `is_correccion_reduccion_rentas_activos_intangibles_temporaria_ejercicio_aumento` | ReducciÃ³n de rentas procedentes de determinados activos intangibles (art. 23 LI | money |  |
| 03033 | `is_correccion_reduccion_rentas_activos_intangibles_temporaria_anteriores_aumento` | ReducciÃ³n de rentas procedentes de determinados activos intangibles (art. 23 LI | money |  |
| 03034 | `is_correccion_reduccion_rentas_activos_intangibles_saldo_inicial` | ReducciÃ³n de rentas procedentes de determinados activos intangibles (art. 23 LI | money |  |
| 03035 | `is_correccion_reduccion_rentas_activos_intangibles_saldo_final` | ReducciÃ³n de rentas procedentes de determinados activos intangibles (art. 23 LI | money |  |
| 03036 | `is_correccion_reduccion_rentas_activos_intangibles_permanente_disminucion` | ReducciÃ³n de rentas procedentes de determinados activos intangibles (art. 23 LI | money |  |
| 03037 | `is_correccion_reduccion_rentas_activos_intangibles_temporaria_ejercicio_disminucion` | ReducciÃ³n de rentas procedentes de determinados activos intangibles (art. 23 LI | money |  |
| 03038 | `is_correccion_reduccion_rentas_activos_intangibles_temporaria_anteriores_disminucion` | ReducciÃ³n de rentas procedentes de determinados activos intangibles (art. 23 LI | money |  |
| 03039 | `is_correccion_reduccion_rentas_activos_intangibles_saldo_inicial` | ReducciÃ³n de rentas procedentes de determinados activos intangibles (art. 23 LI | money |  |
| 03040 | `is_correccion_reduccion_rentas_activos_intangibles_saldo_final` | ReducciÃ³n de rentas procedentes de determinados activos intangibles (art. 23 LI | money |  |
| 03051 | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_aumento` | Impuesto extranjero soportado por el contribuyente, no deducible por afectar a r | money |  |
| 03052 | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_aumento` | Impuesto extranjero soportado por el contribuyente, no deducible por afectar a r | money |  |
| 03053 | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_aumento` | Impuesto extranjero soportado por el contribuyente, no deducible por afectar a r | money |  |
| 03054 | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_saldo_inicial` | Impuesto extranjero soportado por el contribuyente, no deducible por afectar a r | money |  |
| 03055 | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_saldo_final` | Impuesto extranjero soportado por el contribuyente, no deducible por afectar a r | money |  |
| 03056 | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_disminucion` | Impuesto extranjero soportado por el contribuyente, no deducible por afectar a r | money |  |
| 03057 | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_disminucion` | Impuesto extranjero soportado por el contribuyente, no deducible por afectar a r | money |  |
| 03058 | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_disminucion` | Impuesto extranjero soportado por el contribuyente, no deducible por afectar a r | money |  |
| 03059 | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_saldo_inicial` | Impuesto extranjero soportado por el contribuyente, no deducible por afectar a r | money |  |
| 03060 | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_saldo_final` | Impuesto extranjero soportado por el contribuyente, no deducible por afectar a r | money |  |
| 03061 | `is_correccion_impuesto_extranjero_art32_1_permanente_aumento` | Impuesto extranjero sobre los beneficios con cargo a los cuales se pagan los div | money |  |
| 03121 | `is_correccion_bases_negativas_grupo_fiscal_permanente_aumento` | Bases imp. negativas generadas dentro del grupo fiscal por la ent. transmitida y | money |  |
| 03122 | `is_correccion_bases_negativas_grupo_fiscal_permanente_aumento` | Bases imp. negativas generadas dentro del grupo fiscal por la ent. transmitida y | money |  |
| 03123 | `is_correccion_bases_negativas_grupo_fiscal_permanente_aumento` | Bases imp. negativas generadas dentro del grupo fiscal por la ent. transmitida y | money |  |
| 03124 | `is_correccion_bases_negativas_grupo_fiscal_saldo_inicial` | Bases imp. negativas generadas dentro del grupo fiscal por la ent. transmitida y | money |  |
| 03125 | `is_correccion_bases_negativas_grupo_fiscal_saldo_final` | Bases imp. negativas generadas dentro del grupo fiscal por la ent. transmitida y | money |  |
| 03126 | `is_correccion_bases_negativas_grupo_fiscal_permanente_disminucion` | Bases imp. negativas generadas dentro del grupo fiscal por la ent. transmitida y | money |  |
| 03127 | `is_correccion_bases_negativas_grupo_fiscal_permanente_disminucion` | Bases imp. negativas generadas dentro del grupo fiscal por la ent. transmitida y | money |  |
| 03128 | `is_correccion_bases_negativas_grupo_fiscal_permanente_disminucion` | Bases imp. negativas generadas dentro del grupo fiscal por la ent. transmitida y | money |  |
| 03129 | `is_correccion_bases_negativas_grupo_fiscal_saldo_inicial` | Bases imp. negativas generadas dentro del grupo fiscal por la ent. transmitida y | money |  |
| 03130 | `is_correccion_bases_negativas_grupo_fiscal_saldo_final` | Bases imp. negativas generadas dentro del grupo fiscal por la ent. transmitida y | money |  |
| 03141 | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_aumento` | ValoraciÃ³n de bienes y derechos. RÃ©gimen especial operaciones reestructuraciÃ³ | money |  |
| 03142 | `is_correccion_valoracion_bienes_derechos_regimen_especial_temporaria_ejercicio_aumento` | ValoraciÃ³n de bienes y derechos. RÃ©gimen especial operaciones reestructuraciÃ³ | money |  |
| 03143 | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_aumento` | ValoraciÃ³n de bienes y derechos. RÃ©gimen especial operaciones reestructuraciÃ³ | money |  |
| 03144 | `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_inicial` | ValoraciÃ³n de bienes y derechos. RÃ©gimen especial operaciones reestructuraciÃ³ | money |  |
| 03145 | `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final` | ValoraciÃ³n de bienes y derechos. RÃ©gimen especial operaciones reestructuraciÃ³ | money |  |
| 03146 | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_disminucion` | ValoraciÃ³n de bienes y derechos. RÃ©gimen especial operaciones reestructuraciÃ³ | money |  |
| 03147 | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_disminucion` | ValoraciÃ³n de bienes y derechos. RÃ©gimen especial operaciones reestructuraciÃ³ | money |  |
| 03148 | `is_correccion_valoracion_bienes_derechos_regimen_especial_permanente_disminucion` | ValoraciÃ³n de bienes y derechos. RÃ©gimen especial operaciones reestructuraciÃ³ | money |  |
| 03149 | `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_inicial` | ValoraciÃ³n de bienes y derechos. RÃ©gimen especial operaciones reestructuraciÃ³ | money |  |
| 03150 | `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final` | ValoraciÃ³n de bienes y derechos. RÃ©gimen especial operaciones reestructuraciÃ³ | money |  |
| 03246 | `is_correccion_montes_vecinales_cap_xv_permanente_disminucion` | Montes vecinales en mano comÃºn (capÃ­tulo XV del tÃ­tulo VII LIS) - DisminuciÃ³ | money |  |
| 03261 | `is_correccion_aportaciones_entidades_sin_fines_lucro_permanente_aumento` | Aportaciones y colaboraciÃ³n a favor de entidades sin fines lucrativos - Aumento | money |  |
| 03262 | `is_correccion_aportaciones_entidades_sin_fines_lucro_temporaria_ejercicio_aumento` | Aportaciones y colaboraciÃ³n a favor de entidades sin fines lucrativos - Aumento | money |  |
| 03263 | `is_correccion_aportaciones_entidades_sin_fines_lucro_temporaria_anteriores_aumento` | Aportaciones y colaboraciÃ³n a favor de entidades sin fines lucrativos - Aumento | money |  |
| 03264 | `is_correccion_aportaciones_entidades_sin_fines_lucro_saldo_inicial` | Aportaciones y colaboraciÃ³n a favor de entidades sin fines lucrativos - Aumento | money |  |
| 03265 | `is_correccion_aportaciones_entidades_sin_fines_lucro_saldo_final` | Aportaciones y colaboraciÃ³n a favor de entidades sin fines lucrativos - Aumento | money |  |
| 03266 | `is_correccion_aportaciones_entidades_sin_fines_lucro_permanente_disminucion` | Aportaciones y colaboraciÃ³n a favor de entidades sin fines lucrativos - Disminu | money |  |
| 03267 | `is_correccion_aportaciones_entidades_sin_fines_lucro_temporaria_ejercicio_disminucion` | Aportaciones y colaboraciÃ³n a favor de entidades sin fines lucrativos - Disminu | money |  |
| 03268 | `is_correccion_aportaciones_entidades_sin_fines_lucro_temporaria_anteriores_disminucion` | Aportaciones y colaboraciÃ³n a favor de entidades sin fines lucrativos - Disminu | money |  |
| 03269 | `is_correccion_aportaciones_entidades_sin_fines_lucro_saldo_inicial` | Aportaciones y colaboraciÃ³n a favor de entidades sin fines lucrativos - Disminu | money |  |
| 03270 | `is_correccion_aportaciones_entidades_sin_fines_lucro_saldo_final` | Aportaciones y colaboraciÃ³n a favor de entidades sin fines lucrativos - Disminu | money |  |
| 03286 | `is_correccion_cooperativas_fondo_reserva_obligatorio_permanente_disminucion` | Cooperativas: Fondo de reserva obligatorio (Ley 20/1990) - DisminuciÃ³n - Correc | money |  |
| 03316 | `is_correccion_rentas_transmision_inmovilizado_autoridades_portuarias_permanente_disminucion` | Rentas procedentes de transmisiÃ³n de inmovilizado obtenidas por las Autoridades | money |  |
| 03321 | `is_correccion_operaciones_a_plazos_dt1_permanente_aumento` | Operaciones a plazos (DT 1Âª LIS) - Aumento - Correcciones del ejercicio - Perma | money |  |
| 03322 | `is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_aumento` | Operaciones a plazos (DT 1Âª LIS) - Aumento - Correcciones del ejercicio - Tempo | money |  |
| 03323 | `is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_aumento` | Operaciones a plazos (DT 1Âª LIS) - Aumento - Correcciones del ejercicio - Tempo | money |  |
| 03324 | `is_correccion_operaciones_a_plazos_dt1_saldo_inicial` | Operaciones a plazos (DT 1Âª LIS) - Aumento - Saldo pendiente a principio de eje | money |  |
| 03325 | `is_correccion_operaciones_a_plazos_dt1_saldo_final` | Operaciones a plazos (DT 1Âª LIS) - Aumento - Saldo pendiente a fin de ejercicio | money |  |
| 03326 | `is_correccion_operaciones_a_plazos_dt1_permanente_disminucion` | Operaciones a plazos (DT 1Âª LIS) - DisminuciÃ³n - Correcciones del ejercicio -  | money |  |
| 03327 | `is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_disminucion` | Operaciones a plazos (DT 1Âª LIS) - DisminuciÃ³n - Correcciones del ejercicio -  | money |  |
| 03328 | `is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_disminucion` | Operaciones a plazos (DT 1Âª LIS) - DisminuciÃ³n - Correcciones del ejercicio -  | money |  |
| 03329 | `is_correccion_operaciones_a_plazos_dt1_saldo_inicial` | Operaciones a plazos (DT 1Âª LIS) - DisminuciÃ³n - Saldo pendiente a principio d | money |  |
| 03330 | `is_correccion_operaciones_a_plazos_dt1_saldo_final` | Operaciones a plazos (DT 1Âª LIS) - DisminuciÃ³n - Saldo pendiente a fin de ejer | money |  |
| 03331 | `is_correccion_adquisicion_participaciones_no_residentes_dt14_permanente_aumento` | AdquisiciÃ³n de participaciones en entidades no residentes (DT 14Âª LIS) - Aumen | money |  |
| 03332 | `is_correccion_adquisicion_participaciones_no_residentes_dt14_temporaria_ejercicio_aumento` | AdquisiciÃ³n de participaciones en entidades no residentes (DT 14Âª LIS) - Aumen | money |  |
| 03333 | `is_correccion_adquisicion_participaciones_no_residentes_dt14_temporaria_anteriores_aumento` | AdquisiciÃ³n de participaciones en entidades no residentes (DT 14Âª LIS) - Aumen | money |  |
| 03334 | `is_correccion_adquisicion_participaciones_no_residentes_dt14_saldo_inicial` | AdquisiciÃ³n de participaciones en entidades no residentes (DT 14Âª LIS) - Aumen | money |  |
| 03335 | `is_correccion_adquisicion_participaciones_no_residentes_dt14_saldo_final` | AdquisiciÃ³n de participaciones en entidades no residentes (DT 14Âª LIS) - Aumen | money |  |
| 03336 | `is_correccion_adquisicion_participaciones_no_residentes_dt14_permanente_disminucion` | AdquisiciÃ³n de participaciones en entidades no residentes (DT 14Âª LIS) - Dismi | money |  |
| 03337 | `is_correccion_adquisicion_participaciones_no_residentes_dt14_temporaria_ejercicio_disminucion` | AdquisiciÃ³n de participaciones en entidades no residentes (DT 14Âª LIS) - Dismi | money |  |
| 03338 | `is_correccion_adquisicion_participaciones_no_residentes_dt14_temporaria_anteriores_disminucion` | AdquisiciÃ³n de participaciones en entidades no residentes (DT 14Âª LIS) - Dismi | money |  |
| 03339 | `is_correccion_adquisicion_participaciones_no_residentes_dt14_saldo_inicial` | AdquisiciÃ³n de participaciones en entidades no residentes (DT 14Âª LIS) - Dismi | money |  |
| 03340 | `is_correccion_adquisicion_participaciones_no_residentes_dt14_saldo_final` | AdquisiciÃ³n de participaciones en entidades no residentes (DT 14Âª LIS) - Dismi | money |  |
| 03341 | `is_correccion_reinversion_beneficios_extraordinarios_dt24_permanente_aumento` | ReinversiÃ³n de beneficios extraordinarios (DT 24Âª LIS) - Aumento - Correccione | money |  |
| 03342 | `is_correccion_reinversion_beneficios_extraordinarios_dt24_temporaria_ejercicio_aumento` | ReinversiÃ³n de beneficios extraordinarios (DT 24Âª LIS) - Aumento - Correccione | money |  |
| 03343 | `is_correccion_reinversion_beneficios_extraordinarios_dt24_temporaria_anteriores_aumento` | ReinversiÃ³n de beneficios extraordinarios (DT 24Âª LIS) - Aumento - Correccione | money |  |
| 03344 | `is_correccion_reinversion_beneficios_extraordinarios_dt24_saldo_inicial` | ReinversiÃ³n de beneficios extraordinarios (DT 24Âª LIS) - Aumento - Saldo pendi | money |  |
| 03345 | `is_correccion_reinversion_beneficios_extraordinarios_dt24_saldo_final` | ReinversiÃ³n de beneficios extraordinarios (DT 24Âª LIS) - Aumento - Saldo pendi | money |  |
| 03346 | `is_correccion_reinversion_beneficios_extraordinarios_dt24_permanente_disminucion` | ReinversiÃ³n de beneficios extraordinarios (DT 24Âª LIS) - DisminuciÃ³n - Correc | money |  |
| 03347 | `is_correccion_reinversion_beneficios_extraordinarios_dt24_temporaria_ejercicio_disminucion` | ReinversiÃ³n de beneficios extraordinarios (DT 24Âª LIS) - DisminuciÃ³n - Correc | money |  |
| 03348 | `is_correccion_reinversion_beneficios_extraordinarios_dt24_temporaria_anteriores_disminucion` | ReinversiÃ³n de beneficios extraordinarios (DT 24Âª LIS) - DisminuciÃ³n - Correc | money |  |
| 03349 | `is_correccion_reinversion_beneficios_extraordinarios_dt24_saldo_inicial` | ReinversiÃ³n de beneficios extraordinarios (DT 24Âª LIS) - DisminuciÃ³n - Saldo  | money |  |
| 03350 | `is_correccion_reinversion_beneficios_extraordinarios_dt24_saldo_final` | ReinversiÃ³n de beneficios extraordinarios (DT 24Âª LIS) - DisminuciÃ³n - Saldo  | money |  |
| 03371 | `is_correccion_correcciones_entidades_normativa_foral_permanente_aumento` | Correcciones especÃ­ficas de entidades sometidas a la normativa foral - Aumento  | money |  |
| 03372 | `is_correccion_correcciones_entidades_normativa_foral_temporaria_ejercicio_aumento` | Correcciones especÃ­ficas de entidades sometidas a la normativa foral - Aumento  | money |  |
| 03373 | `is_correccion_correcciones_entidades_normativa_foral_temporaria_anteriores_aumento` | Correcciones especÃ­ficas de entidades sometidas a la normativa foral - Aumento  | money |  |
| 03374 | `is_correccion_correcciones_entidades_normativa_foral_saldo_inicial` | Correcciones especÃ­ficas de entidades sometidas a la normativa foral - Aumento  | money |  |
| 03375 | `is_correccion_correcciones_entidades_normativa_foral_saldo_final` | Correcciones especÃ­ficas de entidades sometidas a la normativa foral - Aumento  | money |  |
| 03376 | `is_correccion_correcciones_entidades_normativa_foral_permanente_disminucion` | Correcciones especÃ­ficas de entidades sometidas a la normativa foral - Disminuc | money |  |
| 03377 | `is_correccion_correcciones_entidades_normativa_foral_temporaria_ejercicio_disminucion` | Correcciones especÃ­ficas de entidades sometidas a la normativa foral - Disminuc | money |  |
| 03378 | `is_correccion_correcciones_entidades_normativa_foral_temporaria_anteriores_disminucion` | Correcciones especÃ­ficas de entidades sometidas a la normativa foral - Disminuc | money |  |
| 03379 | `is_correccion_correcciones_entidades_normativa_foral_saldo_inicial` | Correcciones especÃ­ficas de entidades sometidas a la normativa foral - Disminuc | money |  |
| 03380 | `is_correccion_correcciones_entidades_normativa_foral_saldo_final` | Correcciones especÃ­ficas de entidades sometidas a la normativa foral - Disminuc | money |  |
| 03381 | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_permanente_aumento` | Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a u | money |  |
| 03382 | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_ejercicio_aumento` | Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a u | money |  |
| 03383 | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_anteriores_aumento` | Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a u | money |  |
| 03384 | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_inicial` | Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a u | money |  |
| 03385 | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_final` | Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a u | money |  |
| 03386 | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_permanente_disminucion` | Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a u | money |  |
| 03387 | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_ejercicio_disminucion` | Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a u | money |  |
| 03388 | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_anteriores_disminucion` | Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a u | money |  |
| 03389 | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_inicial` | Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a u | money |  |
| 03390 | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_final` | Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a u | money |  |
| 03391 | `is_correccion_otras_correcciones_resultado_permanente_aumento` | Otras correcciones al resultado de la cuenta de pÃ©rdidas y ganancias - Aumento  | money |  |
| 03392 | `is_correccion_otras_correcciones_resultado_temporaria_ejercicio_aumento` | Otras correcciones al resultado de la cuenta de pÃ©rdidas y ganancias - Aumento  | money |  |
| 03393 | `is_correccion_otras_correcciones_resultado_temporaria_anteriores_aumento` | Otras correcciones al resultado de la cuenta de pÃ©rdidas y ganancias - Aumento  | money |  |
| 03394 | `is_correccion_otras_correcciones_resultado_saldo_inicial` | Otras correcciones al resultado de la cuenta de pÃ©rdidas y ganancias - Aumento  | money |  |
| 03395 | `is_correccion_otras_correcciones_resultado_saldo_final` | Otras correcciones al resultado de la cuenta de pÃ©rdidas y ganancias - Aumento  | money |  |
| 03396 | `is_correccion_otras_correcciones_resultado_permanente_disminucion` | Otras correcciones al resultado de la cuenta de pÃ©rdidas y ganancias - Disminuc | money |  |
| 03397 | `is_correccion_otras_correcciones_resultado_temporaria_ejercicio_disminucion` | Otras correcciones al resultado de la cuenta de pÃ©rdidas y ganancias - Disminuc | money |  |
| 03398 | `is_correccion_otras_correcciones_resultado_temporaria_anteriores_disminucion` | Otras correcciones al resultado de la cuenta de pÃ©rdidas y ganancias - Disminuc | money |  |
| 03399 | `is_correccion_otras_correcciones_resultado_saldo_inicial` | Otras correcciones al resultado de la cuenta de pÃ©rdidas y ganancias - Disminuc | money |  |
| 03400 | `is_correccion_otras_correcciones_resultado_saldo_final` | Otras correcciones al resultado de la cuenta de pÃ©rdidas y ganancias - Disminuc | money |  |
| 03588 | `is_correccion_limite_beneficio_operativo_saldo_inicial` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 03589 | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 03590 | `is_correccion_limite_beneficio_operativo_saldo_final` | Pendiente adiciÃ³n por lÃ­mite beneficio operativo no aplicado - Ejercicio gener | money |  |
| 03617 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2025(*) | money |  |
| 03618 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_aplicadas` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2025(*) | money |  |
| 03619 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2025(*) | money |  |
| 03620 | `is_correccion_dotaciones_deterioro_creditos_saldo_inicial_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2025 -  | money |  |
| 03621 | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2025 -  | money |  |
| 03622 | `is_correccion_dotaciones_deterioro_creditos_saldo_final_no_cumplido_condiciones` | Dotaciones deterioro crÃ©ditos u otros activos - Ejercicio generaciÃ³n - 2025 -  | money |  |
| 03646 | `is_correccion_impuesto_margen_intereses_comisiones_df9_permanente_aumento` | CorrecciÃ³n por el Impuesto sobre el margen de intereses y comisiones de determi | money |  |

## Data_type divergences

No role has casillas with differing `data_type` values. The three data types present
are:

- `decimal` — identification / flag fields (62 casillas) and personal headcount (2 casillas), plus one text field.
- `text` — one casilla: `00040` (grupo fiscal number).
- `money` — all monetary adjustment casillas (630 casillas).

All roles that carry `flag_regimen` or `numero_grupo_fiscal` / `personal_fijo` / `personal_no_fijo`
axes are purely `decimal` or `text` typed. All roles carrying monetary axes (`permanente_aumento`,
`temporaria_*`, `saldo_*`, `dotaciones_*`, `importe`, `importe_base_deduccion`) are purely `money` typed.
There are no cross-type collisions.