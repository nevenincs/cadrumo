---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# schema-hardening m200 deducciones-a role assignment

## Scope

Cluster: **deducciones-a** — corporate-tax deductions and credits block of Modelo 200 (IS), revision `2024-y-siguientes`.

Source file: `.vault-scratch/m200-clusters/deducciones-a.json` — 202 casillas across seven deduction sections:

- `deduccion_donativos_entidades_sin_fines_lucro` (donaciones generales + prioritarias mecenazgo)
- `deducciones_i_d_i_excluidas_de_limite` (I+D+i excluded from the global cap, by year and type)
- `deducciones_por_producciones_cinematograficas_extr` (foreign film production — mainland + Canarias variant)
- `deducciones_doble_imposicion_interna_dt_23_1_lis` (internal double-taxation relief, DT 23.1 LIS)
- `deduccion_por_inversiones_y_gastos_realizados_por` (port-authority investments, art. 38 bis LIS)
- `deducciones_dt_24a_1_lis` (transitional deduction DT 24ª.1 LIS, periodificación)

Role naming convention: `is_<domain>_<concept>`, snake_case, lowercase ASCII. Vintage year included in the role name when it appears in the tax label and is semantically part of the deduction concept (e.g., `is_deduccion_idi_excluida_limite_investigacion_2025`). Where the axis (generated/applied/pending) distinguishes the role, a suffix `_pendiente_generada`, `_periodo` (applied this period), or `_pendiente_futuros` is used consistently across sections. Roles reused verbatim from the existing 88-role inventory are noted with "(reused)".

## Role assignments

| id | role | label_snippet | data_type | notes |
|----|------|---------------|-----------|-------|
| 00819 | `is_deduccion_donativos_general` | Donaciones gral – 2015 – Con reiteración | money | reused |
| 00821 | `is_deduccion_donativos_general` | Donaciones gral – 2016 – Con reiteración | money | reused |
| 00834 | `is_deduccion_donativos_general` | Donaciones gral – 2016 – Con reiteración | money | reused |
| 00835 | `is_deduccion_donativos_general` | Donaciones gral – 2017 – Con reiteración | money | reused |
| 00836 | `is_deduccion_donativos_general` | Donaciones gral – 2017 – Con reiteración | money | reused |
| 00837 | `is_deduccion_donativos_general` | Donaciones gral – 2017 – Con reiteración | money | reused |
| 00838 | `is_deduccion_donativos_general` | Donaciones gral – 2018 – Con reiteración | money | reused |
| 00839 | `is_deduccion_donativos_general` | Donaciones gral – 2018 – Con reiteración | money | reused |
| 00840 | `is_deduccion_donativos_general` | Donaciones gral – 2018 – Con reiteración | money | reused |
| 00845 | `is_deduccion_donativos_general` | Donaciones gral – 2019 – Con reiteración | money | reused |
| 00869 | `is_deduccion_donativos_general` | Donaciones gral – 2020 – Con reiteración | money | reused |
| 00872 | `is_deduccion_donativos_general` | Donaciones gral – 2021 – Con reiteración | money | reused |
| 00873 | `is_deduccion_donativos_general` | Donaciones gral – 2021 – Con reiteración | money | reused |
| 00876 | `is_deduccion_donativos_general` | Donaciones gral – 2022 Sin reiteración | money | reused |
| 00891 | `is_deduccion_donativos_general` | Donaciones gral – 2022 – Con reiteración | money | reused |
| 00892 | `is_deduccion_donativos_general` | Donaciones gral – 2022 – Con reiteración | money | reused |
| 00893 | `is_deduccion_donativos_general` | Donaciones gral – 2022 – Con reiteración | money | reused |
| 00934 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00944 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00950 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00951 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00952 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00953 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00954 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00958 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00959 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00964 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00965 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00970 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00971 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00972 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00973 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00980 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00981 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00982 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00983 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00984 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00985 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00994 | `is_deduccion_donativos_general` | Donaciones gral – 2016 Sin reiteración | money | reused |
| 00995 | `is_deduccion_donativos_general` | Donaciones gral – 2016 Sin reiteración | money | reused |
| 01008 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01025 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01036 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01062 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01073 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01074 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01078 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01079 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01080 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01081 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01324 | `is_deduccion_donativos_general` | Donaciones gral – 2023 Sin reiteración | money | reused |
| 01325 | `is_deduccion_donativos_general` | Donaciones gral – 2023 Sin reiteración | money | reused |
| 01326 | `is_deduccion_donativos_general` | Donaciones gral – 2023 – Con reiteración | money | reused |
| 01327 | `is_deduccion_donativos_general` | Donaciones gral – 2023 – Con reiteración | money | reused |
| 01328 | `is_deduccion_donativos_general` | Donaciones gral – 2023 – Con reiteración | money | reused |
| 01373 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01374 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01375 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01376 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01435 | `is_deduccion_donativos_general` | Donaciones gral – 2017 Sin reiteración | money | reused |
| 01436 | `is_deduccion_donativos_general` | Donaciones gral – 2017 Sin reiteración | money | reused |
| 01693 | `is_deduccion_donativos_general` | Donaciones gral – Subtotal 2015-2025 sin reiteración | money | reused; subtotal row, same domain concept |
| 01694 | `is_deduccion_donativos_general` | Donaciones gral – Subtotal 2015-2025 sin reiteración | money | reused |
| 01695 | `is_deduccion_donativos_general` | Donaciones gral – Subtotal 2015-2025 con reiteración | money | reused |
| 01696 | `is_deduccion_donativos_general` | Donaciones gral – Subtotal 2015-2025 con reiteración | money | reused |
| 01697 | `is_deduccion_donativos_general` | Donaciones gral – Subtotal 2015-2025 con reiteración | money | reused |
| 01698 | `is_deduccion_donativos_general` | Donaciones gral – Total – Deducción pendiente/generada | money | reused; total generated amount |
| 01699 | `is_deduccion_donativos_general` | Donaciones gral – Total – Aplicado en esta liquidación | money | reused; total applied this period |
| 01700 | `is_deduccion_donativos_general` | Donaciones gral – Total – Pendiente de aplicación futuros | money | reused; total carry-forward |
| 01705 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01706 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 01719 | `is_deduccion_donativos_general` | Donaciones gral – 2018 Sin reiteración | money | reused |
| 01720 | `is_deduccion_donativos_general` | Donaciones gral – 2018 Sin reiteración | money | reused |
| 01951 | `is_deduccion_donativos_general` | Donaciones gral – 2019 Sin reiteración | money | reused |
| 01952 | `is_deduccion_donativos_general` | Donaciones gral – 2019 Sin reiteración | money | reused |
| 02228 | `is_deduccion_donativos_general` | Donaciones gral – 2020 Sin reiteración | money | reused |
| 02229 | `is_deduccion_donativos_general` | Donaciones gral – 2020 Sin reiteración | money | reused |
| 02381 | `is_deduccion_donativos_general` | Donaciones gral – 2021 Sin reiteración | money | reused |
| 02382 | `is_deduccion_donativos_general` | Donaciones gral – 2021 Sin reiteración | money | reused |
| 02473 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 02474 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 02475 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 02476 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 02499 | `is_deduccion_donativos_general` | Donaciones gral – 2022 Sin reiteración | money | reused |
| 03544 | `is_deduccion_donativos_general` | Donaciones gral – 2025(*) Sin reiteración | money | reused; 2025(*) = periodificación vintage |
| 03545 | `is_deduccion_donativos_general` | Donaciones gral – 2025(*) Sin reiteración | money | reused |
| 03546 | `is_deduccion_donativos_general` | Donaciones gral – 2025(*) – Con reiteración | money | reused |
| 03547 | `is_deduccion_donativos_general` | Donaciones gral – 2025(*) – Con reiteración | money | reused |
| 03548 | `is_deduccion_donativos_general` | Donaciones gral – 2025(*) – Con reiteración | money | reused |
| 03549 | `is_deduccion_donativos_general` | Donaciones gral – 2025 Sin reiteración | money | reused |
| 03550 | `is_deduccion_donativos_general` | Donaciones gral – 2025 Sin reiteración | money | reused |
| 03551 | `is_deduccion_donativos_general` | Donaciones gral – 2025 Sin reiteración | money | reused |
| 03552 | `is_deduccion_donativos_general` | Donaciones gral – 2025 – Con reiteración | money | reused |
| 03553 | `is_deduccion_donativos_general` | Donaciones gral – 2025 – Con reiteración | money | reused |
| 03554 | `is_deduccion_donativos_general` | Donaciones gral – 2025 – Con reiteración | money | reused |
| 03556 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 03557 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 03558 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 03559 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 03560 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 03561 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 03562 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 03563 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 03564 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 03565 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 03566 | `is_deduccion_donativos_prioritarias` | Donaciones prioritarias mecenazgo | money | reused |
| 00823 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2014 I+D – Deducción reducida | money | reused |
| 00824 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2014 I+D – Aplicado esta liquidación | money | reused |
| 00851 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2014 IT – Importe abonado insuf. cuota | money | reused |
| 00919 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2013 I+D – Deducción reducida | money | reused |
| 00977 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2013 IT – Aplicado esta liquidación | money | reused |
| 00978 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2013 IT – Importe abonado insuf. cuota | money | reused |
| 01091 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2021 I+D – Deducción reducida | money | reused |
| 01092 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2021 I+D – Aplicado esta liquidación | money | reused |
| 01093 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2021 I+D – Importe abonado insuf. cuota | money | reused |
| 01095 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2021 IT – Deducción reducida | money | reused |
| 01096 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2021 IT – Aplicado esta liquidación | money | reused |
| 01097 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2021 IT – Importe abonado insuf. cuota | money | reused |
| 01124 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2015 I+D – Deducción reducida | money | reused |
| 01125 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2015 I+D – Aplicado esta liquidación | money | reused |
| 01126 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2015 I+D – Importe abonado insuf. cuota | money | reused |
| 01128 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2015 IT – Deducción reducida | money | reused |
| 01129 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2015 IT – Aplicado esta liquidación | money | reused |
| 01130 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2015 IT – Importe abonado insuf. cuota | money | reused |
| 01386 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2022 I+D – Deducción reducida | money | reused |
| 01387 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2022 I+D – Aplicado esta liquidación | money | reused |
| 01388 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2022 I+D – Importe abonado insuf. cuota | money | reused |
| 01390 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2022 IT – Deducción reducida | money | reused |
| 01391 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2022 IT – Aplicado esta liquidación | money | reused |
| 01392 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2022 IT – Importe abonado insuf. cuota | money | reused |
| 01427 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2016 I+D – Deducción reducida | money | reused |
| 01428 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2016 I+D – Aplicado esta liquidación | money | reused |
| 01429 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2016 I+D – Importe abonado insuf. cuota | money | reused |
| 01431 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2016 IT – Deducción reducida | money | reused |
| 01432 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2016 IT – Aplicado esta liquidación | money | reused |
| 01433 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2016 IT – Importe abonado insuf. cuota | money | reused |
| 01711 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2017 I+D – Deducción reducida | money | reused |
| 01712 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2017 I+D – Aplicado esta liquidación | money | reused |
| 01713 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2017 I+D – Importe abonado insuf. cuota | money | reused |
| 01715 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2017 IT – Deducción reducida | money | reused |
| 01716 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2017 IT – Aplicado esta liquidación | money | reused |
| 01717 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2017 IT – Importe abonado insuf. cuota | money | reused |
| 01969 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2018 I+D – Deducción reducida | money | reused |
| 01970 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2018 I+D – Aplicado esta liquidación | money | reused |
| 01971 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2018 I+D – Importe abonado insuf. cuota | money | reused |
| 01973 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2018 IT – Deducción reducida | money | reused |
| 01974 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2018 IT – Aplicado esta liquidación | money | reused |
| 01975 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2018 IT – Importe abonado insuf. cuota | money | reused |
| 02073 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2024 I+D – Deducción reducida | money | reused |
| 02074 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2024 I+D – Aplicado esta liquidación | money | reused |
| 02075 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2024 I+D – Importe abonado insuf. cuota | money | reused |
| 02246 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2019 I+D – Deducción reducida | money | reused |
| 02247 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2019 I+D – Aplicado esta liquidación | money | reused |
| 02248 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2019 I+D – Importe abonado insuf. cuota | money | reused |
| 02250 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2019 IT – Deducción reducida | money | reused |
| 02251 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2019 IT – Aplicado esta liquidación | money | reused |
| 02252 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2019 IT – Importe abonado insuf. cuota | money | reused |
| 02278 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2024 IT – Aplicado esta liquidación | money | reused; note: no "Deducción reducida" row for 2024 IT in this cluster |
| 02279 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2024 IT – Importe abonado insuf. cuota | money | reused |
| 02392 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2020 I+D – Deducción reducida | money | reused |
| 02393 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2020 I+D – Aplicado esta liquidación | money | reused |
| 02394 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2020 I+D – Importe abonado insuf. cuota | money | reused |
| 02396 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2020 IT – Deducción reducida | money | reused |
| 02397 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2020 IT – Aplicado esta liquidación | money | reused |
| 02398 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2020 IT – Importe abonado insuf. cuota | money | reused |
| 02710 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2023 I+D – Deducción reducida | money | reused |
| 02758 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2023 I+D – Importe abonado insuf. cuota | money | reused; no separate "Aplicado" row for 2023 I+D in cluster |
| 02760 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2023 IT – Deducción reducida | money | reused |
| 02763 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2023 IT – Importe abonado insuf. cuota | money | reused |
| 03576 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2025(*) I+D – Deducción reducida | money | reused |
| 03577 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2025(*) I+D – Aplicado esta liquidación | money | reused |
| 03578 | `is_deduccion_idi_excluida_limite_investigacion` | I+D+i excl. – 2025(*) I+D – Importe abonado insuf. cuota | money | reused |
| 03580 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2025(*) IT – Deducción reducida | money | reused |
| 03581 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2025(*) IT – Aplicado esta liquidación | money | reused |
| 03582 | `is_deduccion_idi_excluida_limite_innovacion` | I+D+i excl. – 2025(*) IT – Importe abonado insuf. cuota | money | reused |
| 00367 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2025(*) – Pendiente períodos futuros | money | new; "Pendiente" axis of Canarias film credit |
| 01310 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2022 – Aplicado | money | reused |
| 01311 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2022 – Importe abonado | money | reused |
| 01312 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2022 – Pendiente períodos futuros | money | new |
| 01314 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2023 – Aplicado | money | reused |
| 01315 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2023 – Importe abonado | money | reused |
| 01316 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2023 – Pendiente períodos futuros | money | new |
| 01932 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2015 – Aplicado | money | reused |
| 01933 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2015 – Importe abonado insuf. cuota | money | reused |
| 01939 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2016 – Aplicado | money | reused |
| 01940 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2016 – Importe abonado insuf. cuota | money | reused |
| 01941 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext – 2016 – Pendiente períodos futuros | money | new |
| 01943 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2017 – Aplicado | money | reused |
| 01944 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2017 – Importe abonado insuf. cuota | money | reused |
| 01945 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext – 2017 – Pendiente períodos futuros | money | new |
| 01947 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2018 – Aplicado | money | reused |
| 01948 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2018 – Importe abonado insuf. cuota | money | reused |
| 01949 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext – 2018 – Pendiente períodos futuros | money | new |
| 02110 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2019 – Aplicado | money | reused |
| 02111 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2019 – Importe abonado insuf. cuota | money | reused |
| 02112 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext – 2019 – Pendiente períodos futuros | money | new |
| 02129 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2020 – Aplicado | money | reused |
| 02130 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2020 – Importe abonado insuf. cuota | money | reused |
| 02131 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext – 2020 – Pendiente períodos futuros | money | new |
| 02133 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2021 – Aplicado | money | reused |
| 02134 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2021 – Importe abonado insuf. cuota | money | reused |
| 02135 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext – 2021 – Pendiente períodos futuros | money | new |
| 02137 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2022 – Aplicado | money | reused |
| 02138 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2022 – Importe abonado insuf. cuota | money | reused |
| 02139 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext – 2022 – Pendiente períodos futuros | money | new |
| 02141 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2023 – Aplicado | money | reused |
| 02142 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2023 – Importe abonado insuf. cuota | money | reused |
| 02143 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext – 2023 – Pendiente períodos futuros | money | new |
| 02149 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2015 – Aplicado | money | reused |
| 02150 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2015 – Importe abonado | money | reused |
| 02151 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2015 – Pendiente períodos futuros | money | new |
| 02153 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2016 – Aplicado | money | reused |
| 02154 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2016 – Importe abonado | money | reused |
| 02155 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2016 – Pendiente períodos futuros | money | new |
| 02157 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2017 – Aplicado | money | reused |
| 02158 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2017 – Importe abonado | money | reused |
| 02159 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2017 – Pendiente períodos futuros | money | new |
| 02161 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2018 – Aplicado | money | reused |
| 02162 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2018 – Importe abonado | money | reused |
| 02163 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2018 – Pendiente períodos futuros | money | new |
| 02165 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2019 – Aplicado | money | reused |
| 02166 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2019 – Importe abonado | money | reused |
| 02167 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2019 – Pendiente períodos futuros | money | new |
| 02169 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2020 – Aplicado | money | reused |
| 02170 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2020 – Importe abonado | money | reused |
| 02171 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2020 – Pendiente períodos futuros | money | new |
| 02173 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2021 – Aplicado | money | reused |
| 02174 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2021 – Importe abonado | money | reused |
| 02175 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2021 – Pendiente períodos futuros | money | new |
| 02355 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2024 – Aplicado | money | reused |
| 02467 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2024 – Importe abonado | money | reused |
| 02468 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2024 – Pendiente períodos futuros | money | new |
| 03536 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2025 – Aplicado | money | reused |
| 03537 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext – 2025 – Importe abonado insuf. cuota | money | reused |
| 03538 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext – 2025 – Pendiente períodos futuros | money | new |
| 03541 | `is_deduccion_cinematografica_extranjera_periodo` | Cinemaext Canarias – 2025 – Importe abonado | money | reused |
| 03542 | `is_deduccion_cinematografica_extranjera_pendiente_futuros` | Cinemaext Canarias – 2025 – Pendiente períodos futuros | money | new |
| 01271 | `is_deduccion_di_interna_tipo_gravamen` | DI interna DT23.1 – 2023 – Tipo gravamen generación | decimal | new; rate field, decimal type |
| 01343 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – Total – 2025 deducción pendiente | money | reused; total row, pending-this-year axis |
| 01346 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – Total – Deducción generada | money | reused |
| 01347 | `is_deduccion_di_interna_total` | DI interna DT23.1 – Total – Pendiente aplic. futuros | money | reused |
| 01596 | `is_deduccion_di_interna_tipo_gravamen` | DI interna DT23.1 – 2017 – Tipo gravamen generación | decimal | new |
| 01597 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – 2017 – 2025 deducción pendiente | money | reused |
| 01598 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – 2017 – Aplicado esta liquidación | money | reused |
| 01599 | `is_deduccion_di_interna_total` | DI interna DT23.1 – 2017 – Pendiente aplic. futuros | money | reused |
| 01829 | `is_deduccion_di_interna_tipo_gravamen` | DI interna DT23.1 – 2018 – Tipo gravamen generación | decimal | new |
| 01830 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – 2018 – 2025 deducción pendiente | money | reused |
| 01831 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – 2018 – Aplicado esta liquidación | money | reused |
| 01832 | `is_deduccion_di_interna_total` | DI interna DT23.1 – 2018 – Pendiente aplic. futuros | money | reused |
| 02197 | `is_deduccion_di_interna_tipo_gravamen` | DI interna DT23.1 – 2019 – Tipo gravamen generación | decimal | new |
| 02198 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – 2019 – 2025 deducción pendiente | money | reused |
| 02199 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – 2019 – Aplicado esta liquidación | money | reused |
| 02200 | `is_deduccion_di_interna_total` | DI interna DT23.1 – 2019 – Pendiente aplic. futuros | money | reused |
| 02320 | `is_deduccion_di_interna_tipo_gravamen` | DI interna DT23.1 – 2020 – Tipo gravamen generación | decimal | new |
| 02321 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – 2020 – 2025 deducción pendiente | money | reused |
| 02322 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – 2020 – Aplicado esta liquidación | money | reused |
| 02323 | `is_deduccion_di_interna_total` | DI interna DT23.1 – 2020 – Pendiente aplic. futuros | money | reused |
| 03412 | `is_deduccion_di_interna_tipo_gravamen` | DI interna DT23.1 – 2025(*) – Tipo gravamen generación | decimal | new |
| 03413 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – 2025(*) – 2025 deducción pendiente | money | reused |
| 03414 | `is_deduccion_di_interna_periodo` | DI interna DT23.1 – 2025(*) – Aplicado esta liquidación | money | reused |
| 03415 | `is_deduccion_di_interna_total` | DI interna DT23.1 – 2025(*) – Pendiente aplic. futuros | money | reused |
| 01288 | `is_deduccion_autoridades_portuarias_importe` | Autoridades portuarias art.38bis – 2020 – Pendiente | money | new; distinct concept from Copa América |
| 01290 | `is_deduccion_autoridades_portuarias_importe` | Autoridades portuarias art.38bis – 2021 – Aplicado | money | new |
| 01291 | `is_deduccion_autoridades_portuarias_importe` | Autoridades portuarias art.38bis – 2021 – Pendiente | money | new |
| 01293 | `is_deduccion_autoridades_portuarias_importe` | Autoridades portuarias art.38bis – 2022 – Aplicado | money | new |
| 01294 | `is_deduccion_autoridades_portuarias_importe` | Autoridades portuarias art.38bis – 2022 – Pendiente | money | new |
| 01296 | `is_deduccion_autoridades_portuarias_importe` | Autoridades portuarias art.38bis – 2023 – Aplicado | money | new |
| 01297 | `is_deduccion_autoridades_portuarias_importe` | Autoridades portuarias art.38bis – 2023 – Pendiente | money | new |
| 02313 | `is_deduccion_autoridades_portuarias_importe` | Autoridades portuarias art.38bis – 2024(*) – Aplicado | money | new |
| 03533 | `is_deduccion_autoridades_portuarias_importe` | Autoridades portuarias art.38bis – 2025 – Aplicado | money | new |
| 03534 | `is_deduccion_autoridades_portuarias_importe` | Autoridades portuarias art.38bis – 2025 – Pendiente | money | new |
| 00745 | `is_deduccion_dt24a1_periodificacion` | DT24ª.1 – 2025(*) Periodificación – Aplicado | money | reused |
| 00746 | `is_deduccion_dt24a1_periodificacion` | DT24ª.1 – 2025(*) Periodificación – Pendiente futuros | money | reused |
| 00750 | `is_deduccion_dt24a1_periodificacion` | DT24ª.1 – 2020 Periodificación – Aplicado | money | reused |
| 00753 | `is_deduccion_dt24a1_periodificacion` | DT24ª.1 – 2021 Periodificación – Aplicado | money | reused |
| 00754 | `is_deduccion_dt24a1_periodificacion` | DT24ª.1 – 2021 Periodificación – Pendiente futuros | money | reused |
| 00756 | `is_deduccion_dt24a1_periodificacion` | DT24ª.1 – 2022 Periodificación – Aplicado | money | reused |
| 00757 | `is_deduccion_dt24a1_periodificacion` | DT24ª.1 – 2022 Periodificación – Pendiente futuros | money | reused |
| 00759 | `is_deduccion_dt24a1_periodificacion` | DT24ª.1 – 2023 Periodificación – Aplicado | money | reused |

## Data_type divergences

One data_type divergence exists within the deducciones_doble_imposicion_interna_dt_23_1_lis section:

- **"Tipo gravamen período generación"** casillas (01271, 01596, 01829, 02197, 02320, 03412) have `data_type = decimal` while all other DI interna casillas are `money`. This is structurally correct: the tax-rate field is a percentage/decimal, not a monetary amount. The new role `is_deduccion_di_interna_tipo_gravamen` is restricted to `decimal` and must not share a role with money-typed DI interna casillas.

All other sections are internally uniform: `money` throughout deducciones_donativos, I+D+i excluidas, cinematográficas, autoridades portuarias, and DT24ª.1 clusters.

## Summary

- **Total casillas classified:** 202
- **Roles reused verbatim from existing 88-role inventory:** 10 roles — `is_deduccion_donativos_general`, `is_deduccion_donativos_prioritarias`, `is_deduccion_idi_excluida_limite_investigacion`, `is_deduccion_idi_excluida_limite_innovacion`, `is_deduccion_cinematografica_extranjera_periodo`, `is_deduccion_di_interna_periodo`, `is_deduccion_di_interna_total`, `is_deduccion_dt24a1_periodificacion`, `is_deduccion_cinematografica_pendiente_generada` (not needed here — this section has no "pendiente/generada" rows), `is_deduccion_cinematografica_extranjera_total` (not needed here — no total rows in this cluster)
- **New roles introduced:** 3
  - `is_deduccion_cinematografica_extranjera_pendiente_futuros` — carry-forward pending axis of foreign film production credit (both mainland and Canarias variants); `money`
  - `is_deduccion_di_interna_tipo_gravamen` — tax-rate field for the double-taxation credit vintage row; `decimal`
  - `is_deduccion_autoridades_portuarias_importe` — deduction for investments by port authorities (art. 38 bis LIS), all axes (applied, pending); `money`
- **Data_type divergences:** 1 — the 6 `decimal` tipo-gravamen casillas within DT23.1 rows are correctly typed and captured by the dedicated new role `is_deduccion_di_interna_tipo_gravamen`; no mixed-type sharing occurs.
- **TOML alignment note:** Existing TOML file `0415-deduccion-por-inversiones-y-gastos-realizados-por-2020.toml` uses `is_deduccion_copa_america_periodo` for casilla 01284 (autoridades portuarias). This appears to be a misclassification in the registry — Copa América (art. 36 Ley 14/2010) and autoridades portuarias (art. 38 bis LIS) are distinct deduction types. The new role `is_deduccion_autoridades_portuarias_importe` correctly reflects the section label. The misclassification is out of scope for this read-only audit but should be corrected in a subsequent hardening pass.
