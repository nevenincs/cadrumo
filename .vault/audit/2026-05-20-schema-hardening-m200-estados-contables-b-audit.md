---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# schema-hardening audit: M200 estados-contables-b role assignment

## Scope

Cluster: **estados-contables-b** — company financial-statement line items:
balance sheet (Activo), balance sheet (Patrimonio neto y pasivo), profit-and-loss
statement (Cuenta de pérdidas y ganancias I and II), and statement of changes in
equity (Estado de cambios del patrimonio neto III).

All casillas in this cluster carry `data_type = money`. No divergences.

Granularity follows the established coarse-bucket convention already used in the
K-estados_financieros family of the prior M200 role-assignment audit: one role
per top-level financial statement rather than per line item. This is consistent
with how `is_balance_activo_importe`, `is_balance_patrimonio_neto_pasivo_importe`,
`is_cuenta_perdidas_ganancias_importe`, and `is_estado_cambios_patrimonio_neto_importe`
are applied throughout the M200 registry TOMLs already on disk.

## Role assignments

| id | role | label_snippet | data_type | notes |
|----|------|---------------|-----------|-------|
| 00388 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo final ej. anterior - Dividendo a cuenta | money | reused |
| 00389 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo final ej. anterior - Otros instrumentos | money | reused |
| 00390 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo final ej. anterior - Ajustes cambios valor | money | reused |
| 00391 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo final ej. anterior - Ajustes patrimonio neto | money | reused |
| 00392 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo final ej. anterior - Subvenciones | money | reused |
| 00393 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo final ej. anterior - Total | money | reused |
| 00402 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes cambio criterio - Dividendo a cuenta | money | reused |
| 00403 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes cambio criterio - Otros instrumentos | money | reused |
| 00404 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes cambio criterio - Ajustes cambios valor | money | reused |
| 00405 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes cambio criterio - Ajustes patrimonio neto | money | reused |
| 00406 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes cambio criterio - Subvenciones | money | reused |
| 00407 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes cambio criterio - Total | money | reused |
| 00416 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes errores ej. anteriores - Dividendo a cuenta | money | reused |
| 00417 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes errores ej. anteriores - Otros instrumentos | money | reused |
| 00418 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes errores ej. anteriores - Ajustes cambios valor | money | reused |
| 00419 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes errores ej. anteriores - Ajustes patrimonio neto | money | reused |
| 00420 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes errores ej. anteriores - Subvenciones | money | reused |
| 00421 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ajustes errores ej. anteriores - Total | money | reused |
| 00430 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo ajustado inicio ejercicio - Dividendo a cuenta | money | reused |
| 00431 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo ajustado inicio ejercicio - Otros instrumentos | money | reused |
| 00432 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo ajustado inicio ejercicio - Ajustes cambios valor | money | reused |
| 00433 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo ajustado inicio ejercicio - Ajustes patrimonio neto | money | reused |
| 00434 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo ajustado inicio ejercicio - Subvenciones | money | reused |
| 00435 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Saldo ajustado inicio ejercicio - Total | money | reused |
| 00444 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Total ingresos y gastos reconocidos - Dividendo a cuenta | money | reused |
| 00445 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Total ingresos y gastos reconocidos - Otros instrumentos | money | reused |
| 00446 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Total ingresos y gastos reconocidos - Ajustes cambios valor | money | reused |
| 00449 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Total ingresos y gastos reconocidos - Total | money | reused |
| 00458 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Resultado cta. PyG - Dividendo a cuenta | money | reused |
| 00462 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Resultado cta. PyG - Subvenciones | money | reused |
| 00463 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Resultado cta. PyG - Total | money | reused |
| 00472 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ingresos/gastos reconocidos en PN - Dividendo a cuenta | money | reused |
| 00476 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ingresos/gastos reconocidos en PN - Subvenciones | money | reused |
| 00477 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ingresos/gastos reconocidos en PN - Total | money | reused |
| 00486 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ingresos fiscales a distribuir - subgrupo A | money | reused |
| 00490 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ingresos fiscales a distribuir - subgrupo B | money | reused |
| 00491 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Ingresos fiscales a distribuir - subgrupo C | money | reused |
| 00503 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otros ingresos y gastos reconocidos - subgrupo A | money | reused |
| 00504 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otros ingresos y gastos reconocidos - subgrupo B | money | reused |
| 00505 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otros ingresos y gastos reconocidos - subgrupo C | money | reused |
| 00514 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Operaciones con socios - Dividendo a cuenta | money | reused |
| 00515 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Operaciones con socios - Otros instrumentos | money | reused |
| 00516 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Operaciones con socios - Ajustes cambios valor | money | reused |
| 00517 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Operaciones con socios - Ajustes patrimonio neto | money | reused |
| 00518 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Operaciones con socios - Subvenciones | money | reused |
| 00519 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Operaciones con socios - Total | money | reused |
| 00528 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Aumentos capital - Dividendo a cuenta | money | reused |
| 00529 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Aumentos capital - Otros instrumentos | money | reused |
| 00530 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Aumentos capital - Ajustes cambios valor | money | reused |
| 00531 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Aumentos capital - Ajustes patrimonio neto | money | reused |
| 00532 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Aumentos capital - Subvenciones | money | reused |
| 00533 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Aumentos capital - Total | money | reused |
| 00542 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - (-) Reducciones capital - Dividendo a cuenta | money | reused |
| 00543 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - (-) Reducciones capital - Otros instrumentos | money | reused |
| 00544 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - (-) Reducciones capital - Ajustes cambios valor | money | reused |
| 00545 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - (-) Reducciones capital - Ajustes PN | money | reused |
| 00546 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - (-) Reducciones capital - Subvenciones | money | reused |
| 00547 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - (-) Reducciones capital - Total | money | reused |
| 00556 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Conversión pasivos en PN - subgrupo A | money | reused |
| 00557 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Conversión pasivos en PN - subgrupo B | money | reused |
| 00558 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Conversión pasivos en PN - subgrupo C | money | reused |
| 00561 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Conversión pasivos en PN - Total | money | reused |
| 00570 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - (-) Distribución dividendos - Dividendo a cuenta | money | reused |
| 00571 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - (-) Distribución dividendos - Otros instrumentos | money | reused |
| 00572 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - (-) Distribución dividendos - Ajustes | money | reused |
| 00575 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - (-) Distribución dividendos - Total | money | reused |
| 00584 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Ops. acciones propias - subgrupo A | money | reused |
| 00585 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Ops. acciones propias - subgrupo B | money | reused |
| 00586 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Ops. acciones propias - subgrupo C | money | reused |
| 00589 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Ops. acciones propias - Total | money | reused |
| 00598 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Incremento/reducción PN - subgrupo A | money | reused |
| 00600 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Incremento/reducción PN - subgrupo B | money | reused |
| 00603 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Incremento/reducción PN - Total | money | reused |
| 00612 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Otras ops. socios - subgrupo A | money | reused |
| 00613 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Otras ops. socios - subgrupo B | money | reused |
| 00614 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Otras ops. socios - subgrupo C | money | reused |
| 00615 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Otras ops. socios - subgrupo D | money | reused |
| 00616 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Otras ops. socios - subgrupo E | money | reused |
| 00617 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Op. socios - Otras ops. socios - Total | money | reused |
| 00626 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Dividendo a cuenta | money | reused |
| 00627 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Otros instrumentos | money | reused |
| 00628 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Ajustes cambios valor | money | reused |
| 00629 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Ajustes patrimonio neto | money | reused |
| 00630 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Subvenciones | money | reused |
| 00631 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Total | money | reused |
| 00640 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - SALDO FINAL DEL EJERCICIO - Dividendo a cuenta | money | reused |
| 00641 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - SALDO FINAL DEL EJERCICIO - Otros instrumentos | money | reused |
| 00642 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - SALDO FINAL DEL EJERCICIO - Ajustes cambios valor | money | reused |
| 00643 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - SALDO FINAL DEL EJERCICIO - Ajustes patrimonio neto | money | reused |
| 00644 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - SALDO FINAL DEL EJERCICIO - Subvenciones | money | reused |
| 00645 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - SALDO FINAL DEL EJERCICIO - Total | money | reused |
| 00723 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Mov. reserva revalorización - Dividendo | money | reused |
| 00724 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Mov. reserva revalorización - Otros | money | reused |
| 00725 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Mov. reserva revalorización - Ajustes valor | money | reused |
| 00726 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Mov. reserva revalorización - Ajustes PN | money | reused |
| 00727 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Mov. reserva revalorización - Subvenciones | money | reused |
| 00728 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Mov. reserva revalorización - Total | money | reused |
| 00737 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Otras variaciones - Dividendo a cuenta | money | reused |
| 00738 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Otras variaciones - Otros instrumentos | money | reused |
| 00739 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Otras variaciones - Ajustes cambios valor | money | reused |
| 00740 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Otras variaciones - Ajustes PN | money | reused |
| 00741 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Otras variaciones - Subvenciones | money | reused |
| 00742 | `is_estado_cambios_patrimonio_neto_importe` | ECPN (III) - Otras variaciones PN - Otras variaciones - Total | money | reused |
| 00254 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Resto | money | reused |
| 00255 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Importe neto cifra negocios | money | reused |
| 00256 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Ventas | money | reused |
| 00257 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Prestaciones de servicios | money | reused |
| 00258 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Variación existencias productos | money | reused |
| 00259 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Trabajos realizados para activo | money | reused |
| 00260 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Aprovisionamientos | money | reused |
| 00261 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Consumo de mercaderías | money | reused |
| 00262 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Consumo materias primas | money | reused |
| 00263 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Trabajos realizados por otras empresas | money | reused |
| 00264 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Deterioro mercaderías/materias primas | money | reused |
| 00265 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Otros ingresos de explotación | money | reused |
| 00266 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Ingresos accesorios gestión corriente | money | reused |
| 00267 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Ingresos accesorios - subgrupo A | money | reused |
| 00268 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Ingresos accesorios - Resto | money | reused |
| 00269 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Subvenciones explotación | money | reused |
| 00270 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Gastos de personal | money | reused |
| 00271 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Sueldos y salarios | money | reused |
| 00274 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Seguridad Social a cargo empresa | money | reused |
| 00275 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Retribuciones largo plazo | money | reused |
| 00276 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Retribuciones instrumentos patrimonio | money | reused |
| 00277 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Otros gastos sociales | money | reused |
| 00278 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Provisiones | money | reused |
| 00279 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Otros gastos de explotación | money | reused |
| 00280 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Servicios exteriores | money | reused |
| 00281 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Tributos | money | reused |
| 00282 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Pérdidas/deterioro operaciones tráfico | money | reused |
| 00283 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Otros gastos gestión corriente | money | reused |
| 00284 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Amortización del inmovilizado | money | reused |
| 00285 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Imputación subvenciones inmovilizado | money | reused |
| 00286 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Excesos de provisiones | money | reused |
| 00287 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Deterioro y resultado enajenaciones | money | reused |
| 00288 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Deterioro y pérdidas | money | reused |
| 00289 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Deterioro y pérdidas - Deterioros | money | reused |
| 00290 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Deterioro y pérdidas - Reversión | money | reused |
| 00291 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Resultados por enajenaciones y otras | money | reused |
| 00292 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Resultados enajenaciones - Beneficios | money | reused |
| 00293 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Resultados enajenaciones - Pérdidas | money | reused |
| 00294 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Diferencia negativa combinaciones negocio | money | reused |
| 00295 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Otros resultados | money | reused |
| 00296 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - RESULTADO DE EXPLOTACIÓN | money | reused |
| 00297 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Ingresos financieros | money | reused |
| 00298 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - De participaciones instrumentos patrimonio | money | reused |
| 00299 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - De participaciones - En empresas grupo | money | reused |
| 00300 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - De participaciones - En terceros | money | reused |
| 00301 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - De valores negociables y otros instr. | money | reused |
| 00302 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - De valores - subgrupo A | money | reused |
| 00303 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - De valores - subgrupo B | money | reused |
| 00304 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Imputación subvenciones carácter financiero | money | reused |
| 00706 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Ingresos financieros holding - De participaciones | money | reused |
| 00707 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Ingresos financieros holding - De valores | money | reused |
| 00708 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Ingresos financieros holding - Resto | money | reused |
| 00709 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Gastos emisión gases efecto invernadero | money | reused |
| 00710 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Deterioro y resultados enajenaciones inm. | money | reused |
| 00711 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Ingresos financieros entidades concesionarias | money | reused |
| 00761 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Variación de existencias | money | reused |
| 00762 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Compras materias primas | money | reused |
| 00763 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Variación materias primas | money | reused |
| 00771 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Compras a socios (cooperativas) | money | reused |
| 00772 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Variación existencias socios (cooperativas) | money | reused |
| 00791 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Fondo Educación Formación Promoción (coop.) | money | reused |
| 00792 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Dotación (cooperativas) | money | reused |
| 00793 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - Subvenciones/ayudas/sanciones (cooperativas) | money | reused |
| 00794 | `is_cuenta_perdidas_ganancias_importe` | CpyG (I) - Op. continuadas - De valores - subgrupo C | money | reused |
| 00306 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Por deudas con empresas grupo | money | reused |
| 00307 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Por deudas con terceros | money | reused |
| 00308 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Por actualización de provisiones | money | reused |
| 00309 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Variación valor razonable instr. financieros | money | reused |
| 00310 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Valor razonable cambios en PyG | money | reused |
| 00311 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Transferencia ajustes valor razonable | money | reused |
| 00312 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Diferencias de cambio | money | reused |
| 00313 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Deterioro y resultado enajenaciones instr. | money | reused |
| 00314 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Deterioros y pérdidas | money | reused |
| 00315 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Deterioros empresas grupo/asociadas | money | reused |
| 00316 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Deterioros otras empresas | money | reused |
| 00317 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Reversión deterioros empresas grupo | money | reused |
| 00318 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Reversión deterioros otras empresas | money | reused |
| 00319 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Resultados por enajenaciones | money | reused |
| 00320 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Resultados enajenaciones - Beneficios grupo | money | reused |
| 00321 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Resultados enajenaciones - Beneficios otras | money | reused |
| 00322 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Resultados enajenaciones - Pérdidas grupo | money | reused |
| 00323 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Resultados enajenaciones - Pérdidas otras | money | reused |
| 00324 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - RESULTADO FINANCIERO | money | reused |
| 00325 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - RESULTADO ANTES DE IMPUESTOS | money | reused |
| 00326 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Impuestos sobre beneficios | money | reused |
| 00327 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - RESULTADO DEL EJERCICIO OP. CONTINUADAS | money | reused |
| 00330 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Incorporación activo gastos financieros | money | reused |
| 00331 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Ingresos financieros convenios acreedores | money | reused |
| 00332 | `is_cuenta_perdidas_ganancias_importe` | CpyG (II) - Op. continuadas - Resto de ingresos y gastos | money | reused |
| 00102 | `is_balance_activo_importe` | Balance Activo (I) - Inmovilizado intangible | money | reused |
| 00103 | `is_balance_activo_importe` | Balance Activo (I) - Desarrollo | money | reused |
| 00104 | `is_balance_activo_importe` | Balance Activo (I) - Concesiones | money | reused |
| 00105 | `is_balance_activo_importe` | Balance Activo (I) - Patentes, licencias, marcas | money | reused |
| 00106 | `is_balance_activo_importe` | Balance Activo (I) - Fondo de comercio | money | reused |
| 00107 | `is_balance_activo_importe` | Balance Activo (I) - Aplicaciones informáticas | money | reused |
| 00108 | `is_balance_activo_importe` | Balance Activo (I) - Investigación | money | reused |
| 00109 | `is_balance_activo_importe` | Balance Activo (I) - Otro inmovilizado intangible | money | reused |
| 00110 | `is_balance_activo_importe` | Balance Activo (I) - Resto | money | reused |
| 00111 | `is_balance_activo_importe` | Balance Activo (I) - Inmovilizado material | money | reused |
| 00112 | `is_balance_activo_importe` | Balance Activo (I) - Terrenos y construcciones | money | reused |
| 00113 | `is_balance_activo_importe` | Balance Activo (I) - Instalaciones técnicas y otro inm. material | money | reused |
| 00114 | `is_balance_activo_importe` | Balance Activo (I) - Inmovilizado en curso y anticipos | money | reused |
| 00115 | `is_balance_activo_importe` | Balance Activo (I) - Inversiones inmobiliarias | money | reused |
| 00116 | `is_balance_activo_importe` | Balance Activo (I) - Terrenos | money | reused |
| 00117 | `is_balance_activo_importe` | Balance Activo (I) - Construcciones | money | reused |
| 00118 | `is_balance_activo_importe` | Balance Activo (I) - Inversiones en empresas grupo/asociadas LP | money | reused |
| 00119 | `is_balance_activo_importe` | Balance Activo (I) - Instrumentos de patrimonio (grupo) | money | reused |
| 00120 | `is_balance_activo_importe` | Balance Activo (I) - Créditos a empresas | money | reused |
| 00121 | `is_balance_activo_importe` | Balance Activo (I) - Valores representativos de deuda (grupo) | money | reused |
| 00122 | `is_balance_activo_importe` | Balance Activo (I) - Derivados (grupo) | money | reused |
| 00123 | `is_balance_activo_importe` | Balance Activo (I) - Otros activos financieros (grupo) | money | reused |
| 00124 | `is_balance_activo_importe` | Balance Activo (I) - Otras inversiones (grupo) | money | reused |
| 00125 | `is_balance_activo_importe` | Balance Activo (I) - Resto (inversiones grupo) | money | reused |
| 00126 | `is_balance_activo_importe` | Balance Activo (I) - Inversiones financieras LP | money | reused |
| 00127 | `is_balance_activo_importe` | Balance Activo (I) - Instrumentos de patrimonio (terceros) | money | reused |
| 00128 | `is_balance_activo_importe` | Balance Activo (I) - Créditos a terceros | money | reused |
| 00129 | `is_balance_activo_importe` | Balance Activo (I) - Valores representativos de deuda (terceros) | money | reused |
| 00130 | `is_balance_activo_importe` | Balance Activo (I) - Derivados (terceros) | money | reused |
| 00131 | `is_balance_activo_importe` | Balance Activo (I) - Otros activos financieros (terceros) | money | reused |
| 00132 | `is_balance_activo_importe` | Balance Activo (I) - Otras inversiones (terceros) | money | reused |
| 00133 | `is_balance_activo_importe` | Balance Activo (I) - Resto (inversiones terceros) | money | reused |
| 00134 | `is_balance_activo_importe` | Balance Activo (I) - Activos por impuesto diferido | money | reused |
| 00135 | `is_balance_activo_importe` | Balance Activo (I) - Deudores comerciales no corrientes | money | reused |
| 00136 | `is_balance_activo_importe` | Balance Activo (I) - ACTIVO CORRIENTE | money | reused |
| 00137 | `is_balance_activo_importe` | Balance Activo (I) - Activos no corrientes mantenidos para venta | money | reused |
| 00138 | `is_balance_activo_importe` | Balance Activo (I) - Existencias | money | reused |
| 00139 | `is_balance_activo_importe` | Balance Activo (I) - Comerciales | money | reused |
| 00140 | `is_balance_activo_importe` | Balance Activo (I) - Materias primas y aprovisionamientos | money | reused |
| 00141 | `is_balance_activo_importe` | Balance Activo (I) - Productos en curso | money | reused |
| 00142 | `is_balance_activo_importe` | Balance Activo (I) - Productos en curso - Ciclo largo | money | reused |
| 00143 | `is_balance_activo_importe` | Balance Activo (I) - Productos en curso - Ciclo corto | money | reused |
| 00144 | `is_balance_activo_importe` | Balance Activo (I) - Productos terminados | money | reused |
| 00145 | `is_balance_activo_importe` | Balance Activo (I) - Productos terminados - Ciclo largo | money | reused |
| 00146 | `is_balance_activo_importe` | Balance Activo (I) - Productos terminados - Ciclo corto | money | reused |
| 00147 | `is_balance_activo_importe` | Balance Activo (I) - Subproductos, residuos y recuperados | money | reused |
| 00148 | `is_balance_activo_importe` | Balance Activo (I) - Anticipos a proveedores | money | reused |
| 00701 | `is_balance_activo_importe` | Balance Activo (I) - Derechos de emisión de gases efecto invernadero | money | reused |

## Data_type divergences

None. All 228 casillas in this cluster carry `data_type = money`. There are zero
data_type divergences within any role group.

---

**Summary**

- Total casillas classified: 228
- Distinct roles used: 3 (all reused from existing taxonomy)
  - `is_estado_cambios_patrimonio_neto_importe` — 100 ids (00388–00742, ECPN III sections)
  - `is_cuenta_perdidas_ganancias_importe` — 79 ids (00254–00794 and 00306–00332, CpyG I and II sections)
  - `is_balance_activo_importe` — 49 ids (00102–00701, Balance Activo I section)
- New roles introduced: 0
- Data_type divergences: 0
