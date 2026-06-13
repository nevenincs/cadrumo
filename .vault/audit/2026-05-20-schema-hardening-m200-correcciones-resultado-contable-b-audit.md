---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# schema-hardening m200 correcciones-resultado-contable-b role assignments

## Scope

Cluster: `correcciones-resultado-contable-b`
Source: `.vault-scratch/m200-clusters/correcciones-resultado-contable-b.json`
Total casillas classified: 117
Revision: `2024-y-siguientes` (single revision, no id reuse)

The cluster spans 30 distinct LIS-article adjustment sections plus two structural outlier sections. The dominant pattern is a repeating 8-field symmetric block per section, decomposed along two axes:

- **direction**: `aumento` / `disminucion`
- **field type**: saldo_inicial (saldo a principio), corrección permanente, corrección temporaria origen ejercicio, corrección temporaria origen anteriores, saldo_final (saldo a fin)

Role naming convention follows `is_correccion_<concept>_<field_type>_<direction>`, where `<concept>` is the stable tax term derived from the LIS-article section key. For structural outlier casillas outside the standard block (detalle subtable, gastos-financieros carry-forward, personal asalariado) the existing roles from `_existing-roles.txt` are reused verbatim.

No sibling audit `2026-05-20-schema-hardening-m200-correcciones-resultado-contable-a.md` existed at classification time; this document establishes the naming baseline for both halves.

## Role assignments

| id | role | label_snippet | data_type | notes |
|----|------|---------------|-----------|-------|
| 01733 | `is_correccion_deterioro_participaciones_dt16_permanente_disminucion` | DT 16ª.3 LIS - Disminución - Correccion (Permanente) | money | DT16.3 asymmetric block, permanente field |
| 01734 | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_disminucion` | DT 16ª.3 LIS - Disminución - Correccion (Temporaria origen ejercicio) | money | DT16.3 asymmetric block, temporaria campo |
| 01735 | `is_correccion_deterioro_participaciones_dt16_saldo_final_disminucion` | DT 16ª.3 LIS - Disminución - Saldo pe(ndiente fin) | money | DT16.3 asymmetric block, saldo final |
| 01861 | `is_correccion_deterioro_participaciones_dt16_permanente_aumento` | DT 16ª.1 y 2 LIS - Aumento - Correc. Permanentes | money | DT16.1/2 full block |
| 01862 | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_aumento` | DT 16ª.1 y 2 LIS - Aumento - Temporarias origen ejercicio | money | DT16.1/2 full block |
| 01863 | `is_correccion_deterioro_participaciones_dt16_temporaria_anterior_aumento` | DT 16ª.1 y 2 LIS - Aumento - Temporarias origen anteriores | money | DT16.1/2 full block |
| 01864 | `is_correccion_deterioro_participaciones_dt16_saldo_final_aumento` | DT 16ª.1 y 2 LIS - Aumento - Saldo fin | money | DT16.1/2 full block |
| 01866 | `is_correccion_deterioro_participaciones_dt16_permanente_disminucion` | DT 16ª.1 y 2 LIS - Disminución - Corr. Permanentes | money | DT16.1/2 full block; shares role with 01733 — same semantic position |
| 01867 | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_disminucion` | DT 16ª.1 y 2 LIS - Disminución - Temporarias origen ejercicio | money | DT16.1/2 full block; shares role with 01734 |
| 01868 | `is_correccion_deterioro_participaciones_dt16_temporaria_anterior_disminucion` | DT 16ª.1 y 2 LIS - Disminución - Temporarias origen anteriores | money | DT16.1/2 full block |
| 01869 | `is_correccion_deterioro_participaciones_dt16_saldo_final_disminucion` | DT 16ª.1 y 2 LIS - Disminución - Saldo fin | money | DT16.1/2 full block; shares role with 01735 |
| 01996 | `is_correccion_deterioro_participaciones_dt16_permanente_aumento` | DT 16ª.3 LIS - Aumento - Correc. Permanentes | money | DT16.3 asymmetric block, single aumento entry; shares role with 01861 |
| 01104 | `is_gastos_financieros_adicion_aplicado` | Pendiente adición límite beneficio operativo 2022 - Aplicado | money | Art.16 carry-forward; generation 2022; reused role |
| 01105 | `is_gastos_financieros_adicion_pendiente` | Pendiente adición límite beneficio operativo 2022 - Pendiente | money | Art.16 carry-forward; generation 2022; reused role |
| 01399 | `is_gastos_financieros_adicion_aplicado` | Pendiente adición límite beneficio operativo 2023 - Aplicado | money | Generation 2023 |
| 01400 | `is_gastos_financieros_adicion_pendiente` | Pendiente adición límite beneficio operativo 2023 - Pendiente | money | Generation 2023 |
| 02259 | `is_gastos_financieros_adicion_aplicado` | Pendiente adición límite beneficio operativo 2020 - Aplicado | money | Generation 2020 |
| 02405 | `is_gastos_financieros_adicion_aplicado` | Pendiente adición límite beneficio operativo 2021 - Aplicado | money | Generation 2021 |
| 02406 | `is_gastos_financieros_adicion_pendiente` | Pendiente adición límite beneficio operativo 2021 - Pendiente | money | Generation 2021 |
| 02770 | `is_gastos_financieros_adicion_aplicado` | Pendiente adición límite beneficio operativo 2024 - Aplicado | money | Generation 2024 |
| 03589 | `is_gastos_financieros_adicion_aplicado` | Pendiente adición límite beneficio operativo 2025 - Aplicado | money | Generation 2025 |
| 03590 | `is_gastos_financieros_adicion_pendiente` | Pendiente adición límite beneficio operativo 2025 - Pendiente | money | Generation 2025 |
| 02177 | `is_correccion_copa_america_permanente_aumento` | Copa América - Aumento - Permanentes | money | Ley 31/2022 |
| 02178 | `is_correccion_copa_america_temporaria_ejercicio_aumento` | Copa América - Aumento - Temporarias origen ejercicio | money | |
| 02179 | `is_correccion_copa_america_temporaria_anterior_aumento` | Copa América - Aumento - Temporarias origen anteriores | money | |
| 02180 | `is_correccion_copa_america_saldo_final_aumento` | Copa América - Aumento - Saldo pendiente fin | money | |
| 02290 | `is_correccion_copa_america_permanente_disminucion` | Copa América - Disminución - Permanentes | money | |
| 02291 | `is_correccion_copa_america_temporaria_ejercicio_disminucion` | Copa América - Disminución - Temporarias origen ejercicio | money | |
| 02292 | `is_correccion_copa_america_temporaria_anterior_disminucion` | Copa América - Disminución - Temporarias origen anteriores | money | |
| 02293 | `is_correccion_copa_america_saldo_final_disminucion` | Copa América - Disminución - Saldo pendiente fin | money | |
| 02502 | `is_correccion_cambio_criterio_contable_temporaria_ejercicio_aumento` | Cambio criterios contables art.11.3.2 - Aumento - Temporarias origen ejercicio | money | Only temporaria entries (no permanente field in this block) |
| 02503 | `is_correccion_cambio_criterio_contable_temporaria_anterior_aumento` | Cambio criterios contables art.11.3.2 - Aumento - Temporarias origen anteriores | money | |
| 02504 | `is_correccion_cambio_criterio_contable_saldo_inicial_aumento` | Cambio criterios contables art.11.3.2 - Aumento - Saldo principio | money | |
| 02505 | `is_correccion_cambio_criterio_contable_saldo_final_aumento` | Cambio criterios contables art.11.3.2 - Aumento - Saldo fin | money | |
| 02507 | `is_correccion_cambio_criterio_contable_temporaria_ejercicio_disminucion` | Cambio criterios contables art.11.3.2 - Disminución - Temporarias origen ejercicio | money | |
| 02508 | `is_correccion_cambio_criterio_contable_temporaria_anterior_disminucion` | Cambio criterios contables art.11.3.2 - Disminución - Temporarias origen anteriores | money | |
| 02509 | `is_correccion_cambio_criterio_contable_saldo_inicial_disminucion` | Cambio criterios contables art.11.3.2 - Disminución - Saldo principio | money | |
| 02510 | `is_correccion_cambio_criterio_contable_saldo_final_disminucion` | Cambio criterios contables art.11.3.2 - Disminución - Saldo fin | money | |
| 02512 | `is_correccion_operaciones_plazos_temporaria_ejercicio_aumento` | Operaciones plazos art.11.4 - Aumento - Temporarias origen ejercicio | money | |
| 02513 | `is_correccion_operaciones_plazos_temporaria_anterior_aumento` | Operaciones plazos art.11.4 - Aumento - Temporarias origen anteriores | money | |
| 02514 | `is_correccion_operaciones_plazos_saldo_inicial_aumento` | Operaciones plazos art.11.4 - Aumento - Saldo principio | money | |
| 02515 | `is_correccion_operaciones_plazos_saldo_final_aumento` | Operaciones plazos art.11.4 - Aumento - Saldo fin | money | |
| 02517 | `is_correccion_operaciones_plazos_temporaria_ejercicio_disminucion` | Operaciones plazos art.11.4 - Disminución - Temporarias origen ejercicio | money | |
| 02518 | `is_correccion_operaciones_plazos_temporaria_anterior_disminucion` | Operaciones plazos art.11.4 - Disminución - Temporarias origen anteriores | money | |
| 02519 | `is_correccion_operaciones_plazos_saldo_inicial_disminucion` | Operaciones plazos art.11.4 - Disminución - Saldo principio | money | |
| 02520 | `is_correccion_operaciones_plazos_saldo_final_disminucion` | Operaciones plazos art.11.4 - Disminución - Saldo fin | money | |
| 02522 | `is_correccion_reversion_deterioro_temporaria_ejercicio_aumento` | Reversión deterioro art.11.6 - Aumento - Temporarias origen ejercicio | money | |
| 02523 | `is_correccion_reversion_deterioro_temporaria_anterior_aumento` | Reversión deterioro art.11.6 - Aumento - Temporarias origen anteriores | money | |
| 02524 | `is_correccion_reversion_deterioro_saldo_inicial_aumento` | Reversión deterioro art.11.6 - Aumento - Saldo principio | money | |
| 02525 | `is_correccion_reversion_deterioro_saldo_final_aumento` | Reversión deterioro art.11.6 - Aumento - Saldo fin | money | |
| 02527 | `is_correccion_reversion_deterioro_temporaria_ejercicio_disminucion` | Reversión deterioro art.11.6 - Disminución - Temporarias origen ejercicio | money | |
| 02528 | `is_correccion_reversion_deterioro_temporaria_anterior_disminucion` | Reversión deterioro art.11.6 - Disminución - Temporarias origen anteriores | money | |
| 02529 | `is_correccion_reversion_deterioro_saldo_inicial_disminucion` | Reversión deterioro art.11.6 - Disminución - Saldo principio | money | |
| 02530 | `is_correccion_reversion_deterioro_saldo_final_disminucion` | Reversión deterioro art.11.6 - Disminución - Saldo fin | money | |
| 02532 | `is_correccion_rentas_negativas_temporaria_ejercicio_aumento` | Rentas negativas art.11.9/11.10 - Aumento - Temporarias origen ejercicio | money | |
| 02533 | `is_correccion_rentas_negativas_temporaria_anterior_aumento` | Rentas negativas art.11.9/11.10 - Aumento - Temporarias origen anteriores | money | |
| 02534 | `is_correccion_rentas_negativas_saldo_inicial_aumento` | Rentas negativas art.11.9/11.10 - Aumento - Saldo principio | money | |
| 02535 | `is_correccion_rentas_negativas_saldo_final_aumento` | Rentas negativas art.11.9/11.10 - Aumento - Saldo fin | money | Label includes "Temporarias (con origen en ejerc." — saldo field |
| 02537 | `is_correccion_rentas_negativas_temporaria_ejercicio_disminucion` | Rentas negativas art.11.9/11.10 - Disminución - Temporarias origen ejercicio | money | |
| 02538 | `is_correccion_rentas_negativas_temporaria_anterior_disminucion` | Rentas negativas art.11.9/11.10 - Disminución - Temporarias origen anteriores | money | |
| 02539 | `is_correccion_rentas_negativas_saldo_inicial_disminucion` | Rentas negativas art.11.9/11.10 - Disminución - Saldo principio | money | |
| 02540 | `is_correccion_rentas_negativas_saldo_final_disminucion` | Rentas negativas art.11.9/11.10 - Disminución - Saldo fin | money | |
| 02552 | `is_correccion_otras_dif_imputacion_temporal_temporaria_ejercicio_aumento` | Otras diferencias imputación temporal art.11 - Aumento - Temporarias origen ejercicio | money | |
| 02553 | `is_correccion_otras_dif_imputacion_temporal_temporaria_anterior_aumento` | Otras diferencias imputación temporal art.11 - Aumento - Temporarias origen anteriores | money | |
| 02554 | `is_correccion_otras_dif_imputacion_temporal_saldo_inicial_aumento` | Otras diferencias imputación temporal art.11 - Aumento - Saldo principio | money | |
| 02555 | `is_correccion_otras_dif_imputacion_temporal_saldo_final_aumento` | Otras diferencias imputación temporal art.11 - Aumento - Saldo fin | money | |
| 02557 | `is_correccion_otras_dif_imputacion_temporal_temporaria_ejercicio_disminucion` | Otras diferencias imputación temporal art.11 - Disminución - Temporarias origen ejercicio | money | |
| 02558 | `is_correccion_otras_dif_imputacion_temporal_temporaria_anterior_disminucion` | Otras diferencias imputación temporal art.11 - Disminución - Temporarias origen anteriores | money | |
| 02559 | `is_correccion_otras_dif_imputacion_temporal_saldo_inicial_disminucion` | Otras diferencias imputación temporal art.11 - Disminución - Saldo principio | money | |
| 02560 | `is_correccion_otras_dif_imputacion_temporal_saldo_final_disminucion` | Otras diferencias imputación temporal art.11 - Disminución - Saldo fin | money | |
| 02572 | `is_correccion_asimetrias_hibridas_temporaria_ejercicio_aumento` | Asimetrías híbridas art.15 bis (excl. 15 bis.12) - Aumento - Temporarias origen ejercicio | money | |
| 02573 | `is_correccion_asimetrias_hibridas_temporaria_anterior_aumento` | Asimetrías híbridas art.15 bis - Aumento - Temporarias origen anteriores | money | |
| 02574 | `is_correccion_asimetrias_hibridas_saldo_inicial_aumento` | Asimetrías híbridas art.15 bis - Aumento - Saldo principio | money | |
| 02575 | `is_correccion_asimetrias_hibridas_saldo_final_aumento` | Asimetrías híbridas art.15 bis - Aumento - Saldo fin | money | |
| 02752 | `is_correccion_asimetrias_hibridas_temporaria_ejercicio_disminucion` | Asimetrías híbridas art.15 bis - Disminución - Temporarias origen ejercicio | money | |
| 02753 | `is_correccion_asimetrias_hibridas_temporaria_anterior_disminucion` | Asimetrías híbridas art.15 bis - Disminución - Temporarias origen anteriores | money | |
| 02754 | `is_correccion_asimetrias_hibridas_saldo_inicial_disminucion` | Asimetrías híbridas art.15 bis - Disminución - Saldo principio | money | |
| 02755 | `is_correccion_asimetrias_hibridas_saldo_final_disminucion` | Asimetrías híbridas art.15 bis - Disminución - Saldo fin | money | |
| 02592 | `is_correccion_amortizacion_idi_temporaria_ejercicio_aumento` | Amortización inmovilizado IDI art.12.3b - Aumento - Temporarias origen ejercicio | money | |
| 02593 | `is_correccion_amortizacion_idi_temporaria_anterior_aumento` | Amortización inmovilizado IDI art.12.3b - Aumento - Temporarias origen anteriores | money | |
| 02594 | `is_correccion_amortizacion_idi_saldo_inicial_aumento` | Amortización inmovilizado IDI art.12.3b - Aumento - Saldo principio | money | |
| 02595 | `is_correccion_amortizacion_idi_saldo_final_aumento` | Amortización inmovilizado IDI art.12.3b - Aumento - Saldo fin | money | |
| 02597 | `is_correccion_amortizacion_idi_temporaria_ejercicio_disminucion` | Amortización inmovilizado IDI art.12.3b - Disminución - Temporarias origen ejercicio | money | |
| 02598 | `is_correccion_amortizacion_idi_temporaria_anterior_disminucion` | Amortización inmovilizado IDI art.12.3b - Disminución - Temporarias origen anteriores | money | |
| 02599 | `is_correccion_amortizacion_idi_saldo_inicial_disminucion` | Amortización inmovilizado IDI art.12.3b - Disminución - Saldo principio | money | |
| 02600 | `is_correccion_amortizacion_idi_saldo_final_disminucion` | Amortización inmovilizado IDI art.12.3b - Disminución - Saldo fin | money | |
| 02612 | `is_correccion_libertad_amortizacion_inmovilizado_temporaria_ejercicio_aumento` | Libertad amortización IM nuevo art.12.3e - Aumento - Temporarias origen ejercicio | money | |
| 02613 | `is_correccion_libertad_amortizacion_inmovilizado_temporaria_anterior_aumento` | Libertad amortización IM nuevo art.12.3e - Aumento - Temporarias origen anteriores | money | |
| 02614 | `is_correccion_libertad_amortizacion_inmovilizado_saldo_inicial_aumento` | Libertad amortización IM nuevo art.12.3e - Aumento - Saldo principio | money | |
| 02615 | `is_correccion_libertad_amortizacion_inmovilizado_saldo_final_aumento` | Libertad amortización IM nuevo art.12.3e - Aumento - Saldo fin | money | |
| 02617 | `is_correccion_libertad_amortizacion_inmovilizado_temporaria_ejercicio_disminucion` | Libertad amortización IM nuevo art.12.3e - Disminución - Temporarias origen ejercicio | money | |
| 02618 | `is_correccion_libertad_amortizacion_inmovilizado_temporaria_anterior_disminucion` | Libertad amortización IM nuevo art.12.3e - Disminución - Temporarias origen anteriores | money | |
| 02619 | `is_correccion_libertad_amortizacion_inmovilizado_saldo_inicial_disminucion` | Libertad amortización IM nuevo art.12.3e - Disminución - Saldo principio | money | |
| 02620 | `is_correccion_libertad_amortizacion_inmovilizado_saldo_final_disminucion` | Libertad amortización IM nuevo art.12.3e - Disminución - Saldo fin | money | |
| 02632 | `is_correccion_libertad_amortizacion_empleo_temporaria_ejercicio_aumento` | Libertad amortización empleo RDL 6/2010 - Aumento - Temporarias origen ejercicio | money | |
| 02633 | `is_correccion_libertad_amortizacion_empleo_temporaria_anterior_aumento` | Libertad amortización empleo RDL 6/2010 - Aumento - Temporarias origen anteriores | money | |
| 02634 | `is_correccion_libertad_amortizacion_empleo_saldo_inicial_aumento` | Libertad amortización empleo RDL 6/2010 - Aumento - Saldo principio | money | |
| 02635 | `is_correccion_libertad_amortizacion_empleo_saldo_final_aumento` | Libertad amortización empleo RDL 6/2010 - Aumento - Saldo fin | money | |
| 02637 | `is_correccion_libertad_amortizacion_empleo_temporaria_ejercicio_disminucion` | Libertad amortización empleo RDL 6/2010 - Disminución - Temporarias origen ejercicio | money | |
| 02638 | `is_correccion_libertad_amortizacion_empleo_temporaria_anterior_disminucion` | Libertad amortización empleo RDL 6/2010 - Disminución - Temporarias origen anteriores | money | |
| 02639 | `is_correccion_libertad_amortizacion_empleo_saldo_inicial_disminucion` | Libertad amortización empleo RDL 6/2010 - Disminución - Saldo principio | money | |
| 02640 | `is_correccion_libertad_amortizacion_empleo_saldo_final_disminucion` | Libertad amortización empleo RDL 6/2010 - Disminución - Saldo fin | money | |
| 02652 | `is_correccion_deterioro_art13_1_temporaria_ejercicio_aumento` | Deterioro art.13.1 (no art.11.12/DT33.1) - Aumento - Temporarias origen ejercicio | money | |
| 02653 | `is_correccion_deterioro_art13_1_temporaria_anterior_aumento` | Deterioro art.13.1 - Aumento - Temporarias origen anteriores | money | |
| 02654 | `is_correccion_deterioro_art13_1_saldo_inicial_aumento` | Deterioro art.13.1 - Aumento - Saldo principio | money | |
| 02655 | `is_correccion_deterioro_art13_1_saldo_final_aumento` | Deterioro art.13.1 - Aumento - Saldo fin | money | |
| 02657 | `is_correccion_deterioro_art13_1_temporaria_ejercicio_disminucion` | Deterioro art.13.1 - Disminución - Temporarias origen ejercicio | money | |
| 02658 | `is_correccion_deterioro_art13_1_temporaria_anterior_disminucion` | Deterioro art.13.1 - Disminución - Temporarias origen anteriores | money | |
| 02659 | `is_correccion_deterioro_art13_1_saldo_inicial_disminucion` | Deterioro art.13.1 - Disminución - Saldo principio | money | |
| 02660 | `is_correccion_deterioro_art13_1_saldo_final_disminucion` | Deterioro art.13.1 - Disminución - Saldo fin | money | |
| 02672 | `is_correccion_deterioro_inmovilizado_fondo_comercio_temporaria_ejercicio_aumento` | Deterioro IM/inv.inmobiliarias/II fondo de comercio art.13.2a/DT15 - Aumento - Temporarias origen ejercicio | money | |
| 02673 | `is_correccion_deterioro_inmovilizado_fondo_comercio_temporaria_anterior_aumento` | Deterioro IM/fondo comercio art.13.2a - Aumento - Temporarias origen anteriores | money | |
| 02674 | `is_correccion_deterioro_inmovilizado_fondo_comercio_saldo_inicial_aumento` | Deterioro IM/fondo comercio art.13.2a - Aumento - Saldo principio | money | |
| 02675 | `is_correccion_deterioro_inmovilizado_fondo_comercio_saldo_final_aumento` | Deterioro IM/fondo comercio art.13.2a - Aumento - Saldo fin | money | |
| 02677 | `is_correccion_deterioro_inmovilizado_fondo_comercio_temporaria_ejercicio_disminucion` | Deterioro IM/fondo comercio art.13.2a - Disminución - Temporarias origen ejercicio | money | |
| 02678 | `is_correccion_deterioro_inmovilizado_fondo_comercio_temporaria_anterior_disminucion` | Deterioro IM/fondo comercio art.13.2a - Disminución - Temporarias origen anteriores | money | |
| 02679 | `is_correccion_deterioro_inmovilizado_fondo_comercio_saldo_inicial_disminucion` | Deterioro IM/fondo comercio art.13.2a - Disminución - Saldo principio | money | |
| 02680 | `is_correccion_deterioro_inmovilizado_fondo_comercio_saldo_final_disminucion` | Deterioro IM/fondo comercio art.13.2a - Disminución - Saldo fin | money | |
| 02712 | `is_correccion_deterioro_valores_deuda_temporaria_ejercicio_aumento` | Deterioro valores deuda art.13.2c/DT15 - Aumento - Temporarias origen ejercicio | money | |
| 02713 | `is_correccion_deterioro_valores_deuda_temporaria_anterior_aumento` | Deterioro valores deuda art.13.2c - Aumento - Temporarias origen anteriores | money | |
| 02714 | `is_correccion_deterioro_valores_deuda_saldo_inicial_aumento` | Deterioro valores deuda art.13.2c - Aumento - Saldo principio | money | |
| 02715 | `is_correccion_deterioro_valores_deuda_saldo_final_aumento` | Deterioro valores deuda art.13.2c - Aumento - Saldo fin | money | |
| 02717 | `is_correccion_deterioro_valores_deuda_temporaria_ejercicio_disminucion` | Deterioro valores deuda art.13.2c - Disminución - Temporarias origen ejercicio | money | |
| 02718 | `is_correccion_deterioro_valores_deuda_temporaria_anterior_disminucion` | Deterioro valores deuda art.13.2c - Disminución - Temporarias origen anteriores | money | |
| 02719 | `is_correccion_deterioro_valores_deuda_saldo_inicial_disminucion` | Deterioro valores deuda art.13.2c - Disminución - Saldo principio | money | |
| 02720 | `is_correccion_deterioro_valores_deuda_saldo_final_disminucion` | Deterioro valores deuda art.13.2c - Disminución - Saldo fin | money | |
| 02732 | `is_correccion_provisiones_pensiones_temporaria_ejercicio_aumento` | Provisiones pensiones art.14.1/14.6/14.8 - Aumento - Temporarias origen ejercicio | money | |
| 02733 | `is_correccion_provisiones_pensiones_temporaria_anterior_aumento` | Provisiones pensiones art.14.1/14.6/14.8 - Aumento - Temporarias origen anteriores | money | |
| 02734 | `is_correccion_provisiones_pensiones_saldo_inicial_aumento` | Provisiones pensiones art.14.1/14.6/14.8 - Aumento - Saldo principio | money | |
| 02735 | `is_correccion_provisiones_pensiones_saldo_final_aumento` | Provisiones pensiones art.14.1/14.6/14.8 - Aumento - Saldo fin | money | |
| 02737 | `is_correccion_provisiones_pensiones_temporaria_ejercicio_disminucion` | Provisiones pensiones art.14.1/14.6/14.8 - Disminución - Temporarias origen ejercicio | money | |
| 02738 | `is_correccion_provisiones_pensiones_temporaria_anterior_disminucion` | Provisiones pensiones art.14.1/14.6/14.8 - Disminución - Temporarias origen anteriores | money | |
| 02739 | `is_correccion_provisiones_pensiones_saldo_inicial_disminucion` | Provisiones pensiones art.14.1/14.6/14.8 - Disminución - Saldo principio | money | |
| 02740 | `is_correccion_provisiones_pensiones_saldo_final_disminucion` | Provisiones pensiones art.14.1/14.6/14.8 - Disminución - Saldo fin | money | |
| 02812 | `is_correccion_jurisdicciones_no_cooperativas_temporaria_ejercicio_aumento` | Jurisdicciones no cooperativas art.15g - Aumento - Temporarias origen ejercicio | money | |
| 02813 | `is_correccion_jurisdicciones_no_cooperativas_temporaria_anterior_aumento` | Jurisdicciones no cooperativas art.15g - Aumento - Temporarias origen anteriores | money | |
| 02814 | `is_correccion_jurisdicciones_no_cooperativas_saldo_inicial_aumento` | Jurisdicciones no cooperativas art.15g - Aumento - Saldo principio | money | |
| 02815 | `is_correccion_jurisdicciones_no_cooperativas_saldo_final_aumento` | Jurisdicciones no cooperativas art.15g - Aumento - Saldo fin | money | |
| 02817 | `is_correccion_jurisdicciones_no_cooperativas_temporaria_ejercicio_disminucion` | Jurisdicciones no cooperativas art.15g - Disminución - Temporarias origen ejercicio | money | |
| 02818 | `is_correccion_jurisdicciones_no_cooperativas_temporaria_anterior_disminucion` | Jurisdicciones no cooperativas art.15g - Disminución - Temporarias origen anteriores | money | |
| 02819 | `is_correccion_jurisdicciones_no_cooperativas_saldo_inicial_disminucion` | Jurisdicciones no cooperativas art.15g - Disminución - Saldo principio | money | |
| 02820 | `is_correccion_jurisdicciones_no_cooperativas_saldo_final_disminucion` | Jurisdicciones no cooperativas art.15g - Disminución - Saldo fin | money | |
| 02862 | `is_correccion_valor_razonable_temporaria_ejercicio_aumento` | Disminución valor razonable art.15l - Aumento - Temporarias origen ejercicio | money | |
| 02863 | `is_correccion_valor_razonable_temporaria_anterior_aumento` | Disminución valor razonable art.15l - Aumento - Temporarias origen anteriores | money | |
| 02864 | `is_correccion_valor_razonable_saldo_inicial_aumento` | Disminución valor razonable art.15l - Aumento - Saldo principio | money | |
| 02865 | `is_correccion_valor_razonable_saldo_final_aumento` | Disminución valor razonable art.15l - Aumento - Saldo fin | money | |
| 02867 | `is_correccion_valor_razonable_temporaria_ejercicio_disminucion` | Disminución valor razonable art.15l - Disminución - Temporarias origen ejercicio | money | |
| 02868 | `is_correccion_valor_razonable_temporaria_anterior_disminucion` | Disminución valor razonable art.15l - Disminución - Temporarias origen anteriores | money | |
| 02869 | `is_correccion_valor_razonable_saldo_inicial_disminucion` | Disminución valor razonable art.15l - Disminución - Saldo principio | money | |
| 02870 | `is_correccion_valor_razonable_saldo_final_disminucion` | Disminución valor razonable art.15l - Disminución - Saldo fin | money | |
| 02882 | `is_correccion_limitacion_gastos_financieros_temporaria_ejercicio_aumento` | Limitación gastos financieros art.16 - Aumento - Temporarias origen ejercicio | money | |
| 02883 | `is_correccion_limitacion_gastos_financieros_temporaria_anterior_aumento` | Limitación gastos financieros art.16 - Aumento - Temporarias origen anteriores | money | |
| 02884 | `is_correccion_limitacion_gastos_financieros_saldo_inicial_aumento` | Limitación gastos financieros art.16 - Aumento - Saldo principio | money | |
| 02885 | `is_correccion_limitacion_gastos_financieros_saldo_final_aumento` | Limitación gastos financieros art.16 - Aumento - Saldo fin | money | |
| 02887 | `is_correccion_limitacion_gastos_financieros_temporaria_ejercicio_disminucion` | Limitación gastos financieros art.16 - Disminución - Temporarias origen ejercicio | money | |
| 02888 | `is_correccion_limitacion_gastos_financieros_temporaria_anterior_disminucion` | Limitación gastos financieros art.16 - Disminución - Temporarias origen anteriores | money | |
| 02889 | `is_correccion_limitacion_gastos_financieros_saldo_inicial_disminucion` | Limitación gastos financieros art.16 - Disminución - Saldo principio | money | |
| 02890 | `is_correccion_limitacion_gastos_financieros_saldo_final_disminucion` | Limitación gastos financieros art.16 - Disminución - Saldo fin | money | |
| 02902 | `is_correccion_ampliacion_capital_compensacion_creditos_temporaria_ejercicio_aumento` | Ampliación capital compensación créditos art.17.2 - Aumento - Temporarias origen ejercicio | money | |
| 02903 | `is_correccion_ampliacion_capital_compensacion_creditos_temporaria_anterior_aumento` | Ampliación capital compensación créditos art.17.2 - Aumento - Temporarias origen anteriores | money | |
| 02904 | `is_correccion_ampliacion_capital_compensacion_creditos_saldo_inicial_aumento` | Ampliación capital compensación créditos art.17.2 - Aumento - Saldo principio | money | |
| 02905 | `is_correccion_ampliacion_capital_compensacion_creditos_saldo_final_aumento` | Ampliación capital compensación créditos art.17.2 - Aumento - Saldo fin | money | |
| 02907 | `is_correccion_ampliacion_capital_compensacion_creditos_temporaria_ejercicio_disminucion` | Ampliación capital compensación créditos art.17.2 - Disminución - Temporarias origen ejercicio | money | |
| 02908 | `is_correccion_ampliacion_capital_compensacion_creditos_temporaria_anterior_disminucion` | Ampliación capital compensación créditos art.17.2 - Disminución - Temporarias origen anteriores | money | |
| 02909 | `is_correccion_ampliacion_capital_compensacion_creditos_saldo_inicial_disminucion` | Ampliación capital compensación créditos art.17.2 - Disminución - Saldo principio | money | |
| 02910 | `is_correccion_ampliacion_capital_compensacion_creditos_saldo_final_disminucion` | Ampliación capital compensación créditos art.17.2 - Disminución - Saldo fin | money | |
| 02932 | `is_correccion_operaciones_vinculadas_temporaria_ejercicio_aumento` | Operaciones vinculadas valor mercado art.18 - Aumento - Temporarias origen ejercicio | money | |
| 02933 | `is_correccion_operaciones_vinculadas_temporaria_anterior_aumento` | Operaciones vinculadas valor mercado art.18 - Aumento - Temporarias origen anteriores | money | |
| 02934 | `is_correccion_operaciones_vinculadas_saldo_inicial_aumento` | Operaciones vinculadas valor mercado art.18 - Aumento - Saldo principio | money | |
| 02935 | `is_correccion_operaciones_vinculadas_saldo_final_aumento` | Operaciones vinculadas valor mercado art.18 - Aumento - Saldo fin | money | |
| 02937 | `is_correccion_operaciones_vinculadas_temporaria_ejercicio_disminucion` | Operaciones vinculadas valor mercado art.18 - Disminución - Temporarias origen ejercicio | money | |
| 02938 | `is_correccion_operaciones_vinculadas_temporaria_anterior_disminucion` | Operaciones vinculadas valor mercado art.18 - Disminución - Temporarias origen anteriores | money | |
| 02939 | `is_correccion_operaciones_vinculadas_saldo_inicial_disminucion` | Operaciones vinculadas valor mercado art.18 - Disminución - Saldo principio | money | |
| 02940 | `is_correccion_operaciones_vinculadas_saldo_final_disminucion` | Operaciones vinculadas valor mercado art.18 - Disminución - Saldo fin | money | |
| 03032 | `is_correccion_reduccion_rentas_intangibles_temporaria_ejercicio_aumento` | Reducción rentas intangibles art.23 - Aumento - Temporarias origen ejercicio | money | |
| 03033 | `is_correccion_reduccion_rentas_intangibles_temporaria_anterior_aumento` | Reducción rentas intangibles art.23 - Aumento - Temporarias origen anteriores | money | |
| 03034 | `is_correccion_reduccion_rentas_intangibles_saldo_inicial_aumento` | Reducción rentas intangibles art.23 - Aumento - Saldo principio | money | |
| 03035 | `is_correccion_reduccion_rentas_intangibles_saldo_final_aumento` | Reducción rentas intangibles art.23 - Aumento - Saldo fin | money | |
| 03037 | `is_correccion_reduccion_rentas_intangibles_temporaria_ejercicio_disminucion` | Reducción rentas intangibles art.23 - Disminución - Temporarias origen ejercicio | money | |
| 03038 | `is_correccion_reduccion_rentas_intangibles_temporaria_anterior_disminucion` | Reducción rentas intangibles art.23 - Disminución - Temporarias origen anteriores | money | |
| 03039 | `is_correccion_reduccion_rentas_intangibles_saldo_inicial_disminucion` | Reducción rentas intangibles art.23 - Disminución - Saldo principio | money | |
| 03040 | `is_correccion_reduccion_rentas_intangibles_saldo_final_disminucion` | Reducción rentas intangibles art.23 - Disminución - Saldo fin | money | |
| 03122 | `is_correccion_bin_grupo_fiscal_transmitida_temporaria_ejercicio_aumento` | BINs grupo fiscal entidad transmitida art.62.2 - Aumento - Temporarias origen ejercicio | money | |
| 03123 | `is_correccion_bin_grupo_fiscal_transmitida_temporaria_anterior_aumento` | BINs grupo fiscal entidad transmitida art.62.2 - Aumento - Temporarias origen anteriores | money | |
| 03124 | `is_correccion_bin_grupo_fiscal_transmitida_saldo_inicial_aumento` | BINs grupo fiscal entidad transmitida art.62.2 - Aumento - Saldo principio | money | |
| 03125 | `is_correccion_bin_grupo_fiscal_transmitida_saldo_final_aumento` | BINs grupo fiscal entidad transmitida art.62.2 - Aumento - Saldo fin | money | |
| 03127 | `is_correccion_bin_grupo_fiscal_transmitida_temporaria_ejercicio_disminucion` | BINs grupo fiscal entidad transmitida art.62.2 - Disminución - Temporarias origen ejercicio | money | |
| 03128 | `is_correccion_bin_grupo_fiscal_transmitida_temporaria_anterior_disminucion` | BINs grupo fiscal entidad transmitida art.62.2 - Disminución - Temporarias origen anteriores | money | |
| 03129 | `is_correccion_bin_grupo_fiscal_transmitida_saldo_inicial_disminucion` | BINs grupo fiscal entidad transmitida art.62.2 - Disminución - Saldo principio | money | |
| 03130 | `is_correccion_bin_grupo_fiscal_transmitida_saldo_final_disminucion` | BINs grupo fiscal entidad transmitida art.62.2 - Disminución - Saldo fin | money | |
| 03262 | `is_correccion_aportaciones_esfl_temporaria_ejercicio_aumento` | Aportaciones entidades sin fines lucrativos - Aumento - Temporarias origen ejercicio | money | |
| 03263 | `is_correccion_aportaciones_esfl_temporaria_anterior_aumento` | Aportaciones entidades sin fines lucrativos - Aumento - Temporarias origen anteriores | money | |
| 03264 | `is_correccion_aportaciones_esfl_saldo_inicial_aumento` | Aportaciones entidades sin fines lucrativos - Aumento - Saldo principio | money | |
| 03265 | `is_correccion_aportaciones_esfl_saldo_final_aumento` | Aportaciones entidades sin fines lucrativos - Aumento - Saldo fin | money | |
| 03267 | `is_correccion_aportaciones_esfl_temporaria_ejercicio_disminucion` | Aportaciones entidades sin fines lucrativos - Disminución - Temporarias origen ejercicio | money | |
| 03268 | `is_correccion_aportaciones_esfl_temporaria_anterior_disminucion` | Aportaciones entidades sin fines lucrativos - Disminución - Temporarias origen anteriores | money | |
| 03269 | `is_correccion_aportaciones_esfl_saldo_inicial_disminucion` | Aportaciones entidades sin fines lucrativos - Disminución - Saldo principio | money | |
| 03270 | `is_correccion_aportaciones_esfl_saldo_final_disminucion` | Aportaciones entidades sin fines lucrativos - Disminución - Saldo fin | money | |
| 03332 | `is_correccion_adquisicion_participaciones_no_residentes_temporaria_ejercicio_aumento` | Adquisición participaciones no residentes DT14 - Aumento - Temporarias origen ejercicio | money | |
| 03333 | `is_correccion_adquisicion_participaciones_no_residentes_temporaria_anterior_aumento` | Adquisición participaciones no residentes DT14 - Aumento - Temporarias origen anteriores | money | |
| 03334 | `is_correccion_adquisicion_participaciones_no_residentes_saldo_inicial_aumento` | Adquisición participaciones no residentes DT14 - Aumento - Saldo principio | money | |
| 03335 | `is_correccion_adquisicion_participaciones_no_residentes_saldo_final_aumento` | Adquisición participaciones no residentes DT14 - Aumento - Saldo fin | money | |
| 03337 | `is_correccion_adquisicion_participaciones_no_residentes_temporaria_ejercicio_disminucion` | Adquisición participaciones no residentes DT14 - Disminución - Temporarias origen ejercicio | money | |
| 03338 | `is_correccion_adquisicion_participaciones_no_residentes_temporaria_anterior_disminucion` | Adquisición participaciones no residentes DT14 - Disminución - Temporarias origen anteriores | money | |
| 03339 | `is_correccion_adquisicion_participaciones_no_residentes_saldo_inicial_disminucion` | Adquisición participaciones no residentes DT14 - Disminución - Saldo principio | money | |
| 03340 | `is_correccion_adquisicion_participaciones_no_residentes_saldo_final_disminucion` | Adquisición participaciones no residentes DT14 - Disminución - Saldo fin | money | |
| 03372 | `is_correccion_foral_temporaria_ejercicio_aumento` | Correcciones específicas normativa foral - Aumento - Temporarias origen ejercicio | money | |
| 03373 | `is_correccion_foral_temporaria_anterior_aumento` | Correcciones específicas normativa foral - Aumento - Temporarias origen anteriores | money | |
| 03374 | `is_correccion_foral_saldo_inicial_aumento` | Correcciones específicas normativa foral - Aumento - Saldo principio | money | |
| 03375 | `is_correccion_foral_saldo_final_aumento` | Correcciones específicas normativa foral - Aumento - Saldo fin | money | |
| 03377 | `is_correccion_foral_temporaria_ejercicio_disminucion` | Correcciones específicas normativa foral - Disminución - Temporarias origen ejercicio | money | |
| 03378 | `is_correccion_foral_temporaria_anterior_disminucion` | Correcciones específicas normativa foral - Disminución - Temporarias origen anteriores | money | |
| 03379 | `is_correccion_foral_saldo_inicial_disminucion` | Correcciones específicas normativa foral - Disminución - Saldo principio | money | |
| 03380 | `is_correccion_foral_saldo_final_disminucion` | Correcciones específicas normativa foral - Disminución - Saldo fin | money | |
| 03392 | `is_correccion_otras_resultado_temporaria_ejercicio_aumento` | Otras correcciones resultado pérdidas y ganancias - Aumento - Temporarias origen ejercicio | money | |
| 03393 | `is_correccion_otras_resultado_temporaria_anterior_aumento` | Otras correcciones resultado pérdidas y ganancias - Aumento - Temporarias origen anteriores | money | |
| 03394 | `is_correccion_otras_resultado_saldo_inicial_aumento` | Otras correcciones resultado pérdidas y ganancias - Aumento - Saldo principio | money | |
| 03395 | `is_correccion_otras_resultado_saldo_final_aumento` | Otras correcciones resultado pérdidas y ganancias - Aumento - Saldo fin | money | |
| 03397 | `is_correccion_otras_resultado_temporaria_ejercicio_disminucion` | Otras correcciones resultado pérdidas y ganancias - Disminución - Temporarias origen ejercicio | money | |
| 03398 | `is_correccion_otras_resultado_temporaria_anterior_disminucion` | Otras correcciones resultado pérdidas y ganancias - Disminución - Temporarias origen anteriores | money | |
| 03399 | `is_correccion_otras_resultado_saldo_inicial_disminucion` | Otras correcciones resultado pérdidas y ganancias - Disminución - Saldo principio | money | |
| 03400 | `is_correccion_otras_resultado_saldo_final_disminucion` | Otras correcciones resultado pérdidas y ganancias - Disminución - Saldo fin | money | |
| 02302 | `is_correcciones_temporarias_importe` | Detalle correcciones PyG - Corrección permanente - Disminuciones | money | REUSED — existing role; detalle subtable permanente disminucion |
| 02303 | `is_correcciones_temporarias_importe` | Detalle correcciones PyG - Corrección temporaria origen ejercicio - Aumentos | money | REUSED — existing role; detalle subtable temporaria ejercicio aumento |
| 02304 | `is_correcciones_temporarias_importe` | Detalle correcciones PyG - Corrección temporaria origen ejercicio - Disminuciones | money | REUSED — existing role |
| 02306 | `is_correcciones_temporarias_importe` | Detalle correcciones PyG - Saldo pendiente temporarias principio - Disminuciones futuras | money | REUSED — existing role; mirrors 02305 pattern in sibling TOML |
| 02308 | `is_correcciones_temporarias_importe` | Detalle correcciones PyG - Corrección temporaria anteriores - Aumentos | money | REUSED — existing role |
| 02310 | `is_correcciones_temporarias_importe` | Detalle correcciones PyG - Saldo pendiente temporarias fin - Disminuciones futuras | money | REUSED — existing role |
| 00076 | `is_correccion_amortizacion_acelerada_vehiculos_permanente_aumento` | Amortización acelerada vehículos DA18 RDL5/2023-RDL7/2026 - Aumento - Permanentes | money | DA18 LIS block; no saldo_inicial in cluster (00075 not in this cluster) |
| 00077 | `is_correccion_amortizacion_acelerada_vehiculos_temporaria_ejercicio_aumento` | Amortización acelerada vehículos DA18 - Aumento - Temporarias origen ejercicio | money | |
| 00042 | `is_personal_asalariado_cifra_media` | Personal asalariado cifra media - Personal no fijo | decimal | REUSED — existing role `is_personal_asalariado_cifra_media`; structural outlier |

## Data_type divergences

One data_type divergence is present in this cluster:

- **id `00042`** (`decimal`) is the sole casilla with `data_type = decimal`. All other 116 casillas carry `data_type = money`. This is expected: casilla 00042 records a headcount figure (average non-fixed employees) which is a numeric count, not a monetary amount. Its existing sibling 00041 (not in this cluster) carries the same `decimal` data_type and the same role `is_personal_asalariado_cifra_media`.

No intra-role data_type inconsistency exists. Every casilla sharing a given role has `money` data_type, and the single `is_personal_asalariado_cifra_media` entry in this cluster is `decimal` consistently with all other instances of that role across M200.

## Summary

- Total casillas classified: **117**
- Reused roles (verbatim from `_existing-roles.txt`): **3** (`is_correcciones_temporarias_importe`, `is_gastos_financieros_adicion_aplicado`, `is_gastos_financieros_adicion_pendiente`, `is_personal_asalariado_cifra_media`) — 4 distinct existing roles, applied to 19 casillas
- New roles introduced: **98** distinct new role strings covering 98 casillas across 28 LIS-article adjustment concepts
- Data_type divergences: **1** (id 00042, `decimal` vs cluster-wide `money`)
