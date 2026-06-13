---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# `schema-hardening` audit: M100 `resultados.calculo_impuesto_res` cluster role assignment

## Scope

Per-id semantic_role classification for every casilla whose `section` places
it under `resultados.calculo_impuesto_res`, `resultados.minimo_per_fam_res`, or
`resultados.irpf_ccaa_res` across all six M100 revisions (2020–2025). Total
unique IDs discovered: **173**. Already-roled (NIF/identity slots from the prior
NIF audit): **29**. Newly classified here: **144**.

This audit is read-only. No TOML files were modified.

---

## Sub-section map

| sub-section | casilla-revision pairs | description |
|---|---:|---|
| `resultados.calculo_impuesto_res` | 7 | Top-level result slots (cuota diferencial 2025 path + rectificacion) |
| `resultados.calculo_impuesto_res.gravamenes_res` | 372 | Cuota integra, deducciones estatales/autonomicas, cuota liquida chain |
| `resultados.calculo_impuesto_res.cuota_autoliquidacion_res` | 30 | Cuota liquida incrementada → cuota resultante (2020–2024) |
| `resultados.calculo_impuesto_res.cuota_diferencial_res` | 5 | Cuota diferencial (2020–2024) |
| `resultados.calculo_impuesto_res.retenciones_res` | 70 | Pagos a cuenta sub-section (2020–2024; moved to standalone section in 2025; already roled by Phase 2) |
| `resultados.calculo_impuesto_res.deduc_mater_res` | 15 | Deduccion maternidad (2020–2024) |
| `resultados.calculo_impuesto_res.ampliacion_deduc_mater_res` | 6 | Ampliation deduccion maternidad 2020–2021 (2022 only) |
| `resultados.calculo_impuesto_res.deduc_conyuge_disc_res` | 58 | Deduccion conyuge con discapacidad |
| `resultados.calculo_impuesto_res.deduc_descendiente_disc_res` | 64 | Deduccion descendiente con discapacidad |
| `resultados.calculo_impuesto_res.deduc_ascendiente_disc_res` | 76 | Deduccion ascendiente con discapacidad |
| `resultados.calculo_impuesto_res.deduc_familia_numerosa_res` | 88 | Deduccion familia numerosa |
| `resultados.calculo_impuesto_res.deduc_monoparental_res` | 10 | Deduccion familia monoparental |
| `resultados.calculo_impuesto_res.regularizacion_descendiente_res` | 11 | Regularizacion abono anticipado descendiente |
| `resultados.calculo_impuesto_res.regularizacion_ascendiente_res` | 11 | Regularizacion abono anticipado ascendiente |
| `resultados.calculo_impuesto_res.datos_extra` | 1 | Discrepancia criterio administrativo (2024 only) |
| `resultados.minimo_per_fam_res` | 84 | Minimo personal y familiar computation |
| `resultados.irpf_ccaa_res` | 18 | IRPF autonomic allocation |

---

## Per-id role-assignment table

Columns: `id | section | proposed_role | label_snippet | data_type | revisions_present | notes`

Casillas already carrying a role from the NIF audit are listed for completeness
with `ALREADY_ROLED` in the notes column and are excluded from the new-role count.

### Already-roled casillas (skip — NIF audit complete)

| id | section | role | label_snippet | data_type | revisions |
|---|---|---|---|---|---|
| 0240 | deduc_conyuge_disc_res | `spouse_nif` | NIF del conyuge | nif | 2020–2025 |
| 0614 | deduc_descendiente_disc_res | `descendant_nif` | NIF del descendiente | nif | 2020–2025 |
| 0620 | deduc_descendiente_disc_res | `assignor_nif` | NIF del cedente | nif | 2020–2025 |
| 0622 | deduc_descendiente_disc_res | `beneficiary_nif` | NIF del beneficiario | nif | 2020–2025 |
| 0625 | deduc_ascendiente_disc_res | `ascendant_nif` | NIF del ascendiente | nif | 2020–2025 |
| 0631 | deduc_ascendiente_disc_res | `assignor_nif` | NIF del cedente | nif | 2020–2025 |
| 0632 | deduc_ascendiente_disc_res | `assignor_nif` | NIF del cedente | nif | 2020–2025 |
| 0633 | deduc_ascendiente_disc_res | `assignor_nif` | NIF del cedente | nif | 2020–2025 |
| 0635 | deduc_ascendiente_disc_res | `beneficiary_nif` | NIF del beneficiario | nif | 2020–2025 |
| 0654 | deduc_familia_numerosa_res | `assignor_nif` | NIF del cedente | nif | 2020–2025 |
| 0655 | deduc_familia_numerosa_res | `assignor_nif` | NIF del cedente | nif | 2020–2025 |
| 0656 | deduc_familia_numerosa_res | `assignor_nif` | NIF del cedente | nif | 2020–2025 |
| 0658 | deduc_familia_numerosa_res | `beneficiary_nif` | NIF del beneficiario | nif | 2020–2025 |
| 0665 | regularizacion_descendiente_res | `descendant_nif` | NIF del descendiente cuya deduccion se regulariza | nif | 2020–2025 |
| 0667 | regularizacion_ascendiente_res | `ascendant_nif` | NIF del ascendiente cuya deduccion se regulariza | nif | 2020–2025 |
| 0592–0609 | retenciones_res (2020–2024) | various `irpf_retencion_*` | — | (absent) | 2020–2024 | Phase 2 already roled |

### minimo_per_fam_res — 14 casillas

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0511 | minimo_per_fam_res | `irpf_minimo_contribuyente_estatal` | Minimo del contribuyente. Importe (estatal) | (absent → decimal) | 2020–2025 | Component of cuota integra estatal computation; art. 56 LIRPF |
| 0512 | minimo_per_fam_res | `irpf_minimo_contribuyente_autonomico` | Minimo del contribuyente. Importe (autonomico) | (absent → decimal) | 2020–2025 | Autonomic counterpart of 0511 |
| 0513 | minimo_per_fam_res | `irpf_minimo_descendientes_estatal` | Minimo por descendientes. Importe (estatal) | (absent → decimal) | 2020–2025 | Art. 58 LIRPF; estatal half |
| 0514 | minimo_per_fam_res | `irpf_minimo_descendientes_autonomico` | Minimo por descendientes. Importe (autonomico) | (absent → decimal) | 2020–2025 | Art. 58 LIRPF; autonomic half |
| 0515 | minimo_per_fam_res | `irpf_minimo_ascendientes_estatal` | Minimo por ascendientes. Importe (estatal) | (absent → decimal) | 2020–2025 | Art. 59 LIRPF; estatal half |
| 0516 | minimo_per_fam_res | `irpf_minimo_ascendientes_autonomico` | Minimo por ascendientes. Importe (autonomico) | (absent → decimal) | 2020–2025 | Art. 59 LIRPF; autonomic half |
| 0517 | minimo_per_fam_res | `irpf_minimo_discapacidad_estatal` | Minimo por discapacidad. Importe (estatal) | (absent → decimal) | 2020–2025 | Art. 60 LIRPF; estatal half |
| 0518 | minimo_per_fam_res | `irpf_minimo_discapacidad_autonomico` | Minimo por discapacidad. Importe (autonomico) | (absent → decimal) | 2020–2025 | Art. 60 LIRPF; autonomic half |
| 0519 | minimo_per_fam_res | `irpf_minimo_personal_familiar_estatal` | Minimo personal y familiar (estatal) | (absent → decimal) | 2020–2025 | Aggregate: 0511+0513+0515+0517 estatal |
| 0520 | minimo_per_fam_res | `irpf_minimo_personal_familiar_autonomico` | Minimo personal y familiar (incrementado/disminuido, autonomico) | (absent → decimal) | 2020–2025 | Aggregate autonomic; may differ from estatal via CCAA regulation |
| 0521 | minimo_per_fam_res | `irpf_minimo_aplicado_base_general_estatal` | Minimo p.y.f. en base liquidable general (estatal) | (absent → decimal) | 2020–2025 | Allocation step: min(0519, base_liq_general_estatal) |
| 0522 | minimo_per_fam_res | `irpf_minimo_aplicado_base_ahorro_estatal` | Minimo p.y.f. en base liquidable ahorro (estatal) | (absent → decimal) | 2020–2025 | Allocation step: min(0519-0521, base_liq_ahorro) |
| 0523 | minimo_per_fam_res | `irpf_minimo_aplicado_base_general_autonomico` | Minimo p.y.f. en base liquidable general (autonomico) | (absent → decimal) | 2020–2025 | Allocation step autonomic |
| 0524 | minimo_per_fam_res | `irpf_minimo_aplicado_base_ahorro_autonomico` | Minimo p.y.f. en base liquidable ahorro (autonomico) | (absent → decimal) | 2020–2025 | Allocation step autonomic |

### gravamenes_res — escala application intermediates (2020–2025)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0528 | gravamenes_res | `irpf_escala_sobre_base_general_estatal` | Escala sobre base liquidable general (estatal) | (absent → decimal) | 2020–2025 | Tax applied to 0505 estatal |
| 0529 | gravamenes_res | `irpf_escala_sobre_base_general_autonomico` | Escala sobre base liquidable general (autonomico) | (absent → decimal) | 2020–2025 | Tax applied to 0505 autonomic |
| 0530 | gravamenes_res | `irpf_escala_sobre_minimo_general_estatal` | Escala sobre minimo en base general (estatal) | (absent → decimal) | 2020–2025 | Tax applied to 0521 estatal |
| 0531 | gravamenes_res | `irpf_escala_sobre_minimo_general_autonomico` | Escala sobre minimo en base general (autonomico) | (absent → decimal) | 2020–2025 | Tax applied to 0523 autonomic |
| 0532 | gravamenes_res | `irpf_cuota_base_liquidable_general_estatal` | Cuotas base liquidable general (estatal) | (absent → decimal) | 2020–2025 | 0528 - 0530 |
| 0533 | gravamenes_res | `irpf_cuota_base_liquidable_general_autonomico` | Cuotas base liquidable general (autonomico) | (absent → decimal) | 2020–2025 | 0529 - 0531 |
| 0534 | gravamenes_res | `irpf_tipo_medio_gravamen_general_estatal` | Tipo medio gravamen base general (estatal) | (absent → decimal) | 2020–2025 | 0532×100/0505; percentage intermediate |
| 0535 | gravamenes_res | `irpf_tipo_medio_gravamen_general_autonomico` | Tipo medio gravamen base general (autonomico) | (absent → decimal) | 2020–2025 | 0533×100/0505 |
| 0536 | gravamenes_res | `irpf_escala_sobre_base_ahorro_estatal` | Escala sobre base liquidable del ahorro (estatal) | (absent → decimal) | 2020–2025 | Tax applied to 0510 estatal |
| 0537 | gravamenes_res | `irpf_escala_sobre_base_ahorro_autonomico` | Escala sobre base liquidable del ahorro (autonomico) | (absent → decimal) | 2020–2025 | Tax applied to 0510 autonomic |
| 0538 | gravamenes_res | `irpf_escala_sobre_minimo_ahorro_estatal` | Escala sobre minimo en base ahorro (estatal) | (absent → decimal) | 2020–2025 | Tax applied to 0522 estatal |
| 0539 | gravamenes_res | `irpf_escala_sobre_minimo_ahorro_autonomico` | Escala sobre minimo en base ahorro (autonomico) | (absent → decimal) | 2020–2025 | Tax applied to 0524 autonomic |
| 0540 | gravamenes_res | `irpf_cuota_base_liquidable_ahorro_estatal` | Cuotas base liquidable ahorro (estatal) | (absent → decimal) | 2020–2025 | 0536 - 0538 |
| 0541 | gravamenes_res | `irpf_cuota_base_liquidable_ahorro_autonomico` | Cuotas base liquidable ahorro (autonomico) | (absent → decimal) | 2020–2025 | 0537 - 0539 |
| 0542 | gravamenes_res | `irpf_tipo_medio_gravamen_ahorro_estatal` | Tipo medio gravamen base ahorro (estatal) | (absent → decimal) | 2020–2025 | 0540×100/0510 |
| 0543 | gravamenes_res | `irpf_tipo_medio_gravamen_ahorro_autonomico` | Tipo medio gravamen base ahorro (autonomico) | (absent → decimal) | 2020–2025 | 0541×100/0510 |

### gravamenes_res — cuota integra (2020–2025)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0545 | gravamenes_res | `irpf_cuota_integra_estatal` | Cuota integra estatal | (absent → decimal) | 2020–2025 | 0532 + 0540 |
| 0546 | gravamenes_res | `irpf_cuota_integra_autonomica` | Cuota integra autonomica | (absent → decimal) | 2020–2025 | 0533 + 0541 |

### gravamenes_res — deducciones applied to cuota (2020–2025)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0547 | gravamenes_res | `irpf_deduccion_vivienda_habitual_estatal` | Deduccion inversion vivienda habitual (estatal) | (absent → decimal) | 2020–2025 | Regimen transitorio art. 68.1 LIRPF; estatal half |
| 0548 | gravamenes_res | `irpf_deduccion_vivienda_habitual_autonomica` | Deduccion inversion vivienda habitual (autonomica) | (absent → decimal) | 2020–2025 | Autonomic half |
| 0549 | gravamenes_res | `irpf_deduccion_empresa_nueva_creacion` | Deduccion inversion empresas nueva o reciente creacion (estatal) | (absent → decimal) | 2020–2025 | Art. 68.1 LIRPF; estatal only |
| 0550 | gravamenes_res | `irpf_deduccion_interes_cultural_estatal` | Inversiones/gastos interes cultural (estatal) | (absent → decimal) | 2020–2025 | Art. 68.3 LIRPF; estatal half |
| 0551 | gravamenes_res | `irpf_deduccion_interes_cultural_autonomica` | Inversiones/gastos interes cultural (autonomica) | (absent → decimal) | 2020–2025 | Autonomic half |
| 0552 | gravamenes_res | `irpf_deduccion_donativos_estatal` | Donativos y otras aportaciones (estatal) | (absent → decimal) | 2020–2025 | Art. 68.3 LIRPF; estatal half |
| 0553 | gravamenes_res | `irpf_deduccion_donativos_autonomica` | Donativos y otras aportaciones (autonomica) | (absent → decimal) | 2020–2025 | Autonomic half |
| 0554 | gravamenes_res | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Incentivos inversion empresarial (estatal) | (absent → decimal) | 2020–2025 | Reg. especiales; estatal half |
| 0555 | gravamenes_res | `irpf_deduccion_incentivos_inversion_empresarial_autonomica` | Incentivos inversion empresarial (autonomica) | (absent → decimal) | 2020–2025 | Autonomic half |
| 0556 | gravamenes_res | `irpf_deduccion_ric_canarias_estatal` | Dotaciones Reserva Inversiones Canarias (estatal) | (absent → decimal) | 2020–2025 | Ley 19/1994; estatal half |
| 0557 | gravamenes_res | `irpf_deduccion_ric_canarias_autonomica` | Dotaciones Reserva Inversiones Canarias (autonomica) | (absent → decimal) | 2020–2025 | Autonomic half |
| 0558 | gravamenes_res | `irpf_deduccion_bienes_corporales_canarias_estatal` | Rendimientos venta bienes corporales producidos Canarias (estatal) | (absent → decimal) | 2020–2025 | Ley 19/1994; estatal half |
| 0559 | gravamenes_res | `irpf_deduccion_bienes_corporales_canarias_autonomica` | Rendimientos venta bienes corporales producidos Canarias (autonomica) | (absent → decimal) | 2020–2025 | Autonomic half |
| 0560 | gravamenes_res | `irpf_deduccion_ceuta_melilla_estatal` | Rentas Ceuta o Melilla (estatal) | (absent → decimal) | 2020–2025 | Art. 68.4 LIRPF; estatal half |
| 0561 | gravamenes_res | `irpf_deduccion_ceuta_melilla_autonomica` | Rentas Ceuta o Melilla (autonomica) | (absent → decimal) | 2020–2025 | Autonomic half |
| 0562 | gravamenes_res | `irpf_deduccion_alquiler_vivienda_habitual_estatal` | Alquiler vivienda habitual regimen transitorio (estatal) | (absent → decimal) | 2020–2025 | Regimen transitorio; estatal half |
| 0563 | gravamenes_res | `irpf_deduccion_alquiler_vivienda_habitual_autonomica` | Alquiler vivienda habitual regimen transitorio (autonomica) | (absent → decimal) | 2020–2025 | Autonomic half |
| 0564 | gravamenes_res | `irpf_deducciones_autonomicas_suma` | Suma deducciones autonomicas | (absent → decimal) | 2020–2025 | Sum from anexo B sub-sections |
| 0565 | gravamenes_res | `irpf_deduccion_unidades_familiares_ue_eee_estatal` | Deduccion unidades familiares UE/EEE (estatal) | (absent → decimal) | 2020–2025 | Residentes UE/EEE art. 93 LIRPF; estatal half |
| 0566 | gravamenes_res | `irpf_deduccion_unidades_familiares_ue_eee_autonomica` | Deduccion unidades familiares UE/EEE (autonomica) | (absent → decimal) | 2020–2025 | Autonomic half |
| 0567 | gravamenes_res | `irpf_deduccion_eficiencia_energetica_viviendas` | Deduccion obras eficiencia energetica viviendas (estatal) | (absent → decimal) | 2021–2025 | Introduced 2021; estatal only in main form |
| 0607 | gravamenes_res | `irpf_deduccion_vehiculos_electricos` | Deduccion adquisicion vehiculos electricos (estatal) | (absent → decimal) | 2023–2025 | Introduced 2023; estatal only |
| 0608 | gravamenes_res | `irpf_deduccion_puntos_recarga` | Deduccion instalacion puntos de recarga (estatal) | (absent → decimal) | 2023–2025 | Introduced 2023; estatal only |
| 0721 | gravamenes_res | `irpf_deduccion_general_importe` | Importe de la deduccion (generic deduction amount) | (absent → decimal) | 2020–2025 | Contextual deduction amount row within gravamenes sub-form |
| 0845 | gravamenes_res | `irpf_deducciones_incentivos_inversion_total` | Total deducciones incentivos inversion empresarial | (absent → decimal) | 2020–2025 | Sum of multiple deduction lines from anexo A |

### gravamenes_res — La Palma + Illes Balears (territorial deducciones, 2022–2025)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0544 | gravamenes_res | `irpf_deduccion_la_palma_estatal` | Por residencia La Palma (estatal) | (absent → decimal) | 2022–2025 | Disaster-zone deduction; estatal half |
| 0584 | gravamenes_res | `irpf_deduccion_la_palma_autonomica` | Por residencia La Palma (autonomica) | (absent → decimal) | 2022–2025 | Autonomic half |
| 0502 | gravamenes_res | `irpf_deduccion_rib_illes_balears_estatal` | Dotaciones Reserva Inversiones Illes Balears (estatal) | (absent → decimal) | 2023–2025 | D.A. 70a Ley 31/2022; estatal half |
| 0503 | gravamenes_res | `irpf_deduccion_rib_illes_balears_autonomica` | Dotaciones Reserva Inversiones Illes Balears (autonomica) | (absent → decimal) | 2023–2025 | Autonomic half |
| 0508 | gravamenes_res | `irpf_deduccion_bienes_corporales_illes_balears_estatal` | Rendimientos venta bienes corporales Illes Balears (estatal) | (absent → decimal) | 2023–2025 | D.A. 70a Ley 31/2022; estatal half |
| 0509 | gravamenes_res | `irpf_deduccion_bienes_corporales_illes_balears_autonomica` | Rendimientos venta bienes corporales Illes Balears (autonomica) | (absent → decimal) | 2023–2025 | Autonomic half |

### gravamenes_res — regularizacion deducciones (loss-of-right / interest on clawback, 2020–2025)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0568 | gravamenes_res | `irpf_incremento_perdida_incentivo_fiscal_estatal` | Incremento cuotas liquidas perdida incentivo fiscal art. 33.3c (estatal) | (absent → decimal) | 2022–2025 | Clawback; estatal half |
| 0569 | gravamenes_res | `irpf_incremento_perdida_incentivo_fiscal_autonomico` | Incremento cuotas liquidas perdida incentivo fiscal (autonomico) | (absent → decimal) | 2022–2025 | Autonomic half |
| 0572 | gravamenes_res | `irpf_perdida_derecho_deduccion_estatal` | Deducciones perdida derecho en el ejercicio (estatal) | (absent → decimal) | 2020–2025 | Recapture amount; estatal half |
| 0573 | gravamenes_res | `irpf_intereses_demora_perdida_deduccion_estatal` | Intereses demora por perdida deduccion (estatal) | (absent → decimal) | 2020–2025 | Late-payment interest; estatal |
| 0574 | gravamenes_res | `irpf_perdida_derecho_deduccion_transitoria_estatal` | Deducciones perdida derecho (transitoria, estatal) | (absent → decimal) | 2020–2025 | Separate row for transitional deducciones; estatal |
| 0575 | gravamenes_res | `irpf_flag_regularizacion_da45_estatal` | Flag: regularizacion motivada D.A. 45a.2a o 45a.3 (estatal) | boolean | 2020–2025 | Boolean flag; no amount role needed |
| 0576 | gravamenes_res | `irpf_intereses_demora_perdida_transitoria_estatal` | Intereses demora deducc. transitoria (estatal) | (absent → decimal) | 2020–2025 | Interest on transitional clawback; estatal |
| 0577 | gravamenes_res | `irpf_perdida_derecho_deduccion_autonomica` | Deducciones perdida derecho en el ejercicio (autonomica) | (absent → decimal) | 2020–2025 | Recapture; autonomic |
| 0578 | gravamenes_res | `irpf_intereses_demora_perdida_deduccion_autonomica` | Intereses demora por perdida deduccion (autonomica) | (absent → decimal) | 2020–2025 | Autonomic |
| 0579 | gravamenes_res | `irpf_perdida_derecho_deduccion_autonomicas_suma` | Deducciones autonomicas perdida derecho | (absent → decimal) | 2020–2025 | Sum of autonomic deduction clawbacks |
| 0580 | gravamenes_res | `irpf_flag_regularizacion_da45_autonomico` | Flag: regularizacion motivada D.A. 45a.2a o 45a.3 (autonomico) | boolean | 2020–2025 | Boolean flag; no amount role |
| 0581 | gravamenes_res | `irpf_intereses_demora_perdida_deduccion_autonomica_2` | Intereses demora deducc. autonomica (segunda fila) | (absent → decimal) | 2020–2025 | Second interest row for autonomic |
| 0582 | gravamenes_res | `irpf_intereses_demora_regularizacion_estatal` | Intereses demora regularizacion anterior (estatal) | (absent → decimal) | 2022–2025 | Regularizacion prior-year interest; estatal |
| 0583 | gravamenes_res | `irpf_intereses_demora_regularizacion_autonomico` | Intereses demora regularizacion anterior (autonomico) | (absent → decimal) | 2022–2025 | Autonomic |

### gravamenes_res — cuota liquida (2020–2025)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0570 | gravamenes_res | `irpf_cuota_liquida_estatal` | Cuota liquida estatal | (absent → decimal) | 2020–2025 | After deductions applied to cuota integra estatal |
| 0571 | gravamenes_res | `irpf_cuota_liquida_autonomica` | Cuota liquida autonomica | (absent → decimal) | 2020–2025 | After deductions applied to cuota integra autonomica |

### gravamenes_res — cuota liquida incrementada (2020–2024 only; removed 2025 restructure)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0585 | gravamenes_res | `irpf_cuota_liquida_estatal_incrementada` | Cuota liquida estatal incrementada | (absent → decimal) | 2020–2024 | 0570 + clawbacks + regularizacion; removed in 2025 restructure |
| 0586 | gravamenes_res | `irpf_cuota_liquida_autonomica_incrementada` | Cuota liquida autonomica incrementada | (absent → decimal) | 2020–2024 | 0571 + clawbacks + regularizacion; removed in 2025 restructure |

### cuota_autoliquidacion_res (2020–2024 only)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0587 | cuota_autoliquidacion_res | `irpf_cuota_liquida_total` | Cuota liquida incrementada total | (absent → decimal) | 2020–2024 | 0585 + 0586 |
| 0588 | cuota_autoliquidacion_res | `irpf_deduccion_doble_imposicion_internacional` | Doble imposicion internacional (rentas extranjero) | (absent → decimal) | 2020–2024 | Art. 80 LIRPF |
| 0589 | cuota_autoliquidacion_res | `irpf_deduccion_doble_imposicion_transparencia` | Doble imposicion internacional (transparencia fiscal internacional) | (absent → decimal) | 2020–2024 | Art. 91 LIRPF |
| 0590 | cuota_autoliquidacion_res | `irpf_deduccion_doble_imposicion_imputacion_rentas` | Doble imposicion (imputacion rentas inmobiliarias internacionales) | (absent → decimal) | 2020–2024 | Art. 85 LIRPF |
| 0591 | cuota_autoliquidacion_res | `irpf_retenciones_consideradas_practicadas` | Retenciones no practicadas con consideracion de practicadas | (absent → decimal) | 2020–2024 | Legal fiction retenciones art. 99.5 LIRPF |
| 0595 | cuota_autoliquidacion_res | `irpf_cuota_resultante_autoliquidacion` | Cuota resultante de la autoliquidacion | (absent → decimal) | 2020–2024 | 0587 - 0588 - 0589 - 0590 - 0591 |

### cuota_diferencial_res (2020–2024 only)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0610 | cuota_diferencial_res | `irpf_cuota_diferencial` | Cuota diferencial | decimal | 2020–2024 | 0595 - total pagos a cuenta; signed (can be negative = devolucion); data_type=decimal confirmed |

### Top-level calculo_impuesto_res

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0670 | calculo_impuesto_res | `irpf_resultado_declaracion` | Resultado de la declaracion | decimal | 2020–2024 | Full computation result in 2020–2024; replaced by 2025 restructure path through 0700 |
| 0701 | calculo_impuesto_res | `irpf_resultado_rectificacion_devolucion` | Importe a devolver por rectificacion | (absent → decimal) | 2024–2025 | Specific field for refund resulting from a rectification filing |

### irpf_ccaa_res (3 casillas, 2020–2025)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0671 | irpf_ccaa_res | `irpf_cuota_liquida_autonomica_ccaa` | Cuota liquida autonomica incrementada (traslade 0586) | (absent → decimal) | 2020–2025 | Copy of 0586 for CCAA allocation form |
| 0672 | irpf_ccaa_res | `irpf_deduccion_doble_imposicion_autonomica_50pct` | 50% deducciones doble imposicion (autonomica allocation) | (absent → decimal) | 2020–2025 | 50% of (0588+0589+0590) |
| 0675 | irpf_ccaa_res | `irpf_cuota_ccaa_residencia` | IRPF correspondiente a la CCAA de residencia | (absent → decimal) | 2020–2025 | 0671 - 0672; feeds CCAA settlement |

### datos_extra (2024 only)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0669 | datos_extra | `irpf_discrepancia_criterio_administrativo` | Discrepancia de criterio administrativo | decimal | 2024 only | Single-revision; data_type=decimal confirmed. Typo-twin warning expected. |

### deduc_mater_res (2020–2024)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0611 | deduc_mater_res | `irpf_deduccion_maternidad` | Importe de la deduccion (maternidad) | (absent → decimal) | 2020–2024 | Art. 81 LIRPF |
| 0612 | deduc_mater_res | `irpf_abono_anticipado_maternidad` | Abono anticipado deduccion maternidad | (absent → decimal) | 2020–2024 | Art. 81bis LIRPF advance payment |
| 0613 | deduc_mater_res | `irpf_incremento_maternidad_guarderia` | Incremento por guarderias (maternidad) | (absent → decimal) | 2020–2024 | Art. 81.2 LIRPF nursery incremental |

### ampliacion_deduc_mater_res (2022 only)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 1911 | ampliacion_deduc_mater_res | `irpf_num_hijos_maternidad_2020` | Numero hijos deduccion maternidad 2020 | (absent → integer) | 2022 only | Count field; integer-valued despite absent data_type. Typo-twin warning expected. |
| 1912 | ampliacion_deduc_mater_res | `irpf_incremento_maternidad_no_aplicado_2020` | Incremento deduccion maternidad no aplicada 2020 | (absent → decimal) | 2022 only | Catch-up amount for 2020. Typo-twin warning expected. |
| 1913 | ampliacion_deduc_mater_res | `irpf_incremento_maternidad_guarderia_no_aplicado_2020` | Incremento guarderias maternidad no aplicado 2020 | (absent → decimal) | 2022 only | Nursery catch-up 2020. Typo-twin warning expected. |
| 1914 | ampliacion_deduc_mater_res | `irpf_num_hijos_maternidad_2021` | Numero hijos deduccion maternidad 2021 | (absent → integer) | 2022 only | Count field 2021. Typo-twin warning expected. |
| 1915 | ampliacion_deduc_mater_res | `irpf_incremento_maternidad_no_aplicado_2021` | Incremento deduccion maternidad no aplicada 2021 | (absent → decimal) | 2022 only | Catch-up amount 2021. Typo-twin warning expected. |
| 1916 | ampliacion_deduc_mater_res | `irpf_incremento_maternidad_guarderia_no_aplicado_2021` | Incremento guarderias maternidad no aplicado 2021 | (absent → decimal) | 2022 only | Nursery catch-up 2021. Typo-twin warning expected. |

### deduc_conyuge_disc_res — non-NIF fields (2020–2025)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0241 | deduc_conyuge_disc_res | `irpf_conyuge_discapacidad_nombre` | Nombre del conyuge | text | 2020–2025 | Non-monetary supporting data |
| 0242 | deduc_conyuge_disc_res | `irpf_conyuge_discapacidad_fecha_inicio` | Fecha inicio discapacidad | text | 2020–2025 | Date field (text encoding) |
| 0243 | deduc_conyuge_disc_res | `irpf_conyuge_discapacidad_fecha_fin` | Fecha fin discapacidad | text | 2020–2025 | Date field (text encoding) |
| 0244 | deduc_conyuge_disc_res | `irpf_conyuge_discapacidad_otro_contribuyente_flag` | Otro contribuyente tiene derecho (flag) | boolean | 2020–2025 | Boolean; no amount role |
| 0245 | deduc_conyuge_disc_res | `irpf_matrimonio_vigente_todo_anio_flag` | Matrimonio vigente todo el anio (flag) | boolean | 2020–2025 | Boolean |
| 0246 | deduc_conyuge_disc_res | `irpf_matrimonio_mes_inicio` | Primer mes matrimonio vigente | (absent → integer) | 2020–2025 | Month ordinal 1–12 |
| 0247 | deduc_conyuge_disc_res | `irpf_matrimonio_mes_fin` | Ultimo mes completo matrimonio vigente | (absent → integer) | 2020–2025 | Month ordinal 1–12 |
| 0248 | deduc_conyuge_disc_res | `irpf_deduccion_conyuge_discapacidad` | Importe de la deduccion (conyuge disc.) | (absent → decimal) | 2020–2024 | Amount; dropped 2025 form restructure |
| 0249 | deduc_conyuge_disc_res | `irpf_abono_anticipado_conyuge_discapacidad` | Abono anticipado deduccion conyuge | (absent → decimal) | 2020–2024 | Advance payment amount |

### deduc_descendiente_disc_res — non-NIF fields

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0615 | deduc_descendiente_disc_res | `irpf_descendiente_discapacidad_nombre` | Nombre del descendiente | text | 2020–2025 | |
| 0616 | deduc_descendiente_disc_res | `irpf_descendiente_discapacidad_fecha_inicio` | Fecha inicio discapacidad | text | 2020–2025 | |
| 0617 | deduc_descendiente_disc_res | `irpf_descendiente_discapacidad_fecha_fin` | Fecha fin discapacidad | text | 2020–2025 | |
| 0618 | deduc_descendiente_disc_res | `irpf_descendiente_num_contribuyentes_derecho` | Num. personas con derecho al minimo por descendiente | (absent → integer) | 2020–2025 | Integer count |
| 0619 | deduc_descendiente_disc_res | `irpf_descendiente_cedido_flag` | Le han cedido el derecho (flag) | boolean | 2020–2025 | |
| 0621 | deduc_descendiente_disc_res | `irpf_descendiente_cede_flag` | Cede el derecho (flag) | boolean | 2020–2025 | |
| 0623 | deduc_descendiente_disc_res | `irpf_deduccion_descendiente_discapacidad` | Importe de la deduccion (descendiente disc.) | (absent → decimal) | 2020–2024 | |
| 0624 | deduc_descendiente_disc_res | `irpf_abono_anticipado_descendiente_discapacidad` | Abono anticipado deduccion descendiente | (absent → decimal) | 2020–2024 | |

### deduc_ascendiente_disc_res — non-NIF fields

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0626 | deduc_ascendiente_disc_res | `irpf_ascendiente_discapacidad_nombre` | Nombre del ascendiente | text | 2020–2025 | |
| 0627 | deduc_ascendiente_disc_res | `irpf_ascendiente_discapacidad_fecha_inicio` | Fecha inicio discapacidad | text | 2020–2025 | |
| 0628 | deduc_ascendiente_disc_res | `irpf_ascendiente_discapacidad_fecha_fin` | Fecha fin discapacidad | text | 2020–2025 | |
| 0629 | deduc_ascendiente_disc_res | `irpf_ascendiente_num_contribuyentes_derecho` | Num. personas con derecho al minimo por ascendiente | (absent → integer) | 2020–2025 | |
| 0630 | deduc_ascendiente_disc_res | `irpf_ascendiente_cedido_flag` | Le han cedido el derecho (flag) | boolean | 2020–2025 | |
| 0634 | deduc_ascendiente_disc_res | `irpf_ascendiente_cede_flag` | Cede el derecho (flag) | boolean | 2020–2025 | |
| 0636 | deduc_ascendiente_disc_res | `irpf_deduccion_ascendiente_discapacidad` | Importe de la deduccion (ascendiente disc.) | (absent → decimal) | 2020–2024 | |
| 0637 | deduc_ascendiente_disc_res | `irpf_abono_anticipado_ascendiente_discapacidad` | Abono anticipado deduccion ascendiente | (absent → decimal) | 2020–2024 | |

### deduc_familia_numerosa_res — non-NIF fields

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0647 | deduc_familia_numerosa_res | `irpf_familia_numerosa_titulo_id` | Numero identificacion titulo familia numerosa | text | 2020–2025 | Title document ID |
| 0648 | deduc_familia_numerosa_res | `irpf_familia_numerosa_categoria_general_flag` | Categoria familia numerosa General (flag) | boolean | 2020–2025 | |
| 0649 | deduc_familia_numerosa_res | `irpf_familia_numerosa_categoria_especial_flag` | Categoria familia numerosa Especial (flag) | boolean | 2020–2025 | |
| 0650 | deduc_familia_numerosa_res | `irpf_familia_numerosa_fecha_inicio` | Fecha inicio titulo | text | 2020–2025 | |
| 0651 | deduc_familia_numerosa_res | `irpf_familia_numerosa_fecha_caducidad` | Fecha caducidad titulo | text | 2020–2025 | |
| 0652 | deduc_familia_numerosa_res | `irpf_familia_numerosa_num_ascendientes` | Num. ascendientes en la familia numerosa | (absent → integer) | 2020–2025 | |
| 0653 | deduc_familia_numerosa_res | `irpf_familia_numerosa_cedido_flag` | Le han cedido el derecho (flag) | boolean | 2020–2025 | |
| 0657 | deduc_familia_numerosa_res | `irpf_familia_numerosa_cede_flag` | Cede el derecho (flag) | boolean | 2020–2025 | |
| 0659 | deduc_familia_numerosa_res | `irpf_familia_numerosa_hijos_exceden_minimo_flag` | Hijos exceden minimo de la categoria (flag) | boolean | 2020–2025 | |
| 0660 | deduc_familia_numerosa_res | `irpf_deduccion_familia_numerosa` | Importe de la deduccion (familia numerosa) | (absent → decimal) | 2020–2024 | |
| 0661 | deduc_familia_numerosa_res | `irpf_abono_anticipado_familia_numerosa` | Abono anticipado deduccion familia numerosa | (absent → decimal) | 2020–2024 | |

### deduc_monoparental_res (2020–2024)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0662 | deduc_monoparental_res | `irpf_deduccion_monoparental` | Importe de la deduccion (monoparental) | (absent → decimal) | 2020–2024 | Art. 81bis LIRPF monoparental |
| 0663 | deduc_monoparental_res | `irpf_abono_anticipado_monoparental` | Abono anticipado deduccion monoparental | (absent → decimal) | 2020–2024 | |

### regularizacion_descendiente_res / regularizacion_ascendiente_res (non-NIF fields)

| id | section | proposed_role | label_snippet | data_type | revisions | notes |
|---|---|---|---|---|---|---|
| 0664 | regularizacion_descendiente_res | `irpf_regularizacion_cobro_anticipado_descendiente` | Importe cobro anticipado a regularizar (descendiente) | (absent → decimal) | 2020–2024 | |
| 0666 | regularizacion_ascendiente_res | `irpf_regularizacion_cobro_anticipado_ascendiente` | Importe cobro anticipado a regularizar (ascendiente) | (absent → decimal) | 2020–2024 | |

---

## New roles introduced

All new roles carry the `irpf_` prefix. Data_type is `decimal` unless noted.
"absent → decimal" means the TOML `data_type` field is absent; the bulk-apply
pass should infer and confirm `decimal` before writing; boolean and text roles
require no data_type reconciliation.

### minimo_per_fam_res roles (14)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_minimo_contribuyente_estatal` | decimal | non_negative | Minimo del contribuyente (art. 56 LIRPF), estatal allocation |
| `irpf_minimo_contribuyente_autonomico` | decimal | non_negative | Minimo del contribuyente, autonomic allocation |
| `irpf_minimo_descendientes_estatal` | decimal | non_negative | Minimo por descendientes (art. 58 LIRPF), estatal |
| `irpf_minimo_descendientes_autonomico` | decimal | non_negative | Minimo por descendientes, autonomic |
| `irpf_minimo_ascendientes_estatal` | decimal | non_negative | Minimo por ascendientes (art. 59 LIRPF), estatal |
| `irpf_minimo_ascendientes_autonomico` | decimal | non_negative | Minimo por ascendientes, autonomic |
| `irpf_minimo_discapacidad_estatal` | decimal | non_negative | Minimo por discapacidad (art. 60 LIRPF), estatal |
| `irpf_minimo_discapacidad_autonomico` | decimal | non_negative | Minimo por discapacidad, autonomic |
| `irpf_minimo_personal_familiar_estatal` | decimal | non_negative | Aggregate minimo personal y familiar, estatal (0511+0513+0515+0517) |
| `irpf_minimo_personal_familiar_autonomico` | decimal | any | Aggregate autonomic; can be adjusted up/down by CCAA regulation |
| `irpf_minimo_aplicado_base_general_estatal` | decimal | non_negative | Fraction of minimo applied against base liquidable general, estatal |
| `irpf_minimo_aplicado_base_ahorro_estatal` | decimal | non_negative | Fraction of minimo applied against base liquidable del ahorro, estatal |
| `irpf_minimo_aplicado_base_general_autonomico` | decimal | non_negative | Same allocation step, autonomic |
| `irpf_minimo_aplicado_base_ahorro_autonomico` | decimal | non_negative | Same allocation step, autonomic |

### gravamenes_res — escala application roles (16)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_escala_sobre_base_general_estatal` | decimal | non_negative | Tax from general scale applied to base liquidable general, estatal |
| `irpf_escala_sobre_base_general_autonomico` | decimal | non_negative | Same, autonomic scale |
| `irpf_escala_sobre_minimo_general_estatal` | decimal | non_negative | Tax from general scale applied to minimo allocation on base general, estatal |
| `irpf_escala_sobre_minimo_general_autonomico` | decimal | non_negative | Same, autonomic |
| `irpf_cuota_base_liquidable_general_estatal` | decimal | non_negative | Net cuota from base liquidable general after minimo offset, estatal |
| `irpf_cuota_base_liquidable_general_autonomico` | decimal | non_negative | Same, autonomic |
| `irpf_tipo_medio_gravamen_general_estatal` | decimal | non_negative | Effective rate (percent) on base liquidable general, estatal |
| `irpf_tipo_medio_gravamen_general_autonomico` | decimal | non_negative | Same, autonomic |
| `irpf_escala_sobre_base_ahorro_estatal` | decimal | non_negative | Tax from savings scale applied to base liquidable del ahorro, estatal |
| `irpf_escala_sobre_base_ahorro_autonomico` | decimal | non_negative | Same, autonomic |
| `irpf_escala_sobre_minimo_ahorro_estatal` | decimal | non_negative | Tax from savings scale applied to minimo allocation on base ahorro, estatal |
| `irpf_escala_sobre_minimo_ahorro_autonomico` | decimal | non_negative | Same, autonomic |
| `irpf_cuota_base_liquidable_ahorro_estatal` | decimal | non_negative | Net cuota from base liquidable del ahorro after minimo offset, estatal |
| `irpf_cuota_base_liquidable_ahorro_autonomico` | decimal | non_negative | Same, autonomic |
| `irpf_tipo_medio_gravamen_ahorro_estatal` | decimal | non_negative | Effective rate (percent) on base liquidable del ahorro, estatal |
| `irpf_tipo_medio_gravamen_ahorro_autonomico` | decimal | non_negative | Same, autonomic |

### gravamenes_res — cuota integra, liquida, incrementada (6)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_cuota_integra_estatal` | decimal | non_negative | Cuota integra estatal (sum of general + ahorro cuotas, estatal) |
| `irpf_cuota_integra_autonomica` | decimal | non_negative | Cuota integra autonomica |
| `irpf_cuota_liquida_estatal` | decimal | non_negative | Cuota liquida estatal (after applicable deductions) |
| `irpf_cuota_liquida_autonomica` | decimal | non_negative | Cuota liquida autonomica |
| `irpf_cuota_liquida_estatal_incrementada` | decimal | non_negative | Cuota liquida estatal incrementada by clawbacks (2020–2024 form; absent in 2025) |
| `irpf_cuota_liquida_autonomica_incrementada` | decimal | non_negative | Cuota liquida autonomica incrementada (2020–2024 form) |

### gravamenes_res — deducciones roles (22)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_deduccion_vivienda_habitual_estatal` | decimal | non_negative | Deduccion inversion vivienda habitual (transitional regime), estatal |
| `irpf_deduccion_vivienda_habitual_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deduccion_empresa_nueva_creacion` | decimal | non_negative | Deduccion inversion empresas nueva o reciente creacion (estatal only) |
| `irpf_deduccion_interes_cultural_estatal` | decimal | non_negative | Deducciones inversiones interes cultural, estatal |
| `irpf_deduccion_interes_cultural_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deduccion_donativos_estatal` | decimal | non_negative | Donativos y otras aportaciones deduction, estatal |
| `irpf_deduccion_donativos_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deduccion_incentivos_inversion_empresarial_estatal` | decimal | non_negative | Incentivos inversion empresarial, estatal |
| `irpf_deduccion_incentivos_inversion_empresarial_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deduccion_ric_canarias_estatal` | decimal | non_negative | Reserva Inversiones Canarias (Ley 19/1994), estatal |
| `irpf_deduccion_ric_canarias_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deduccion_bienes_corporales_canarias_estatal` | decimal | non_negative | Rendimientos bienes corporales producidos Canarias, estatal |
| `irpf_deduccion_bienes_corporales_canarias_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deduccion_ceuta_melilla_estatal` | decimal | non_negative | Rentas Ceuta/Melilla, estatal |
| `irpf_deduccion_ceuta_melilla_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deduccion_alquiler_vivienda_habitual_estatal` | decimal | non_negative | Alquiler vivienda habitual transitional regime, estatal |
| `irpf_deduccion_alquiler_vivienda_habitual_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deducciones_autonomicas_suma` | decimal | non_negative | Sum of all autonomic deducciones from anexo B |
| `irpf_deduccion_unidades_familiares_ue_eee_estatal` | decimal | non_negative | Unidades familiares UE/EEE (art. 93 LIRPF), estatal |
| `irpf_deduccion_unidades_familiares_ue_eee_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deduccion_eficiencia_energetica_viviendas` | decimal | non_negative | Obras eficiencia energetica viviendas (introduced 2021), estatal |
| `irpf_deduccion_vehiculos_electricos` | decimal | non_negative | Adquisicion vehiculos electricos (introduced 2023), estatal |
| `irpf_deduccion_puntos_recarga` | decimal | non_negative | Instalacion puntos de recarga (introduced 2023), estatal |
| `irpf_deduccion_general_importe` | decimal | non_negative | Generic deduction amount row within gravamenes sub-form (contextual) |
| `irpf_deducciones_incentivos_inversion_total` | decimal | non_negative | Total deducciones incentivos inversion empresarial (sum across anexo A rows) |

### gravamenes_res — territorial (La Palma + Illes Balears) (6)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_deduccion_la_palma_estatal` | decimal | non_negative | Residencia habitual isla La Palma, estatal |
| `irpf_deduccion_la_palma_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deduccion_rib_illes_balears_estatal` | decimal | non_negative | Reserva Inversiones Illes Balears (D.A. 70a Ley 31/2022), estatal |
| `irpf_deduccion_rib_illes_balears_autonomica` | decimal | non_negative | Same, autonomic |
| `irpf_deduccion_bienes_corporales_illes_balears_estatal` | decimal | non_negative | Rendimientos bienes corporales Illes Balears, estatal |
| `irpf_deduccion_bienes_corporales_illes_balears_autonomica` | decimal | non_negative | Same, autonomic |

### gravamenes_res — clawback / regularizacion roles (12)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_incremento_perdida_incentivo_fiscal_estatal` | decimal | non_negative | Incremento cuotas por perdida incentivo fiscal art. 33.3c (estatal) |
| `irpf_incremento_perdida_incentivo_fiscal_autonomico` | decimal | non_negative | Same, autonomic |
| `irpf_perdida_derecho_deduccion_estatal` | decimal | non_negative | Deductions recaptured due to loss-of-right in exercise, estatal |
| `irpf_intereses_demora_perdida_deduccion_estatal` | decimal | non_negative | Interest on recaptured deductions, estatal |
| `irpf_perdida_derecho_deduccion_transitoria_estatal` | decimal | non_negative | Transitional-regime deduction recapture, estatal |
| `irpf_flag_regularizacion_da45_estatal` | boolean | — | Flag: regularizacion under D.A. 45a LIRPF, estatal |
| `irpf_intereses_demora_perdida_transitoria_estatal` | decimal | non_negative | Interest on transitional-regime clawback, estatal |
| `irpf_perdida_derecho_deduccion_autonomica` | decimal | non_negative | Deduction recapture, autonomic |
| `irpf_intereses_demora_perdida_deduccion_autonomica` | decimal | non_negative | Interest on recaptured deductions, autonomic |
| `irpf_perdida_derecho_deduccion_autonomicas_suma` | decimal | non_negative | Sum of autonomic deduction recaptures |
| `irpf_flag_regularizacion_da45_autonomico` | boolean | — | Flag: regularizacion under D.A. 45a LIRPF, autonomic |
| `irpf_intereses_demora_perdida_deduccion_autonomica_2` | decimal | non_negative | Second interest row for autonomic clawbacks |
| `irpf_intereses_demora_regularizacion_estatal` | decimal | non_negative | Interest on prior-year regularizacion, estatal |
| `irpf_intereses_demora_regularizacion_autonomico` | decimal | non_negative | Same, autonomic |

### cuota_autoliquidacion_res roles (6)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_cuota_liquida_total` | decimal | non_negative | Cuota liquida incrementada total (0585+0586; 2020–2024) |
| `irpf_deduccion_doble_imposicion_internacional` | decimal | non_negative | Doble imposicion internacional (rentas extranjero, art. 80 LIRPF) |
| `irpf_deduccion_doble_imposicion_transparencia` | decimal | non_negative | Doble imposicion (transparencia fiscal internacional, art. 91 LIRPF) |
| `irpf_deduccion_doble_imposicion_imputacion_rentas` | decimal | non_negative | Doble imposicion (imputacion rentas inmobiliarias internacionales, art. 85 LIRPF) |
| `irpf_retenciones_consideradas_practicadas` | decimal | non_negative | Retenciones with legal-fiction status (art. 99.5 LIRPF) |
| `irpf_cuota_resultante_autoliquidacion` | decimal | any | Cuota resultante de la autoliquidacion (can be negative) |

### cuota_diferencial + resultado_declaracion (3)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_cuota_diferencial` | decimal | any | Cuota diferencial (0595 − total pagos a cuenta; signed; can be negative for devolucion) |
| `irpf_resultado_declaracion` | decimal | any | Full result of the declaracion (2020–2024 path) |
| `irpf_resultado_rectificacion_devolucion` | decimal | non_positive | Amount to be returned as result of a rectificacion filing |

### irpf_ccaa_res roles (3)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_cuota_liquida_autonomica_ccaa` | decimal | non_negative | Copy of 0586 fed into the CCAA allocation form |
| `irpf_deduccion_doble_imposicion_autonomica_50pct` | decimal | non_negative | 50% of double-taxation deductions allocated to autonomic computation |
| `irpf_cuota_ccaa_residencia` | decimal | non_negative | Final IRPF share attributable to the taxpayer's CCAA of residence |

### datos_extra (1)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_discrepancia_criterio_administrativo` | decimal | any | Discrepancia de criterio administrativo (2024 only; typo-twin warning expected) |

### deduc_mater_res (3)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_deduccion_maternidad` | decimal | non_negative | Deduccion maternidad (art. 81 LIRPF) |
| `irpf_abono_anticipado_maternidad` | decimal | non_negative | Abono anticipado maternidad |
| `irpf_incremento_maternidad_guarderia` | decimal | non_negative | Incremento deduccion maternidad por guarderias |

### ampliacion_deduc_mater_res (6, single-revision 2022)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_num_hijos_maternidad_2020` | integer | non_negative | Numero hijos deduccion maternidad 2020 (catch-up row; 2022 only) |
| `irpf_incremento_maternidad_no_aplicado_2020` | decimal | non_negative | Incremento maternidad no aplicado 2020 |
| `irpf_incremento_maternidad_guarderia_no_aplicado_2020` | decimal | non_negative | Incremento guarderias maternidad no aplicado 2020 |
| `irpf_num_hijos_maternidad_2021` | integer | non_negative | Numero hijos deduccion maternidad 2021 (catch-up row; 2022 only) |
| `irpf_incremento_maternidad_no_aplicado_2021` | decimal | non_negative | Incremento maternidad no aplicado 2021 |
| `irpf_incremento_maternidad_guarderia_no_aplicado_2021` | decimal | non_negative | Incremento guarderias maternidad no aplicado 2021 |

### deduc_conyuge / descendiente / ascendiente / familia_numerosa / monoparental — supporting fields (30)

| role | data_type | sign | definition |
|---|---|---|---|
| `irpf_conyuge_discapacidad_nombre` | text | — | Nombre del conyuge con discapacidad |
| `irpf_conyuge_discapacidad_fecha_inicio` | text | — | Fecha inicio discapacidad conyuge |
| `irpf_conyuge_discapacidad_fecha_fin` | text | — | Fecha fin discapacidad conyuge |
| `irpf_conyuge_discapacidad_otro_contribuyente_flag` | boolean | — | Otro contribuyente tiene derecho a la deduccion por el conyuge |
| `irpf_matrimonio_vigente_todo_anio_flag` | boolean | — | Matrimonio vigente todo el anio fiscal |
| `irpf_matrimonio_mes_inicio` | integer | non_negative | Primer mes vigencia matrimonio (1–12) |
| `irpf_matrimonio_mes_fin` | integer | non_negative | Ultimo mes completo vigencia matrimonio (1–12) |
| `irpf_deduccion_conyuge_discapacidad` | decimal | non_negative | Importe deduccion conyuge con discapacidad |
| `irpf_abono_anticipado_conyuge_discapacidad` | decimal | non_negative | Abono anticipado deduccion conyuge |
| `irpf_descendiente_discapacidad_nombre` | text | — | Nombre del descendiente con discapacidad |
| `irpf_descendiente_discapacidad_fecha_inicio` | text | — | Fecha inicio discapacidad descendiente |
| `irpf_descendiente_discapacidad_fecha_fin` | text | — | Fecha fin discapacidad descendiente |
| `irpf_descendiente_num_contribuyentes_derecho` | integer | non_negative | Personas con derecho al minimo por descendiente |
| `irpf_descendiente_cedido_flag` | boolean | — | Le han cedido el derecho (descendiente) |
| `irpf_descendiente_cede_flag` | boolean | — | Cede el derecho (descendiente) |
| `irpf_deduccion_descendiente_discapacidad` | decimal | non_negative | Importe deduccion descendiente con discapacidad |
| `irpf_abono_anticipado_descendiente_discapacidad` | decimal | non_negative | Abono anticipado deduccion descendiente |
| `irpf_ascendiente_discapacidad_nombre` | text | — | Nombre del ascendiente con discapacidad |
| `irpf_ascendiente_discapacidad_fecha_inicio` | text | — | Fecha inicio discapacidad ascendiente |
| `irpf_ascendiente_discapacidad_fecha_fin` | text | — | Fecha fin discapacidad ascendiente |
| `irpf_ascendiente_num_contribuyentes_derecho` | integer | non_negative | Personas con derecho al minimo por ascendiente |
| `irpf_ascendiente_cedido_flag` | boolean | — | Le han cedido el derecho (ascendiente) |
| `irpf_ascendiente_cede_flag` | boolean | — | Cede el derecho (ascendiente) |
| `irpf_deduccion_ascendiente_discapacidad` | decimal | non_negative | Importe deduccion ascendiente con discapacidad |
| `irpf_abono_anticipado_ascendiente_discapacidad` | decimal | non_negative | Abono anticipado deduccion ascendiente |
| `irpf_familia_numerosa_titulo_id` | text | — | Numero identificacion titulo familia numerosa |
| `irpf_familia_numerosa_categoria_general_flag` | boolean | — | Categoria General de familia numerosa |
| `irpf_familia_numerosa_categoria_especial_flag` | boolean | — | Categoria Especial de familia numerosa |
| `irpf_familia_numerosa_fecha_inicio` | text | — | Fecha inicio titulo familia numerosa |
| `irpf_familia_numerosa_fecha_caducidad` | text | — | Fecha caducidad titulo |
| `irpf_familia_numerosa_num_ascendientes` | integer | non_negative | Numero ascendientes en la familia numerosa |
| `irpf_familia_numerosa_cedido_flag` | boolean | — | Le han cedido el derecho (familia numerosa) |
| `irpf_familia_numerosa_cede_flag` | boolean | — | Cede el derecho (familia numerosa) |
| `irpf_familia_numerosa_hijos_exceden_minimo_flag` | boolean | — | Hijos exceden minimo de la categoria |
| `irpf_deduccion_familia_numerosa` | decimal | non_negative | Importe deduccion familia numerosa |
| `irpf_abono_anticipado_familia_numerosa` | decimal | non_negative | Abono anticipado deduccion familia numerosa |
| `irpf_deduccion_monoparental` | decimal | non_negative | Importe deduccion familia monoparental |
| `irpf_abono_anticipado_monoparental` | decimal | non_negative | Abono anticipado deduccion monoparental |
| `irpf_regularizacion_cobro_anticipado_descendiente` | decimal | non_negative | Importe cobro anticipado a regularizar (descendiente) |
| `irpf_regularizacion_cobro_anticipado_ascendiente` | decimal | non_negative | Importe cobro anticipado a regularizar (ascendiente) |

---

## Cross-revision id-reuse hazards

No true cross-revision semantic-reuse hazards were found within this cluster
(contrast with casilla 0598, which was documented in the retenciones Phase 2 audit).
All 173 IDs maintain consistent section and semantic meaning across the revisions
in which they appear. Section path changes (e.g., `retenciones_res` sub-section
present only in 2020–2024 because the 2025 form moved those casillas to a standalone
section) are structural reorganisations, not semantic reuse.

**Structural-drift notes (not hazards):**

- **0585, 0586** (`irpf_cuota_liquida_estatal_incrementada` /
  `irpf_cuota_liquida_autonomica_incrementada`): absent from 2025. The 2025 form
  integrates clawback increments directly into the cuota liquida computation
  without materialising separate `incrementada` rows. Roles proposed for
  2020–2024 only; no 2025 casilla carries these roles.

- **0587–0595** (`cuota_autoliquidacion_res` sub-section): absent from 2025.
  The 2025 form restructure eliminated this sub-section; the computation
  path flows directly through result_declaracion without materialising the
  intermediate `cuota_resultante_autoliquidacion` row.

- **0670** (`irpf_resultado_declaracion`): present 2020–2024 only. The 2025
  form replaces this with the externally-visible `resultado_ingresar_o_devolver_irpf`
  on casilla 0700 (already roled, canonical taxonomy). The
  `irpf_resultado_declaracion` role is therefore 2020–2024-scoped only and
  co-exists with the already-roled 0700 (2024–2025) without conflict.

---

## decimal / money divergences

**No `money`-typed casillas were found in this cluster.** All casillas with an
explicit data_type use `decimal` (11 casilla-revision pairs: 0610 ×5, 0669 ×1,
0670 ×5). The remaining ~675 casilla-revision pairs carry no `data_type` field
(blank, not `money`). The bulk-apply pass must infer `decimal` for amount fields
(all numeric roles in this cluster) before writing roles; the intra-role
consistency validator will confirm homogeneity at registry load.

**No decimal/money split roles were created.** All new monetary roles in this
cluster bind to `decimal`. This is consistent with the existing
`base_imponible_irpf` and `resultado_ingresar_o_devolver_irpf` roles that also
bind `decimal` for M100 intermediate computation fields.

---

## Typo-twin warning inventory

Single-revision roles that will trigger the validator's typo-twin advisory at
registry load (expected and documented):

| role | revision(s) | reason |
|---|---|---|
| `irpf_discrepancia_criterio_administrativo` | 2024 only | 2024 one-off administrative override field |
| `irpf_num_hijos_maternidad_2020` | 2022 only | Catch-up row for pre-pandemic deduction backlog |
| `irpf_incremento_maternidad_no_aplicado_2020` | 2022 only | Same catch-up mechanism |
| `irpf_incremento_maternidad_guarderia_no_aplicado_2020` | 2022 only | Same |
| `irpf_num_hijos_maternidad_2021` | 2022 only | 2021-backlog catch-up row |
| `irpf_incremento_maternidad_no_aplicado_2021` | 2022 only | Same |
| `irpf_incremento_maternidad_guarderia_no_aplicado_2021` | 2022 only | Same |

All seven are genuine single-occurrence roles tied to specific legislative
catch-up mechanisms. The warnings are expected output.

---

## Acceptance notes

- **144 casilla IDs** classified; **29 already-roled** (NIF/identity slots) confirmed.
- **~137 new semantic roles** introduced (not counting reused cross-revision
  roles for already-roled IDs). The exact count after deduplication is
  captured in the new-roles tables above.
- All new roles use `irpf_` prefix per the naming convention.
- No `money` data_type is present in this cluster; all numeric roles bind
  `decimal`. Bulk-apply may upgrade absent `data_type` to `decimal` for
  amount casillas; the role consistency validator will enforce homogeneity.
- The 7 single-revision roles (all in `ampliacion_deduc_mater_res` / `datos_extra`)
  will emit typo-twin warnings; these are documented above.
- `irpf_resultado_declaracion` (0670, 2020–2024) intentionally does NOT reuse
  `resultado_ingresar_o_devolver_irpf` — that role is reserved for casilla 0700
  (2024–2025 only) which is the final signed result exposed through the canonical
  result_declaracion surface.
- The new roles should be appended to the canonical taxonomy reference
  (`2026-05-19-schema-hardening-role-taxonomy-reference.md`) after the
  bulk-apply commit lands.
