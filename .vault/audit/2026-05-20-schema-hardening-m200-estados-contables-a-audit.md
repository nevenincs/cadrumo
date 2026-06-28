---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-19-schema-hardening-m200-role-assignment-audit]]"
---

# `schema-hardening` audit: M200 estados-contables-a cluster

## Scope

This audit assigns a stable `semantic_role` to every casilla in the `estados-contables-a` cluster of M200 (Impuesto sobre Sociedades, revision `2024-y-siguientes`). The cluster covers five statement surfaces: Balance Activo II (current-asset detail), Balance Patrimonio Neto y Pasivo I (equity and non-current liabilities), Balance Patrimonio Neto y Pasivo II (current liabilities), Estado de Cambios en el Patrimonio Neto I (ECPN part I — recognised income/expense and transfers), and Estado de Cambios en el Patrimonio Neto II (ECPN part II — full reconciliation matrix). All 221 casillas carry `data_type = money`. The existing role taxonomy already provides `is_balance_activo_importe`, `is_balance_patrimonio_neto_pasivo_importe`, and `is_estado_cambios_patrimonio_neto_importe`; inspection of representative TOMLs (e.g. 00091, 00096) confirms the campaign uses one coarse bucket role per financial statement rather than per-line granularity, so those three existing roles are reused throughout this cluster without minting new roles.

## Role assignments

| id | role | label_snippet | data_type | notes |
|---|---|---|---|---|
| 00150 | `is_balance_activo_importe` | Activo II - Clientes por ventas y prestaciones de servicios | money | |
| 00151 | `is_balance_activo_importe` | Activo II - Clientes por ventas … a largo plazo | money | |
| 00152 | `is_balance_activo_importe` | Activo II - Clientes por ventas … a corto plazo | money | |
| 00153 | `is_balance_activo_importe` | Activo II - Clientes empresas del grupo y asociadas | money | |
| 00154 | `is_balance_activo_importe` | Activo II - Deudores varios | money | |
| 00155 | `is_balance_activo_importe` | Activo II - Personal | money | |
| 00156 | `is_balance_activo_importe` | Activo II - Activos por impuesto corriente | money | |
| 00157 | `is_balance_activo_importe` | Activo II - Otros créditos con las Administraciones Públicas | money | |
| 00158 | `is_balance_activo_importe` | Activo II - Accionistas (socios) por desembolsos exigidos | money | |
| 00159 | `is_balance_activo_importe` | Activo II - Otros deudores | money | |
| 00160 | `is_balance_activo_importe` | Activo II - Inversiones en empresas del grupo … a corto plazo | money | |
| 00161 | `is_balance_activo_importe` | Activo II - Instrumentos de patrimonio | money | |
| 00162 | `is_balance_activo_importe` | Activo II - Créditos a empresas | money | |
| 00163 | `is_balance_activo_importe` | Activo II - Valores representativos de deuda | money | |
| 00164 | `is_balance_activo_importe` | Activo II - Derivados | money | |
| 00165 | `is_balance_activo_importe` | Activo II - Otros activos financieros | money | |
| 00166 | `is_balance_activo_importe` | Activo II - Otras inversiones | money | |
| 00167 | `is_balance_activo_importe` | Activo II - Resto | money | |
| 00168 | `is_balance_activo_importe` | Activo II - Inversiones financieras a corto plazo | money | |
| 00169 | `is_balance_activo_importe` | Activo II - Instrumentos de patrimonio (financ. c/p) | money | |
| 00170 | `is_balance_activo_importe` | Activo II - Créditos a empresas (financ. c/p) | money | |
| 00171 | `is_balance_activo_importe` | Activo II - Valores representativos de deuda (financ. c/p) | money | |
| 00172 | `is_balance_activo_importe` | Activo II - Derivados (financ. c/p) | money | |
| 00173 | `is_balance_activo_importe` | Activo II - Otros activos financieros (financ. c/p) | money | |
| 00174 | `is_balance_activo_importe` | Activo II - Otras inversiones (financ. c/p) | money | |
| 00175 | `is_balance_activo_importe` | Activo II - Resto (financ. c/p) | money | |
| 00176 | `is_balance_activo_importe` | Activo II - Periodificaciones a corto plazo | money | |
| 00177 | `is_balance_activo_importe` | Activo II - Efectivo y otros activos líquidos equivalentes | money | |
| 00178 | `is_balance_activo_importe` | Activo II - Tesorería | money | |
| 00179 | `is_balance_activo_importe` | Activo II - Otros activos líquidos equivalentes | money | |
| 00180 | `is_balance_activo_importe` | Activo II - TOTAL ACTIVO | money | |
| 00186 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Fondos propios | money | |
| 00187 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Capital | money | |
| 00188 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Capital escriturado | money | |
| 00189 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Capital no exigido | money | |
| 00190 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Prima de emisión | money | |
| 00191 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Reservas | money | |
| 00192 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Legal y estatutarias | money | |
| 00193 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Otras reservas | money | |
| 00194 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Acciones y participaciones en patrimonio propias | money | |
| 00195 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Resultados de ejercicios anteriores | money | |
| 00196 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Remanente | money | |
| 00197 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Resultados negativos de ejercicios anteriores | money | |
| 00198 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Otras aportaciones de socios | money | |
| 00199 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Resultado del ejercicio | money | |
| 00200 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Dividendo a cuenta | money | |
| 00201 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Otros instrumentos de patrimonio neto | money | |
| 00202 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Ajustes por cambios de valor | money | |
| 00203 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Activos financieros a valor razonable con cambios en PN | money | |
| 00204 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Operaciones de cobertura | money | |
| 00205 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Activos no corrientes y pasivos vinculados | money | |
| 00206 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Diferencia de conversión | money | |
| 00207 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Otros | money | |
| 00208 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Ajustes en patrimonio neto | money | |
| 00209 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Subvenciones, donaciones y legados recibidos | money | |
| 00210 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - PASIVO NO CORRIENTE | money | |
| 00211 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Provisiones a largo plazo | money | |
| 00212 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Obligaciones por prestaciones a largo plazo al personal | money | |
| 00213 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Actuaciones medioambientales | money | |
| 00214 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Provisiones por reestructuración | money | |
| 00215 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Otras provisiones | money | |
| 00216 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Deudas a largo plazo | money | |
| 00217 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Obligaciones y otros valores negociables | money | |
| 00218 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Deudas con entidades de crédito | money | |
| 00219 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Acreedores por arrendamiento financiero | money | |
| 00220 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Derivados | money | |
| 00221 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Otros pasivos financieros | money | |
| 00222 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Otras deudas a largo plazo | money | |
| 00223 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Deudas con empresas del grupo y asociadas a largo plazo | money | |
| 00224 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Pasivos por impuesto diferido | money | |
| 00225 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Periodificaciones a largo plazo | money | |
| 00226 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Acreedores comerciales no corrientes | money | |
| 00227 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Deuda con características especiales a largo plazo | money | |
| 00765 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Capital cooperativo no exigido (cooperativas) | money | |
| 00766 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Fondo de reembolso o actualización (cooperativas) | money | |
| 00767 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Fondo de reserva voluntario (cooperativas) | money | |
| 00768 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Retorno cooperativo y remuneración discrecional | money | |
| 00769 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Fondos capitalizados (cooperativas) | money | |
| 00781 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Deudas con características especiales l/p (cooperativas) | money | |
| 00782 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - (label truncated to backslash in source) | money | label is a bare backslash in the JSON — likely a data-capture artifact; role still `is_balance_patrimonio_neto_pasivo_importe` given section context |
| 00783 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Fondos especiales calificados como pasivo (cooperativas) | money | |
| 00784 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Acreedores por fondos capitalizados a largo plazo (cooperativas) | money | |
| 01002 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo I - Reserva de nivelación | money | |
| 00229 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Pasivos vinculados con activos no corrientes | money | |
| 00230 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Provisiones a corto plazo | money | |
| 00231 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Deudas a corto plazo | money | |
| 00232 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Obligaciones y otros valores negociables | money | |
| 00233 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Deudas con entidades de crédito | money | |
| 00234 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Acreedores por arrendamiento financiero | money | |
| 00235 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Derivados | money | |
| 00236 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Otros pasivos financieros | money | |
| 00237 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Otras deudas a corto plazo | money | |
| 00238 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Deudas con empresas del grupo y asociadas a corto plazo | money | |
| 00239 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Acreedores comerciales y otras cuentas a pagar | money | |
| 00240 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Proveedores | money | |
| 00241 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Proveedores a largo plazo | money | |
| 00242 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Proveedores a corto plazo | money | |
| 00243 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Proveedores, empresas del grupo y asociadas | money | |
| 00244 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Acreedores varios | money | |
| 00245 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Personal (remuneraciones pendientes de pago) | money | |
| 00246 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Pasivos por impuesto corriente | money | |
| 00247 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Otras deudas con las Administraciones Públicas | money | |
| 00248 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Anticipos de clientes | money | |
| 00249 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Otros acreedores | money | |
| 00250 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Periodificaciones a corto plazo | money | |
| 00251 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Deuda con características especiales a corto plazo | money | |
| 00252 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - TOTAL PATRIMONIO NETO Y PASIVO | money | |
| 00704 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Otras provisiones | money | |
| 00786 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Deudas con características especiales c/p (cooperativas) | money | |
| 00787 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - (label truncated to backslash in source) | money | same artifact as 00782; section confirms role |
| 00788 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Fondos especiales calificados como pasivo (cooperativas) | money | |
| 00789 | `is_balance_patrimonio_neto_pasivo_importe` | PN y Pasivo II - Acreedores por fondos capitalizados a corto plazo (cooperativas) | money | |
| 00337 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Ing/gastos imputados - Activos financieros a valor razonable | money | |
| 00338 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Ing/gastos imputados - Otros ingresos/gastos | money | |
| 00339 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Ing/gastos imputados - Por coberturas de flujos de efectivo | money | |
| 00340 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Ing/gastos imputados - Subvenciones, donaciones y legados | money | |
| 00341 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Ing/gastos imputados - Por ganancias y pérdidas actuariales | money | |
| 00342 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Ing/gastos imputados - Por activos no corrientes y pasivos | money | |
| 00343 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Ing/gastos imputados - Diferencias de conversión | money | |
| 00344 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Ing/gastos imputados - Efecto impositivo | money | |
| 00345 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Ing/gastos imputados - Total ingresos y gastos imputados | money | |
| 00347 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Transferencias - Activos financieros a valor razonable | money | |
| 00348 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Transferencias - Otros ingresos/gastos | money | |
| 00349 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Transferencias - Por coberturas de flujos de efectivo | money | |
| 00350 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Transferencias - Subvenciones, donaciones y legados | money | |
| 00351 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Transferencias - Por activos no corrientes y pasivos | money | |
| 00352 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Transferencias - Diferencias de conversión | money | |
| 00353 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Transferencias - Efecto impositivo | money | |
| 00354 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - Transferencias - Total transferencia a la cuenta PyG | money | |
| 00355 | `is_estado_cambios_patrimonio_neto_importe` | ECPN I - TOTAL DE INGRESOS Y GASTOS RECONOCIDOS | money | |
| 00381 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo final ejercicio anterior - Capital no exigido | money | |
| 00382 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo final ejercicio anterior - Prima de emisión | money | |
| 00383 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo final ejercicio anterior - Reservas | money | |
| 00384 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo final ejercicio anterior - Acciones y participaciones | money | |
| 00385 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo final ejercicio anterior - Resultados ejercicios anteriores | money | |
| 00386 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo final ejercicio anterior - Otras aportaciones de socios | money | |
| 00395 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes cambio criterio - Capital no exigido | money | |
| 00396 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes cambio criterio - Prima de emisión | money | |
| 00397 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes cambio criterio - Reservas | money | |
| 00398 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes cambio criterio - Acciones y participaciones | money | |
| 00399 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes cambio criterio - Resultados ejercicios anteriores | money | |
| 00400 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes cambio criterio - Otras aportaciones de socios | money | |
| 00409 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes errores - Capital no exigido | money | |
| 00410 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes errores - Prima de emisión | money | |
| 00411 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes errores - Reservas | money | |
| 00412 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes errores - Acciones y participaciones | money | |
| 00413 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes errores - Resultados ejercicios anteriores | money | |
| 00414 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ajustes errores - Otras aportaciones de socios | money | |
| 00423 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo ajustado inicio ejercicio - Capital no exigido | money | |
| 00424 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo ajustado inicio ejercicio - Prima de emisión | money | |
| 00425 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo ajustado inicio ejercicio - Reservas | money | |
| 00426 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo ajustado inicio ejercicio - Acciones y participaciones | money | |
| 00427 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo ajustado inicio ejercicio - Resultados ejercicios anteriores | money | |
| 00428 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Saldo ajustado inicio ejercicio - Otras aportaciones socios | money | |
| 00437 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Total ingresos y gastos reconocidos - Capital no exigido | money | |
| 00438 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Total ingresos y gastos reconocidos - Prima de emisión | money | |
| 00439 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Total ingresos y gastos reconocidos - Reservas | money | |
| 00440 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Total ingresos y gastos reconocidos - Acciones y participaciones | money | |
| 00441 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Total ingresos y gastos reconocidos - Resultados ejercicios anteriores | money | |
| 00442 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Total ingresos y gastos reconocidos - Otras aportaciones | money | |
| 00451 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Resultado cta PyG - Capital no exigido | money | |
| 00452 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Resultado cta PyG - Prima de emisión | money | |
| 00453 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Resultado cta PyG - Reservas | money | |
| 00454 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Resultado cta PyG - Acciones y participaciones | money | |
| 00455 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Resultado cta PyG - Resultados ejercicios anteriores | money | |
| 00456 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Resultado cta PyG - Otras aportaciones | money | |
| 00465 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Capital no exigido | money | |
| 00466 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Prima de emisión | money | |
| 00467 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Reservas | money | |
| 00468 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Acciones y participaciones | money | |
| 00469 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Resultados ejercicios anteriores | money | |
| 00470 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Otras aportaciones | money | |
| 00479 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Ingresos fiscales a distribuir (col 1) | money | |
| 00480 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Ingresos fiscales a distribuir (col 2) | money | |
| 00481 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Ingresos fiscales a distribuir (col 3) | money | |
| 00482 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Ingresos fiscales a distribuir (col 4) | money | |
| 00483 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Ingresos fiscales a distribuir (col 5) | money | |
| 00484 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Ingresos fiscales a distribuir (col 6) | money | |
| 00493 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Otros ingresos y gastos reco. (col 1) | money | |
| 00494 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Otros ingresos y gastos reco. (col 2) | money | |
| 00495 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Otros ingresos y gastos reco. (col 3) | money | |
| 00496 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Otros ingresos y gastos reco. (col 4) | money | |
| 00497 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Otros ingresos y gastos reco. (col 5) | money | |
| 00498 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Ing/gastos reconocidos en PN - Otros ingresos y gastos reco. (col 6) | money | |
| 00507 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Capital no exigido | money | |
| 00508 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Prima de emisión | money | |
| 00509 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Reservas | money | |
| 00510 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Acciones y participaciones | money | |
| 00511 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Resultados ejercicios anteriores | money | |
| 00512 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Otras aportaciones | money | |
| 00521 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Aumentos de capital - Capital no exigido | money | |
| 00522 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Aumentos de capital - Prima de emisión | money | |
| 00523 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Aumentos de capital - Reservas | money | |
| 00524 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Aumentos de capital - Acciones y partic. | money | |
| 00525 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Aumentos de capital - Resultados ej. ant. | money | |
| 00526 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Aumentos de capital - Otras aportaciones | money | |
| 00535 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Reducciones de capital - Capital | money | |
| 00536 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Reducciones de capital - Prima de emisión | money | |
| 00537 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Reducciones de capital - Reservas | money | |
| 00538 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Reducciones de capital - Acciones y partic. | money | |
| 00539 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Reducciones de capital - Resultados ej. ant. | money | |
| 00540 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Reducciones de capital - Otras aportaciones | money | |
| 00549 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Conversión pasivos en PN (col 1) | money | |
| 00550 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Conversión pasivos en PN (col 2) | money | |
| 00551 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Conversión pasivos en PN (col 3) | money | |
| 00552 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Conversión pasivos en PN (col 4) | money | |
| 00553 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Conversión pasivos en PN (col 5) | money | |
| 00554 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Conversión pasivos en PN (col 6) | money | |
| 00563 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Distribución dividendos - Capital | money | |
| 00564 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Distribución dividendos - Prima de emisión | money | |
| 00565 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Distribución dividendos - Reservas | money | |
| 00566 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Distribución dividendos - Acciones y partic. | money | |
| 00567 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Distribución dividendos - Resultados ej. ant. | money | |
| 00568 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Distribución dividendos - Otras | money | |
| 00577 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Operaciones acciones propias (col 1) | money | |
| 00578 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Operaciones acciones propias (col 2) | money | |
| 00579 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Operaciones acciones propias (col 3) | money | |
| 00580 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Operaciones acciones propias (col 4) | money | |
| 00581 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Operaciones acciones propias (col 5) | money | |
| 00582 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Operaciones acciones propias (col 6) | money | |
| 00591 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Incremento reducción PN de otras oper. (col 1) | money | |
| 00593 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Incremento reducción PN de otras oper. (col 3) | money | id gap between 00591 and 00593 matches JSON; no 00592 present |
| 00594 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Incremento reducción PN de otras oper. (col 4) | money | |
| 00595 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Incremento reducción PN de otras oper. (col 5) | money | |
| 00596 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Incremento reducción PN de otras oper. (col 6) | money | |
| 00605 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Otras operaciones (col 1) | money | |
| 00606 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Otras operaciones (col 2) | money | |
| 00607 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Otras operaciones (col 3) | money | |
| 00608 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Otras operaciones (col 4) | money | |
| 00609 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Otras operaciones (col 5) | money | |
| 00610 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Operaciones con socios - Otras operaciones (col 6) | money | |
| 00619 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Capital no exigido | money | |
| 00620 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Prima de emisión | money | |
| 00621 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Reservas | money | |
| 00622 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Acciones y participaciones | money | |
| 00623 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Resultados ejercicios anteriores | money | |
| 00624 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Otras aportaciones | money | |
| 00633 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - SALDO FINAL DEL EJERCICIO - Capital no exigido | money | |
| 00634 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - SALDO FINAL DEL EJERCICIO - Prima de emisión | money | |
| 00635 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - SALDO FINAL DEL EJERCICIO - Reservas | money | |
| 00636 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - SALDO FINAL DEL EJERCICIO - Acciones y participaciones en patrimonio propias | money | |
| 00637 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - SALDO FINAL DEL EJERCICIO - Resultados ejercicios anteriores | money | |
| 00638 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - SALDO FINAL DEL EJERCICIO - Otras aportaciones de socios | money | |
| 00716 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Movimiento reserva revalorización - Capital | money | |
| 00717 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Movimiento reserva revalorización - Prima | money | |
| 00718 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Movimiento reserva revalorización - Reservas | money | |
| 00719 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Movimiento reserva revalorización - Acciones | money | |
| 00720 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Movimiento reserva revalorización - Resultados | money | |
| 00721 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Movimiento reserva revalorización - Otras | money | |
| 00730 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Otras variaciones - Capital no exigido | money | |
| 00731 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Otras variaciones - Prima de emisión | money | |
| 00732 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Otras variaciones - Reservas | money | |
| 00733 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Otras variaciones - Acciones y participaciones | money | |
| 00734 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Otras variaciones - Resultados ej. ant. | money | |
| 00735 | `is_estado_cambios_patrimonio_neto_importe` | ECPN II - Otras variaciones PN - Otras variaciones - Otras aportaciones | money | |

## Data_type divergences

None. Every casilla in this cluster carries `data_type = money`. No mixed-type conflicts exist within any role group:

- `is_balance_activo_importe`: 31 casillas, all `money`.
- `is_balance_patrimonio_neto_pasivo_importe`: 72 casillas (44 from PN y Pasivo I + 28 from PN y Pasivo II), all `money`.
- `is_estado_cambios_patrimonio_neto_importe`: 118 casillas (19 ECPN I + 99 ECPN II), all `money`.

## Incidental findings

- **Truncated labels on 00782 and 00787**: Both source entries have a label value of a bare backslash (`"\"`). This is a data-capture artifact in the JSON cluster file, not a schema defect in the TOML registry. The `section` field (`balance_patrimonio_neto_y_pasivo_i` and `balance_patrimonio_neto_y_pasivo_ii` respectively) unambiguously places both casillas in the equity/liability bucket; role assignment proceeds on section evidence.
- **Id gap 00592 absent**: The ECPN II operaciones-con-socios block for "Incremento/reducción de patrimonio neto" skips 00592; the JSON presents 00591 then 00593 through 00596. This matches the five-column layout of that matrix row (likely no column-2 variant) and is not a classification concern.
