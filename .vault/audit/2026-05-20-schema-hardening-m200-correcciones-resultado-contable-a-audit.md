---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# schema-hardening M200 correcciones-resultado-contable-a role assignment

## Scope

Cluster: `correcciones-resultado-contable-a`
Total casillas classified: 145
Revision: `2024-y-siguientes` (single M200 revision — no id reuse)

The cluster covers two structural families:

1. **dotaciones_deterioro_creditos_u_otros_activos** — year-cohort carry-forward tracking table (LIS art. 13.1 / art. 130 DT) with sub-sections `ejercicio_generacion` (one row per originating tax year) and `total` (column-sum row).
2. **Standard LIS-article adjustment blocks** — 12 named adjustment types, each with `aumento` and `disminucion` sub-sections. Every block follows the same 4-field repeating structure: temporarias-origen-ejercicio, temporarias-origen-anteriores, saldo-pendiente-inicio, saldo-pendiente-fin. Permanentes fields in the same blocks are already assigned `is_correccion_aumento` / `is_correccion_disminucion` in existing TOMLs and are excluded from this table.

### New roles introduced (11)

| role | description |
|---|---|
| `is_dotacion_deterioro_conversion_activo_diferido` | Dotaciones aplicadas a conversión de activos por impuesto diferido (art. 130 LIS) — per cohort and total |
| `is_dotacion_deterioro_integrada_ejercicio` | Dotaciones integradas en la base imponible en esta liquidación — per cohort and total |
| `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotaciones pendientes de integración a principio de periodo, que **no** han cumplido condiciones de deducibilidad — per cohort and total |
| `is_dotacion_deterioro_pendiente_inicio_con_cond` | Dotaciones pendientes de integración a principio de periodo, que **sí** han cumplido condiciones de deducibilidad — per cohort and total |
| `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotaciones pendientes de integración en periodos futuros, que no han cumplido condiciones de deducibilidad — per cohort and total |
| `is_dotacion_deterioro_pendiente_futuro_con_cond` | Dotaciones pendientes de integración en periodos futuros, que han cumplido condiciones de deducibilidad — per cohort and total |
| `is_correccion_temporaria_ejercicio_aumento` | Corrección temporaria con origen en el **ejercicio corriente** — Aumento (any LIS-article block) |
| `is_correccion_temporaria_anteriores_aumento` | Corrección temporaria con origen en **ejercicios anteriores** — Aumento |
| `is_correccion_saldo_pendiente_inicio_aumento` | Saldo de corrección pendiente a principio de ejercicio — Aumento |
| `is_correccion_saldo_pendiente_fin_aumento` | Saldo de corrección pendiente a fin de ejercicio — Aumento |
| `is_correccion_temporaria_ejercicio_disminucion` | Corrección temporaria con origen en el ejercicio corriente — Disminución |
| `is_correccion_temporaria_anteriores_disminucion` | Corrección temporaria con origen en ejercicios anteriores — Disminución |
| `is_correccion_saldo_pendiente_inicio_disminucion` | Saldo de corrección pendiente a principio de ejercicio — Disminución |
| `is_correccion_saldo_pendiente_fin_disminucion` | Saldo de corrección pendiente a fin de ejercicio — Disminución |

Note: 14 new role strings are defined. `is_correccion_aumento`, `is_correccion_disminucion`, `is_dotacion_deterioro_ejercicio`, and `is_dotacion_deterioro_total` are reused from the existing 88-role taxonomy.

## Role assignments

| id | role | label_snippet | data_type | notes |
|---|---|---|---|---|
| 01163 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2022 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 01164 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2022 — Dotac. pendientes integración periodos futuros — no han cumplido cond. | money | ejercicio_generacion |
| 01218 | `is_dotacion_deterioro_integrada_ejercicio` | Dotac. deterio. créd. — 2024 — Dotac. integradas en esta liquidación | money | ejercicio_generacion |
| 01219 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2024 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 01409 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2007 y anteriores — Dotac. pendientes integración a principio periodo | money | ejercicio_generacion; label truncated, single pendiente-inicio variant for legacy cohort |
| 01471 | `is_dotacion_deterioro_integrada_ejercicio` | Dotac. deterio. créd. — 2022 — Dotac. integradas en esta liquidación | money | ejercicio_generacion |
| 01474 | `is_dotacion_deterioro_integrada_ejercicio` | Dotac. deterio. créd. — 2007 y anteriores — Dotac. integradas en esta liquidación | money | ejercicio_generacion |
| 01475 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2007 y anteriores — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 01476 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2007 y anteriores — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion; label truncated |
| 01477 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2008 a 2015 — Dotac. pendientes integración a principio | money | ejercicio_generacion |
| 01478 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2008 a 2015 — Dotac. pendientes integración a principio | money | ejercicio_generacion; second variant (label truncated, likely "con cond" vs "sin cond") — both share role pending full label resolution |
| 01479 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2023 — Dotac. pendientes integración a principio | money | ejercicio_generacion |
| 01480 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2023 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 01481 | `is_dotacion_deterioro_integrada_ejercicio` | Dotac. deterio. créd. — 2008 a 2015 — Dotac. integradas en esta liquidación | money | ejercicio_generacion |
| 01482 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2008 a 2015 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 01483 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2008 a 2015 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 01484 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2008 a 2015 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion; second variant (label truncated) |
| 01485 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2016 — Dotac. pendientes integración a principio | money | ejercicio_generacion |
| 01486 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2016 — Dotac. pendientes integración a principio | money | ejercicio_generacion; second variant |
| 01487 | `is_dotacion_deterioro_integrada_ejercicio` | Dotac. deterio. créd. — 2016 — Dotac. integradas en esta liquidación | money | ejercicio_generacion |
| 01488 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2016 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 01489 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2016 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 01490 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2016 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion; second variant |
| 01491 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2017 — Dotac. pendientes integración a principio | money | ejercicio_generacion |
| 01492 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2017 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 01493 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2017 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 01495 | `is_dotacion_deterioro_pendiente_inicio_con_cond` | Dotac. deterio. créd. — Total — Dotac. pendientes integración a principio — que han cumplido condiciones | money | total |
| 01496 | `is_dotacion_deterioro_integrada_ejercicio` | Dotac. deterio. créd. — Total — Dotac. integradas en esta liquidación | money | total |
| 01497 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — Total — Dotac. aplicadas conversión activos imp. diferido | money | total |
| 01498 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — Total — Dotac. pendientes integración periodos futuros — que no han cumplido | money | total |
| 01499 | `is_dotacion_deterioro_pendiente_futuro_con_cond` | Dotac. deterio. créd. — Total — Dotac. pendientes integración periodos futuros — que han cumplido | money | total |
| 01627 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2025(*) — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 01628 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2025(*) — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 01748 | `is_dotacion_deterioro_integrada_ejercicio` | Dotac. deterio. créd. — 2017 — Dotac. integradas en esta liquidación | money | ejercicio_generacion |
| 01749 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2017 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 01750 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2018 — Dotac. pendientes integración a principio | money | ejercicio_generacion |
| 01751 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2018 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 01752 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2018 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 01885 | `is_correccion_disminucion` | Libertad amort. vehículos DA 18ª — Disminución — Correcciones ejercicio — Permanentes | money | **REUSE** existing role |
| 01962 | `is_correccion_temporaria_anteriores_disminucion` | Libertad amort. vehículos DA 18ª — Disminución — Correcciones ejercicio — Temporarias (origen ejercicios anteriores) | money | ejercicio_generacion does not apply; standard adjustment block |
| 01989 | `is_dotacion_deterioro_integrada_ejercicio` | Dotac. deterio. créd. — 2018 — Dotac. integradas en esta liquidación | money | ejercicio_generacion |
| 01990 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2018 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 01991 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2019 — Dotac. pendientes integración a principio | money | ejercicio_generacion |
| 01992 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2019 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 01993 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2019 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 02262 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2019 — Dotac. pendientes integración a principio (second variant) | money | ejercicio_generacion; 2019 cohort has two pendiente-inicio rows |
| 02263 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2019 — Dotac. pendientes integración periodos futuros (second variant) | money | ejercicio_generacion |
| 02264 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2020 — Dotac. pendientes integración a principio | money | ejercicio_generacion |
| 02265 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2020 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 02266 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2020 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 02432 | `is_dotacion_deterioro_integrada_ejercicio` | Dotac. deterio. créd. — 2020 — Dotac. integradas en esta liquidación | money | ejercicio_generacion |
| 02433 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2020 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion; second variant |
| 02434 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2021 — Dotac. pendientes integración a principio | money | ejercicio_generacion |
| 02435 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2021 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 02436 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2021 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 02542 | `is_correccion_temporaria_ejercicio_aumento` | Ajustes quita/espera art. 11.13 — Aumento — Correcciones del ejercicio (origen ejercicio) | money | |
| 02543 | `is_correccion_temporaria_anteriores_aumento` | Ajustes quita/espera art. 11.13 — Aumento — Correcciones del ejercicio (origen anteriores) | money | |
| 02544 | `is_correccion_saldo_pendiente_inicio_aumento` | Ajustes quita/espera art. 11.13 — Aumento — Saldo pendiente a principio de ejercicio | money | |
| 02545 | `is_correccion_saldo_pendiente_fin_aumento` | Ajustes quita/espera art. 11.13 — Aumento — Saldo pendiente a fin de ejercicio | money | |
| 02547 | `is_correccion_temporaria_ejercicio_disminucion` | Ajustes quita/espera art. 11.13 — Disminución — Correcciones del ejercicio (origen ejercicio) | money | |
| 02548 | `is_correccion_temporaria_anteriores_disminucion` | Ajustes quita/espera art. 11.13 — Disminución — Correcciones del ejercicio (origen anteriores) | money | |
| 02549 | `is_correccion_saldo_pendiente_inicio_disminucion` | Ajustes quita/espera art. 11.13 — Disminución — Saldo pendiente a principio de ejercicio | money | |
| 02550 | `is_correccion_saldo_pendiente_fin_disminucion` | Ajustes quita/espera art. 11.13 — Disminución — Saldo pendiente a fin de ejercicio | money | |
| 02562 | `is_correccion_temporaria_ejercicio_aumento` | Diferencias amort. contable/fiscal art. 12.1 — Aumento — Temporarias (origen ejercicio) | money | |
| 02563 | `is_correccion_temporaria_anteriores_aumento` | Diferencias amort. contable/fiscal art. 12.1 — Aumento — Temporarias (origen anteriores) | money | |
| 02564 | `is_correccion_saldo_pendiente_inicio_aumento` | Diferencias amort. contable/fiscal art. 12.1 — Aumento — Saldo pendiente inicio | money | |
| 02565 | `is_correccion_saldo_pendiente_fin_aumento` | Diferencias amort. contable/fiscal art. 12.1 — Aumento — Saldo pendiente fin | money | |
| 02567 | `is_correccion_temporaria_ejercicio_disminucion` | Diferencias amort. contable/fiscal art. 12.1 — Disminución — Temporarias (origen ejercicio) | money | |
| 02568 | `is_correccion_temporaria_anteriores_disminucion` | Diferencias amort. contable/fiscal art. 12.1 — Disminución — Temporarias (origen anteriores) | money | |
| 02569 | `is_correccion_saldo_pendiente_inicio_disminucion` | Diferencias amort. contable/fiscal art. 12.1 — Disminución — Saldo pendiente inicio | money | |
| 02570 | `is_correccion_saldo_pendiente_fin_disminucion` | Diferencias amort. contable/fiscal art. 12.1 — Disminución — Saldo pendiente fin | money | |
| 02582 | `is_correccion_temporaria_ejercicio_aumento` | Amort. intangible/fondo comercio art. 12.2 — Aumento — Temporarias (origen ejercicio) | money | |
| 02583 | `is_correccion_temporaria_anteriores_aumento` | Amort. intangible/fondo comercio art. 12.2 — Aumento — Temporarias (origen anteriores) | money | |
| 02584 | `is_correccion_saldo_pendiente_inicio_aumento` | Amort. intangible/fondo comercio art. 12.2 — Aumento — Saldo pendiente inicio | money | |
| 02585 | `is_correccion_saldo_pendiente_fin_aumento` | Amort. intangible/fondo comercio art. 12.2 — Aumento — Saldo pendiente fin | money | |
| 02587 | `is_correccion_temporaria_ejercicio_disminucion` | Amort. intangible/fondo comercio art. 12.2 — Disminución — Temporarias (origen ejercicio) | money | |
| 02588 | `is_correccion_temporaria_anteriores_disminucion` | Amort. intangible/fondo comercio art. 12.2 — Disminución — Temporarias (origen anteriores) | money | |
| 02589 | `is_correccion_saldo_pendiente_inicio_disminucion` | Amort. intangible/fondo comercio art. 12.2 — Disminución — Saldo pendiente inicio | money | |
| 02590 | `is_correccion_saldo_pendiente_fin_disminucion` | Amort. intangible/fondo comercio art. 12.2 — Disminución — Saldo pendiente fin | money | |
| 02602 | `is_correccion_temporaria_ejercicio_aumento` | Libertad amort. gastos I+D art. 12.3c — Aumento — Temporarias (origen ejercicio) | money | |
| 02603 | `is_correccion_temporaria_anteriores_aumento` | Libertad amort. gastos I+D art. 12.3c — Aumento — Temporarias (origen anteriores) | money | |
| 02604 | `is_correccion_saldo_pendiente_inicio_aumento` | Libertad amort. gastos I+D art. 12.3c — Aumento — Saldo pendiente inicio | money | |
| 02605 | `is_correccion_saldo_pendiente_fin_aumento` | Libertad amort. gastos I+D art. 12.3c — Aumento — Saldo pendiente fin | money | |
| 02607 | `is_correccion_temporaria_ejercicio_disminucion` | Libertad amort. gastos I+D art. 12.3c — Disminución — Temporarias (origen ejercicio) | money | |
| 02608 | `is_correccion_temporaria_anteriores_disminucion` | Libertad amort. gastos I+D art. 12.3c — Disminución — Temporarias (origen anteriores) | money | |
| 02609 | `is_correccion_saldo_pendiente_inicio_disminucion` | Libertad amort. gastos I+D art. 12.3c — Disminución — Saldo pendiente inicio | money | |
| 02610 | `is_correccion_saldo_pendiente_fin_disminucion` | Libertad amort. gastos I+D art. 12.3c — Disminución — Saldo pendiente fin | money | |
| 02622 | `is_correccion_temporaria_ejercicio_aumento` | Otros supuestos libertad amort. art. 12.3a/d — Aumento — Temporarias (origen ejercicio) | money | |
| 02623 | `is_correccion_temporaria_anteriores_aumento` | Otros supuestos libertad amort. art. 12.3a/d — Aumento — Temporarias (origen anteriores) | money | |
| 02624 | `is_correccion_saldo_pendiente_inicio_aumento` | Otros supuestos libertad amort. art. 12.3a/d — Aumento — Saldo pendiente inicio | money | |
| 02625 | `is_correccion_saldo_pendiente_fin_aumento` | Otros supuestos libertad amort. art. 12.3a/d — Aumento — Saldo pendiente fin | money | |
| 02627 | `is_correccion_temporaria_ejercicio_disminucion` | Otros supuestos libertad amort. art. 12.3a/d — Disminución — Temporarias (origen ejercicio) | money | |
| 02628 | `is_correccion_temporaria_anteriores_disminucion` | Otros supuestos libertad amort. art. 12.3a/d — Disminución — Temporarias (origen anteriores) | money | |
| 02629 | `is_correccion_saldo_pendiente_inicio_disminucion` | Otros supuestos libertad amort. art. 12.3a/d — Disminución — Saldo pendiente inicio | money | |
| 02630 | `is_correccion_saldo_pendiente_fin_disminucion` | Otros supuestos libertad amort. art. 12.3a/d — Disminución — Saldo pendiente fin | money | |
| 02642 | `is_correccion_temporaria_ejercicio_aumento` | Libertad amort. sin mantenimiento empleo RDL 13/2010 — Aumento — Temporarias (origen ejercicio) | money | |
| 02643 | `is_correccion_temporaria_anteriores_aumento` | Libertad amort. sin mantenimiento empleo RDL 13/2010 — Aumento — Temporarias (origen anteriores) | money | |
| 02644 | `is_correccion_saldo_pendiente_inicio_aumento` | Libertad amort. sin mantenimiento empleo RDL 13/2010 — Aumento — Saldo pendiente inicio | money | |
| 02645 | `is_correccion_saldo_pendiente_fin_aumento` | Libertad amort. sin mantenimiento empleo RDL 13/2010 — Aumento — Saldo pendiente fin | money | |
| 02647 | `is_correccion_temporaria_ejercicio_disminucion` | Libertad amort. sin mantenimiento empleo RDL 13/2010 — Disminución — Temporarias (origen ejercicio) | money | |
| 02648 | `is_correccion_temporaria_anteriores_disminucion` | Libertad amort. sin mantenimiento empleo RDL 13/2010 — Disminución — Temporarias (origen anteriores) | money | |
| 02649 | `is_correccion_saldo_pendiente_inicio_disminucion` | Libertad amort. sin mantenimiento empleo RDL 13/2010 — Disminución — Saldo pendiente inicio | money | |
| 02650 | `is_correccion_saldo_pendiente_fin_disminucion` | Libertad amort. sin mantenimiento empleo RDL 13/2010 — Disminución — Saldo pendiente fin | money | |
| 02662 | `is_correccion_temporaria_ejercicio_aumento` | Deterioro art. 13.1 / provisiones art. 14.1-14.2 — Aumento — Temporarias (origen ejercicio) | money | |
| 02663 | `is_correccion_temporaria_anteriores_aumento` | Deterioro art. 13.1 / provisiones art. 14.1-14.2 — Aumento — Temporarias (origen anteriores) | money | |
| 02664 | `is_correccion_saldo_pendiente_inicio_aumento` | Deterioro art. 13.1 / provisiones art. 14.1-14.2 — Aumento — Saldo pendiente inicio | money | |
| 02665 | `is_correccion_saldo_pendiente_fin_aumento` | Deterioro art. 13.1 / provisiones art. 14.1-14.2 — Aumento — Saldo pendiente fin | money | |
| 02667 | `is_correccion_temporaria_ejercicio_disminucion` | Deterioro art. 13.1 / provisiones art. 14.1-14.2 — Disminución — Temporarias (origen ejercicio) | money | |
| 02668 | `is_correccion_temporaria_anteriores_disminucion` | Deterioro art. 13.1 / provisiones art. 14.1-14.2 — Disminución — Temporarias (origen anteriores) | money | |
| 02669 | `is_correccion_saldo_pendiente_inicio_disminucion` | Deterioro art. 13.1 / provisiones art. 14.1-14.2 — Disminución — Saldo pendiente inicio | money | |
| 02670 | `is_correccion_saldo_pendiente_fin_disminucion` | Deterioro art. 13.1 / provisiones art. 14.1-14.2 — Disminución — Saldo pendiente fin | money | |
| 02682 | `is_correccion_temporaria_ejercicio_aumento` | Deterioro valores partic. capital/FP art. 13.2 — Aumento — Temporarias (origen ejercicio) | money | |
| 02683 | `is_correccion_temporaria_anteriores_aumento` | Deterioro valores partic. capital/FP art. 13.2 — Aumento — Temporarias (origen anteriores) | money | |
| 02684 | `is_correccion_saldo_pendiente_inicio_aumento` | Deterioro valores partic. capital/FP art. 13.2 — Aumento — Saldo pendiente inicio | money | |
| 02685 | `is_correccion_saldo_pendiente_fin_aumento` | Deterioro valores partic. capital/FP art. 13.2 — Aumento — Saldo pendiente fin | money | |
| 02687 | `is_correccion_temporaria_ejercicio_disminucion` | Deterioro valores partic. capital/FP art. 13.2 — Disminución — Temporarias (origen ejercicio) | money | |
| 02688 | `is_correccion_temporaria_anteriores_disminucion` | Deterioro valores partic. capital/FP art. 13.2 — Disminución — Temporarias (origen anteriores) | money | |
| 02689 | `is_correccion_saldo_pendiente_inicio_disminucion` | Deterioro valores partic. capital/FP art. 13.2 — Disminución — Saldo pendiente inicio | money | |
| 02690 | `is_correccion_saldo_pendiente_fin_disminucion` | Deterioro valores partic. capital/FP art. 13.2 — Disminución — Saldo pendiente fin | money | |
| 02722 | `is_correccion_temporaria_ejercicio_aumento` | Límite art. 11.12 sobre deterioro art. 13.1 / provisiones — Aumento — Temporarias (origen ejercicio) | money | |
| 02723 | `is_correccion_temporaria_anteriores_aumento` | Límite art. 11.12 sobre deterioro art. 13.1 / provisiones — Aumento — Temporarias (origen anteriores) | money | |
| 02724 | `is_correccion_saldo_pendiente_inicio_aumento` | Límite art. 11.12 sobre deterioro art. 13.1 / provisiones — Aumento — Saldo pendiente inicio | money | |
| 02725 | `is_correccion_saldo_pendiente_fin_aumento` | Límite art. 11.12 sobre deterioro art. 13.1 / provisiones — Aumento — Saldo pendiente fin | money | |
| 02727 | `is_correccion_temporaria_ejercicio_disminucion` | Límite art. 11.12 sobre deterioro art. 13.1 / provisiones — Disminución — Temporarias (origen ejercicio) | money | |
| 02728 | `is_correccion_temporaria_anteriores_disminucion` | Límite art. 11.12 sobre deterioro art. 13.1 / provisiones — Disminución — Temporarias (origen anteriores) | money | |
| 02729 | `is_correccion_saldo_pendiente_inicio_disminucion` | Límite art. 11.12 sobre deterioro art. 13.1 / provisiones — Disminución — Saldo pendiente inicio | money | |
| 02730 | `is_correccion_saldo_pendiente_fin_disminucion` | Límite art. 11.12 sobre deterioro art. 13.1 / provisiones — Disminución — Saldo pendiente fin | money | |
| 02742 | `is_correccion_temporaria_ejercicio_aumento` | Otras provisiones no deducibles art. 14 (no art. 11.12) — Aumento — Temporarias (origen ejercicio) | money | |
| 02743 | `is_correccion_temporaria_anteriores_aumento` | Otras provisiones no deducibles art. 14 (no art. 11.12) — Aumento — Temporarias (origen anteriores) | money | |
| 02744 | `is_correccion_saldo_pendiente_inicio_aumento` | Otras provisiones no deducibles art. 14 (no art. 11.12) — Aumento — Saldo pendiente inicio | money | |
| 02745 | `is_correccion_saldo_pendiente_fin_aumento` | Otras provisiones no deducibles art. 14 (no art. 11.12) — Aumento — Saldo pendiente fin | money | |
| 02747 | `is_correccion_temporaria_ejercicio_disminucion` | Otras provisiones no deducibles art. 14 (no art. 11.12) — Disminución — Temporarias (origen ejercicio) | money | |
| 02748 | `is_correccion_temporaria_anteriores_disminucion` | Otras provisiones no deducibles art. 14 (no art. 11.12) — Disminución — Temporarias (origen anteriores) | money | |
| 02749 | `is_correccion_saldo_pendiente_inicio_disminucion` | Otras provisiones no deducibles art. 14 (no art. 11.12) — Disminución — Saldo pendiente inicio | money | |
| 02750 | `is_correccion_saldo_pendiente_fin_disminucion` | Otras provisiones no deducibles art. 14 (no art. 11.12) — Disminución — Saldo pendiente fin | money | |
| 02803 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2023 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 02804 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2024 — Dotac. pendientes integración a principio | money | ejercicio_generacion |
| 02805 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2024 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 02806 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2024 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 02852 | `is_correccion_temporaria_ejercicio_aumento` | Deterioro valores partic. capital/FP art. 15k — Aumento — Temporarias (origen ejercicio) | money | |
| 02853 | `is_correccion_temporaria_anteriores_aumento` | Deterioro valores partic. capital/FP art. 15k — Aumento — Temporarias (origen anteriores) | money | |
| 02854 | `is_correccion_saldo_pendiente_inicio_aumento` | Deterioro valores partic. capital/FP art. 15k — Aumento — Saldo pendiente inicio | money | |
| 02855 | `is_correccion_saldo_pendiente_fin_aumento` | Deterioro valores partic. capital/FP art. 15k — Aumento — Saldo pendiente fin | money | |
| 02857 | `is_correccion_temporaria_ejercicio_disminucion` | Deterioro valores partic. capital/FP art. 15k — Disminución — Temporarias (origen ejercicio) | money | |
| 02858 | `is_correccion_temporaria_anteriores_disminucion` | Deterioro valores partic. capital/FP art. 15k — Disminución — Temporarias (origen anteriores) | money | |
| 02859 | `is_correccion_saldo_pendiente_inicio_disminucion` | Deterioro valores partic. capital/FP art. 15k — Disminución — Saldo pendiente inicio | money | |
| 02860 | `is_correccion_saldo_pendiente_fin_disminucion` | Deterioro valores partic. capital/FP art. 15k — Disminución — Saldo pendiente fin | money | |
| 02872 | `is_correccion_temporaria_ejercicio_aumento` | Deuda tributaria ITP/AJD art. 15m — Aumento — Temporarias (origen ejercicio) | money | |
| 02873 | `is_correccion_temporaria_anteriores_aumento` | Deuda tributaria ITP/AJD art. 15m — Aumento — Temporarias (origen anteriores) | money | |
| 02874 | `is_correccion_saldo_pendiente_inicio_aumento` | Deuda tributaria ITP/AJD art. 15m — Aumento — Saldo pendiente inicio | money | |
| 02875 | `is_correccion_saldo_pendiente_fin_aumento` | Deuda tributaria ITP/AJD art. 15m — Aumento — Saldo pendiente fin | money | |
| 02877 | `is_correccion_temporaria_ejercicio_disminucion` | Deuda tributaria ITP/AJD art. 15m — Disminución — Temporarias (origen ejercicio) | money | |
| 02878 | `is_correccion_temporaria_anteriores_disminucion` | Deuda tributaria ITP/AJD art. 15m — Disminución — Temporarias (origen anteriores) | money | |
| 02879 | `is_correccion_saldo_pendiente_inicio_disminucion` | Deuda tributaria ITP/AJD art. 15m — Disminución — Saldo pendiente inicio | money | |
| 02880 | `is_correccion_saldo_pendiente_fin_disminucion` | Deuda tributaria ITP/AJD art. 15m — Disminución — Saldo pendiente fin | money | |
| 02892 | `is_correccion_temporaria_ejercicio_aumento` | Revalorizaciones contables art. 17.1 — Aumento — Temporarias (origen ejercicio) | money | |
| 02893 | `is_correccion_temporaria_anteriores_aumento` | Revalorizaciones contables art. 17.1 — Aumento — Temporarias (origen anteriores) | money | |
| 02894 | `is_correccion_saldo_pendiente_inicio_aumento` | Revalorizaciones contables art. 17.1 — Aumento — Saldo pendiente inicio | money | |
| 02895 | `is_correccion_saldo_pendiente_fin_aumento` | Revalorizaciones contables art. 17.1 — Aumento — Saldo pendiente fin | money | |
| 02897 | `is_correccion_temporaria_ejercicio_disminucion` | Revalorizaciones contables art. 17.1 — Disminución — Temporarias (origen ejercicio) | money | |
| 02898 | `is_correccion_temporaria_anteriores_disminucion` | Revalorizaciones contables art. 17.1 — Disminución — Temporarias (origen anteriores) | money | |
| 02899 | `is_correccion_saldo_pendiente_inicio_disminucion` | Revalorizaciones contables art. 17.1 — Disminución — Saldo pendiente inicio | money | |
| 02900 | `is_correccion_saldo_pendiente_fin_disminucion` | Revalorizaciones contables art. 17.1 — Disminución — Saldo pendiente fin | money | |
| 02922 | `is_correccion_temporaria_ejercicio_aumento` | Transmisiones lucrativas/societarias valor mercado art. 17.4 — Aumento — Temporarias (origen ejercicio) | money | |
| 02923 | `is_correccion_temporaria_anteriores_aumento` | Transmisiones lucrativas/societarias valor mercado art. 17.4 — Aumento — Temporarias (origen anteriores) | money | |
| 02924 | `is_correccion_saldo_pendiente_inicio_aumento` | Transmisiones lucrativas/societarias valor mercado art. 17.4 — Aumento — Saldo pendiente inicio | money | |
| 02925 | `is_correccion_saldo_pendiente_fin_aumento` | Transmisiones lucrativas/societarias valor mercado art. 17.4 — Aumento — Saldo pendiente fin | money | |
| 02927 | `is_correccion_temporaria_ejercicio_disminucion` | Transmisiones lucrativas/societarias valor mercado art. 17.4 — Disminución — Temporarias (origen ejercicio) | money | |
| 02928 | `is_correccion_temporaria_anteriores_disminucion` | Transmisiones lucrativas/societarias valor mercado art. 17.4 — Disminución — Temporarias (origen anteriores) | money | |
| 02929 | `is_correccion_saldo_pendiente_inicio_disminucion` | Transmisiones lucrativas/societarias valor mercado art. 17.4 — Disminución — Saldo pendiente inicio | money | |
| 02930 | `is_correccion_saldo_pendiente_fin_disminucion` | Transmisiones lucrativas/societarias valor mercado art. 17.4 — Disminución — Saldo pendiente fin | money | |
| 02952 | `is_correccion_temporaria_ejercicio_aumento` | Efectos valoración contable/fiscal art. 20 — Aumento — Temporarias (origen ejercicio) | money | |
| 02953 | `is_correccion_temporaria_anteriores_aumento` | Efectos valoración contable/fiscal art. 20 — Aumento — Temporarias (origen anteriores) | money | |
| 02954 | `is_correccion_saldo_pendiente_inicio_aumento` | Efectos valoración contable/fiscal art. 20 — Aumento — Saldo pendiente inicio | money | |
| 02955 | `is_correccion_saldo_pendiente_fin_aumento` | Efectos valoración contable/fiscal art. 20 — Aumento — Saldo pendiente fin | money | |
| 02957 | `is_correccion_temporaria_ejercicio_disminucion` | Efectos valoración contable/fiscal art. 20 — Disminución — Temporarias (origen ejercicio) | money | |
| 02958 | `is_correccion_temporaria_anteriores_disminucion` | Efectos valoración contable/fiscal art. 20 — Disminución — Temporarias (origen anteriores) | money | |
| 02959 | `is_correccion_saldo_pendiente_inicio_disminucion` | Efectos valoración contable/fiscal art. 20 — Disminución — Saldo pendiente inicio | money | |
| 02960 | `is_correccion_saldo_pendiente_fin_disminucion` | Efectos valoración contable/fiscal art. 20 — Disminución — Saldo pendiente fin | money | |
| 03052 | `is_correccion_temporaria_ejercicio_aumento` | Impuesto extranjero no deducible (doble imposición) — Aumento — Temporarias (origen ejercicio) | money | |
| 03053 | `is_correccion_temporaria_anteriores_aumento` | Impuesto extranjero no deducible (doble imposición) — Aumento — Temporarias (origen anteriores) | money | |
| 03054 | `is_correccion_saldo_pendiente_inicio_aumento` | Impuesto extranjero no deducible (doble imposición) — Aumento — Saldo pendiente inicio | money | |
| 03055 | `is_correccion_saldo_pendiente_fin_aumento` | Impuesto extranjero no deducible (doble imposición) — Aumento — Saldo pendiente fin | money | |
| 03057 | `is_correccion_temporaria_ejercicio_disminucion` | Impuesto extranjero no deducible (doble imposición) — Disminución — Temporarias (origen ejercicio) | money | |
| 03058 | `is_correccion_temporaria_anteriores_disminucion` | Impuesto extranjero no deducible (doble imposición) — Disminución — Temporarias (origen anteriores) | money | |
| 03059 | `is_correccion_saldo_pendiente_inicio_disminucion` | Impuesto extranjero no deducible (doble imposición) — Disminución — Saldo pendiente inicio | money | |
| 03060 | `is_correccion_saldo_pendiente_fin_disminucion` | Impuesto extranjero no deducible (doble imposición) — Disminución — Saldo pendiente fin | money | |
| 03142 | `is_correccion_temporaria_ejercicio_aumento` | Valoración bienes/derechos reestructuración cap. VII tít. VII — Aumento — Temporarias (origen ejercicio) | money | |
| 03143 | `is_correccion_temporaria_anteriores_aumento` | Valoración bienes/derechos reestructuración cap. VII tít. VII — Aumento — Temporarias (origen anteriores) | money | |
| 03144 | `is_correccion_saldo_pendiente_inicio_aumento` | Valoración bienes/derechos reestructuración cap. VII tít. VII — Aumento — Saldo pendiente inicio | money | |
| 03145 | `is_correccion_saldo_pendiente_fin_aumento` | Valoración bienes/derechos reestructuración cap. VII tít. VII — Aumento — Saldo pendiente fin | money | |
| 03147 | `is_correccion_temporaria_ejercicio_disminucion` | Valoración bienes/derechos reestructuración cap. VII tít. VII — Disminución — Temporarias (origen ejercicio) | money | |
| 03148 | `is_correccion_temporaria_anteriores_disminucion` | Valoración bienes/derechos reestructuración cap. VII tít. VII — Disminución — Temporarias (origen anteriores) | money | |
| 03149 | `is_correccion_saldo_pendiente_inicio_disminucion` | Valoración bienes/derechos reestructuración cap. VII tít. VII — Disminución — Saldo pendiente inicio | money | |
| 03150 | `is_correccion_saldo_pendiente_fin_disminucion` | Valoración bienes/derechos reestructuración cap. VII tít. VII — Disminución — Saldo pendiente fin | money | |
| 03322 | `is_correccion_temporaria_ejercicio_aumento` | Operaciones a plazos DT 1ª — Aumento — Temporarias (origen ejercicio) | money | |
| 03323 | `is_correccion_temporaria_anteriores_aumento` | Operaciones a plazos DT 1ª — Aumento — Temporarias (origen anteriores) | money | |
| 03324 | `is_correccion_saldo_pendiente_inicio_aumento` | Operaciones a plazos DT 1ª — Aumento — Saldo pendiente inicio | money | |
| 03325 | `is_correccion_saldo_pendiente_fin_aumento` | Operaciones a plazos DT 1ª — Aumento — Saldo pendiente fin | money | |
| 03327 | `is_correccion_temporaria_ejercicio_disminucion` | Operaciones a plazos DT 1ª — Disminución — Temporarias (origen ejercicio) | money | |
| 03328 | `is_correccion_temporaria_anteriores_disminucion` | Operaciones a plazos DT 1ª — Disminución — Temporarias (origen anteriores) | money | |
| 03329 | `is_correccion_saldo_pendiente_inicio_disminucion` | Operaciones a plazos DT 1ª — Disminución — Saldo pendiente inicio | money | |
| 03330 | `is_correccion_saldo_pendiente_fin_disminucion` | Operaciones a plazos DT 1ª — Disminución — Saldo pendiente fin | money | |
| 03342 | `is_correccion_temporaria_ejercicio_aumento` | Reinversión beneficios extraordinarios DT 24ª — Aumento — Temporarias (origen ejercicio) | money | |
| 03343 | `is_correccion_temporaria_anteriores_aumento` | Reinversión beneficios extraordinarios DT 24ª — Aumento — Temporarias (origen anteriores) | money | |
| 03344 | `is_correccion_saldo_pendiente_inicio_aumento` | Reinversión beneficios extraordinarios DT 24ª — Aumento — Saldo pendiente inicio | money | |
| 03345 | `is_correccion_saldo_pendiente_fin_aumento` | Reinversión beneficios extraordinarios DT 24ª — Aumento — Saldo pendiente fin | money | |
| 03347 | `is_correccion_temporaria_ejercicio_disminucion` | Reinversión beneficios extraordinarios DT 24ª — Disminución — Temporarias (origen ejercicio) | money | |
| 03348 | `is_correccion_temporaria_anteriores_disminucion` | Reinversión beneficios extraordinarios DT 24ª — Disminución — Temporarias (origen anteriores) | money | |
| 03349 | `is_correccion_saldo_pendiente_inicio_disminucion` | Reinversión beneficios extraordinarios DT 24ª — Disminución — Saldo pendiente inicio | money | |
| 03350 | `is_correccion_saldo_pendiente_fin_disminucion` | Reinversión beneficios extraordinarios DT 24ª — Disminución — Saldo pendiente fin | money | |
| 03382 | `is_correccion_temporaria_ejercicio_aumento` | Eliminaciones pendientes grupos — Aumento — Temporarias (origen ejercicio) | money | |
| 03383 | `is_correccion_temporaria_anteriores_aumento` | Eliminaciones pendientes grupos — Aumento — Temporarias (origen anteriores) | money | |
| 03384 | `is_correccion_saldo_pendiente_inicio_aumento` | Eliminaciones pendientes grupos — Aumento — Saldo pendiente inicio | money | |
| 03385 | `is_correccion_saldo_pendiente_fin_aumento` | Eliminaciones pendientes grupos — Aumento — Saldo pendiente fin | money | |
| 03387 | `is_correccion_temporaria_ejercicio_disminucion` | Eliminaciones pendientes grupos — Disminución — Temporarias (origen ejercicio) | money | |
| 03388 | `is_correccion_temporaria_anteriores_disminucion` | Eliminaciones pendientes grupos — Disminución — Temporarias (origen anteriores) | money | |
| 03389 | `is_correccion_saldo_pendiente_inicio_disminucion` | Eliminaciones pendientes grupos — Disminución — Saldo pendiente inicio | money | |
| 03390 | `is_correccion_saldo_pendiente_fin_disminucion` | Eliminaciones pendientes grupos — Disminución — Saldo pendiente fin | money | |
| 03618 | `is_dotacion_deterioro_integrada_ejercicio` | Dotac. deterio. créd. — 2025(*) — Dotac. integradas en esta liquidación | money | ejercicio_generacion |
| 03619 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2025(*) — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 03620 | `is_dotacion_deterioro_pendiente_inicio_sin_cond` | Dotac. deterio. créd. — 2025 — Dotac. pendientes integración a principio | money | ejercicio_generacion |
| 03621 | `is_dotacion_deterioro_conversion_activo_diferido` | Dotac. deterio. créd. — 2025 — Dotac. aplicadas conversión activos imp. diferido | money | ejercicio_generacion |
| 03622 | `is_dotacion_deterioro_pendiente_futuro_sin_cond` | Dotac. deterio. créd. — 2025 — Dotac. pendientes integración periodos futuros | money | ejercicio_generacion |
| 01678 | `is_correccion_temporaria_ejercicio_aumento` | Operaciones art. 19 distintas cambio residencia UE/EEE — Aumento — Temporarias (origen ejercicio) | money | |
| 01679 | `is_correccion_temporaria_anteriores_aumento` | Operaciones art. 19 distintas cambio residencia UE/EEE — Aumento — Temporarias (origen anteriores) | money | |
| 01680 | `is_correccion_saldo_pendiente_fin_aumento` | Operaciones art. 19 distintas cambio residencia UE/EEE — Aumento — Saldo pendiente fin | money | no saldo-inicio field in this block |
| 01682 | `is_correccion_temporaria_ejercicio_disminucion` | Operaciones art. 19 distintas cambio residencia UE/EEE — Disminución — Temporarias (origen ejercicio) | money | |
| 01687 | `is_correccion_temporaria_anteriores_disminucion` | Operaciones art. 19 distintas cambio residencia UE/EEE — Disminución — Temporarias (origen anteriores) | money | |
| 01688 | `is_correccion_saldo_pendiente_fin_disminucion` | Operaciones art. 19 distintas cambio residencia UE/EEE — Disminución — Saldo pendiente fin | money | no saldo-inicio field |
| 01742 | `is_correccion_temporaria_ejercicio_aumento` | Libertad amort. vehículos DA 18ª RDL 4/2024 — Aumento — Temporarias (origen ejercicio) | money | |
| 01885 | `is_correccion_disminucion` | Libertad amort. vehículos DA 18ª — Disminución — Permanentes | money | **REUSE** existing role; casilla added per TOML already assigned |
| 01962 | `is_correccion_temporaria_anteriores_disminucion` | Libertad amort. vehículos DA 18ª — Disminución — Temporarias (origen ejercicios anteriores) | money | |

## Data_type divergences

None. All 145 casillas in this cluster carry `data_type = "money"`. No divergences detected.

### Structural notes

- Casillas 01477/01478 (2008–2015 cohort, pendiente-inicio) and 01485/01486 (2016 cohort) show two rows with the same functional role (`is_dotacion_deterioro_pendiente_inicio_sin_cond`). The label fragments are truncated in the cluster JSON; full labels in the TOML would distinguish "que no han cumplido" vs "que han cumplido condiciones". If the second variants prove to be the "con condición" variant, they should be reclassified to `is_dotacion_deterioro_pendiente_inicio_con_cond`. Verification requires reading the complete label from TOML.
- Similarly for 01483/01484 (2008–2015 pendiente-futuro): may be sin/con cond variants. Same applies to 01489/01490 (2016) and 01749 (2017 second pendiente-futuro).
- The art. 19 LIS block (01678–01688) is structurally abbreviated: no "saldo pendiente a principio" field appears in the cluster JSON, only temporarias + saldo-fin. Assign `is_correccion_saldo_pendiente_fin_aumento` / `_disminucion` accordingly.
- The DA 18ª vehículos block (01742, 01885, 01962) has three casillas: one aumento temporaria-ejercicio and two disminucion (permanentes + temporarias-anteriores). Casilla 01885 is already assigned `is_correccion_disminucion` in the TOML; 01962 is unassigned.
