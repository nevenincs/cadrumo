---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-enrollment-campaign-queue-audit]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# `schema-hardening` audit: M200 IS role assignment

## Summary

- Total casillas: 1004
- Already-roled (existing): 2 (00027 `base_imponible_negativa_is`, 00599 `resultado_ingresar_o_devolver_is`)
- Newly classified: 1002
- Distinct roles proposed (including 2 existing): 88
- Section families: 12

## Section families overview

| Family | Description | Sections | Casillas |
|--------|-------------|----------|----------|
| `A-liquidacion` | Liquidacion (pages 011-011b) — cuota integra, deducciones, cuota liquida, retenciones, pagos fraccionados | 5 | 70 |
| `B-correcciones` | Detalle correcciones resultado contable — ~80 LIS-article correction categories (amortizacion, deterioro, diferencias temporarias, exenciones, operaciones especiales, gastos no deducibles) | 96 | 256 |
| `C-bases_negativas` | Bases imponibles negativas y compensaciones — carry-forward BINs by year + conversion de activos por impuesto diferido (AID) | 3 | 52 |
| `D-reservas` | Reservas (capitalizacion art.25 LIS, nivelacion art.105 LIS, inversiones Canarias ley-19/1994, Illes Balears DA70a LIS) | 6 | 66 |
| `E-deducciones` | Deducciones (I+D+i art.35, cinematograficas art.36, inversion Canarias, DT24a, Copa America, reversion medidas temporales) | 8 | 220 |
| `F-deducciones_donativos` | Deducciones donativos entidades sin fines lucro (ley 49/2002) | 1 | 40 |
| `F-identificacion` | Identificacion — checkboxes de tipo entidad, regimen fiscal, opciones (decimals/text) + n. grupo fiscal + personal asalariado | 76 | 76 |
| `G-doble_imposicion` | Deducciones doble imposicion interna e internacional (LIS + RDLeg 4/2004) | 4 | 32 |
| `H-cooperativas` | Regimen especial cooperativas (Ley 20/1990) — liquidacion, compensacion cuotas, base imponible | 1 | 72 |
| `I-navieras` | Regimen especial buques y empresas navieras en funcion del tonelaje + compensacion bases negativas navieras | 1 | 14 |
| `J-tributacion_conjunta` | Tributacion conjunta Estado y Administraciones Forales (Concierto Economico / Convenio Economico) + atribucion de rentas | 3 | 28 |
| `K-estados_financieros` | Estados financieros (balance activo, balance patrimonio neto y pasivo, cuenta PYG, estado cambios patrimonio neto) | 9 | 76 |
| `existing` | Ya roled (base_imponible_negativa_is, resultado_ingresar_o_devolver_is) | 2 | 2 |

## Per-id role assignment

Roles marked `[existing]` were already declared in the TOML file; all others are proposals.

| id | section_top | role | label_snippet | data_type | rationale |
|----|-------------|------|---------------|-----------|-----------|
| 00184 | liquidacion_ii | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 00272 | liquidacion_i | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 00333 | liquidacion_i | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 00356 | liquidacion_i | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 00365 | liquidacion_ii | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 00368 | liquidacion_i | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 00370 | liquidacion_ii | `is_liquidacion_ii_importe` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 00371 | liquidacion_i | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 00372 | liquidacion_ii | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 00501 | liquidacion_i | `is_liquidacion_i_importe` | Liquidación I - Resultado de la cuenta de pérdidas y gananci | money | liquidacion section label match |
| 00559 | liquidacion_iii | `is_base_imponible` | Liquidación III - Base imponible - Sólo entidades ZEC - Base | money | liquidacion section label match |
| 00573 | liquidacion_iii | `is_liquidacion_iii_importe` | Liquidación III - Bonificaciones/Deducciones doble imposició | money | liquidacion section label match |
| 00592 | liquidacion | `is_cuota_liquida` | Cuota liquida | money | liquidacion section label match |
| 00601 | liquidacion_iv | `is_pagos_fraccionados` | Liquidación IV - Pagos fraccionados/Cuota diferencial - Pago | money | liquidacion section label match |
| 00775 | liquidacion_i | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 00778 | liquidacion_ii | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 00813 | liquidacion_ii | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 00815 | liquidacion_iii | `is_liquidacion_iii_importe` | Liquidación III - Bonificaciones/Deducciones doble imposició | money | liquidacion section label match |
| 00866 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Rectificación - Estado [00866] | money | liquidacion section label match |
| 00925 | liquidacion_iii | `is_compensacion_bases_negativas` | Liquidación III - Base imponible - Rentas que no limitan com | money | liquidacion section label match |
| 00932 | liquidacion_iii | `is_base_imponible` | Liquidación III - Base imponible - Sólo sociedades cooperati | money | liquidacion section label match |
| 01003 | liquidacion_i | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 01011 | liquidacion_i | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 01014 | liquidacion_ii | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 01018 | liquidacion_ii | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 01022 | liquidacion_ii | `is_liquidacion_ii_importe` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 01026 | liquidacion_ii | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 01029 | liquidacion_ii | `is_liquidacion_ii_importe` | Liquidación II - Entidades que forman parte de grupos de con | money | liquidacion section label match |
| 01032 | liquidacion_iii | `is_base_imponible` | Liquidación III - Base imponible - Reserva de capitalización | money | liquidacion section label match |
| 01037 | liquidacion_iii | `is_base_imponible` | Liquidación III - Base imponible - Sólo sociedades cooperati | money | liquidacion section label match |
| 01039 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Otras deducciones - Deducciones por producc | money | liquidacion section label match |
| 01042 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Resultado de la autoliquidación - Abono ded | money | liquidacion section label match |
| 01230 | liquidacion_i | `is_resultado_contable` | Liquidación I - Resultado de la cuenta de pérdidas y gananci | money | liquidacion section label match |
| 01234 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Resultado de la autoliquidación - Abono ded | money | liquidacion section label match |
| 01275 | liquidacion_ii | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 01280 | liquidacion_iii | `is_liquidacion_iii_importe` | Liquidación III - Bonificaciones/Deducciones doble imposició | money | liquidacion section label match |
| 01285 | liquidacion_iii | `is_base_imponible` | Liquidación III - Base imponible - Sólo sociedades cooperati | money | liquidacion section label match |
| 01319 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Resultado de la autoliquidación - Abono de  | money | liquidacion section label match |
| 01320 | liquidacion_ii | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 01330 | liquidacion_iii | `is_base_imponible` | Liquidación III - Base Imponible - Base imponible después de | money | liquidacion section label match |
| 01332 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Resultado de la autoliquidación - Abono ded | money | liquidacion section label match |
| 01344 | liquidacion_iii | `is_liquidacion_iii_importe` | Liquidación III - Bonificaciones/Deducciones doble imposició | money | liquidacion section label match |
| 01509 | liquidacion_iii | `is_compensacion_bases_negativas` | Liquidación III - Base imponible - - Rentas que no limitan c | money | liquidacion section label match |
| 01514 | liquidacion_i | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 01572 | liquidacion_i | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 01574 | liquidacion_ii | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 01576 | liquidacion_iii | `is_base_imponible` | Liquidación III - Base imponible - Régimen especial de buque | money | liquidacion section label match |
| 01578 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Rectificativa - Resultado a ingresar como c | money | liquidacion section label match |
| 01583 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Rectificativa - Resultado a ingresar como c | money | liquidacion section label match |
| 01586 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Resultado de la autoliquidación - Estado [0 | money | liquidacion section label match |
| 01588 | liquidacion_iv | `is_base_imponible` | Liquidación IV - Opción de fraccionamiento en supuestos de c | money | liquidacion section label match |
| 01589 | liquidacion_ii | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 01764 | liquidacion_ii | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 01766 | liquidacion_iv | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio a ingresar o a devolver | money | liquidacion section label match |
| 01784 | liquidacion_iv | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio a ingresar o a devolver | money | liquidacion section label match |
| 01807 | liquidacion_i | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 01822 | liquidacion_ii | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 01881 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Resultado de la autoliquidación - Abono de  | money | liquidacion section label match |
| 01887 | liquidacion_iii | `is_compensacion_bases_negativas` | Liquidación III - Base imponible - Régimen especial de buque | money | liquidacion section label match |
| 01890 | liquidacion_iii | `is_compensacion_bases_negativas` | Liquidación III - Base imponible - Régimen especial de buque | money | liquidacion section label match |
| 01892 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Resultado de la autoliquidación - Abono ded | money | liquidacion section label match |
| 01905 | liquidacion_ii | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 02181 | liquidacion_ii | `is_liquidacion_ii_importe` | Liquidación II - Detalle correcciones resultado cta. pérdida | money | liquidacion section label match |
| 02311 | liquidacion_i | `is_liquidacion_i_importe` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 02314 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Otras deducciones - Deducciones por producc | money | liquidacion section label match |
| 02469 | liquidacion_i | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 02480 | liquidacion_iv | `is_base_imponible` | Liquidación IV - Opción de fraccionamiento en supuestos de c | money | liquidacion section label match |
| 02919 | liquidacion_i | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 03242 | liquidacion_iv | `is_liquidacion_iv_importe` | Liquidación IV - Opción de fraccionamiento en supuestos de c | money | liquidacion section label match |
| 03401 | liquidacion_i | `is_liquidacion_i_importe` | Liquidación I - Detalle correcciones resultado cta. pérdidas | money | liquidacion section label match |
| 00075 | amortizacion_acelerada_de_determinados_v | `is_correccion_aumento` | Amortización acelerada de determinados vehículos y de nuevas | money | correccion section subsection key |
| 00941 | reversion_por_deterioro_de_valores_repre | `is_correccion_aumento` | Reversión por deterioro de valores representativos - Dotacio | money | correccion section subsection key |
| 00990 | reversion_por_deterioro_de_valores_repre | `is_correccion_aumento` | Reversión por deterioro de valores representativos - Dotacio | money | correccion section subsection key |
| 00991 | reversion_por_deterioro_de_valores_repre | `is_correccion_aumento` | Reversión por deterioro de valores representativos - Dotacio | money | correccion section subsection key |
| 01009 | ajustes_por_deterioro_de_valores_repr_de | `is_correccion_disminucion` | Ajustes por deterioro de valores repr. de partic. en el capi | money | correccion section subsection key |
| 01098 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01100 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01103 | pendiente_adicion_por_limite_beneficio_o | `is_gastos_financieros_limitacion_importe` | Pendiente adición por límite beneficio operativo no aplicado | money | correccion section subsection key |
| 01143 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01148 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01162 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01184 | libertad_de_amortizacion_de_determinados | `is_correccion_aumento` | Libertad de amortización de determinados vehículos y de nuev | money | correccion section subsection key |
| 01188 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01191 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01192 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01193 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01198 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01201 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01202 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01209 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01212 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01217 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01240 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros - Límite art. 16 | money | correccion section subsection key |
| 01245 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros - Límite art. 16 | money | correccion section subsection key |
| 01393 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01395 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01398 | pendiente_adicion_por_limite_beneficio_o | `is_gastos_financieros_limitacion_importe` | Pendiente adición por límite beneficio operativo no aplicado | money | correccion section subsection key |
| 01408 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01462 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01464 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01470 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01473 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01494 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_total` | Dotaciones deterioro créditos u otros activos - Total - Dota | money | correccion section subsection key |
| 01500 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01602 | ajustes_por_deterioro_de_valores_repr_de | `is_correccion_aumento` | Ajustes por deterioro de valores repr. de partic. en el capi | money | correccion section subsection key |
| 01626 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01674 | cambio_de_residencia_a_estados_miembros_ | `is_correccion_aumento` | Cambio de residencia a Estados miembros de la Unión Europea  | money | correccion section subsection key |
| 01675 | cambio_de_residencia_a_estados_miembros_ | `is_correccion_disminucion` | Cambio de residencia a Estados miembros de la Unión Europea  | money | correccion section subsection key |
| 01676 | operaciones_del_art_19_lis_distintas_del | `is_correccion_aumento` | Operaciones del art. 19 LIS distintas del cambio de residenc | money | correccion section subsection key |
| 01677 | operaciones_del_art_19_lis_distintas_del | `is_correccion_aumento` | Operaciones del art. 19 LIS distintas del cambio de residenc | money | correccion section subsection key |
| 01681 | operaciones_del_art_19_lis_distintas_del | `is_correccion_disminucion` | Operaciones del art. 19 LIS distintas del cambio de residenc | money | correccion section subsection key |
| 01686 | operaciones_del_art_19_lis_distintas_del | `is_correccion_disminucion` | Operaciones del art. 19 LIS distintas del cambio de residenc | money | correccion section subsection key |
| 01732 | ajustes_por_deterioro_de_valores_repr_de | `is_correccion_disminucion` | Ajustes por deterioro de valores repr. de partic. en el capi | money | correccion section subsection key |
| 01736 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01738 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01741 | libertad_de_amortizacion_de_determinados | `is_correccion_aumento` | Libertad de amortización de determinados vehículos y de nuev | money | correccion section subsection key |
| 01747 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01820 | libertad_de_amortizacion_de_determinados | `is_correccion_aumento` | Libertad de amortización de determinados vehículos y de nuev | money | correccion section subsection key |
| 01860 | ajustes_por_deterioro_de_valores_repr_de | `is_correccion_aumento` | Ajustes por deterioro de valores repr. de partic. en el capi | money | correccion section subsection key |
| 01865 | ajustes_por_deterioro_de_valores_repr_de | `is_correccion_disminucion` | Ajustes por deterioro de valores repr. de partic. en el capi | money | correccion section subsection key |
| 01882 | socio_sicav_rentas_derivadas_de_liquidac | `is_correccion_disminucion` | Socio SICAV: rentas derivadas de liquidaciones de SICAV (DT  | money | correccion section subsection key |
| 01883 | libertad_de_amortizacion_de_determinados | `is_correccion_aumento` | Libertad de amortización de determinados vehículos y de nuev | money | correccion section subsection key |
| 01884 | libertad_de_amortizacion_de_determinados | `is_correccion_disminucion` | Libertad de amortización de determinados vehículos y de nuev | money | correccion section subsection key |
| 01915 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01961 | libertad_de_amortizacion_de_determinados | `is_correccion_disminucion` | Libertad de amortización de determinados vehículos y de nuev | money | correccion section subsection key |
| 01977 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01979 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 01984 | libertad_de_amortizacion_de_determinados | `is_correccion_disminucion` | Libertad de amortización de determinados vehículos y de nuev | money | correccion section subsection key |
| 01988 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 01995 | ajustes_por_deterioro_de_valores_repr_de | `is_correccion_aumento` | Ajustes por deterioro de valores repr. de partic. en el capi | money | correccion section subsection key |
| 02079 | informacion_adicional_para_el_calculo_de | `is_informacion_adicional_limites_importe` | Información adicional para el cálculo de límites de deduccio | money | correccion section subsection key |
| 02080 | informacion_adicional_para_el_calculo_de | `is_informacion_adicional_limites_importe` | Información adicional para el cálculo de límites de deduccio | money | correccion section subsection key |
| 02176 | xxxvii_copa_america_barcelona_ley_31_202 | `is_correccion_aumento` | XXXVII Copa América Barcelona (Ley 31/2022) - Aumento - Sald | money | correccion section subsection key |
| 02240 | ajustes_por_deterioro_de_valores_repr_de | `is_correccion_aumento` | Ajustes por deterioro de valores repr. de partic. en el capi | money | correccion section subsection key |
| 02253 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 02255 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 02258 | pendiente_adicion_por_limite_beneficio_o | `is_gastos_financieros_limitacion_importe` | Pendiente adición por límite beneficio operativo no aplicado | money | correccion section subsection key |
| 02261 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 02287 | informacion_adicional_para_el_calculo_de | `is_informacion_adicional_limites_importe` | Información adicional para el cálculo de límites de deduccio | money | correccion section subsection key |
| 02288 | informacion_adicional_para_el_calculo_de | `is_informacion_adicional_limites_importe` | Información adicional para el cálculo de límites de deduccio | money | correccion section subsection key |
| 02289 | xxxvii_copa_america_barcelona_ley_31_202 | `is_correccion_disminucion` | XXXVII Copa América Barcelona (Ley 31/2022) - Disminución -  | money | correccion section subsection key |
| 02301 | detalle_correcciones_resultado_perdidas_ | `is_correcciones_temporarias_importe` | Detalle correcciones resultado pérdidas y ganancias - Correc | money | correccion section subsection key |
| 02305 | detalle_correcciones_resultado_perdidas_ | `is_correcciones_temporarias_importe` | Detalle correcciones resultado pérdidas y ganancias - Saldo  | money | correccion section subsection key |
| 02307 | detalle_correcciones_resultado_perdidas_ | `is_correcciones_temporarias_importe` | Detalle correcciones resultado pérdidas y ganancias - Correc | money | correccion section subsection key |
| 02309 | detalle_correcciones_resultado_perdidas_ | `is_correcciones_temporarias_importe` | Detalle correcciones resultado pérdidas y ganancias - Saldo  | money | correccion section subsection key |
| 02368 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros - Límite art. 16 | money | correccion section subsection key |
| 02370 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 02375 | ajustes_por_deterioro_de_valores_repr_de | `is_correccion_aumento` | Ajustes por deterioro de valores repr. de partic. en el capi | money | correccion section subsection key |
| 02399 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 02401 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 02404 | pendiente_adicion_por_limite_beneficio_o | `is_gastos_financieros_limitacion_importe` | Pendiente adición por límite beneficio operativo no aplicado | money | correccion section subsection key |
| 02409 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 02431 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 02438 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 02444 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 02447 | pendiente_adicion_por_limite_beneficio_o | `is_gastos_financieros_limitacion_importe` | Pendiente adición por límite beneficio operativo no aplicado | money | correccion section subsection key |
| 02465 | pendiente_adicion_por_limite_beneficio_o | `is_gastos_financieros_limitacion_importe` | Pendiente adición por límite beneficio operativo no aplicado | money | correccion section subsection key |
| 02495 | informacion_adicional_para_el_calculo_de | `is_informacion_adicional_limites_importe` | Información adicional para el cálculo de límites de deduccio | money | correccion section subsection key |
| 02496 | informacion_adicional_para_el_calculo_de | `is_informacion_adicional_limites_importe` | Información adicional para el cálculo de límites de deduccio | money | correccion section subsection key |
| 02501 | cambio_de_criterios_contables_art_11_3_2 | `is_correccion_aumento` | Cambio de criterios contables (art. 11.3.2º LIS) - Aumento - | money | correccion section subsection key |
| 02506 | cambio_de_criterios_contables_art_11_3_2 | `is_correccion_disminucion` | Cambio de criterios contables (art. 11.3.2º LIS) - Disminuci | money | correccion section subsection key |
| 02511 | operaciones_a_plazos_art_11_4_lis | `is_correccion_aumento` | Operaciones a plazos (art. 11.4 LIS) - Aumento - Correccione | money | correccion section subsection key |
| 02516 | operaciones_a_plazos_art_11_4_lis | `is_correccion_disminucion` | Operaciones a plazos (art. 11.4 LIS) - Disminución - Correcc | money | correccion section subsection key |
| 02521 | reversion_del_deterioro_del_valor_de_los | `is_correccion_aumento` | Reversión del deterioro del valor de los elementos patrimoni | money | correccion section subsection key |
| 02526 | reversion_del_deterioro_del_valor_de_los | `is_correccion_disminucion` | Reversión del deterioro del valor de los elementos patrimoni | money | correccion section subsection key |
| 02531 | rentas_negativas_art_11_9_y_11_10_lis | `is_correccion_aumento` | Rentas negativas (art. 11.9 y 11.10 LIS) - Aumento - Correcc | money | correccion section subsection key |
| 02536 | rentas_negativas_art_11_9_y_11_10_lis | `is_correccion_disminucion` | Rentas negativas (art. 11.9 y 11.10 LIS) - Disminución - Cor | money | correccion section subsection key |
| 02541 | ajustes_por_rentas_derivadas_de_operacio | `is_correccion_aumento` | Ajustes por rentas derivadas de operaciones con quita o espe | money | correccion section subsection key |
| 02546 | ajustes_por_rentas_derivadas_de_operacio | `is_correccion_disminucion` | Ajustes por rentas derivadas de operaciones con quita o espe | money | correccion section subsection key |
| 02551 | otras_diferencias_de_imputacion_temporal | `is_correccion_aumento` | Otras diferencias de imputación temporal de ingresos y gasto | money | correccion section subsection key |
| 02556 | otras_diferencias_de_imputacion_temporal | `is_correccion_disminucion` | Otras diferencias de imputación temporal de ingresos y gasto | money | correccion section subsection key |
| 02561 | diferencias_entre_amortizacion_contable_ | `is_correccion_aumento` | Diferencias entre amortización contable y fiscal (art. 12.1  | money | correccion section subsection key |
| 02566 | diferencias_entre_amortizacion_contable_ | `is_correccion_disminucion` | Diferencias entre amortización contable y fiscal (art. 12.1  | money | correccion section subsection key |
| 02571 | asimetrias_hibridas_art_15_bis_lis_excep | `is_correccion_aumento` | Asimetrías híbridas (art. 15 bis LIS, excepto art. 15 bis.12 | money | correccion section subsection key |
| 02578 | deduccion_del_30_importe_gastos_de_amort | `is_correccion_disminucion` | Deducción del 30% importe gastos de amortiz. contable (exclu | money | correccion section subsection key |
| 02581 | amortizacion_del_inmovilizado_intangible | `is_correccion_aumento` | Amortización del inmovilizado intangible y fondo de comercio | money | correccion section subsection key |
| 02586 | amortizacion_del_inmovilizado_intangible | `is_correccion_disminucion` | Amortización del inmovilizado intangible y fondo de comercio | money | correccion section subsection key |
| 02591 | amortizacion_de_inmovilizado_afecto_a_ac | `is_correccion_aumento` | Amortización de inmovilizado afecto a actividades de investi | money | correccion section subsection key |
| 02596 | amortizacion_de_inmovilizado_afecto_a_ac | `is_correccion_disminucion` | Amortización de inmovilizado afecto a actividades de investi | money | correccion section subsection key |
| 02601 | libertad_de_amortizacion_de_gastos_de_in | `is_correccion_aumento` | Libertad de amortización de gastos de investigación y desarr | money | correccion section subsection key |
| 02606 | libertad_de_amortizacion_de_gastos_de_in | `is_correccion_disminucion` | Libertad de amortización de gastos de investigación y desarr | money | correccion section subsection key |
| 02611 | libertad_de_amortizacion_inmovilizado_ma | `is_correccion_aumento` | Libertad de amortización inmovilizado material nuevo (art. 1 | money | correccion section subsection key |
| 02616 | libertad_de_amortizacion_inmovilizado_ma | `is_correccion_disminucion` | Libertad de amortización inmovilizado material nuevo (art. 1 | money | correccion section subsection key |
| 02621 | otros_supuestos_de_libertad_de_amortizac | `is_correccion_aumento` | Otros supuestos de libertad de amortización (art. 12.3 a) y  | money | correccion section subsection key |
| 02626 | otros_supuestos_de_libertad_de_amortizac | `is_correccion_disminucion` | Otros supuestos de libertad de amortización (art. 12.3 a) y  | money | correccion section subsection key |
| 02631 | libertad_de_amortizacion_con_mantenimien | `is_correccion_aumento` | Libertad de amortización con mantenimiento de empleo (RDL 6/ | money | correccion section subsection key |
| 02636 | libertad_de_amortizacion_con_mantenimien | `is_correccion_disminucion` | Libertad de amortización con mantenimiento de empleo (RDL 6/ | money | correccion section subsection key |
| 02641 | libertad_de_amortizacion_sin_mantenimien | `is_correccion_aumento` | Libertad de amortización sin mantenimiento de empleo (RDL 13 | money | correccion section subsection key |
| 02646 | libertad_de_amortizacion_sin_mantenimien | `is_correccion_disminucion` | Libertad de amortización sin mantenimiento de empleo (RDL 13 | money | correccion section subsection key |
| 02651 | perdidas_por_deterioro_del_art_13_1_lis_ | `is_correccion_aumento` | Pérdidas por deterioro del art. 13.1 LIS no afectada por el  | money | correccion section subsection key |
| 02656 | perdidas_por_deterioro_del_art_13_1_lis_ | `is_correccion_disminucion` | Pérdidas por deterioro del art. 13.1 LIS no afectada por el  | money | correccion section subsection key |
| 02661 | perdidas_por_deterioro_del_art_13_1_lis_ | `is_correccion_aumento` | Pérdidas por deterioro del art. 13.1 LIS y provisiones y gas | money | correccion section subsection key |
| 02666 | perdidas_por_deterioro_del_art_13_1_lis_ | `is_correccion_disminucion` | Pérdidas por deterioro del art. 13.1 LIS y provisiones y gas | money | correccion section subsection key |
| 02671 | perdidas_por_deterioro_de_im_inversiones | `is_correccion_aumento` | Pérdidas por deterioro de IM, inversiones inmobiliarias e II | money | correccion section subsection key |
| 02676 | perdidas_por_deterioro_de_im_inversiones | `is_correccion_disminucion` | Pérdidas por deterioro de IM, inversiones inmobiliarias e II | money | correccion section subsection key |
| 02681 | ajustes_por_perdidas_por_deterioro_de_va | `is_correccion_aumento` | Ajustes por pérdidas por deterioro de valores representativo | money | correccion section subsection key |
| 02686 | ajustes_por_perdidas_por_deterioro_de_va | `is_correccion_disminucion` | Ajustes por pérdidas por deterioro de valores representativo | money | correccion section subsection key |
| 02699 | exencion_sobre_dividendos_o_participacio | `is_correccion_disminucion` | Exención sobre dividendos o participaciones en beneficios de | money | correccion section subsection key |
| 02711 | perdidas_por_deterioro_de_valores_repres | `is_correccion_aumento` | Pérdidas por deterioro de valores representativos de deuda ( | money | correccion section subsection key |
| 02716 | perdidas_por_deterioro_de_valores_repres | `is_correccion_disminucion` | Pérdidas por deterioro de valores representativos de deuda ( | money | correccion section subsection key |
| 02721 | aplicacion_del_limite_del_art_11_12_lis_ | `is_correccion_aumento` | Aplicación del límite del art. 11.12 LIS a las pérdidas por  | money | correccion section subsection key |
| 02726 | aplicacion_del_limite_del_art_11_12_lis_ | `is_correccion_disminucion` | Aplicación del límite del art. 11.12 LIS a las pérdidas por  | money | correccion section subsection key |
| 02731 | gastos_y_provisiones_por_pensiones_no_af | `is_correccion_aumento` | Gastos y provisiones por pensiones no afectados por el art.  | money | correccion section subsection key |
| 02736 | gastos_y_provisiones_por_pensiones_no_af | `is_correccion_disminucion` | Gastos y provisiones por pensiones no afectados por el art.  | money | correccion section subsection key |
| 02741 | otras_provisiones_no_deducibles_fiscalme | `is_correccion_aumento` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no | money | correccion section subsection key |
| 02746 | otras_provisiones_no_deducibles_fiscalme | `is_correccion_disminucion` | Otras provisiones no deducibles fiscalmente (art. 14 LIS) no | money | correccion section subsection key |
| 02751 | asimetrias_hibridas_art_15_bis_lis_excep | `is_correccion_disminucion` | Asimetrías híbridas (art. 15 bis LIS, excepto art. 15 bis.12 | money | correccion section subsection key |
| 02756 | subvenciones_publicas_incluidas_en_el_re | `is_correccion_disminucion` | Subvenciones públicas incluidas en el resultado del ejercici | money | correccion section subsection key |
| 02761 | gastos_no_deducibles_por_considerarse_re | `is_correccion_aumento` | Gastos no deducibles por considerarse retribución de fondos  | money | correccion section subsection key |
| 02764 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 02766 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 02769 | pendiente_adicion_por_limite_beneficio_o | `is_gastos_financieros_limitacion_importe` | Pendiente adición por límite beneficio operativo no aplicado | money | correccion section subsection key |
| 02771 | multas_sanciones_y_otros_art_15_c_lis | `is_correccion_aumento` | Multas, sanciones y otros (art. 15 c) LIS) - Aumento - Corre | money | correccion section subsection key |
| 02772 | pendiente_adicion_por_limite_beneficio_o | `is_gastos_financieros_limitacion_importe` | Pendiente adición por límite beneficio operativo no aplicado | money | correccion section subsection key |
| 02781 | perdidas_del_juego_art_15_d_lis | `is_correccion_aumento` | Pérdidas del juego (art. 15 d) LIS) - Aumento - Correcciones | money | correccion section subsection key |
| 02791 | gastos_por_donativos_y_liberalidades_art | `is_correccion_aumento` | Gastos por donativos y liberalidades (art. 15 e) LIS) - Aume | money | correccion section subsection key |
| 02800 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 02801 | gastos_de_actuaciones_contrarias_al_orde | `is_correccion_aumento` | Gastos de actuaciones contrarias al ordenamiento jurídico (a | money | correccion section subsection key |
| 02802 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 02810 | reversion_por_deterioro_de_valores_repre | `is_correccion_aumento` | Reversión por deterioro de valores representativos - Dotacio | money | correccion section subsection key |
| 02811 | operaciones_realizadas_con_jurisdiccione | `is_correccion_aumento` | Operaciones realizadas con jurisdicciones no cooperativas (a | money | correccion section subsection key |
| 02816 | operaciones_realizadas_con_jurisdiccione | `is_correccion_disminucion` | Operaciones realizadas con jurisdicciones no cooperativas (a | money | correccion section subsection key |
| 02821 | gastos_financieros_derivados_de_deudas_c | `is_correccion_aumento` | Gastos financieros derivados de deudas con entidades del gru | money | correccion section subsection key |
| 02831 | gastos_derivados_de_la_extincion_de_la_r | `is_correccion_aumento` | Gastos derivados de la extinción de la relación laboral o me | money | correccion section subsection key |
| 02844 | exencion_sobre_dividendos_o_participacio | `is_correccion_disminucion` | Exención sobre dividendos o participaciones en beneficios de | money | correccion section subsection key |
| 02851 | perdidas_por_deterioro_de_valores_repr_d | `is_correccion_aumento` | Pérdidas por deterioro de valores repr. de partic. en el cap | money | correccion section subsection key |
| 02856 | perdidas_por_deterioro_de_valores_repr_d | `is_correccion_disminucion` | Pérdidas por deterioro de valores repr. de partic. en el cap | money | correccion section subsection key |
| 02861 | disminucion_de_valor_originada_por_crite | `is_correccion_aumento` | Disminución de valor originada por criterio de valor razonab | money | correccion section subsection key |
| 02866 | disminucion_de_valor_originada_por_crite | `is_correccion_disminucion` | Disminución de valor originada por criterio de valor razonab | money | correccion section subsection key |
| 02871 | deuda_tributaria_de_actos_juridicos_docu | `is_correccion_aumento` | Deuda tributaria de actos jurídicos documentados (ITP y AJD) | money | correccion section subsection key |
| 02876 | deuda_tributaria_de_actos_juridicos_docu | `is_correccion_disminucion` | Deuda tributaria de actos jurídicos documentados (ITP y AJD) | money | correccion section subsection key |
| 02881 | ajustes_por_la_limitacion_en_la_deducibi | `is_correccion_aumento` | Ajustes por la limitación en la deducibilidad de gastos fina | money | correccion section subsection key |
| 02886 | ajustes_por_la_limitacion_en_la_deducibi | `is_correccion_disminucion` | Ajustes por la limitación en la deducibilidad de gastos fina | money | correccion section subsection key |
| 02891 | revalorizaciones_contables_art_17_1_lis | `is_correccion_aumento` | Revalorizaciones contables (art. 17.1 LIS) - Aumento - Corre | money | correccion section subsection key |
| 02896 | revalorizaciones_contables_art_17_1_lis | `is_correccion_disminucion` | Revalorizaciones contables (art. 17.1 LIS) - Disminución - C | money | correccion section subsection key |
| 02901 | operaciones_de_aumento_de_capital_o_fond | `is_correccion_aumento` | Operaciones de aumento de capital o fondos propios por compe | money | correccion section subsection key |
| 02906 | operaciones_de_aumento_de_capital_o_fond | `is_correccion_disminucion` | Operaciones de aumento de capital o fondos propios por compe | money | correccion section subsection key |
| 02911 | socio_sicav_reducciones_de_capital_y_dis | `is_correccion_aumento` | Socio SICAV: Reducciones de capital y distribución de la pri | money | correccion section subsection key |
| 02921 | transmisiones_lucrativas_y_societarias_a | `is_correccion_aumento` | Transmisiones lucrativas y societarias: aplicación del valor | money | correccion section subsection key |
| 02926 | transmisiones_lucrativas_y_societarias_a | `is_correccion_disminucion` | Transmisiones lucrativas y societarias: aplicación del valor | money | correccion section subsection key |
| 02931 | operaciones_vinculadas_aplicacion_del_va | `is_correccion_aumento` | Operaciones vinculadas: aplicación del valor de mercado (art | money | correccion section subsection key |
| 02936 | operaciones_vinculadas_aplicacion_del_va | `is_correccion_disminucion` | Operaciones vinculadas: aplicación del valor de mercado (art | money | correccion section subsection key |
| 02951 | efectos_de_la_valoracion_contable_difere | `is_correccion_aumento` | Efectos de la valoración contable diferente a la fiscal (art | money | correccion section subsection key |
| 02956 | efectos_de_la_valoracion_contable_difere | `is_correccion_disminucion` | Efectos de la valoración contable diferente a la fiscal (art | money | correccion section subsection key |
| 02966 | exencion_sobre_dividendos_o_participacio | `is_correccion_disminucion` | Exención sobre dividendos o participaciones en beneficios de | money | correccion section subsection key |
| 02972 | pendiente_adicion_por_limite_beneficio_o | `is_gastos_financieros_limitacion_importe` | Pendiente adición por límite beneficio operativo no aplicado | money | correccion section subsection key |
| 02976 | exencion_sobre_dividendos_o_participacio | `is_correccion_disminucion` | Exención sobre dividendos o participaciones en beneficios de | money | correccion section subsection key |
| 02981 | exencion_sobre_la_renta_obtenida_en_la_t | `is_correccion_aumento` | Exención sobre la renta obtenida en la transmisión de valore | money | correccion section subsection key |
| 02986 | exencion_sobre_la_renta_obtenida_en_la_t | `is_correccion_disminucion` | Exención sobre la renta obtenida en la transmisión de valore | money | correccion section subsection key |
| 02991 | exencion_sobre_la_renta_obtenida_en_la_t | `is_correccion_aumento` | Exención sobre la renta obtenida en la transmisión de valore | money | correccion section subsection key |
| 02996 | exencion_sobre_la_renta_obtenida_en_la_t | `is_correccion_disminucion` | Exención sobre la renta obtenida en la transmisión de valore | money | correccion section subsection key |
| 03001 | exencion_sobre_la_renta_obtenida_en_los_ | `is_correccion_aumento` | Exención sobre la renta obtenida en los supuestos del art. 2 | money | correccion section subsection key |
| 03006 | exencion_sobre_la_renta_obtenida_en_los_ | `is_correccion_disminucion` | Exención sobre la renta obtenida en los supuestos del art. 2 | money | correccion section subsection key |
| 03011 | exencion_sobre_la_renta_obtenida_en_los_ | `is_correccion_aumento` | Exención sobre la renta obtenida en los supuestos del art. 2 | money | correccion section subsection key |
| 03016 | exencion_sobre_la_renta_obtenida_en_los_ | `is_correccion_disminucion` | Exención sobre la renta obtenida en los supuestos del art. 2 | money | correccion section subsection key |
| 03021 | exencion_de_rentas_en_el_extranjero_art_ | `is_correccion_aumento` | Exención de rentas en el extranjero (art. 22 LIS) - Aumento  | money | correccion section subsection key |
| 03026 | exencion_de_rentas_en_el_extranjero_art_ | `is_correccion_disminucion` | Exención de rentas en el extranjero (art. 22 LIS) - Disminuc | money | correccion section subsection key |
| 03031 | reduccion_de_rentas_procedentes_de_deter | `is_correccion_aumento` | Reducción de rentas procedentes de determinados activos inta | money | correccion section subsection key |
| 03036 | reduccion_de_rentas_procedentes_de_deter | `is_correccion_disminucion` | Reducción de rentas procedentes de determinados activos inta | money | correccion section subsection key |
| 03041 | obra_benefico_social_de_las_cajas_de_aho | `is_correccion_aumento` | Obra benéfico-social de las cajas de ahorro y fundaciones ba | money | correccion section subsection key |
| 03046 | obra_benefico_social_de_las_cajas_de_aho | `is_correccion_disminucion` | Obra benéfico-social de las cajas de ahorro y fundaciones ba | money | correccion section subsection key |
| 03051 | impuesto_extranjero_soportado_por_el_con | `is_correccion_aumento` | Impuesto extranjero soportado por el contribuyente, no deduc | money | correccion section subsection key |
| 03056 | impuesto_extranjero_soportado_por_el_con | `is_correccion_disminucion` | Impuesto extranjero soportado por el contribuyente, no deduc | money | correccion section subsection key |
| 03061 | impuesto_extranjero_sobre_los_beneficios | `is_correccion_aumento` | Impuesto extranjero sobre los beneficios con cargo a los cua | money | correccion section subsection key |
| 03071 | agrupacion_de_interes_economico_cap_ii_d | `is_correccion_aumento` | Agrupación de interés económico (Cap. II del Tít. VII LIS) - | money | correccion section subsection key |
| 03076 | agrupacion_de_interes_economico_cap_ii_d | `is_correccion_disminucion` | Agrupación de interés económico (Cap. II del Tít. VII LIS) - | money | correccion section subsection key |
| 03081 | union_temporal_de_empresas_ajustes_del_a | `is_correccion_aumento` | Unión temporal de empresas, ajustes del art. 45.1 LIS - Aume | money | correccion section subsection key |
| 03086 | union_temporal_de_empresas_ajustes_del_a | `is_correccion_disminucion` | Unión temporal de empresas, ajustes del art. 45.1 LIS - Dism | money | correccion section subsection key |
| 03091 | union_temporal_de_empresas_ajustes_por_r | `is_correccion_aumento` | Unión temporal de empresas, ajustes por rentas exentas de UT | money | correccion section subsection key |
| 03096 | union_temporal_de_empresas_ajustes_por_r | `is_correccion_disminucion` | Unión temporal de empresas, ajustes por rentas exentas de UT | money | correccion section subsection key |
| 03101 | union_temporal_de_empresas_ajustes_por_r | `is_correccion_aumento` | Unión temporal de empresas, ajustes por rentas exentas por p | money | correccion section subsection key |
| 03106 | union_temporal_de_empresas_ajustes_por_r | `is_correccion_disminucion` | Unión temporal de empresas, ajustes por rentas exentas por p | money | correccion section subsection key |
| 03111 | union_temporal_de_empresas_ajustes_por_c | `is_correccion_aumento` | Unión temporal de empresas, ajustes por criterios de imputac | money | correccion section subsection key |
| 03116 | union_temporal_de_empresas_ajustes_por_c | `is_correccion_disminucion` | Unión temporal de empresas, ajustes por criterios de imputac | money | correccion section subsection key |
| 03121 | bases_imp_negativas_generadas_dentro_del | `is_correccion_aumento` | Bases imp. negativas generadas dentro del grupo fiscal por l | money | correccion section subsection key |
| 03126 | bases_imp_negativas_generadas_dentro_del | `is_correccion_disminucion` | Bases imp. negativas generadas dentro del grupo fiscal por l | money | correccion section subsection key |
| 03131 | sociedades_y_fondos_de_capital_riesgo_y_ | `is_correccion_aumento` | Sociedades y fondos de capital-riesgo y sociedades de desarr | money | correccion section subsection key |
| 03136 | sociedades_y_fondos_de_capital_riesgo_y_ | `is_correccion_disminucion` | Sociedades y fondos de capital-riesgo y sociedades de desarr | money | correccion section subsection key |
| 03141 | valoracion_de_bienes_y_derechos_regimen_ | `is_correccion_aumento` | Valoración de bienes y derechos. Régimen especial operacione | money | correccion section subsection key |
| 03146 | valoracion_de_bienes_y_derechos_regimen_ | `is_correccion_disminucion` | Valoración de bienes y derechos. Régimen especial operacione | money | correccion section subsection key |
| 03151 | mineria_e_hidrocarburos_factor_agotamien | `is_correccion_aumento` | Minería e hidrocarburos: factor agotamiento (arts. 91 y 95 L | money | correccion section subsection key |
| 03156 | mineria_e_hidrocarburos_factor_agotamien | `is_correccion_disminucion` | Minería e hidrocarburos: factor agotamiento (arts. 91 y 95 L | money | correccion section subsection key |
| 03161 | hidrocarburos_amortizacion_de_inversione | `is_correccion_aumento` | Hidrocarburos: Amortización de inversiones intangibles y gas | money | correccion section subsection key |
| 03166 | hidrocarburos_amortizacion_de_inversione | `is_correccion_disminucion` | Hidrocarburos: Amortización de inversiones intangibles y gas | money | correccion section subsection key |
| 03171 | transparencia_fiscal_internacional_art_1 | `is_correccion_aumento` | Transparencia fiscal internacional (art. 100 LIS) - Aumento  | money | correccion section subsection key |
| 03176 | transparencia_fiscal_internacional_art_1 | `is_correccion_disminucion` | Transparencia fiscal internacional (art. 100 LIS) - Disminuc | money | correccion section subsection key |
| 03181 | empresas_de_reducida_dimension_libertad_ | `is_correccion_aumento` | Empresas de reducida dimensión: libertad de amortización (ar | money | correccion section subsection key |
| 03186 | empresas_de_reducida_dimension_libertad_ | `is_correccion_disminucion` | Empresas de reducida dimensión: libertad de amortización (ar | money | correccion section subsection key |
| 03191 | empresas_de_reducida_dimension_amortizac | `is_correccion_aumento` | Empresas de reducida dimensión: amortización acelerada (art. | money | correccion section subsection key |
| 03196 | empresas_de_reducida_dimension_amortizac | `is_correccion_disminucion` | Empresas de reducida dimensión: amortización acelerada (art. | money | correccion section subsection key |
| 03201 | empresas_de_reducida_dimension_perdidas_ | `is_correccion_aumento` | Empresas de reducida dimensión: pérdidas por deterioro crédi | money | correccion section subsection key |
| 03206 | empresas_de_reducida_dimension_perdidas_ | `is_correccion_disminucion` | Empresas de reducida dimensión: pérdidas por deterioro crédi | money | correccion section subsection key |
| 03211 | arrendamiento_financiero_regimen_especia | `is_correccion_aumento` | Arrendamiento financiero: régimen especial (art. 106 LIS) -  | money | correccion section subsection key |
| 03216 | arrendamiento_financiero_regimen_especia | `is_correccion_disminucion` | Arrendamiento financiero: régimen especial (art. 106 LIS) -  | money | correccion section subsection key |
| 03221 | regimen_fiscal_entidades_de_tenencia_de_ | `is_correccion_aumento` | Régimen fiscal entidades de tenencia de valores extranjeros  | money | correccion section subsection key |
| 03226 | regimen_fiscal_entidades_de_tenencia_de_ | `is_correccion_disminucion` | Régimen fiscal entidades de tenencia de valores extranjeros  | money | correccion section subsection key |
| 03231 | regimen_de_entidades_parcialmente_exenta | `is_correccion_aumento` | Régimen de entidades parcialmente exentas (capítulo XIV del  | money | correccion section subsection key |
| 03236 | regimen_de_entidades_parcialmente_exenta | `is_correccion_disminucion` | Régimen de entidades parcialmente exentas (capítulo XIV del  | money | correccion section subsection key |
| 03241 | gastos_que_sean_objeto_de_la_deduccion_p | `is_correccion_aumento` | Gastos que sean objeto de la deducción por inversiones reali | money | correccion section subsection key |
| 03246 | montes_vecinales_en_mano_comun_capitulo_ | `is_correccion_disminucion` | Montes vecinales en mano común (capítulo XV del título VII L | money | correccion section subsection key |
| 03251 | regimen_de_entidades_navieras_en_funcion | `is_correccion_aumento` | Régimen de entidades navieras en función del tonelaje (capít | money | correccion section subsection key |
| 03256 | regimen_de_entidades_navieras_en_funcion | `is_correccion_disminucion` | Régimen de entidades navieras en función del tonelaje (capít | money | correccion section subsection key |
| 03261 | aportaciones_y_colaboracion_a_favor_de_e | `is_correccion_aumento` | Aportaciones y colaboración a favor de entidades sin fines l | money | correccion section subsection key |
| 03266 | aportaciones_y_colaboracion_a_favor_de_e | `is_correccion_disminucion` | Aportaciones y colaboración a favor de entidades sin fines l | money | correccion section subsection key |
| 03271 | regimen_fiscal_entidades_sin_fines_lucra | `is_correccion_aumento` | Régimen fiscal entidades sin fines lucrativos (Ley 49/2002)  | money | correccion section subsection key |
| 03276 | regimen_fiscal_entidades_sin_fines_lucra | `is_correccion_disminucion` | Régimen fiscal entidades sin fines lucrativos (Ley 49/2002)  | money | correccion section subsection key |
| 03286 | cooperativas_fondo_de_reserva_obligatori | `is_correccion_disminucion` | Cooperativas: Fondo de reserva obligatorio (Ley 20/1990) - D | money | correccion section subsection key |
| 03301 | exencion_transmision_bienes_inmuebles_da | `is_correccion_aumento` | Exención transmisión bienes inmuebles (DA 6ª LIS) - Aumento  | money | correccion section subsection key |
| 03306 | exencion_transmision_bienes_inmuebles_da | `is_correccion_disminucion` | Exención transmisión bienes inmuebles (DA 6ª LIS) - Disminuc | money | correccion section subsection key |
| 03316 | rentas_procedentes_de_transmision_de_inm | `is_correccion_disminucion` | Rentas procedentes de transmisión de inmovilizado obtenidas  | money | correccion section subsection key |
| 03321 | operaciones_a_plazos_dt_1a_lis | `is_correccion_aumento` | Operaciones a plazos (DT 1ª LIS) - Aumento - Correcciones de | money | correccion section subsection key |
| 03326 | operaciones_a_plazos_dt_1a_lis | `is_correccion_disminucion` | Operaciones a plazos (DT 1ª LIS) - Disminución - Correccione | money | correccion section subsection key |
| 03331 | adquisicion_de_participaciones_en_entida | `is_correccion_aumento` | Adquisición de participaciones en entidades no residentes (D | money | correccion section subsection key |
| 03336 | adquisicion_de_participaciones_en_entida | `is_correccion_disminucion` | Adquisición de participaciones en entidades no residentes (D | money | correccion section subsection key |
| 03341 | reinversion_de_beneficios_extraordinario | `is_correccion_aumento` | Reinversión de beneficios extraordinarios (DT 24ª LIS) - Aum | money | correccion section subsection key |
| 03346 | reinversion_de_beneficios_extraordinario | `is_correccion_disminucion` | Reinversión de beneficios extraordinarios (DT 24ª LIS) - Dis | money | correccion section subsection key |
| 03371 | correcciones_especificas_de_entidades_so | `is_correccion_aumento` | Correcciones específicas de entidades sometidas a la normati | money | correccion section subsection key |
| 03376 | correcciones_especificas_de_entidades_so | `is_correccion_disminucion` | Correcciones específicas de entidades sometidas a la normati | money | correccion section subsection key |
| 03381 | eliminaciones_pendientes_de_incorporar_d | `is_correccion_aumento` | Eliminaciones pendientes de incorporar de sociedades que dej | money | correccion section subsection key |
| 03386 | eliminaciones_pendientes_de_incorporar_d | `is_correccion_disminucion` | Eliminaciones pendientes de incorporar de sociedades que dej | money | correccion section subsection key |
| 03391 | otras_correcciones_al_resultado_de_la_cu | `is_correccion_aumento` | Otras correcciones al resultado de la cuenta de pérdidas y g | money | correccion section subsection key |
| 03396 | otras_correcciones_al_resultado_de_la_cu | `is_correccion_disminucion` | Otras correcciones al resultado de la cuenta de pérdidas y g | money | correccion section subsection key |
| 03583 | limitacion_deducibilidad_gastos_financie | `is_gastos_financieros_limitacion_importe` | Limitación deducibilidad gastos financieros. gastos financie | money | correccion section subsection key |
| 03588 | pendiente_adicion_por_limite_beneficio_o | `is_gastos_financieros_limitacion_importe` | Pendiente adición por límite beneficio operativo no aplicado | money | correccion section subsection key |
| 03617 | dotaciones_deterioro_creditos_u_otros_ac | `is_dotacion_deterioro_ejercicio` | Dotaciones deterioro créditos u otros activos - Ejercicio ge | money | correccion section subsection key |
| 03646 | correccion_por_el_impuesto_sobre_el_marg | `is_correccion_aumento` | Corrección por el Impuesto sobre el margen de intereses y co | money | correccion section subsection key |
| 00646 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 1999 - Pen | money | bases negativas / AID section |
| 00649 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2000 - Pen | money | bases negativas / AID section |
| 00652 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2001 - Pen | money | bases negativas / AID section |
| 00655 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2002 - Pen | money | bases negativas / AID section |
| 00658 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2003 - Pen | money | bases negativas / AID section |
| 00661 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2004 - Pen | money | bases negativas / AID section |
| 00664 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2005 - Pen | money | bases negativas / AID section |
| 00667 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2006 - Pen | money | bases negativas / AID section |
| 00670 | detalle_compensacion_bases_imponibles_ne | `is_bin_total_pendiente` | Detalle compensación bases imponibles negativas - TOTAL - Pe | money | bases negativas / AID section |
| 00675 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2014 - Apl | money | bases negativas / AID section |
| 00699 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2014 - Pen | money | bases negativas / AID section |
| 00743 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2007 - Pen | money | bases negativas / AID section |
| 00747 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2007 - Apl | money | bases negativas / AID section |
| 00812 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 00816 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 00817 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_exceso_cuota_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 00878 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_exceso_cuota_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 00882 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_exceso_cuota_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 00896 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2022 - Pen | money | bases negativas / AID section |
| 01020 | conversion_de_activos_por_impuesto_difer | `is_conversion_aid_abono` | Conversión de activos por impuesto diferido en crédito exigi | money | bases negativas / AID section |
| 01021 | conversion_de_activos_por_impuesto_difer | `is_conversion_aid_compensacion` | Conversión de activos por impuesto diferido en crédito exigi | money | bases negativas / AID section |
| 01043 | conversion_de_activos_por_impuesto_difer | `is_conversion_aid_abono` | Conversión de activos por impuesto diferido en crédito exigi | money | bases negativas / AID section |
| 01044 | conversion_de_activos_por_impuesto_difer | `is_conversion_aid_compensacion` | Conversión de activos por impuesto diferido en crédito exigi | money | bases negativas / AID section |
| 01045 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2015 - Pen | money | bases negativas / AID section |
| 01048 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2025 - Pen | money | bases negativas / AID section |
| 01116 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 01131 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 01413 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 01423 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_exceso_cuota_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 01519 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2016 - Pen | money | bases negativas / AID section |
| 01524 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_dt33a_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 01542 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 01579 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_exceso_cuota_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 01590 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_dt33a_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 01592 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2017 - Pen | money | bases negativas / AID section |
| 01753 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 01825 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2018 - Pen | money | bases negativas / AID section |
| 01994 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 02100 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 02193 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2019 - Pen | money | bases negativas / AID section |
| 02267 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 02316 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2025(*) -  | money | bases negativas / AID section |
| 02417 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 02490 | conversion_de_activos_por_impuesto_difer | `is_conversion_aid_rectificativa` | Conversión de activos por impuesto diferido en crédito exigi | money | bases negativas / AID section |
| 02785 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 02792 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 02796 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_exceso_cuota_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 03243 | conversion_de_activos_por_impuesto_difer | `is_conversion_aid_rectificativa` | Conversión de activos por impuesto diferido en crédito exigi | money | bases negativas / AID section |
| 03317 | conversion_de_activos_por_impuesto_difer | `is_conversion_aid_rectificativa` | Conversión de activos por impuesto diferido en crédito exigi | money | bases negativas / AID section |
| 03402 | detalle_compensacion_bases_imponibles_ne | `is_bin_pendiente_aplicacion` | Detalle compensación bases imponibles negativas - 2024 - Pen | money | bases negativas / AID section |
| 03603 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_art130_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 03613 | conversion_activos_impuesto_diferido_cre | `is_conversion_aid_exceso_cuota_importe` | Conversión activos impuesto diferido crédito exigible frente | money | bases negativas / AID section |
| 00094 | reserva_para_inversiones_en_illes_balear | `is_reserva_inversiones_illes_balears_importe` | Reserva para inversiones en Illes Balears (DA 70ª Ley 31/202 | money | reservas section |
| 00751 | reserva_para_inversiones_en_illes_balear | `is_reserva_inversiones_illes_balears_importe` | Reserva para inversiones en Illes Balears (DA 70ª Ley 31/202 | money | reservas section |
| 00801 | reserva_para_inversiones_en_illes_balear | `is_reserva_inversiones_illes_balears_importe` | Reserva para inversiones en Illes Balears (DA 70ª Ley 31/202 | money | reservas section |
| 00811 | reserva_para_inversiones_en_illes_balear | `is_reserva_inversiones_illes_balears_importe` | Reserva para inversiones en Illes Balears (DA 70ª Ley 31/202 | money | reservas section |
| 00927 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - Importe de la d | money | reservas section |
| 00928 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2020 - Apli | money | reservas section |
| 00938 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2020 - Apli | money | reservas section |
| 01109 | reserva_de_nivelacion | `is_reserva_nivelacion_adicion` | Reserva de nivelación - Reducción base imponible - Ejercicio | money | reservas section |
| 01112 | reserva_de_nivelacion | `is_reserva_nivelacion_dotacion` | Reserva de nivelación - Dotación de la reserva - Ejercicio g | money | reservas section |
| 01137 | reserva_capitalizacion | `is_reserva_capitalizacion_pendiente` | Reserva Capitalización - Total - Derecho reducir B.I. genera | money | reservas section |
| 01140 | reserva_capitalizacion | `is_reserva_capitalizacion_importe` | Reserva Capitalización - Reserva Capitalización dotada en el | money | reservas section |
| 01147 | reserva_de_nivelacion | `is_reserva_nivelacion_adicion` | Reserva de nivelación - Reducción base imponible - Total - I | money | reservas section |
| 01149 | reserva_de_nivelacion | `is_reserva_nivelacion_adicion` | Reserva de nivelación - Reducción base imponible - Total - I | money | reservas section |
| 01158 | reserva_de_nivelacion | `is_reserva_nivelacion_dotacion` | Reserva de nivelación - Dotación de la reserva - Total - Imp | money | reservas section |
| 01165 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2020 - Pend | money | reservas section |
| 01168 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2021 - Apli | money | reservas section |
| 01172 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2021 - Apli | money | reservas section |
| 01175 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2021 - Pend | money | reservas section |
| 01401 | reserva_capitalizacion | `is_reserva_capitalizacion_pendiente` | Reserva Capitalización - 2023 - Derecho reducir B.I. generad | money | reservas section |
| 01404 | reserva_de_nivelacion | `is_reserva_nivelacion_adicion` | Reserva de nivelación - Reducción base imponible - Ejercicio | money | reservas section |
| 01410 | reserva_de_nivelacion | `is_reserva_nivelacion_dotacion` | Reserva de nivelación - Dotación de la reserva - Ejercicio g | money | reservas section |
| 01604 | reserva_de_nivelacion | `is_reserva_nivelacion_incumplimiento` | Reserva de nivelación - Reducción base imponible - Ejercicio | money | reservas section |
| 01707 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - RIIB 2023  | money | reservas section |
| 01709 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - RIIB 2024  | money | reservas section |
| 01730 | reserva_de_nivelacion | `is_reserva_nivelacion_adicion` | Reserva de nivelación - Reducción base imponible - Ejercicio | money | reservas section |
| 01744 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2021 - Pend | money | reservas section |
| 01745 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2022 - Apli | money | reservas section |
| 01821 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2022 - Pend | money | reservas section |
| 01872 | reserva_de_nivelacion | `is_reserva_nivelacion_dotacion` | Reserva de nivelación - Dotación de la reserva - Ejercicio g | money | reservas section |
| 01936 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - RIIB 2023  | money | reservas section |
| 01985 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2020 - Apli | money | reservas section |
| 01986 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2021 - Apli | money | reservas section |
| 02241 | reserva_de_nivelacion | `is_reserva_nivelacion_dotacion` | Reserva de nivelación - Dotación de la reserva - Ejercicio g | money | reservas section |
| 02362 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - Inversione | money | reservas section |
| 02374 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - Inversione | money | reservas section |
| 02410 | reserva_de_nivelacion | `is_reserva_nivelacion_adicion` | Reserva de nivelación - Reducción base imponible - Ejercicio | money | reservas section |
| 02413 | reserva_de_nivelacion | `is_reserva_nivelacion_dotacion` | Reserva de nivelación - Dotación de la reserva - Ejercicio g | money | reservas section |
| 02430 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2022 - Apli | money | reservas section |
| 02773 | reserva_capitalizacion | `is_reserva_capitalizacion_pendiente` | Reserva Capitalización - 2024(*) - Derecho reducir B.I. gene | money | reservas section |
| 02776 | reserva_de_nivelacion | `is_reserva_nivelacion_adicion` | Reserva de nivelación - Reducción base imponible - Ejercicio | money | reservas section |
| 02780 | reserva_de_nivelacion | `is_reserva_nivelacion_dotacion` | Reserva de nivelación - Dotación de la reserva - Ejercicio g | money | reservas section |
| 02782 | reserva_de_nivelacion | `is_reserva_nivelacion_dotacion` | Reserva de nivelación - Dotación de la reserva - Ejercicio g | money | reservas section |
| 02807 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2022 - Pend | money | reservas section |
| 02808 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2023 - Apli | money | reservas section |
| 02822 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2023 - Pend | money | reservas section |
| 02914 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - RIIB 2023  | money | reservas section |
| 02918 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - Importe de | money | reservas section |
| 02941 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - Inversione | money | reservas section |
| 02975 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2023 - Pend | money | reservas section |
| 02977 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2023 - Apli | money | reservas section |
| 03291 | reserva_para_inversiones_en_canarias_ley | `is_reserva_inversiones_canarias_importe` | Reserva para inversiones en Canarias (Ley 19/1994) - Aumento | money | reservas section |
| 03296 | reserva_para_inversiones_en_canarias_ley | `is_reserva_inversiones_canarias_importe` | Reserva para inversiones en Canarias (Ley 19/1994) - Disminu | money | reservas section |
| 03313 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2024 - Pend | money | reservas section |
| 03354 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - Inversiones ant | money | reservas section |
| 03591 | reserva_capitalizacion | `is_reserva_capitalizacion_pendiente` | Reserva Capitalización - 2025 - Derecho reducir B.I. generad | money | reservas section |
| 03594 | reserva_capitalizacion | `is_reserva_capitalizacion_aumento` | Reserva Capitalización - Incremento porcentual de la plantil | money | reservas section |
| 03595 | reserva_de_nivelacion | `is_reserva_nivelacion_adicion` | Reserva de nivelación - Reducción base imponible - Ejercicio | money | reservas section |
| 03599 | reserva_de_nivelacion | `is_reserva_nivelacion_dotacion` | Reserva de nivelación - Dotación de la reserva - Ejercicio g | money | reservas section |
| 03623 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2024 - Pend | money | reservas section |
| 03627 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - RIC 2025 - Inte | money | reservas section |
| 03629 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - Inversiones ant | money | reservas section |
| 03630 | reg_especial_reserva_inversiones_canaria | `is_reserva_inversiones_canarias_importe` | Rég. especial reserva inversiones Canarias - Inversiones ant | money | reservas section |
| 03636 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - RIIB 2024  | money | reservas section |
| 03640 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - RIIB 2025  | money | reservas section |
| 03642 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - Inversione | money | reservas section |
| 03643 | reg_especial_reserva_inversiones_illes_b | `is_reserva_inversiones_illes_balears_importe` | Rég. especial reserva inversiones Illes Balears - Inversione | money | reservas section |
| 00181 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2008 Suma deduc | money | deduccion section + subsection key |
| 00183 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2012 Suma deduc | money | deduccion section + subsection key |
| 00366 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 00459 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2013 Investigac | money | deduccion section + subsection key |
| 00460 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_innovacion_tecnologica` | Deducc. para incentivar determ.actividades - 2013 Innovación | money | deduccion section + subsection key |
| 00473 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2007 Suma deduc | money | deduccion section + subsection key |
| 00696 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 00744 | deducciones_dt_24a_1_lis | `is_deduccion_dt24a1_periodificacion` | Deducciones DT 24ª.1 LIS - 2025(*) Periodificación - Deducci | money | deduccion section + subsection key |
| 00749 | deducciones_dt_24a_1_lis | `is_deduccion_dt24a1_periodificacion` | Deducciones DT 24ª.1 LIS - 2020 Periodificación - Deducción  | money | deduccion section + subsection key |
| 00752 | deducciones_dt_24a_1_lis | `is_deduccion_dt24a1_periodificacion` | Deducciones DT 24ª.1 LIS - 2021 Periodificación - Deducción  | money | deduccion section + subsection key |
| 00755 | deducciones_dt_24a_1_lis | `is_deduccion_dt24a1_periodificacion` | Deducciones DT 24ª.1 LIS - 2022 Periodificación - Deducción  | money | deduccion section + subsection key |
| 00758 | deducciones_dt_24a_1_lis | `is_deduccion_dt24a1_periodificacion` | Deducciones DT 24ª.1 LIS - 2023 Periodificación - Deducción  | money | deduccion section + subsection key |
| 00774 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones en La Palma, La | money | deduccion section + subsection key |
| 00779 | deducciones_dt_24a_1_lis | `is_deduccion_dt24a1_periodificacion` | Deducciones DT 24ª.1 LIS - 2025 Periodificación - Deducción  | money | deduccion section + subsection key |
| 00802 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones Canarias 2017 - | money | deduccion section + subsection key |
| 00803 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDLeg. | money | deduccion section + subsection key |
| 00806 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones Canarias 2017 - | money | deduccion section + subsection key |
| 00810 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2015 Investigac | money | deduccion section + subsection key |
| 00814 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_info_adicional` | Deducciones I+D+i excluidas de límite - Información adiciona | money | deduccion section + subsection key |
| 00822 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2014 Investigación y | money | deduccion section + subsection key |
| 00828 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_diferimiento` | Deducc. para incentivar determ.actividades - 2025 Diferim. d | money | deduccion section + subsection key |
| 00831 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_total` | Deducc. para incentivar determ.actividades - Total - Deducci | money | deduccion section + subsection key |
| 00841 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Total Deducc. Art. 36  | money | deduccion section + subsection key |
| 00843 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Total Deducc. Art. 36  | money | deduccion section + subsection key |
| 00850 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2014 Innovación tecn | money | deduccion section + subsection key |
| 00852 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2018 - Deducc | money | deduccion section + subsection key |
| 00854 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2010 - Deducc | money | deduccion section + subsection key |
| 00856 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2018 - Pendie | money | deduccion section + subsection key |
| 00857 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2011 - Deducc | money | deduccion section + subsection key |
| 00860 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2012 - Deducc | money | deduccion section + subsection key |
| 00863 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2013 - Deducc | money | deduccion section + subsection key |
| 00870 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2023 Inversione | money | deduccion section + subsection key |
| 00880 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2023 Inversione | money | deduccion section + subsection key |
| 00883 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2014 - Deducc | money | deduccion section + subsection key |
| 00886 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_total` | Deducciones inversión Canarias - Total - Deducción pendiente | money | deduccion section + subsection key |
| 00899 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 00901 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 00918 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2013 Investigación y | money | deduccion section + subsection key |
| 00929 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 2 LI | money | deduccion section + subsection key |
| 00945 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2010 Suma deduc | money | deduccion section + subsection key |
| 00960 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2011 Suma deduc | money | deduccion section + subsection key |
| 00966 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2013 Suma deduc | money | deduccion section + subsection key |
| 00976 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2013 Innovación tecn | money | deduccion section + subsection key |
| 00986 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2015 Investigac | money | deduccion section + subsection key |
| 00992 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 2 LI | money | deduccion section + subsection key |
| 01055 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 01058 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones Canarias 2016 - | money | deduccion section + subsection key |
| 01063 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2014 Suma deduc | money | deduccion section + subsection key |
| 01066 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2014 Investigac | money | deduccion section + subsection key |
| 01069 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_innovacion_tecnologica` | Deducc. para incentivar determ.actividades - 2014 Innovación | money | deduccion section + subsection key |
| 01082 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01090 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2021 Investigación y | money | deduccion section + subsection key |
| 01094 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2021 Innovación tecn | money | deduccion section + subsection key |
| 01123 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2015 Investigación y | money | deduccion section + subsection key |
| 01127 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2015 Innovación tecn | money | deduccion section + subsection key |
| 01166 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01169 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01170 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_total` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01173 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_total` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01178 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 2 LI | money | deduccion section + subsection key |
| 01182 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_total` | Deducción por reversión de medidas temporales (D.T.37ª. 2 LI | money | deduccion section + subsection key |
| 01185 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_total` | Deducción por reversión de medidas temporales (D.T.37ª. 2 LI | money | deduccion section + subsection key |
| 01284 | deduccion_por_inversiones_y_gastos_reali | `is_deduccion_copa_america_periodo` | Deducción por inversiones y gastos realizados por las autori | money | deduccion section + subsection key |
| 01287 | deduccion_por_inversiones_y_gastos_reali | `is_deduccion_copa_america_periodo` | Deducción por inversiones y gastos realizados por las autori | money | deduccion section + subsection key |
| 01289 | deduccion_por_inversiones_y_gastos_reali | `is_deduccion_copa_america_periodo` | Deducción por inversiones y gastos realizados por las autori | money | deduccion section + subsection key |
| 01292 | deduccion_por_inversiones_y_gastos_reali | `is_deduccion_copa_america_periodo` | Deducción por inversiones y gastos realizados por las autori | money | deduccion section + subsection key |
| 01295 | deduccion_por_inversiones_y_gastos_reali | `is_deduccion_copa_america_periodo` | Deducción por inversiones y gastos realizados por las autori | money | deduccion section + subsection key |
| 01298 | deduccion_por_inversiones_y_gastos_reali | `is_deduccion_copa_america_total` | Deducción por inversiones y gastos realizados por las autori | money | deduccion section + subsection key |
| 01304 | deduccion_por_inversiones_y_gastos_reali | `is_deduccion_copa_america_total` | Deducción por inversiones y gastos realizados por las autori | money | deduccion section + subsection key |
| 01309 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 01313 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 01317 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_total` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 01322 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_total` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 01353 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 01357 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2016 - Deducc | money | deduccion section + subsection key |
| 01363 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2025(*) Investi | money | deduccion section + subsection key |
| 01366 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_innovacion_tecnologica` | Deducc. para incentivar determ.actividades - 2025(*) Innovac | money | deduccion section + subsection key |
| 01377 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01385 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2022 Investigación y | money | deduccion section + subsection key |
| 01389 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2022 Innovación tecn | money | deduccion section + subsection key |
| 01426 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2016 Investigación y | money | deduccion section + subsection key |
| 01430 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2016 Innovación tecn | money | deduccion section + subsection key |
| 01437 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01438 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01442 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01446 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 2 LI | money | deduccion section + subsection key |
| 01447 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 2 LI | money | deduccion section + subsection key |
| 01451 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 2 LI | money | deduccion section + subsection key |
| 01515 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 01522 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 01571 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 01614 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2024 - Deducc | money | deduccion section + subsection key |
| 01617 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2016 Investigac | money | deduccion section + subsection key |
| 01620 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_innovacion_tecnologica` | Deducc. para incentivar determ.actividades - 2016 Innovación | money | deduccion section + subsection key |
| 01683 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_otras` | Deducc. para incentivar determ.actividades - 2026(****) Otra | money | deduccion section + subsection key |
| 01710 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2017 Investigación y | money | deduccion section + subsection key |
| 01714 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2017 Innovación tecn | money | deduccion section + subsection key |
| 01721 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01763 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos en La Palma,  | money | deduccion section + subsection key |
| 01775 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 01778 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2017 - Deducc | money | deduccion section + subsection key |
| 01781 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones Canarias 2018 - | money | deduccion section + subsection key |
| 01800 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos en La Palma,  | money | deduccion section + subsection key |
| 01802 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones Canarias 2024 - | money | deduccion section + subsection key |
| 01805 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones en La Palma, La | money | deduccion section + subsection key |
| 01838 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 01847 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones en La Palma, La | money | deduccion section + subsection key |
| 01848 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2022 Suma deduc | money | deduccion section + subsection key |
| 01850 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2017 Investigac | money | deduccion section + subsection key |
| 01853 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_innovacion_tecnologica` | Deducc. para incentivar determ.actividades - 2017 Innovación | money | deduccion section + subsection key |
| 01873 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2022 Suma deduc | money | deduccion section + subsection key |
| 01874 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2022 Investigac | money | deduccion section + subsection key |
| 01894 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_innovacion_tecnologica` | Deducc. para incentivar determ.actividades - 2022 Innovación | money | deduccion section + subsection key |
| 01897 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2022 Inversione | money | deduccion section + subsection key |
| 01913 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos en La Palma,  | money | deduccion section + subsection key |
| 01916 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2018 Inversione | money | deduccion section + subsection key |
| 01919 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2019 Inversione | money | deduccion section + subsection key |
| 01922 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2020 Inversione | money | deduccion section + subsection key |
| 01925 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2021 Inversione | money | deduccion section + subsection key |
| 01928 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2025(*) Inversi | money | deduccion section + subsection key |
| 01931 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 01935 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_info_adicional` | Deducciones I+D+i excluidas de límite - Información adiciona | money | deduccion section + subsection key |
| 01937 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 01938 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 01942 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 01946 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 01953 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 01968 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2018 Investigación y | money | deduccion section + subsection key |
| 01972 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2018 Innovación tecn | money | deduccion section + subsection key |
| 02070 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 2 LI | money | deduccion section + subsection key |
| 02072 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2024 Investigación y | money | deduccion section + subsection key |
| 02077 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2023 - Pendie | money | deduccion section + subsection key |
| 02078 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos en La Palma,  | money | deduccion section + subsection key |
| 02081 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2015 Inversione | money | deduccion section + subsection key |
| 02084 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2016 Inversione | money | deduccion section + subsection key |
| 02087 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2017 Suma deduc | money | deduccion section + subsection key |
| 02088 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2017 Inversione | money | deduccion section + subsection key |
| 02091 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2018 Suma deduc | money | deduccion section + subsection key |
| 02094 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2019 Suma deduc | money | deduccion section + subsection key |
| 02097 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2020 Suma deduc | money | deduccion section + subsection key |
| 02109 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 02116 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2019 - Deducc | money | deduccion section + subsection key |
| 02119 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones en La Palma, La | money | deduccion section + subsection key |
| 02122 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones Canarias 2019 - | money | deduccion section + subsection key |
| 02125 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones en La Palma, La | money | deduccion section + subsection key |
| 02128 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 02132 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 02136 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 02140 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 02144 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_total` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 02145 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2021 Suma deduc | money | deduccion section + subsection key |
| 02147 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_total` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 02148 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 02152 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 02156 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 02160 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 02164 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 02168 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 02172 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 02206 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 02209 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2020 - Deducc | money | deduccion section + subsection key |
| 02212 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones Canarias 2020 - | money | deduccion section + subsection key |
| 02215 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones en La Palma, La | money | deduccion section + subsection key |
| 02220 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2024 Innovación tecn | money | deduccion section + subsection key |
| 02221 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2018 Investigac | money | deduccion section + subsection key |
| 02224 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_innovacion_tecnologica` | Deducc. para incentivar determ.actividades - 2018 Innovación | money | deduccion section + subsection key |
| 02230 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 02245 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2019 Investigación y | money | deduccion section + subsection key |
| 02249 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2019 Innovación tecn | money | deduccion section + subsection key |
| 02277 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2024 Innovación tecn | money | deduccion section + subsection key |
| 02294 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2015 Suma deduc | money | deduccion section + subsection key |
| 02297 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2016 Suma deduc | money | deduccion section + subsection key |
| 02300 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2017 Suma deduc | money | deduccion section + subsection key |
| 02312 | deduccion_por_inversiones_y_gastos_reali | `is_deduccion_copa_america_periodo` | Deducción por inversiones y gastos realizados por las autori | money | deduccion section + subsection key |
| 02329 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 02332 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2021 - Deducc | money | deduccion section + subsection key |
| 02335 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos en La Palma,  | money | deduccion section + subsection key |
| 02347 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones Canarias 2021 - | money | deduccion section + subsection key |
| 02350 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones en La Palma, La | money | deduccion section + subsection key |
| 02353 | deduccion_por_inversiones_y_gastos_reali | `is_deduccion_copa_america_periodo` | Deducción por inversiones y gastos realizados por las autori | money | deduccion section + subsection key |
| 02354 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 02356 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2019 Investigac | money | deduccion section + subsection key |
| 02359 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_innovacion_tecnologica` | Deducc. para incentivar determ.actividades - 2019 Innovación | money | deduccion section + subsection key |
| 02383 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 02391 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2020 Investigación y | money | deduccion section + subsection key |
| 02395 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2020 Innovación tecn | money | deduccion section + subsection key |
| 02437 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 02443 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 02445 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_pendiente_generada` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 02448 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2021 Suma deduc | money | deduccion section + subsection key |
| 02449 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2025(*) Suma de | money | deduccion section + subsection key |
| 02461 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2025(*) Suma de | money | deduccion section + subsection key |
| 02466 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 02477 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 2 LI | money | deduccion section + subsection key |
| 02497 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos en La Palma,  | money | deduccion section + subsection key |
| 02500 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2017 Suma deduc | money | deduccion section + subsection key |
| 02701 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 02709 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2023 Investigación y | money | deduccion section + subsection key |
| 02757 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2023 Investigación y | money | deduccion section + subsection key |
| 02759 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2023 Innovación tecn | money | deduccion section + subsection key |
| 02762 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2023 Innovación tecn | money | deduccion section + subsection key |
| 03421 | deducc_disposic_transit_24a_7_lis | `is_deduccion_dt24a7_periodo` | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2 | money | deduccion section + subsection key |
| 03424 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos 2025 - Deducc | money | deduccion section + subsection key |
| 03427 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Activos fijos en La Palma,  | money | deduccion section + subsection key |
| 03430 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones Canarias 2025 - | money | deduccion section + subsection key |
| 03433 | deducciones_inversion_canarias | `is_deduccion_inversion_canarias_importe` | Deducciones inversión Canarias - Inversiones en La Palma, La | money | deduccion section + subsection key |
| 03436 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_suma_periodo` | Deducc. para incentivar determ.actividades - 2024 Suma deduc | money | deduccion section + subsection key |
| 03439 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_investigacion_aplicada` | Deducc. para incentivar determ.actividades - 2024 Investigac | money | deduccion section + subsection key |
| 03442 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_innovacion_tecnologica` | Deducc. para incentivar determ.actividades - 2024 Innovación | money | deduccion section + subsection key |
| 03445 | deducc_para_incentivar_determ_actividade | `is_deduccion_inversiones_africa_canarias` | Deducc. para incentivar determ.actividades - 2024 Inversione | money | deduccion section + subsection key |
| 03523 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_evento_especial` | Deducc. para incentivar determ.actividades - 2025: Barcelona | money | deduccion section + subsection key |
| 03526 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_evento_especial` | Deducc. para incentivar determ.actividades - 2025: Barcelona | money | deduccion section + subsection key |
| 03529 | deducc_para_incentivar_determ_actividade | `is_deduccion_idi_evento_especial` | Deducc. para incentivar determ.actividades - 2025: Rally Isl | money | deduccion section + subsection key |
| 03532 | deduccion_por_inversiones_y_gastos_reali | `is_deduccion_copa_america_periodo` | Deducción por inversiones y gastos realizados por las autori | money | deduccion section + subsection key |
| 03535 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras (a | money | deduccion section + subsection key |
| 03539 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_pendiente_generada` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 03540 | deducciones_por_producciones_cinematogra | `is_deduccion_cinematografica_extranjera_periodo` | Deducciones por producciones cinematográficas extranjeras en | money | deduccion section + subsection key |
| 03567 | deduccion_por_reversion_de_medidas_tempo | `is_deduccion_reversion_medidas_periodo` | Deducción por reversión de medidas temporales (D.T.37ª. 1 LI | money | deduccion section + subsection key |
| 03575 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_investigacion` | Deducciones I+D+i excluidas de límite - 2025(*) Investigació | money | deduccion section + subsection key |
| 03579 | deducciones_i_d_i_excluidas_de_limite | `is_deduccion_idi_excluida_limite_innovacion` | Deducciones I+D+i excluidas de límite - 2025(*) Innovación t | money | deduccion section + subsection key |
| 00369 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 00818 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 00833 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 00842 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 00844 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 00868 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 00871 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 00890 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 00895 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_total` | Deducción donativos entidades sin fines lucro - Total deducc | money | donativos section subsection |
| 00933 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 00943 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 00949 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 00963 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 00969 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 00974 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_base` | Deducción donativos entidades sin fines lucro - Base de la d | money | donativos section subsection |
| 00975 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 00979 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 00993 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 01000 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01007 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01017 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01024 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01035 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01061 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01072 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01323 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 01329 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01372 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01434 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 01692 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 01704 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01718 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 01729 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 01950 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 02227 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 02380 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 02472 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 02498 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 03543 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_general` | Deducción donativos entidades sin fines lucro - Donaciones d | money | donativos section subsection |
| 03555 | deduccion_donativos_entidades_sin_fines_ | `is_deduccion_donativos_prioritarias` | Deducción donativos entidades sin fines lucro - Donaciones p | money | donativos section subsection |
| 00001 | entidad_sin_animo_de_lucro_acogida_regim | `is_identificacion_flag` | Entidad sin ánimo de lucro acogida régimen fiscal Título II  | decimal | identificacion section + decimal/text dtype |
| 00002 | entidad_parcialmente_exenta | `is_identificacion_flag` | Entidad parcialmente exenta [00002] | decimal | identificacion section + decimal/text dtype |
| 00003 | sociedad_de_inversion_de_capital_variabl | `is_identificacion_flag` | Sociedad de inversión de capital variable o fondo de inversi | decimal | identificacion section + decimal/text dtype |
| 00004 | sociedad_de_inversion_inmobiliaria_o_fon | `is_identificacion_flag` | Sociedad de inversión inmobiliaria o fondo de inversión inmo | decimal | identificacion section + decimal/text dtype |
| 00005 | comunidades_titulares_de_montes_vecinale | `is_identificacion_flag` | Comunidades titulares de montes vecinales en mano común [000 | decimal | identificacion section + decimal/text dtype |
| 00006 | incentivos_entidad_de_reducida_dimension | `is_identificacion_flag` | Incentivos entidad de reducida dimensión ( cap XI, tít. VII  | decimal | identificacion section + decimal/text dtype |
| 00007 | imputacion_en_base_imponible_rentas_posi | `is_identificacion_flag` | Imputación en base imponible rentas positivas art. 100 LIS [ | decimal | identificacion section + decimal/text dtype |
| 00008 | sociedad_de_inversion_de_capital_variabl | `is_identificacion_flag` | Sociedad de inversión de capital variable que no cumpla los  | decimal | identificacion section + decimal/text dtype |
| 00009 | entidad_dominante_de_grupo_fiscal | `is_identificacion_flag` | Entidad dominante de grupo fiscal [00009] | decimal | identificacion section + decimal/text dtype |
| 00010 | entidad_dependiente_de_grupo_fiscal | `is_identificacion_flag` | Entidad dependiente de grupo fiscal [00010] | decimal | identificacion section + decimal/text dtype |
| 00011 | entidad_de_tenencia_de_valores_extranjer | `is_identificacion_flag` | Entidad de tenencia de valores extranjeros [00011] | decimal | identificacion section + decimal/text dtype |
| 00012 | socimi | `is_identificacion_flag` | SOCIMI [00012] | decimal | identificacion section + decimal/text dtype |
| 00013 | agrupacion_de_interes_economico_espanola | `is_identificacion_flag` | Agrupación de interés económico española [00013] | decimal | identificacion section + decimal/text dtype |
| 00014 | agrupacion_europea_de_interes_economico | `is_identificacion_flag` | Agrupación europea de interés económico [00014] | decimal | identificacion section + decimal/text dtype |
| 00015 | entidad_zec_sin_consolidacion_fiscal | `is_identificacion_flag` | Entidad ZEC (sin consolidación fiscal) [00015] | decimal | identificacion section + decimal/text dtype |
| 00017 | cooperativa_protegida | `is_identificacion_flag` | Cooperativa protegida [00017] | decimal | identificacion section + decimal/text dtype |
| 00018 | cooperativa_especialmente_protegida | `is_identificacion_flag` | Cooperativa especialmente protegida [00018] | decimal | identificacion section + decimal/text dtype |
| 00019 | resto_cooperativas | `is_identificacion_flag` | Resto cooperativas [00019] | decimal | identificacion section + decimal/text dtype |
| 00020 | otros_regimenes_especiales | `is_identificacion_flag` | Otros regímenes especiales [00020] | decimal | identificacion section + decimal/text dtype |
| 00021 | establecimiento_permanente | `is_identificacion_flag` | Establecimiento permanente [00021] | decimal | identificacion section + decimal/text dtype |
| 00022 | regimen_entidades_navieras_en_funcion_de | `is_identificacion_flag` | Régimen entidades navieras en función del tonelaje [00022] | decimal | identificacion section + decimal/text dtype |
| 00023 | gran_empresa | `is_identificacion_flag` | Gran empresa [00023] | decimal | identificacion section + decimal/text dtype |
| 00024 | entidad_de_credito | `is_identificacion_flag` | Entidad de crédito [00024] | decimal | identificacion section + decimal/text dtype |
| 00025 | entidad_aseguradora | `is_identificacion_flag` | Entidad aseguradora [00025] | decimal | identificacion section + decimal/text dtype |
| 00026 | entidad_inactiva | `is_identificacion_flag` | Entidad inactiva [00026] | decimal | identificacion section + decimal/text dtype |
| 00028 | tributacion_conjunta_estado_diput_cdad_f | `is_identificacion_flag` | Tributación conjunta Estado/Diput.Cdad.Forales [00028] | decimal | identificacion section + decimal/text dtype |
| 00029 | regimen_especial_canarias | `is_identificacion_flag` | Régimen especial Canarias [00029] | decimal | identificacion section + decimal/text dtype |
| 00030 | transmision_elementos_patrimoniales_arts | `is_identificacion_flag` | Transmisión elementos patrimoniales arts. 27.2.d) y 77.1 L.I | decimal | identificacion section + decimal/text dtype |
| 00031 | entidades_de_capital_riesgo | `is_identificacion_flag` | Entidades de capital-riesgo [00031] | decimal | identificacion section + decimal/text dtype |
| 00032 | sociedades_desarrollo_industrial_regiona | `is_identificacion_flag` | Sociedades desarrollo industrial regional [00032] | decimal | identificacion section + decimal/text dtype |
| 00033 | regimen_especial_mineria | `is_identificacion_flag` | Régimen especial minería [00033] | decimal | identificacion section + decimal/text dtype |
| 00034 | regimen_especial_hidrocarburos | `is_identificacion_flag` | Régimen especial hidrocarburos [00034] | decimal | identificacion section + decimal/text dtype |
| 00035 | regimen_especial_fusiones_escisiones_apo | `is_identificacion_flag` | Régimen especial fusiones, escisiones, aportaciones activos  | decimal | identificacion section + decimal/text dtype |
| 00036 | sociedad_de_garantia_reciproca_o_de_reaf | `is_identificacion_flag` | Sociedad de garantía recíproca o de reafianzamiento [00036] | decimal | identificacion section + decimal/text dtype |
| 00037 | opcion_de_fraccionamiento_art_19_1_lis | `is_identificacion_flag` | Opción de fraccionamiento art. 19.1 LIS [00037] | decimal | identificacion section + decimal/text dtype |
| 00038 | entidad_dedicada_al_arrend_viviendas | `is_identificacion_flag` | Entidad dedicada al arrend. viviendas [00038] | decimal | identificacion section + decimal/text dtype |
| 00039 | entidad_que_forma_parte_de_un_grupo_merc | `is_identificacion_flag` | Entidad que forma parte de un grupo mercantil (art. 42 del C | decimal | identificacion section + decimal/text dtype |
| 00040 | grupo_fiscal | `is_grupo_fiscal_numero` | Grupo fiscal - Claves 00009 ó 00010 - Nº de grupo fiscal [00 | text | identificacion section + decimal/text dtype |
| 00041 | personal_asalariado_cifra_media_del_ejer | `is_personal_asalariado_cifra_media` | Personal asalariado (cifra media del ejercicio) Personal fij | decimal | identificacion section + decimal/text dtype |
| 00043 | obligacion_informacion_dt_5a_ris | `is_identificacion_flag` | Obligación información DT 5ª RIS [00043] | decimal | identificacion section + decimal/text dtype |
| 00044 | contribuyente_que_genera_deducciones_del | `is_identificacion_flag` | Contribuyente que genera deducciones del art. 36.1 y 36.3 LI | decimal | identificacion section + decimal/text dtype |
| 00045 | inversiones_anticipadas | `is_identificacion_flag` | Inversiones anticipadas - reserva inversiones en Canarias (a | decimal | identificacion section + decimal/text dtype |
| 00046 | entidad_en_reg_atribuc_de_rentas_constit | `is_identificacion_flag` | Entidad en rég. Atribuc. de rentas constituida en el extranj | decimal | identificacion section + decimal/text dtype |
| 00047 | entidades_sometidas_a_normativa_foral | `is_identificacion_flag` | Entidades sometidas a normativa foral [00047] | decimal | identificacion section + decimal/text dtype |
| 00048 | fondo_de_pensiones_real_decreto_legislat | `is_identificacion_flag` | Fondo de Pensiones Real Decreto Legislativo 1/2002 de 29 de  | decimal | identificacion section + decimal/text dtype |
| 00049 | regimenes_especiales_de_normativa_foral | `is_identificacion_flag` | Regímenes especiales de normativa foral [00049] | decimal | identificacion section + decimal/text dtype |
| 00056 | entidad_en_regimen_de_atribucion_de_rent | `is_identificacion_flag` | Entidad en régimen de atribución de rentas con tributación p | decimal | identificacion section + decimal/text dtype |
| 00057 | regimen_fiscal_salida_socimi | `is_identificacion_flag` | Régimen fiscal salida SOCIMI [00057] | decimal | identificacion section + decimal/text dtype |
| 00058 | mutua_de_seguros_o_mutualidad_de_previsi | `is_identificacion_flag` | Mutua de seguros o Mutualidad de previsión social [00058] | decimal | identificacion section + decimal/text dtype |
| 00059 | opcion_art_39_2_lis | `is_identificacion_flag` | Opción art. 39.2 LIS [00059] | decimal | identificacion section + decimal/text dtype |
| 00060 | fondos_o_activos_de_titulizacion | `is_identificacion_flag` | Fondos o activos de titulización [00060] | decimal | identificacion section + decimal/text dtype |
| 00061 | estados_de_cuentas_de_instituciones_de_i | `is_identificacion_flag` | Estados de cuentas de Instituciones de Inversión Colectiva:  | decimal | identificacion section + decimal/text dtype |
| 00062 | reg_fiscal_de_operac_de_aportacion_de_ac | `is_identificacion_flag` | Reg.fiscal de operac.de aportación de activos a sdades. para | decimal | identificacion section + decimal/text dtype |
| 00063 | tipo_de_gravamen_reducido_para_entidades | `is_identificacion_flag` | Tipo de gravamen reducido para entidades de nueva creación ( | decimal | identificacion section + decimal/text dtype |
| 00064 | regimen_fiscal_entrada_socimi | `is_identificacion_flag` | Régimen fiscal entrada SOCIMI [00064] | decimal | identificacion section + decimal/text dtype |
| 00065 | bonificacion_personal_investigador_rd_47 | `is_identificacion_flag` | Bonificación personal investigador (RD 475/2014) [00065] | decimal | identificacion section + decimal/text dtype |
| 00066 | entidad_patrimonial | `is_identificacion_flag` | Entidad patrimonial [00066] | decimal | identificacion section + decimal/text dtype |
| 00068 | estados_de_cuentas_de_entidades_de_credi | `is_identificacion_flag` | Estados de cuentas de Entidades de Crédito: Entidades que si | decimal | identificacion section + decimal/text dtype |
| 00070 | compensacion_bases_imponibles_negativas_ | `is_identificacion_flag` | Compensación bases imponibles negativas para entidades de nu | decimal | identificacion section + decimal/text dtype |
| 00071 | tipo_gravamen_reducido_para_entidades_de | `is_identificacion_flag` | Tipo gravamen reducido para entidades de nueva creación (art | decimal | identificacion section + decimal/text dtype |
| 00072 | extincion_de_entidad | `is_identificacion_flag` | Extinción de entidad [00072] | decimal | identificacion section + decimal/text dtype |
| 00073 | opcion_del_0_7_de_la_cuota_integra_para_ | `is_identificacion_flag` | Opción del 0,7% de la cuota íntegra para fines sociales [000 | decimal | identificacion section + decimal/text dtype |
| 00074 | contribuyente_que_financia_producciones_ | `is_identificacion_flag` | Contribuyente que financia producciones con derecho a la ded | decimal | identificacion section + decimal/text dtype |
| 00078 | diocesis_provincia_religiosa_o_entidad_e | `is_identificacion_flag` | Diócesis, provincia religiosa o entidad eclesiástica que int | decimal | identificacion section + decimal/text dtype |
| 00079 | entidad_zec_en_consolidacion_fiscal | `is_identificacion_flag` | Entidad ZEC en consolidación fiscal [00079] | decimal | identificacion section + decimal/text dtype |
| 00080 | uniones_federaciones_y_confederaciones_d | `is_identificacion_flag` | Uniones, federaciones y confederaciones de cooperativas [000 | decimal | identificacion section + decimal/text dtype |
| 00081 | filial_grupo_multinacional_o_grupo_nacio | `is_identificacion_flag` | Filial grupo multinacional o grupo nacional de gran magnitud | decimal | identificacion section + decimal/text dtype |
| 00082 | sociedad_matriz_ultima_grupo_multinacion | `is_identificacion_flag` | Sociedad matriz última grupo multinacional o grupo nacional  | decimal | identificacion section + decimal/text dtype |
| 00083 | tipo_gravamen_reducido_para_empresa_emer | `is_identificacion_flag` | Tipo gravamen reducido para empresa emergente [00083] | decimal | identificacion section + decimal/text dtype |
| 00084 | regimen_especial_de_disolucion_y_liquida | `is_identificacion_flag` | Régimen especial de disolución y liquidación de SICAV (DT 41 | decimal | identificacion section + decimal/text dtype |
| 00085 | union_temporal_de_empresas | `is_identificacion_flag` | Unión temporal de empresas [00085] | decimal | identificacion section + decimal/text dtype |
| 00086 | regimen_especial_illes_balears | `is_identificacion_flag` | Régimen especial Illes Balears [00086] | decimal | identificacion section + decimal/text dtype |
| 00087 | inversiones_anticipadas_reserva_inversio | `is_identificacion_flag` | Inversiones anticipadas-reserva inversiones en Illes Balears | decimal | identificacion section + decimal/text dtype |
| 00088 | tipo_gravamen_reducido_para_entidades_co | `is_identificacion_flag` | Tipo gravamen reducido para entidades con INCN periodo anter | decimal | identificacion section + decimal/text dtype |
| 00089 | participe_de_agrupacion_de_interes_econo | `is_identificacion_flag` | Partícipe de agrupación de interés económico o de unión temp | decimal | identificacion section + decimal/text dtype |
| 00090 | opcion_art_39_3_lis | `is_identificacion_flag` | Opción art. 39.3 LIS [00090] | decimal | identificacion section + decimal/text dtype |
| 00714 | deducciones_doble_imposicion_interna_rdl | `is_deduccion_di_interna_rdleg_importe` | Deducciones doble imposición interna RDLeg. 4/2004 - DI inte | money | doble imposicion section |
| 00825 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_rdleg_importe` | Deducciones doble imposición internacional RDLeg. 4/2004 - D | money | doble imposicion section |
| 00846 | deducciones_doble_imposicion_interna_rdl | `is_deduccion_di_interna_rdleg_importe` | Deducciones doble imposición interna RDLeg. 4/2004 - DI inte | money | doble imposicion section |
| 00849 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_rdleg_importe` | Deducciones doble imposición internacional RDLeg. 4/2004 - D | money | doble imposicion section |
| 00894 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_rdleg_importe` | Deducciones doble imposición internacional RDLeg. 4/2004 - D | money | doble imposicion section |
| 00920 | deducciones_doble_imposicion_interna_rdl | `is_deduccion_di_interna_rdleg_importe` | Deducciones doble imposición interna RDLeg. 4/2004 - DI inte | decimal | doble imposicion section |
| 00921 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_rdleg_importe` | Deducciones doble imposición internacional RDLeg. 4/2004 - D | decimal | doble imposicion section |
| 00926 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_rdleg_importe` | Deducciones doble imposición internacional RDLeg. 4/2004 - D | decimal | doble imposicion section |
| 01013 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 01050 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | decimal | doble imposicion section |
| 01270 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_periodo` | Deducciones doble imposición interna (DT 23.1 LIS) - DI inte | money | doble imposicion section |
| 01299 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_periodo` | Deducciones doble imposición interna (DT 23.1 LIS) - DI inte | money | doble imposicion section |
| 01318 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_periodo` | Deducciones doble imposición interna (DT 23.1 LIS) - DI inte | money | doble imposicion section |
| 01342 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_total` | Deducciones doble imposición interna (DT 23.1 LIS) - Total - | money | doble imposicion section |
| 01345 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_total` | Deducciones doble imposición interna (DT 23.1 LIS) - Total - | money | doble imposicion section |
| 01348 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 01360 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_periodo` | Deducciones doble imposición interna (DT 23.1 LIS) - DI inte | money | doble imposicion section |
| 01361 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 01457 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 01472 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 01505 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 01595 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_periodo` | Deducciones doble imposición interna (DT 23.1 LIS) - DI inte | money | doble imposicion section |
| 01770 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 01828 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_periodo` | Deducciones doble imposición interna (DT 23.1 LIS) - DI inte | money | doble imposicion section |
| 01833 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 02076 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_periodo` | Deducciones doble imposición interna (DT 23.1 LIS) - DI inte | money | doble imposicion section |
| 02196 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_periodo` | Deducciones doble imposición interna (DT 23.1 LIS) - DI inte | money | doble imposicion section |
| 02201 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 02319 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_periodo` | Deducciones doble imposición interna (DT 23.1 LIS) - DI inte | money | doble imposicion section |
| 02324 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 03411 | deducciones_doble_imposicion_interna_dt_ | `is_deduccion_di_interna_periodo` | Deducciones doble imposición interna (DT 23.1 LIS) - DI inte | money | doble imposicion section |
| 03416 | deducciones_doble_imposicion_internacion | `is_deduccion_di_internacional_periodo` | Deducciones doble imposición internacional LIS - DI internac | money | doble imposicion section |
| 00016 | reg_cooperativas | `is_cooperativa_base_imponible` | Rég. cooperativas - Determ. base imponible - 11. Reserva inv | money | reg_cooperativas label match |
| 00099 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2010 Aplica | money | reg_cooperativas label match |
| 00100 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2010 Pendie | money | reg_cooperativas label match |
| 00587 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2009 Pendie | money | reg_cooperativas label match |
| 00672 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2007 Pendie | money | reg_cooperativas label match |
| 00673 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2000 Pendie | money | reg_cooperativas label match |
| 00674 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2000 Aplica | money | reg_cooperativas label match |
| 00676 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2001 Pendie | money | reg_cooperativas label match |
| 00677 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2001 Aplica | money | reg_cooperativas label match |
| 00678 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2001 Pendie | money | reg_cooperativas label match |
| 00679 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2002 Pendie | money | reg_cooperativas label match |
| 00680 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2002 Aplica | money | reg_cooperativas label match |
| 00681 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2002 Pendie | money | reg_cooperativas label match |
| 00682 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2003 Pendie | money | reg_cooperativas label match |
| 00683 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2003 Aplica | money | reg_cooperativas label match |
| 00684 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2003 Pendie | money | reg_cooperativas label match |
| 00685 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2004 Pendie | money | reg_cooperativas label match |
| 00686 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2004 Aplica | money | reg_cooperativas label match |
| 00687 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2004 Pendie | money | reg_cooperativas label match |
| 00688 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2005 Pendie | money | reg_cooperativas label match |
| 00689 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2005 Aplica | money | reg_cooperativas label match |
| 00690 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2005 Pendie | money | reg_cooperativas label match |
| 00691 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2006 Pendie | money | reg_cooperativas label match |
| 00692 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2006 Aplica | money | reg_cooperativas label match |
| 00693 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2006 Pendie | money | reg_cooperativas label match |
| 00694 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. Total. Pend | money | reg_cooperativas label match |
| 00773 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2012 Aplica | money | reg_cooperativas label match |
| 00777 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2012 Pendie | money | reg_cooperativas label match |
| 00900 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2009 Pendie | money | reg_cooperativas label match |
| 00907 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2013 Pendie | money | reg_cooperativas label match |
| 00908 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2013 Aplica | money | reg_cooperativas label match |
| 00909 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2013 Pendie | money | reg_cooperativas label match |
| 00910 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2014 Pendie | money | reg_cooperativas label match |
| 00911 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2014 Aplica | money | reg_cooperativas label match |
| 00912 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2014 Pendie | money | reg_cooperativas label match |
| 00935 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2015 Pendie | money | reg_cooperativas label match |
| 00936 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2015 Aplica | money | reg_cooperativas label match |
| 00937 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2015 Pendie | money | reg_cooperativas label match |
| 01186 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2021 Pendie | money | reg_cooperativas label match |
| 01187 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2021 Aplica | money | reg_cooperativas label match |
| 01190 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2021 Pendie | money | reg_cooperativas label match |
| 01224 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2000 Pendie | money | reg_cooperativas label match |
| 01225 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2024 Pendie | money | reg_cooperativas label match |
| 01511 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2016 Pendie | money | reg_cooperativas label match |
| 01512 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2016 Aplica | money | reg_cooperativas label match |
| 01513 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2016 Pendie | money | reg_cooperativas label match |
| 01516 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2022 Pendie | money | reg_cooperativas label match |
| 01517 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2022 Aplica | money | reg_cooperativas label match |
| 01518 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2022 Pendie | money | reg_cooperativas label match |
| 01767 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2017 Pendie | money | reg_cooperativas label match |
| 01768 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2017 Aplica | money | reg_cooperativas label match |
| 01769 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2017 Pendie | money | reg_cooperativas label match |
| 02113 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2018 Pendie | money | reg_cooperativas label match |
| 02114 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2018 Aplica | money | reg_cooperativas label match |
| 02115 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2018 Pendie | money | reg_cooperativas label match |
| 02281 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2019 Pendie | money | reg_cooperativas label match |
| 02282 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2019 Aplica | money | reg_cooperativas label match |
| 02283 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2019 Pendie | money | reg_cooperativas label match |
| 02452 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2020 Pendie | money | reg_cooperativas label match |
| 02453 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2020 Aplica | money | reg_cooperativas label match |
| 02454 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2020 Pendie | money | reg_cooperativas label match |
| 02827 | reg_cooperativas | `is_cooperativa_base_imponible` | Rég. cooperativas - Determ. base imponible - 1, Ingresos com | money | reg_cooperativas label match |
| 02832 | reg_cooperativas | `is_cooperativa_base_imponible` | Rég. cooperativas - Determ. base imponible - 3. Gastos gener | money | reg_cooperativas label match |
| 02845 | reg_cooperativas | `is_cooperativa_base_imponible` | Rég. cooperativas - Determ. base imponible - 9. 50% Dotación | money | reg_cooperativas label match |
| 02850 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2023 Pendie | money | reg_cooperativas label match |
| 02912 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2023 Aplica | money | reg_cooperativas label match |
| 02913 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2023 Pendie | money | reg_cooperativas label match |
| 03357 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2024 Pendie | money | reg_cooperativas label match |
| 03358 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2024 Aplica | money | reg_cooperativas label match |
| 03633 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2025(*) Pen | money | reg_cooperativas label match |
| 03634 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2025(*) Apl | money | reg_cooperativas label match |
| 03635 | reg_cooperativas | `is_cooperativa_compensacion_cuotas` | Rég. cooperativas - Detalle compensación cuotas. 2025(*) Pen | money | reg_cooperativas label match |
| 00069 | regimen_especial_de_buques_y_empresas_na | `is_naviera_importe` | Régimen especial de buques y empresas navieras en Canarias [ | decimal | navieras label match |
| 00091 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 00092 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 00097 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 00987 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 01010 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 01177 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 01200 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 01886 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 01888 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 01889 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 01891 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 03405 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 03408 | regimen_especial_de_buques_y_empresas_na | `is_naviera_base_imponible_negativa` | Régimen especial de buques y empresas navieras en Canarias:  | money | navieras label match |
| 00050 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_proporcion` | Tributación conjunta Estado y Adm.Forales - Concierto económ | money | tributacion_conjunta label match |
| 00055 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_proporcion` | Tributación conjunta Estado y Adm.Forales - Convenio económi | money | tributacion_conjunta label match |
| 00447 | tributacion_conjunta_estado_y_adm_forale | `is_pagos_fraccionados` | Tributación conjunta Estado y Adm.Forales - Pagos fraccionad | money | tributacion_conjunta label match |
| 00474 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_cuota` | Tributación conjunta Estado y Adm.Forales - Cuota diferencia | money | tributacion_conjunta label match |
| 00487 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_intereses` | Tributación conjunta Estado y Adm.Forales - Intereses demora | money | tributacion_conjunta label match |
| 00913 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_incremento` | Tributación conjunta Estado y Adm.Forales - Incremento por i | money | tributacion_conjunta label match |
| 01300 | tributacion_conjunta_estado_y_adm_forale | `is_conversion_aid_importe` | Tributación conjunta Estado y Adm.Forales - Conversión de ac | money | tributacion_conjunta label match |
| 01305 | tributacion_conjunta_estado_y_adm_forale | `is_conversion_aid_importe` | Tributación conjunta Estado y Adm.Forales - Conversión de ac | money | tributacion_conjunta label match |
| 01334 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_cuota` | Tributación conjunta Estado y Adm.Forales - Abono deduccione | money | tributacion_conjunta label match |
| 01338 | tributacion_conjunta_estado_y_adm_forale | `is_conversion_aid_abono` | Tributación conjunta Estado y Adm.Forales - Abono deduccione | money | tributacion_conjunta label match |
| 01607 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_rectificacion` | Tributación conjunta Estado y Adm.Forales - Rectificativa: R | money | tributacion_conjunta label match |
| 01611 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_rectificacion` | Tributación conjunta Estado y Adm.Forales - Rectificativa: D | money | tributacion_conjunta label match |
| 01623 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_rectificacion` | Tributación conjunta Estado y Adm.Forales - Rectificativa: D | money | tributacion_conjunta label match |
| 01624 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_resultado` | Tributación conjunta Estado y Adm.Forales - Resultado de la  | money | tributacion_conjunta label match |
| 01629 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_resultado` | Tributación conjunta Estado y Adm.Forales - Resultado de la  | money | tributacion_conjunta label match |
| 01631 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_opcion_0_7` | Tributación conjunta Estado y Adm.Forales - Opción de fracci | money | tributacion_conjunta label match |
| 01646 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_resultado` | Tributación conjunta Estado y Adm.Forales - Resultado de la  | money | tributacion_conjunta label match |
| 01650 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_rectificacion` | Tributación conjunta Estado y Adm.Forales - Rectificativa: R | money | tributacion_conjunta label match |
| 01654 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_resultado` | Tributación conjunta Estado y Adm.Forales - Resultado inclui | money | tributacion_conjunta label match |
| 01658 | tributacion_conjunta_estado_y_adm_forale | `is_conversion_aid_importe` | Tributación conjunta Estado y Adm.Forales - Conversión de ac | money | tributacion_conjunta label match |
| 01841 | entidad_en_regimen_de_atribucion_de_rent | `is_atribucion_rentas_importe` | Entidad en régimen de atribución de rentas: asimetrías híbri | money | tributacion_conjunta label match |
| 01846 | entidad_en_regimen_de_atribucion_de_rent | `is_atribucion_rentas_importe` | Entidad en régimen de atribución de rentas: asimetrías híbri | money | tributacion_conjunta label match |
| 01856 | entidad_en_regimen_de_atribucion_de_rent | `is_atribucion_rentas_importe` | Entidad en régimen de atribución de rentas: asimetrías híbri | money | tributacion_conjunta label match |
| 01877 | tributacion_conjunta_estado_y_adm_forale | `is_conversion_aid_abono` | Tributación conjunta Estado y Adm.Forales - Abono deduccione | money | tributacion_conjunta label match |
| 02378 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_rectificacion` | Tributación conjunta Estado y Adm.Forales - Discrepancia de  | money | tributacion_conjunta label match |
| 02407 | tributacion_conjunta_estado_y_adm_forale | `is_tributacion_conjunta_rectificacion` | Tributación conjunta Estado y Adm.Forales - Discrepancia de  | money | tributacion_conjunta label match |
| 03361 | entidades_en_reg_de_atribucion_de_rentas | `is_atribucion_rentas_importe` | Entidades en rég. de atribución de rentas const. en el extra | money | tributacion_conjunta label match |
| 03366 | entidades_en_reg_de_atribucion_de_rentas | `is_atribucion_rentas_importe` | Entidades en rég. de atribución de rentas const. en el extra | money | tributacion_conjunta label match |
| 00101 | balance_activo_i | `is_balance_activo_importe` | Balance: Activo (I) - Activo - ACTIVO NO CORRIENTE [00101] | money | estados financieros section prefix |
| 00149 | balance_activo_ii | `is_balance_activo_importe` | Balance: Activo (II) - Activo - Deudores comerciales y otras | money | estados financieros section prefix |
| 00185 | balance_patrimonio_neto_y_pasivo_i | `is_balance_patrimonio_neto_pasivo_importe` | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pa | money | estados financieros section prefix |
| 00228 | balance_patrimonio_neto_y_pasivo_ii | `is_balance_patrimonio_neto_pasivo_importe` | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y p | money | estados financieros section prefix |
| 00253 | cuenta_de_perdidas_y_ganancias_i | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas | money | estados financieros section prefix |
| 00273 | cuenta_de_perdidas_y_ganancias_i | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas | money | estados financieros section prefix |
| 00305 | cuenta_de_perdidas_y_ganancias_ii | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (II) - Operaciones continuada | money | estados financieros section prefix |
| 00328 | cuenta_de_perdidas_y_ganancias_ii | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (II) - Operaciones interrumpi | money | estados financieros section prefix |
| 00329 | cuenta_de_perdidas_y_ganancias_ii | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (II) - Operaciones continuada | money | estados financieros section prefix |
| 00336 | estado_de_cambios_patrimonio_neto_i | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (I) - Ingresos y gastos im | money | estados financieros section prefix |
| 00346 | estado_de_cambios_patrimonio_neto_i | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (I) - Transferencias a la  | money | estados financieros section prefix |
| 00380 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Saldo, final del ej | money | estados financieros section prefix |
| 00387 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Saldo final del ej | money | estados financieros section prefix |
| 00394 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Ajustes por cambio  | money | estados financieros section prefix |
| 00401 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Ajustes por cambio | money | estados financieros section prefix |
| 00408 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Ajustes por errores | money | estados financieros section prefix |
| 00415 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Ajustes por errore | money | estados financieros section prefix |
| 00422 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Saldo ajustado, ini | money | estados financieros section prefix |
| 00429 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Saldo ajustado, in | money | estados financieros section prefix |
| 00436 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Total ingresos y ga | money | estados financieros section prefix |
| 00443 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Total ingresos y g | money | estados financieros section prefix |
| 00448 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Total ingresos y g | money | estados financieros section prefix |
| 00450 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Resultado cuenta pé | money | estados financieros section prefix |
| 00457 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Resultado cuenta p | money | estados financieros section prefix |
| 00461 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Resultado cuenta p | money | estados financieros section prefix |
| 00464 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Ingresos y gastos r | money | estados financieros section prefix |
| 00471 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Ingresos y gastos  | money | estados financieros section prefix |
| 00475 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Ingresos y gastos  | money | estados financieros section prefix |
| 00478 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Ingresos y gastos r | money | estados financieros section prefix |
| 00485 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Ingresos y gastos  | money | estados financieros section prefix |
| 00489 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Ingresos y gastos  | money | estados financieros section prefix |
| 00492 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Ingresos y gastos r | money | estados financieros section prefix |
| 00499 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Ingresos y gastos  | money | estados financieros section prefix |
| 00500 | cuenta_de_perdidas_y_ganancias_ii | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (II) - Operaciones interrumpi | money | estados financieros section prefix |
| 00502 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Ingresos y gastos  | money | estados financieros section prefix |
| 00506 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Operaciones con soc | money | estados financieros section prefix |
| 00513 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00520 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Operaciones con soc | money | estados financieros section prefix |
| 00527 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00534 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Operaciones con soc | money | estados financieros section prefix |
| 00541 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00548 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Operaciones con soc | money | estados financieros section prefix |
| 00555 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00560 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00562 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Operaciones con soc | money | estados financieros section prefix |
| 00569 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00574 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00576 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Operaciones con soc | money | estados financieros section prefix |
| 00583 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00588 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00590 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Operaciones con soc | money | estados financieros section prefix |
| 00597 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00602 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00604 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Operaciones con soc | money | estados financieros section prefix |
| 00611 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Operaciones con so | money | estados financieros section prefix |
| 00618 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Otras variaciones d | money | estados financieros section prefix |
| 00625 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Otras variaciones  | money | estados financieros section prefix |
| 00632 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJ | money | estados financieros section prefix |
| 00639 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL E | money | estados financieros section prefix |
| 00700 | balance_activo_i | `is_balance_activo_importe` | Balance: Activo (I) - Activo - Propiedad intelectual [00700] | money | estados financieros section prefix |
| 00702 | balance_patrimonio_neto_y_pasivo_i | `is_balance_patrimonio_neto_pasivo_importe` | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pa | money | estados financieros section prefix |
| 00703 | balance_patrimonio_neto_y_pasivo_ii | `is_balance_patrimonio_neto_pasivo_importe` | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y p | money | estados financieros section prefix |
| 00705 | cuenta_de_perdidas_y_ganancias_i | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas | money | estados financieros section prefix |
| 00712 | balance_patrimonio_neto_y_pasivo_i | `is_balance_patrimonio_neto_pasivo_importe` | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pa | money | estados financieros section prefix |
| 00715 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Otras variaciones d | money | estados financieros section prefix |
| 00722 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Otras variaciones  | money | estados financieros section prefix |
| 00729 | estado_de_cambios_patrimonio_neto_ii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (II) - Otras variaciones d | money | estados financieros section prefix |
| 00736 | estado_de_cambios_patrimonio_neto_iii | `is_estado_cambios_patrimonio_neto_importe` | Estado de cambios patrimonio neto (III) - Otras variaciones  | money | estados financieros section prefix |
| 00760 | cuenta_de_perdidas_y_ganancias_i | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas | money | estados financieros section prefix |
| 00764 | balance_patrimonio_neto_y_pasivo_i | `is_balance_patrimonio_neto_pasivo_importe` | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pa | money | estados financieros section prefix |
| 00770 | cuenta_de_perdidas_y_ganancias_i | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas | money | estados financieros section prefix |
| 00780 | balance_patrimonio_neto_y_pasivo_i | `is_balance_patrimonio_neto_pasivo_importe` | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pa | money | estados financieros section prefix |
| 00785 | balance_patrimonio_neto_y_pasivo_ii | `is_balance_patrimonio_neto_pasivo_importe` | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y p | money | estados financieros section prefix |
| 00790 | cuenta_de_perdidas_y_ganancias_i | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas | money | estados financieros section prefix |
| 00796 | cuenta_de_perdidas_y_ganancias_ii | `is_cuenta_perdidas_ganancias_importe` | Cuenta de pérdidas y ganancias (II) - Operaciones continuada | money | estados financieros section prefix |
| 01001 | balance_patrimonio_neto_y_pasivo_i | `is_balance_patrimonio_neto_pasivo_importe` | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pa | money | estados financieros section prefix |
| 00027 | base_imponible_negativa_o_cero | `base_imponible_negativa_is` | Base imponible negativa o cero [00027] | decimal | pre-existing role declaration |
| 00599 | liquidacion | `resultado_ingresar_o_devolver_is` | Cuota del ejercicio a ingresar o a devolver | money | pre-existing role declaration |

## New roles introduced

These roles are proposed by this audit and do NOT appear in the canonical taxonomy reference.
All bind `data_type = "money"` unless noted.

| role | data_type | sign | definition |
|------|-----------|------|------------|
| `is_identificacion_flag` | decimal | n/a | Boolean/checkbox flag on page 001 identifying entity type or regime. Decimal 0/1 convention. |
| `is_identificacion_texto` | text | n/a | Free-text identifier on page 001 (e.g. grupo fiscal number). |
| `is_grupo_fiscal_numero` | text | n/a | Grupo fiscal identifier number — text field. |
| `is_personal_asalariado_cifra_media` | decimal | non_negative | Cifra media de personal asalariado del ejercicio. |
| `is_resultado_contable` | money | any | Resultado contable (accounting profit/loss) at the IS annual declaration level. Equivalent of M202 is_pf_mod_40_3_resultado_contable without the quarterly qualifier. |
| `is_correcciones_aumentos` | money | non_negative | Total aumentos al resultado contable (sum of all LIS correction increases). |
| `is_correcciones_disminuciones` | money | non_negative | Total disminuciones al resultado contable (sum of all LIS correction decreases). |
| `is_base_imponible_previa` | money | any | Base imponible previa (before compensacion BINs and reserva capitalizacion). |
| `is_base_imponible` | money | any | Base imponible (after reserva capitalizacion / nivelacion reductions). |
| `is_compensacion_bases_negativas` | money | non_negative | Compensacion de bases imponibles negativas de ejercicios anteriores applied in this period. |
| `is_tipo_gravamen` | decimal | non_negative | Tipo de gravamen (tax rate) as a percentage. |
| `is_cuota_integra` | money | non_negative | Cuota integra (tax before deductions). |
| `is_cuota_liquida` | money | non_negative | Cuota liquida (tax after deductions, before retenciones and pagos). |
| `is_cuota_a_ingresar` | money | non_negative | Cuota a ingresar final after retenciones and pagos. |
| `is_liquidacion_importe` | money | any | Generic liquidacion section amount not matching a more specific role. |
| `is_liquidacion_i_importe` | money | any | Generic liquidacion_i section amount. |
| `is_liquidacion_ii_importe` | money | any | Generic liquidacion_ii section amount. |
| `is_liquidacion_iii_importe` | money | any | Generic liquidacion_iii section amount. |
| `is_liquidacion_iv_importe` | money | any | Generic liquidacion_iv section amount. |
| `is_correccion_aumento` | money | non_negative | Single LIS-article correction aumentos item. Shared role across ~80 correccion sections. |
| `is_correccion_disminucion` | money | non_negative | Single LIS-article correction disminucion item. Shared role across ~80 correccion sections. |
| `is_correccion_total` | money | any | Total correccion amount for a multi-year detail section. |
| `is_correccion_dotacion_ejercicio` | money | non_negative | Dotacion generated in this ejercicio (e.g. dotaciones deterioro creditos). |
| `is_correccion_importe` | money | any | Generic correccion amount where subsection key is not aumento/disminucion. |
| `is_conversion_activo_diferido_importe` | money | any | Conversion activos impuesto diferido item (abono/compensacion/rectificativa variants). |
| `is_gastos_financieros_limitacion_importe` | money | any | Limitacion deducibilidad gastos financieros (art.16 LIS) tracking amounts. |
| `is_dotacion_deterioro_ejercicio` | money | non_negative | Dotacion deterioro creditos u otros activos generated in this ejercicio. |
| `is_dotacion_deterioro_total` | money | non_negative | Total dotacion deterioro pendiente de reversion. |
| `is_conversion_aid_art130_importe` | money | any | AID conversion frente Hacienda Publica (art.130 LIS). |
| `is_conversion_aid_exceso_cuota_importe` | money | any | AID conversion por exceso cuota liquida positiva. |
| `is_conversion_aid_dt33a_importe` | money | any | AID conversion DT33a y DA13a LIS. |
| `is_conversion_aid_importe` | money | any | Generic AID conversion amount. |
| `is_conversion_aid_abono` | money | non_negative | AID conversion abono (credit applied to tax debt). |
| `is_conversion_aid_compensacion` | money | non_negative | AID conversion compensacion (offset against cuota). |
| `is_conversion_aid_rectificativa` | money | any | AID conversion rectificativa adjustment. |
| `is_bin_pendiente_aplicacion` | money | non_positive | Base imponible negativa pendiente de compensacion from a prior year. Non-positive by definition. |
| `is_bin_total_pendiente` | money | non_positive | Total BIN pendiente de aplicacion across all prior years. |
| `is_correcciones_temporarias_importe` | money | any | Detalle correcciones temporarias (saldo pendiente / correcciones al resultado). |
| `is_reserva_capitalizacion_aumento` | money | non_negative | Incremento de fondos propios generating the reserva capitalizacion. |
| `is_reserva_capitalizacion_reduccion` | money | non_negative | Reduccion base imponible por reserva capitalizacion. |
| `is_reserva_capitalizacion_pendiente` | money | non_negative | Reserva capitalizacion pendiente de dotacion. |
| `is_reserva_capitalizacion_incumplimiento` | money | non_negative | Reserva capitalizacion incumplimiento amount. |
| `is_reserva_capitalizacion_importe` | money | any | Generic reserva capitalizacion amount. |
| `is_reserva_nivelacion_dotacion` | money | non_negative | Dotacion reserva nivelacion (reduces base imponible). |
| `is_reserva_nivelacion_adicion` | money | non_negative | Adicion a base imponible por reserva nivelacion reversion or income application. |
| `is_reserva_nivelacion_pendiente` | money | non_negative | Reserva nivelacion saldo pendiente de adicion. |
| `is_reserva_nivelacion_incumplimiento` | money | non_negative | Reserva nivelacion incumplimiento amount. |
| `is_reserva_nivelacion_importe` | money | any | Generic reserva nivelacion amount. |
| `is_reserva_inversiones_canarias_importe` | money | any | Reserva para inversiones en Canarias (ley 19/1994 art.27) tracking amounts. |
| `is_reserva_inversiones_illes_balears_importe` | money | any | Reserva para inversiones en Illes Balears (DA70a LIS) tracking amounts. |
| `is_cooperativa_compensacion_cuotas` | money | any | Cooperativa cuota negativa pendiente/aplicada en compensacion (Ley 20/1990). |
| `is_cooperativa_cuota_integra` | money | non_negative | Cuota integra cooperativa (protegida + especialmente protegida + resto). |
| `is_cooperativa_cuota_liquida` | money | non_negative | Cuota liquida cooperativa after bonificaciones. |
| `is_cooperativa_base_imponible` | money | any | Base imponible cooperativa (extracooperativa / cooperativa). |
| `is_cooperativa_resultado_contable` | money | any | Resultado contable cooperativa. |
| `is_cooperativa_retenciones` | money | non_negative | Retenciones e ingresos a cuenta cooperativa. |
| `is_cooperativa_pagos_fraccionados` | money | non_negative | Pagos fraccionados cooperativa. |
| `is_cooperativa_tipo_gravamen` | decimal | non_negative | Tipo de gravamen cooperativa (%). |
| `is_cooperativa_importe` | money | any | Generic cooperativa liquidacion amount. |
| `is_naviera_base_imponible_negativa` | money | non_positive | Base imponible negativa pendiente en regimen especial navieras tonelaje. |
| `is_naviera_compensacion` | money | non_negative | Compensacion BIN en regimen especial navieras. |
| `is_naviera_importe` | money | any | Generic regimen especial navieras amount. |
| `is_balance_activo_importe` | money | any | Balance de situacion activo (PGCE format) balance sheet line. |
| `is_balance_patrimonio_neto_pasivo_importe` | money | any | Balance patrimonio neto y pasivo line. |
| `is_cuenta_perdidas_ganancias_importe` | money | any | Cuenta de perdidas y ganancias line (operaciones continuadas / interrumpidas). |
| `is_estado_cambios_patrimonio_neto_importe` | money | any | Estado de cambios en el patrimonio neto (I, II, III) line. |
| `is_atribucion_rentas_importe` | money | any | Entidades en regimen de atribucion de rentas — amount attributed or corrected. |
| `is_tributacion_conjunta_proporcion` | money | non_negative | Proporcion tributacion conjunta Estado/Administraciones Forales (concierto/convenio). |
| `is_tributacion_conjunta_cuota` | money | any | Cuota resultante en tributacion conjunta. |
| `is_tributacion_conjunta_resultado` | money | any | Resultado final in tributacion conjunta settlement. |
| `is_tributacion_conjunta_rectificacion` | money | any | Rectificacion amount in tributacion conjunta context. |
| `is_tributacion_conjunta_intereses` | money | any | Intereses de demora in tributacion conjunta. |
| `is_tributacion_conjunta_incremento` | money | any | Incremento in tributacion conjunta base. |
| `is_tributacion_conjunta_opcion_0_7` | money | any | Opcion 0.7% cuota integra para fines sociales in tributacion conjunta context. |
| `is_tributacion_conjunta_discrepancia` | money | any | Discrepancia in tributacion conjunta calculation. |
| `is_tributacion_conjunta_importe` | money | any | Generic tributacion conjunta amount. |
| `is_informacion_adicional_limites_importe` | money | any | Informacion adicional para calculo de limites deduccion I+D+i (art.35 LIS). |
| `is_deduccion_idi_investigacion_aplicada` | money | non_negative | Deduccion I+D (art.35.1 LIS / CT) aplicada en el periodo, by generation year. |
| `is_deduccion_idi_innovacion_tecnologica` | money | non_negative | Deduccion IT (art.35.2 LIS / IT) aplicada en el periodo, by generation year. |
| `is_deduccion_idi_suma_periodo` | money | non_negative | Suma deducciones I+D+i generadas en a given year (cap.IV tit.VI). |
| `is_deduccion_inversiones_africa_canarias` | money | non_negative | Deduccion inversiones territorios Africa occidental y gastos publicitarios (art.27bis LIS / Canarias). |
| `is_deduccion_idi_diferimiento` | money | non_negative | Deduccion I+D+i diferida pendiente from prior period. |
| `is_deduccion_idi_total` | money | non_negative | Total I+D+i deduction pendiente fin de periodo (all years combined). |
| `is_deduccion_idi_evento_especial` | money | non_negative | Special-event deduction (Barcelona 2026, Copa America, Rally Islas Canarias). |
| `is_deduccion_idi_otras` | money | non_negative | Otras deducciones relativas a programas de apoyo. |
| `is_deduccion_idi_importe` | money | non_negative | Generic I+D+i incentivos deduction amount. |
| `is_deduccion_idi_excluida_limite_investigacion` | money | non_negative | Deduccion I+D excluida de limite (art.35.1), by generation year. |
| `is_deduccion_idi_excluida_limite_innovacion` | money | non_negative | Deduccion IT excluida de limite (art.35.2), by generation year. |
| `is_deduccion_idi_excluida_limite_info_adicional` | money | non_negative | Informacion adicional para calculo de limites en deducciones excluidas. |
| `is_deduccion_idi_excluida_limite_importe` | money | non_negative | Generic I+D+i excluida de limite amount. |
| `is_deduccion_di_interna_periodo` | money | non_negative | Deduccion doble imposicion interna (DT23.1 LIS), by generation year. |
| `is_deduccion_di_interna_total` | money | non_negative | Total deduccion doble imposicion interna pendiente. |
| `is_deduccion_di_interna_rdleg_importe` | money | non_negative | Deduccion doble imposicion interna RDLeg 4/2004 (pre-LIS) amount. |
| `is_deduccion_di_internacional_periodo` | money | non_negative | Deduccion doble imposicion internacional (LIS), by generation year. |
| `is_deduccion_di_internacional_total` | money | non_negative | Total deduccion doble imposicion internacional pendiente. |
| `is_deduccion_di_internacional_rdleg_importe` | money | non_negative | Deduccion doble imposicion internacional RDLeg 4/2004 (pre-LIS) amount. |
| `is_deduccion_dt24a1_periodificacion` | money | non_negative | Deduccion DT24a.1 LIS periodificacion amount. |
| `is_deduccion_dt24a7_periodo` | money | non_negative | Deduccion DT24a.7 LIS (reinversion beneficios extraordinarios), by year. |
| `is_deduccion_dt24a7_total` | money | non_negative | Total deduccion DT24a.7 LIS pendiente. |
| `is_deduccion_donativos_general` | money | non_negative | Deduccion por donaciones de caracter general (ley 49/2002). |
| `is_deduccion_donativos_prioritarias` | money | non_negative | Deduccion por donaciones actividades prioritarias de mecenazgo. |
| `is_deduccion_donativos_base` | money | non_negative | Base de la deduccion por donaciones. |
| `is_deduccion_donativos_total` | money | non_negative | Total deducciones donativos entidades sin fines lucro. |
| `is_deduccion_donativos_importe` | money | non_negative | Generic donativo deduction amount. |
| `is_deduccion_copa_america_periodo` | money | non_negative | Deduccion Copa America / inversiones autoridades portuarias, by year. |
| `is_deduccion_copa_america_total` | money | non_negative | Total deduccion Copa America. |
| `is_deduccion_reversion_medidas_periodo` | money | non_negative | Deduccion reversion medidas temporales (DT37a LIS), by year. |
| `is_deduccion_reversion_medidas_total` | money | non_negative | Total deduccion reversion medidas temporales. |
| `is_deduccion_inversion_canarias_importe` | money | non_negative | Deduccion inversion Canarias activos fijos / inversiones, by type and year. |
| `is_deduccion_inversion_canarias_total` | money | non_negative | Total deduccion inversion Canarias pendiente. |
| `is_deduccion_cinematografica_extranjera_periodo` | money | non_negative | Deduccion producciones cinematograficas extranjeras (art.36.2/36.3 LIS), by year. |
| `is_deduccion_cinematografica_extranjera_total` | money | non_negative | Total deduccion producciones cinematograficas extranjeras pendiente. |
| `is_deduccion_cinematografica_pendiente_generada` | money | non_negative | Deduccion cinematografica extranjera pendiente generada en el periodo. |
| `is_reserva_nivelacion_reduccion` | money | non_negative | Reduccion base imponible by reserva nivelacion in liquidacion context. |
| `is_reserva_capitalizacion_reduccion` | money | non_negative | Reduccion base imponible by reserva capitalizacion in liquidacion context. |

## Top reuse patterns

1. **`is_correccion_aumento` / `is_correccion_disminucion`** — shared across all ~80 LIS-article correction
   sections (185 casillas combined). Every correccion section has a symmetric aumento/disminucion pair.
   These two roles cover the broadest footprint in the form.

2. **`is_cooperativa_compensacion_cuotas`** — 68 casillas across the `reg_cooperativas` section.
   Each year (1999–2025) contributes three casillas: pendiente al principio, aplicado en esta liquidacion,
   pendiente al final. The section structure repeats identically for each generation year.

3. **`is_estado_cambios_patrimonio_neto_importe`** — 53 casillas across the three subsections
   (`estado_de_cambios_patrimonio_neto_i/ii/iii`). Each subsection is a PGC-mandated equity
   movement table; all rows share the same monetary role.

## Open questions / classification ambiguities

### 1. `is_liquidacion_iv_importe` (13 casillas)
The `liquidacion_iv` section spans a ZEC/consolidated IS regime page whose exact label structure
was not resolvable from the label snippets alone (labels are truncated in the TOML). The label-match
heuristics assigned most to recognized sub-concepts (`is_resultado_contable`, `is_tipo_gravamen`, etc.)
but 13 fell to the generic `is_liquidacion_iv_importe` role. Manual review recommended.

### 2. Tributacion conjunta `is_tributacion_conjunta_*` (24 casillas)
The `tributacion_conjunta_estado_y_adm_forales` section has complex sub-structure (concierto/convenio,
AID-conversion amounts, rectificativas, resultados). Label-based classification was applied but
some sub-slots may semantically overlap with existing roles (e.g. `is_pagos_fraccionados` reused).
The AID-conversion sub-slots inside this section were mapped to `is_conversion_aid_*` roles; the
overlap with the general AID section should be validated at rollout.

### 3. Cooperativas: `is_cooperativa_cuota_integra` / `is_cooperativa_cuota_liquida` vs. IS main roles
Cooperativas compute their own cuota integra and cuota liquida under Ley 20/1990, which differs from
the general LIS cuota. The cooperative-specific roles intentionally do NOT reuse `is_cuota_integra`
/ `is_cuota_liquida` to avoid cross-section validator inconsistency (constraints and sign conventions
may differ). If the snapshot-build validator permits per-section role islands, this can be revisited.

### 4. `is_identificacion_flag` (74 casillas) — consistency validation
All page-001 entity-type checkbox casillas carry `data_type = "decimal"`. The role is proposed
consistently for all 74 but the validator will check for constraint consistency across the role.
If any casilla carries a non-zero constraint (e.g. `non_negative`) that differs from the default,
the validator will reject it. All decimal flags should be unconstrained.

### 5. Reserved-role overlap for `is_retenciones_ingresos_a_cuenta` and `is_pagos_fraccionados`
These two roles already exist in the canonical taxonomy (bound to `money / non_negative`). They are
reused here in the liquidacion context. The liquidacion casillas for these concepts must carry
`constraints = "non_negative"` to satisfy the intra-role consistency validator.