---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# `schema-hardening` audit: M200 IS liquidacion role assignment

## Scope

Cluster: `liquidacion` — Liquidación I–IV blocks plus `tributacion_conjunta_estado_y_adm_forales` joint
State/Foral-administration taxation.

Sections covered:

- `liquidacion_i/detalle_correcciones_resultado_cta_perdidas_y_gana`
- `liquidacion_i/resultado_de_la_cuenta_de_perdidas_y_ganancias`
- `liquidacion_ii/detalle_correcciones_resultado_cta_perdidas_y_gana`
- `liquidacion_ii/entidades_que_forman_parte_de_grupos_de_consolidac`
- `liquidacion_iii/base_imponible`
- `liquidacion_iv/cuota_del_ejercicio_a_ingresar_o_a_devolver`
- `liquidacion_iv/otras_deducciones`
- `liquidacion_iv/opcion_de_fraccionamiento_en_supuestos_de_cambios`
- `liquidacion_iv/rectificativa`
- `liquidacion_iv/resultado_de_la_autoliquidacion`
- `tributacion_conjunta_estado_y_adm_forales/abono_deducciones_i_d_i_insuf_cuota`
- `tributacion_conjunta_estado_y_adm_forales/abono_deducciones_producciones_extranjeras`
- `tributacion_conjunta_estado_y_adm_forales/abono_deducciones_producciones_extranjeras_en_cana`
- `tributacion_conjunta_estado_y_adm_forales/concierto_economico`
- `tributacion_conjunta_estado_y_adm_forales/conversion_de_activos_por_impuesto_diferido_en_cre`
- `tributacion_conjunta_estado_y_adm_forales/discrepancia_de_criterio_administrativo_para_deter`
- `tributacion_conjunta_estado_y_adm_forales/incremento_por_incumplimiento_requisitos_socimi`
- `tributacion_conjunta_estado_y_adm_forales/intereses_demora`
- `tributacion_conjunta_estado_y_adm_forales/opcion_de_fraccionamiento_art_19_1_lis`
- `tributacion_conjunta_estado_y_adm_forales/rectificativa_devolucion_acordada_por_la_agencia_t`
- `tributacion_conjunta_estado_y_adm_forales/rectificativa_resultado_a_ingresar_como_consecuenc`
- `tributacion_conjunta_estado_y_adm_forales/rectificativa_resultado_de_la_autoliquidacion_incl`
- `tributacion_conjunta_estado_y_adm_forales/resultado_de_la_autoliquidacion`
- `tributacion_conjunta_estado_y_adm_forales/resultado_incluido_en_el_1er_fraccionamiento_de_ar`
- `tributacion_conjunta_estado_y_adm_forales/resultado_de_la_autoliquidacion_incluido_el_1o_fra`

Total casillas classified: 116

## Role assignments

Role naming: `is_` prefix following M200 convention, snake_case, stable tax term only.

Role reuse decisions follow verbatim matches from `_existing-roles.txt` (88 roles).

New roles introduced in this cluster (not in existing-roles.txt):

- `is_correcciones_resultado_contable_impuesto` — correction to P&L for tax on the group (casilla 01231)
- `is_consolidacion_fiscal_eliminacion` — fiscal-group consolidation eliminations/incorporations (01030)
- `is_consolidacion_fiscal_integracion` — fiscal-group individual dotation integration (01031)
- `is_reserva_nivelacion_incumplimiento` — already present in existing-roles.txt (01038 mapped to it)
- `is_cooperativa_cuota_integra_previa` — cuota íntegra previa for cooperative entities after nivelación (01331)
- `is_cooperativa_reserva_nivelacion_cuota` — nivelación reserve converted to quotas for cooperative (01286)
- `is_cooperativa_reversion_deterioro` — reversal of impairment losses for cooperative entities (01510)
- `is_naviera_base_imponible_foral` — naviera partial BI for foral split (01577)
- `is_deduccion_reversion_medidas_periodo` — already in existing-roles.txt; reused for 01040, 01041
- `is_deduccion_inversion_autoridades_portuarias` — deducción inversiones autoridades portuarias art.38 bis (02315)
- `is_fraccionamiento_cambio_residencia_deuda` — deuda tributaria under art.19.1 LIS exit-tax instalment (02481–02484)
- `is_fraccionamiento_cambio_residencia_resultado` — result of the self-assessment under the instalment option (02485–02489)
- `is_tributacion_conjunta_abono_idi` — abono deducciones I+D+i insuficiencia de cuota (01335–01337)
- `is_tributacion_conjunta_abono_cinematografica` — abono deducciones producciones extranjeras (01339–01341, 01878–01880)
- `is_tributacion_conjunta_fraccionamiento_importe` — importe integrado / deuda tributaria under fraccionamiento art.19.1 (01632–01645)
- `is_tributacion_conjunta_fraccionamiento_resultado` — resultado autoliquidación including 1st instalment (01647–01657)
- `is_tributacion_conjunta_discrepancia` — discrepancia de criterio administrativo (02379, 02408)

| id | role | label_snippet | data_type | notes |
|----|------|---------------|-----------|-------|
| 00051 | `is_tributacion_conjunta_proporcion` | Tributación conjunta … Concierto económico - Volumen operaciones en el extranjero | money | Reused: volume-of-operations breakdown within concierto económico; same role as 00050 |
| 00052 | `is_tributacion_conjunta_proporcion` | Tributación conjunta … Volumen operaciones en Araba/Álava | money | Reused: Araba/Álava proportion |
| 00053 | `is_tributacion_conjunta_proporcion` | Tributación conjunta … Volumen operaciones en Gipuzkoa | money | Reused: Gipuzkoa proportion |
| 00054 | `is_tributacion_conjunta_proporcion` | Tributación conjunta … Volumen operaciones en Bizkaia | money | Reused: Bizkaia proportion |
| 00334 | `is_atribucion_rentas_importe` | Liquidación I - Detalle correcciones … Entidad en régimen de atribución de rentas: a | money | Reused: attribution-of-income entity correction |
| 00335 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Gastos y provisiones por pensiones no afectos | money | Reused: LIS art.14 pension provision non-deductible increase |
| 00357 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Operaciones a plazos (art.11.4 LIS) - Aumento | money | Reused: instalment-sale timing increase |
| 00358 | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones … Operaciones a plazos (art.11.4 LIS) - Disminu | money | Reused: instalment-sale timing decrease |
| 00359 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Reversión del deterioro de valor elem. patrim | money | Reused: impairment reversal increase |
| 00360 | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones … Reversión del deterioro de valor elem. patrim | money | Reused: impairment reversal decrease |
| 00361 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … otras diferencias de imputac. temporal de ing | money | Reused: other temporal difference increase |
| 00362 | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones … Otras diferencias de imputac. temporal de ing | money | Reused: other temporal difference decrease |
| 00363 | `is_gastos_financieros_limitacion_importe` | Liquidación I - Detalle correcciones … Ajustes por la limitación en la deduc. de gas | money | Reused: financial expense limitation adjustment increase |
| 00364 | `is_gastos_financieros_limitacion_importe` | Liquidación I - Detalle correcciones … Ajustes por la limitación en la deduc. de gas | money | Reused: financial expense limitation adjustment decrease |
| 00373 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … Obra benéfico-social de las cajas de ahorro — aumento | money | Reused: cajas de ahorro welfare-work increase |
| 00374 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Obra benéfico-social de las cajas de ahorro — disminución | money | Reused: cajas de ahorro welfare-work decrease |
| 00375 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … Agrupación de interés económico (Cap. II Tit — aumento | money | Reused: AIE correction increase |
| 00376 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Agrupación de interés económico (Cap. II Tit — disminución | money | Reused: AIE correction decrease |
| 00377 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … Soc. y fondos de capital-riesgo y soc. desar — aumento | money | Reused: venture capital / dev society correction increase |
| 00378 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Soc. y fondos de capital-riesgo y soc. desar — disminución | money | Reused: venture capital / dev society correction decrease |
| 00379 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … Valoración bienes y derechos. Régimen especi | money | Reused: special-regime asset valuation correction |
| 00488 | `is_tributacion_conjunta_intereses` | Tributación conjunta … Intereses demora - Bizkaia | money | Reused: late-interest charge for Bizkaia |
| 00776 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Amortización acelerada de determinados vehícu | money | Reused: accelerated vehicle depreciation correction |
| 00914 | `is_tributacion_conjunta_incremento` | Tributación conjunta … Incremento por incumplimiento requisitos SOCIMI - Gipuzkoa | money | Reused: SOCIMI non-compliance increment Gipuzkoa |
| 00915 | `is_tributacion_conjunta_incremento` | Tributación conjunta … Incremento por incumplimiento requisitos SOCIMI - Bizkaia | money | Reused: SOCIMI non-compliance increment Bizkaia |
| 00916 | `is_tributacion_conjunta_incremento` | Tributación conjunta … Incremento por incumplimiento requisitos SOCIMI - Navarra | money | Reused: SOCIMI non-compliance increment Navarra |
| 01004 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Libertad de amortización inmovilizado materia | money | Reused: free-depreciation correction increase |
| 01005 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Amortización del inmovilizado intangible y fo | money | Reused: intangible / goodwill amortisation increase |
| 01006 | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones … Amortización del inmovilizado intangible y fo | money | Reused: intangible / goodwill amortisation decrease |
| 01012 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Operaciones vinculadas: aplicación del valor | money | Reused: related-party transaction arm's-length correction |
| 01015 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … Efectos de la valoración contable diferente | money | Reused: different accounting valuation effect increase |
| 01016 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Efectos de la valoración contable diferente | money | Reused: different accounting valuation effect decrease |
| 01019 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … Unión temporal de empresas, ajustes por crit | money | Reused: UTE income recognition adjustment increase |
| 01023 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … Unión temporal de empresas, ajustes por rent | money | Reused: UTE rent adjustment increase |
| 01027 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … Eliminaciones pdte. de incorporar sdes.que d | money | Reused: pending eliminations / incorporations increase |
| 01028 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Eliminaciones pdte. de incorporar sdes.que d | money | Reused: pending eliminations / incorporations decrease |
| 01030 | `is_consolidacion_fiscal_eliminacion` | Liquidación II - Entidades que forman parte de grupos de consolidac. … Eliminaciones e incorporaciones | money | New: fiscal-group consolidation eliminations/incorporations |
| 01031 | `is_consolidacion_fiscal_integracion` | Liquidación II - Entidades que forman parte de grupos de consolidac. … Integración individual de las dotaciones | money | New: fiscal-group individual integration of provisions |
| 01033 | `is_reserva_nivelacion_adicion` | Liquidación III - Base Imponible - Entidades Reducida dimensión - Reserva de nivelación - Aumentos | money | Reused: nivelación reserve addition (ERD) |
| 01034 | `is_reserva_nivelacion_dotacion` | Liquidación III - Base Imponible - Entidades Reducida dimensión - Reserva de nivelación - Disminuciones | money | Reused: nivelación reserve deduction (ERD) |
| 01038 | `is_reserva_nivelacion_incumplimiento` | Liquidación III - Base imponible - Incremento por incumplimiento reserva de nivelación | money | Reused: nivelación reserve non-compliance increment |
| 01040 | `is_deduccion_reversion_medidas_periodo` | Liquidación IV - Otras deducciones - Deducciones por reversión de medidas temporales DT 37ª.1 LIS | money | Reused: reversal of temporary measures deduction DT37a.1 |
| 01041 | `is_deduccion_reversion_medidas_periodo` | Liquidación IV - Otras deducciones - Deducciones por reversión de medidas temporales DT 37ª.2 LIS | money | Reused: reversal of temporary measures deduction DT37a.2 |
| 01231 | `is_correcciones_resultado_contable_impuesto` | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones al impuesto contable referidos al grupo fi | money | New: correction to accounting-tax charge for fiscal group |
| 01276 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … BI negativas generadas dentro del grupo fisc | money | Reused: negative taxable bases generated inside fiscal group |
| 01286 | `is_cooperativa_reserva_nivelacion_cuota` | Liquidación III - Base imponible - Sólo sociedades cooperativas - Reserva de nivelación convertido en cuotas | money | New: cooperativa nivelación reserve converted to quota |
| 01301 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido en crédito exigible … [01301] | money | Reused: AID conversion amount (Bizkaia/Gipuzkoa/Navarra split) |
| 01302 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01302] | money | Reused |
| 01303 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01303] | money | Reused |
| 01306 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01306] | money | Reused |
| 01307 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01307] | money | Reused |
| 01308 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01308] | money | Reused |
| 01321 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … Unión temporal de empresas, ajustes del art. | money | Reused: UTE LIS art.43 adjustment increase |
| 01331 | `is_cooperativa_cuota_integra_previa` | Liquidación III - Sólo sociedades cooperativas - Cuota íntegra previa después de la reserva de nivelaci | money | New: cooperativa cuota íntegra previa post-nivelación |
| 01333 | `is_deduccion_cinematografica_extranjera_periodo` | Liquidación IV - Resultado de la autoliquidación - Abono deducciones por producciones cinematográficas extranjeras | money | Reused: cinema foreign production deduction credit current period |
| 01335 | `is_tributacion_conjunta_abono_idi` | Tributación conjunta … Abono deducciones I+D+i insuf. cuota - Gipuzkoa | money | New: I+D+i deduction credit where quota insufficient, Gipuzkoa |
| 01336 | `is_tributacion_conjunta_abono_idi` | Tributación conjunta … Abono deducciones I+D+i insuf. cuota - Bizkaia | money | New: Bizkaia |
| 01337 | `is_tributacion_conjunta_abono_idi` | Tributación conjunta … Abono deducciones I+D+i insuf. cuota - Navarra | money | New: Navarra |
| 01339 | `is_tributacion_conjunta_abono_cinematografica` | Tributación conjunta … Abono deducciones producciones extranjeras - Gipuzkoa | money | New: foreign-production deduction credit, Gipuzkoa |
| 01340 | `is_tributacion_conjunta_abono_cinematografica` | Tributación conjunta … Abono deducciones producciones extranjeras - Bizkaia | money | New: Bizkaia |
| 01341 | `is_tributacion_conjunta_abono_cinematografica` | Tributación conjunta … Abono deducciones producciones extranjeras - Navarra | money | New: Navarra |
| 01510 | `is_cooperativa_reversion_deterioro` | Liquidación III - Base imponible - Sólo sociedades cooperativas - Rentas correspondientes a la reversión de deterioros | money | New: cooperativa impairment reversal income |
| 01573 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Cambio de residencia a Estados miembros de la | money | Reused: exit-tax on change of residency to EU state |
| 01575 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … Operaciones del art. 19 LIS distintas del ca | money | Reused: art.19 LIS operations other than residency change |
| 01577 | `is_naviera_base_imponible_foral` | Liquidación III - Base imponible - Régimen especial de buques y empresas navieras en Canarias - Parte de la base imponib | money | New: naviera partial BI allocated to foral territory |
| 01584 | `is_tributacion_conjunta_rectificacion` | Liquidación IV - Rectificativa - Devolución acordada por la Agencia Tributaria … [01584] | money | Reused: rectificative return agreed by AEAT |
| 01585 | `is_tributacion_conjunta_rectificacion` | Liquidación IV - Rectificativa - Devolución acordada por la Agencia Tributaria … [01585] | money | Reused: rectificative return (second territorial split) |
| 01587 | `is_tributacion_conjunta_resultado` | Liquidación IV - Resultado de la autoliquidación - D. Forales/Navarra | money | Reused: final self-assessment result for Foral/Navarra |
| 01608 | `is_tributacion_conjunta_rectificacion` | Tributación conjunta … Rectificativa: Resultado a ingresar … [01608] | money | Reused: rectificative amount to pay |
| 01609 | `is_tributacion_conjunta_rectificacion` | Tributación conjunta … Rectificativa: Resultado a ingresar … [01609] | money | Reused |
| 01610 | `is_tributacion_conjunta_rectificacion` | Tributación conjunta … Rectificativa: Resultado a ingresar … [01610] | money | Reused |
| 01612 | `is_tributacion_conjunta_rectificacion` | Tributación conjunta … Rectificativa: Devolución acordada … [01612] | money | Reused |
| 01613 | `is_tributacion_conjunta_rectificacion` | Tributación conjunta … Rectificativa: Devolución acordada … [01613] | money | Reused |
| 01625 | `is_tributacion_conjunta_resultado` | Tributación conjunta … Resultado de la autoliquidación - Gipuzkoa | money | Reused: final self-assessment result Gipuzkoa |
| 01630 | `is_tributacion_conjunta_resultado` | Tributación conjunta … Resultado de la autoliquidación - Navarra | money | Reused: Navarra |
| 01632 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - Importe integrado - Gipuzkoa | money | New: integrated amount in the first instalment (Gipuzkoa) |
| 01633 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - Importe integrado - Bizkaia | money | New: Bizkaia |
| 01634 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - Importe integrado - Navarra | money | New: Navarra |
| 01635 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - Deuda tributaria - Araba/Álava | money | New: tax debt under instalment option (Araba/Álava) |
| 01636 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - Deuda tributaria - Gipuzkoa | money | New: Gipuzkoa |
| 01637 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - Deuda tributaria - Bizkaia | money | New: Bizkaia |
| 01641 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - Deuda tributaria - Navarra | money | New: Navarra |
| 01642 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - 1º fraccionamiento - Araba/Álava | money | New: 1st instalment amount (Araba/Álava) |
| 01643 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - 1º fraccionamiento - Gipuzkoa | money | New: Gipuzkoa |
| 01644 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - 1º fraccionamiento - Bizkaia | money | New: Bizkaia |
| 01645 | `is_tributacion_conjunta_fraccionamiento_importe` | Tributación conjunta … Opción de fraccionamiento art. 19.1 LIS - 1º fraccionamiento - Navarra | money | New: Navarra |
| 01647 | `is_tributacion_conjunta_fraccionamiento_resultado` | Tributación conjunta … Resultado de la autoliquidación incluido el 1º fraccionamiento - Gipuzkoa | money | New: self-assessment result incl. 1st instalment (Gipuzkoa) |
| 01648 | `is_tributacion_conjunta_fraccionamiento_resultado` | Tributación conjunta … Resultado de la autoliquidación incluido el 1º fraccionamiento - Bizkaia | money | New: Bizkaia |
| 01649 | `is_tributacion_conjunta_fraccionamiento_resultado` | Tributación conjunta … Resultado de la autoliquidación incluido el 1º fraccionamiento - Navarra | money | New: Navarra |
| 01651 | `is_tributacion_conjunta_fraccionamiento_resultado` | Tributación conjunta … Rectificativa: Resultado de la autoliquidación incluido el 1er fraccionamiento [01651] | money | New: rectificative result incl. 1st instalment |
| 01652 | `is_tributacion_conjunta_fraccionamiento_resultado` | Tributación conjunta … Rectificativa: Resultado … [01652] | money | New |
| 01653 | `is_tributacion_conjunta_fraccionamiento_resultado` | Tributación conjunta … Rectificativa: Resultado … [01653] | money | New |
| 01655 | `is_tributacion_conjunta_fraccionamiento_resultado` | Tributación conjunta … Resultado incluido en el 1er fraccionamiento de art. 19.1 LIS - Gipuzkoa | money | New: amount included in 1st instalment (Gipuzkoa) |
| 01656 | `is_tributacion_conjunta_fraccionamiento_resultado` | Tributación conjunta … Resultado incluido en el 1er fraccionamiento … Bizkaia | money | New |
| 01657 | `is_tributacion_conjunta_fraccionamiento_resultado` | Tributación conjunta … Resultado incluido en el 1er fraccionamiento … Navarra | money | New |
| 01659 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01659] | money | Reused: AID conversion (additional foral split rows) |
| 01660 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01660] | money | Reused |
| 01661 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01661] | money | Reused |
| 01662 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01662] | money | Reused |
| 01663 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01663] | money | Reused |
| 01664 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01664] | money | Reused |
| 01665 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01665] | money | Reused |
| 01666 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01666] | money | Reused |
| 01667 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01667] | money | Reused |
| 01668 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01668] | money | Reused |
| 01669 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01669] | money | Reused |
| 01670 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01670] | money | Reused |
| 01671 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01671] | money | Reused |
| 01672 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01672] | money | Reused |
| 01673 | `is_conversion_aid_importe` | Tributación conjunta … Conversión de activos por impuesto diferido … [01673] | money | Reused |
| 01765 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Exención sobre dividendos o participaciones | money | Reused: art.21 LIS dividend exemption reduction |
| 01785 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por rendimientos del capital mobiliario - Efe | money | Reused: withholding on capital income (effective amount) |
| 01786 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por rendimientos del capital mobiliario - Imp | money | Reused: withholding on capital income (imputed amount) |
| 01787 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por arrendamientos de inmuebles urbanos - Efe | money | Reused: withholding on urban property rent (effective) |
| 01788 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por arrendamientos de inmuebles urbanos - Imp | money | Reused: withholding on urban property rent (imputed) |
| 01789 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por rendimientos del capital mobiliario atrib | money | Reused: capital-income withholding via attribution-of-income entity (effective) |
| 01790 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por rendimientos del capital mobiliario atrib | money | Reused: (imputed) |
| 01791 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por arrendamientos de inmuebles urbanos atrib | money | Reused: property-rent withholding via attribution entity (effective) |
| 01792 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por arrendamientos de inmuebles urbanos atrib | money | Reused: (imputed) |
| 01793 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por otros conceptos diferentes a los rendimie | money | Reused: withholding on other concepts (effective) |
| 01794 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por otros conceptos diferentes a los rendimie | money | Reused: (imputed) |
| 01795 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones e ingresos a cuenta participaciones IIC - Efe | money | Reused: CIV participations withholding (effective) |
| 01796 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones e ingresos a cuenta participaciones IIC - Imp | money | Reused: CIV participations withholding (imputed) |
| 01797 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones sobre los premios de determinadas loterías y | money | Reused: lottery prize withholding |
| 01798 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por otros conceptos NO incluidos en las casil | money | Reused: other withholdings not listed in preceding casillas (effective) |
| 01799 | `is_retenciones_ingresos_a_cuenta` | Liquidación IV - Cuota del ejercicio … Retenciones por otros conceptos NO incluidos en las casil | money | Reused: (imputed) |
| 01808 | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones … Disminución de valor originada por criterio d | money | Reused: value decrease from accounting criterion change |
| 01811 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Pérdidas por deterioro de valores repr. de pa | money | Reused: impairment losses on equity instruments increase |
| 01812 | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones … Disminución de valor originada por criterio d | money | Reused: value decrease (second row of same category) |
| 01813 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Deuda tributaria de actos jurídicos documenta | money | Reused: stamp-duty tax debt correction (art.15c LIS) increase |
| 01814 | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones … Deuda tributaria de actos jurídicos documenta | money | Reused: decrease |
| 01815 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Multas, sanciones y otros (art. 15 c) LIS) | money | Reused: fines & penalties non-deductible correction |
| 01816 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Gastos de actuaciones contrarias al ordenamie | money | Reused: expenses contrary to legal order (art.15e LIS) |
| 01817 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Gastos derivados de la extinción de la relaci | money | Reused: termination-related expenses exceeding statutory limit |
| 01818 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Operaciones de aumento de capital o fondos pr | money | Reused: capital-increase operations correction increase |
| 01819 | `is_correcciones_disminuciones` | Liquidación I - Detalle correcciones … Operaciones de aumento de capital o fondos pr | money | Reused: decrease |
| 01824 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Rentas procedentes de transmisión de inmovil | money | Reused: immovable-asset transfer income reduction |
| 01878 | `is_tributacion_conjunta_abono_cinematografica` | Tributación conjunta … Abono deducciones producciones extranjeras en Canarias - Gipuzkoa | money | New: Canarias foreign-production deduction credit (Gipuzkoa) |
| 01879 | `is_tributacion_conjunta_abono_cinematografica` | Tributación conjunta … Abono deducciones producciones extranjeras en Canarias - Bizkaia | money | New: Bizkaia |
| 01880 | `is_tributacion_conjunta_abono_cinematografica` | Tributación conjunta … Abono deducciones producciones extranjeras en Canarias - Navarra | money | New: Navarra |
| 01893 | `is_deduccion_cinematografica_extranjera_periodo` | Liquidación IV - Resultado de la autoliquidación - Abono de deducciones por producciones cinematográficas extranjeras en | money | Reused: Canarias variant of cinema foreign-production deduction |
| 01906 | `is_correcciones_aumentos` | Liquidación II - Detalle correcciones … XXXVII Copa América Barcelona (Ley 31/2022) | money | Reused: Copa América special event correction |
| 02182 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Exención sobre la renta obtenida en la trans | money | Reused: art.21 LIS exemption on asset-disposal income (decrease) |
| 02183 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Exención sobre la renta obtenida en la trans | money | Reused |
| 02184 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Exención sobre la renta obtenida en la trans | money | Reused |
| 02185 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Exención sobre la renta obtenida en la trans | money | Reused |
| 02186 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Exención sobre la renta obtenida en los supu | money | Reused: art.21 LIS exemption (partial cases) |
| 02187 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Exención sobre la renta obtenida en los supu | money | Reused |
| 02188 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Exención sobre la renta obtenida en los supu | money | Reused |
| 02189 | `is_correcciones_disminuciones` | Liquidación II - Detalle correcciones … Exención sobre la renta obtenida en los supu | money | Reused |
| 02315 | `is_deduccion_inversion_autoridades_portuarias` | Liquidación IV - Otras deducciones - Deducción por inversiones y gastos realizados por las autoridades portuarias | money | New: port authority investment deduction art.38 bis LIS |
| 02379 | `is_tributacion_conjunta_discrepancia` | Tributación conjunta … Discrepancia de criterio administrativo para determinados supuestos de autol | money | New: administrative-criterion discrepancy (self-assessment adjustment) |
| 02408 | `is_tributacion_conjunta_discrepancia` | Tributación conjunta … Discrepancia de criterio administrativo … [02408] | money | New: second territorial split |
| 02470 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Asimetrías híbridas (art. 15 bis LIS, excepto | money | Reused: hybrid mismatches art.15 bis LIS correction |
| 02481 | `is_fraccionamiento_cambio_residencia_deuda` | Liquidación IV - Opción de fraccionamiento … Deuda tributaria resu [02481] | money | New: exit-tax debt under instalment option |
| 02482 | `is_fraccionamiento_cambio_residencia_deuda` | Liquidación IV - Opción de fraccionamiento … Deuda tributaria resu [02482] | money | New: second split |
| 02483 | `is_fraccionamiento_cambio_residencia_deuda` | Liquidación IV - Opción de fraccionamiento … 1er fraccionamiento [02483] | money | New: 1st instalment amount |
| 02484 | `is_fraccionamiento_cambio_residencia_deuda` | Liquidación IV - Opción de fraccionamiento … 1er fraccionamiento [02484] | money | New |
| 02485 | `is_fraccionamiento_cambio_residencia_resultado` | Liquidación IV - Opción de fraccionamiento … Resultado de la autol [02485] | money | New: self-assessment result under exit-tax instalment |
| 02486 | `is_fraccionamiento_cambio_residencia_resultado` | Liquidación IV - Opción de fraccionamiento … Resultado de la autol [02486] | money | New |
| 02487 | `is_fraccionamiento_cambio_residencia_resultado` | Liquidación IV - Opción de fraccionamiento … Rectificativa - Resul [02487] | money | New: rectificative result under exit-tax instalment |
| 02488 | `is_fraccionamiento_cambio_residencia_resultado` | Liquidación IV - Opción de fraccionamiento … Rectificativa - Resul [02488] | money | New |
| 02489 | `is_fraccionamiento_cambio_residencia_resultado` | Liquidación IV - Opción de fraccionamiento … Resultado incluido el [02489] | money | New: amount included in 1st instalment |
| 02920 | `is_correcciones_aumentos` | Liquidación I - Detalle correcciones … Ajustes por deterioro de valores repr. de par | money | Reused: equity-instrument impairment adjustment increase |

## Data_type divergences

All 116 casillas in this cluster carry `data_type = money`. No divergences detected.

## Summary

- Total casillas classified: 116
- Roles reused verbatim from existing-roles.txt: 16 distinct roles, covering 88 casillas
- New roles introduced: 13
  - `is_correcciones_resultado_contable_impuesto`
  - `is_consolidacion_fiscal_eliminacion`
  - `is_consolidacion_fiscal_integracion`
  - `is_cooperativa_cuota_integra_previa`
  - `is_cooperativa_reserva_nivelacion_cuota`
  - `is_cooperativa_reversion_deterioro`
  - `is_naviera_base_imponible_foral`
  - `is_deduccion_inversion_autoridades_portuarias`
  - `is_fraccionamiento_cambio_residencia_deuda`
  - `is_fraccionamiento_cambio_residencia_resultado`
  - `is_tributacion_conjunta_abono_idi`
  - `is_tributacion_conjunta_abono_cinematografica`
  - `is_tributacion_conjunta_fraccionamiento_importe`
  - `is_tributacion_conjunta_fraccionamiento_resultado`
  - `is_tributacion_conjunta_discrepancia`
- Data_type divergences: 0 (all casillas are `money`)
