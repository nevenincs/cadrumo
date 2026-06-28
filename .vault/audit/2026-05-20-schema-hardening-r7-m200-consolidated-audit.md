---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening r7 m200 consolidated role corrections

## Scope

Consolidation of six semantic-role audit batches (batch-1 through batch-6) covering all 566
`semantic_role` values in the Modelo 200 (Impuesto sobre Sociedades) 2024-y-siguientes casilla
registry.

Each batch was audited for: (1) name accuracy against casilla labels and section paths,
(2) member coherence, (3) appropriate granularity. Verdicts were RENAME, SPLIT, OUTLIER, or OK.
This document consolidates all non-OK verdicts into a single conflict-free per-casilla mapping.

Source data: `.vault-scratch/r7-m200/batch-1.json` — `batch-6.json`.
Registry TOMLs consulted for split resolution: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/`.
Read-only: no source files were modified.

---

## Cross-batch conflicts resolved

The following roles appeared in multiple batches with conflicting or potentially inconsistent verdicts.
Each conflict was adjudicated to produce one canonical decision.

### 1. `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_*` family (8 roles, across batches 1–6)

Batches 1, 3, 4, 6 explicitly flagged these roles as RENAME (cooperativas wrong, concept is grupo fiscal
group-exit). Batches 2 and 5 gave OK verdicts for two siblings.

**Decision:** rename the entire family uniformly. Every member label reads
"Eliminaciones pendientes de incorporar de sociedades que dejen de pertenecer a un grupo" — no mention
of cooperativas. The cooperative-specific reading was an authoring error in the original role names.

Canonical stem: `is_correccion_eliminaciones_pendientes_grupo_*`.

### 2. `is_correccion_amortizacion_inmovilizado_actividades_economicas_*` family (8 roles, across batches 1–6)

Batches 1 and 3 explicitly renamed two of the siblings. Batches 2, 4, 5, 6 gave OK verdicts for the
remaining six.

**Decision:** rename the entire family uniformly. Every member in every sibling role is from section
`amortizacion_de_inmovilizado_afecto_a_actividades_de_investigacion_y_desarrollo` (art. 12.3 b) LIS).
`actividades_economicas` is factually wrong for all members.

Canonical stem: `is_correccion_amortizacion_inmovilizado_idi_*`.

### 3. `is_deduccion_copa_america_*` naming (batch-4 roles)

Batch-4 flagged `is_deduccion_copa_america_total` → `is_deduccion_eventos_especiales_pendiente` because
the Copa América event has ended and the members are three different special-event deductions.
Separate roles `is_correccion_copa_america_barcelona_*` keep the Copa América specific event name with
the statutory law reference (Ley 31/2022).

**Decision:** `is_deduccion_copa_america_total` → `is_deduccion_eventos_especiales_pendiente`;
`is_correccion_copa_america_barcelona_*` roles retain event+law reference for statutory traceability.

### 4. `is_tributacion_conjunta_fraccionamiento_resultado` (batch-4)

Batch-4 marked this as both RENAME and SPLIT. The split concern (fraccionamiento result vs. rectificativa
sub-form) is adequately handled by the rename to `is_tributacion_conjunta_fraccionamiento_y_rectificativa`
which signals both variants.

**Decision:** RENAME only; no structural split needed. All 9 members remain together under the renamed role.

### 5. `is_liquidacion_iv_importe` (batch-5) — conflict with batch-4 outliers

Batch-4 sent casillas 01040, 01041, 01587 **to** `is_liquidacion_iv_importe` as their correct home.
Batch-5 then flagged `is_liquidacion_iv_importe` itself for RENAME → `is_liquidacion_iv_resultado_misc`.

**Decision:** apply both. The outlier casillas move to the role; that role is simultaneously renamed.
Final destination for 01040, 01041, 01587: `is_liquidacion_iv_resultado_misc`.

### 6. `is_reserva_nivelacion_adicion` (batch-3) — member 01034 conflict

The SPLIT of `is_reserva_nivelacion_adicion` sends member 01034 to `is_reserva_nivelacion_dotacion`.
Batch-5 then flags `is_reserva_nivelacion_dotacion` as having its own outlier (01034 is Liq III deduction
step, not dotacion schedule).

**Decision:** 01034 goes to a dedicated `is_reserva_nivelacion_deduccion_liquidacion_iii` role which
is its precise semantic home. This resolves the two-step chain without creating a circular move.

### 7. `is_correccion_aumento` vs `is_correcciones_aumentos` (batch-3 outlier vs batch-6 split)

`is_correcciones_aumentos` (batch-3): disminucion casillas move to `is_correcciones_disminuciones`.
`is_correccion_aumento` (batch-6): all members split into exencion vs regimenes_especiales sub-roles.
These are two distinct roles (different names, different content).

**Decision:** both corrections apply independently; no conflict.

### 8. `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_disminucion` (batch-1)

Casillas 03057 and 03058 are temporaria members mislabelled under the permanente role. Their target roles
(`_temporaria_ejercicio_disminucion`, `_temporaria_anteriores_disminucion`) do not appear elsewhere in
the batch JSONs as existing roles. They are new roles that need to be created.

**Decision:** move 03057 and 03058 to new granular roles consistent with the established naming convention.
Only casilla 03056 remains in the permanente role.

---

## Corrections

| id | current_role | correct_role | reason |
|---|---|---|---|
| `00001` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00002` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00003` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00004` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00005` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00006` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00007` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00008` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00009` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00010` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00011` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00012` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00013` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00014` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00015` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00017` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00018` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00019` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00020` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00021` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00022` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00023` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00024` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00025` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00026` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00027` | `base_imponible_negativa_is` | `is_base_imponible_negativa` | missing is_ prefix; all other roles use is_ convention |
| `00028` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00029` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00030` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00031` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00032` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00033` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00034` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00035` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00036` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00037` | `is_identificacion_flag` | `is_identificacion_opcion_flag` | taxpayer election/option flag (fraccionamiento, art.39.2, 0.7%, art.39.3) |
| `00038` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00039` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00043` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00044` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00045` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00046` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00047` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00048` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00049` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00056` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00057` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00058` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00059` | `is_identificacion_flag` | `is_identificacion_opcion_flag` | taxpayer election/option flag (fraccionamiento, art.39.2, 0.7%, art.39.3) |
| `00060` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00061` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00062` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00063` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00064` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00065` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00066` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00068` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00069` | `is_naviera_importe` | `is_naviera_regimen_flag` | member is decimal identification checkbox for Canarian shipping tonnage regime, not monetary amount |
| `00070` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00071` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00072` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00073` | `is_identificacion_flag` | `is_identificacion_opcion_flag` | taxpayer election/option flag (fraccionamiento, art.39.2, 0.7%, art.39.3) |
| `00074` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00078` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00079` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00080` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00081` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00082` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00083` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00084` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00085` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00086` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00087` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00088` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00089` | `is_identificacion_flag` | `is_identificacion_regimen_flag` | entity type / regime identification checkbox |
| `00090` | `is_identificacion_flag` | `is_identificacion_opcion_flag` | taxpayer election/option flag (fraccionamiento, art.39.2, 0.7%, art.39.3) |
| `00181` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `00183` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `00253` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00254` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00255` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00256` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00257` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00258` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00259` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00260` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00261` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00262` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00263` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00264` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00265` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00266` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00267` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00268` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00269` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00270` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00271` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00272` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00273` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00274` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00275` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00276` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00277` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00278` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00279` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00280` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00281` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00282` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00283` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00284` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00285` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00286` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00287` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00288` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00289` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00290` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00291` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00292` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00293` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00294` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00295` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00296` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00297` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00298` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00299` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00300` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00301` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00302` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00303` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00304` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00305` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00306` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00307` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00308` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00309` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00310` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00311` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00312` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00313` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00314` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00315` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00316` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00317` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00318` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00319` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00320` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00321` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00322` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00323` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00324` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00325` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00326` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00327` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00328` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00329` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00330` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00331` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00332` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00334` | `is_atribucion_rentas_importe` | `is_correccion_asimetrias_hibridas_atribucion_rentas_importe` | asimetrias hibridas art.15 bis.12 LIS attributions |
| `00336` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_imputados_importe` | ECPN split by sub-section: ingresos_y_gastos_imputados_al_patrimonio_neto |
| `00337` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_imputados_importe` | ECPN split by sub-section: ingresos_y_gastos_imputados_al_patrimonio_neto |
| `00338` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_imputados_importe` | ECPN split by sub-section: ingresos_y_gastos_imputados_al_patrimonio_neto |
| `00339` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_imputados_importe` | ECPN split by sub-section: ingresos_y_gastos_imputados_al_patrimonio_neto |
| `00340` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_imputados_importe` | ECPN split by sub-section: ingresos_y_gastos_imputados_al_patrimonio_neto |
| `00341` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_imputados_importe` | ECPN split by sub-section: ingresos_y_gastos_imputados_al_patrimonio_neto |
| `00342` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_imputados_importe` | ECPN split by sub-section: ingresos_y_gastos_imputados_al_patrimonio_neto |
| `00343` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_imputados_importe` | ECPN split by sub-section: ingresos_y_gastos_imputados_al_patrimonio_neto |
| `00344` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_imputados_importe` | ECPN split by sub-section: ingresos_y_gastos_imputados_al_patrimonio_neto |
| `00345` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_imputados_importe` | ECPN split by sub-section: ingresos_y_gastos_imputados_al_patrimonio_neto |
| `00346` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_transferencias_perdidas_ganancias_importe` | ECPN split by sub-section: transferencias_a_la_cta_perdidas_y_ganancias |
| `00347` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_transferencias_perdidas_ganancias_importe` | ECPN split by sub-section: transferencias_a_la_cta_perdidas_y_ganancias |
| `00348` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_transferencias_perdidas_ganancias_importe` | ECPN split by sub-section: transferencias_a_la_cta_perdidas_y_ganancias |
| `00349` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_transferencias_perdidas_ganancias_importe` | ECPN split by sub-section: transferencias_a_la_cta_perdidas_y_ganancias |
| `00350` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_transferencias_perdidas_ganancias_importe` | ECPN split by sub-section: transferencias_a_la_cta_perdidas_y_ganancias |
| `00351` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_transferencias_perdidas_ganancias_importe` | ECPN split by sub-section: transferencias_a_la_cta_perdidas_y_ganancias |
| `00352` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_transferencias_perdidas_ganancias_importe` | ECPN split by sub-section: transferencias_a_la_cta_perdidas_y_ganancias |
| `00353` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_transferencias_perdidas_ganancias_importe` | ECPN split by sub-section: transferencias_a_la_cta_perdidas_y_ganancias |
| `00354` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_transferencias_perdidas_ganancias_importe` | ECPN split by sub-section: transferencias_a_la_cta_perdidas_y_ganancias |
| `00355` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_transferencias_perdidas_ganancias_importe` | ECPN split by sub-section: transferencias_a_la_cta_perdidas_y_ganancias |
| `00356` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00358` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00360` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00362` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00363` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_ajuste_liquidacion` | P&L adjustment rows for art.16 LIS in Liquidacion I |
| `00364` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_ajuste_liquidacion` | P&L adjustment rows for art.16 LIS in Liquidacion I |
| `00366` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `00368` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00370` | `is_liquidacion_ii_importe` | `is_liquidacion_ii_detalle_correcciones` | members are correction detail rows, not all Liq-II values; rename clarifies scope |
| `00372` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00374` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00376` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00378` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00380` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00381` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00382` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00383` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00384` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00385` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00386` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00387` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00388` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00389` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00390` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00391` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00392` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00393` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ejercicio_anterior_importe` | ECPN split by sub-section: saldo_final_del_ejercicio_anterior |
| `00394` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00395` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00396` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00397` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00398` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00399` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00400` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00401` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00402` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00403` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00404` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00405` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00406` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00407` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_criterio_importe` | ECPN split by sub-section: ajustes_por_cambio_de_criterio_de_ejercicios_anter |
| `00408` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00409` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00410` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00411` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00412` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00413` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00414` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00415` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00416` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00417` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00418` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00419` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00420` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00421` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ajuste_errores_importe` | ECPN split by sub-section: ajustes_por_errores_de_ejercicios_anteriores |
| `00422` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00423` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00424` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00425` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00426` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00427` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00428` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00429` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00430` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00431` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00432` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00433` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00434` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00435` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_ajustado_inicio_importe` | ECPN split by sub-section: saldo_ajustado_inicio_del_ejercicio |
| `00436` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00437` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00438` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00439` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00440` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00441` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00442` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00443` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00444` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00445` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00446` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00448` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00449` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_total_ingresos_gastos_reconocidos_importe` | ECPN split by sub-section: total_ingresos_y_gastos_reconocidos |
| `00450` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00451` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00452` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00453` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00454` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00455` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00456` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00457` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00458` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00459` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `00461` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00462` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00463` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_resultado_perdidas_ganancias_importe` | ECPN split by sub-section: resultado_cuenta_perdidas_y_ganancias |
| `00464` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00465` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00466` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00467` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00468` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00469` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00470` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00471` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00472` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00473` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `00474` | `is_tributacion_conjunta_cuota` | `is_tributacion_conjunta_cuota_diferencial` | cuota diferencial liquidacion result for Araba/Alava |
| `00475` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00476` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00477` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00478` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00479` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00480` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00481` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00482` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00483` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00484` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00485` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00486` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00489` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00490` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00491` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00492` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00493` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00494` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00495` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00496` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00497` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00498` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00499` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00500` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00502` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00503` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00504` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00505` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_ingresos_gastos_en_pn_importe` | ECPN split by sub-section: ingresos_y_gastos_reconocidos_en_patrimonio_neto |
| `00506` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00507` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00508` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00509` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00510` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00511` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00512` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00513` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00514` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00515` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00516` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00517` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00518` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00519` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00520` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00521` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00522` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00523` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00524` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00525` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00526` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00527` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00528` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00529` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00530` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00531` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00532` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00533` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00534` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00535` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00536` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00537` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00538` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00539` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00540` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00541` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00542` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00543` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00544` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00545` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00546` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00547` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00548` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00549` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00550` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00551` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00552` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00553` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00554` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00555` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00556` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00557` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00558` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00559` | `is_base_imponible` | `is_base_imponible_zec_importe` | ZEC BI at special rate adjustment (disminuciones) |
| `00560` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00561` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00562` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00563` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00564` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00565` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00566` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00567` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00568` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00569` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00570` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00571` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00572` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00574` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00575` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00576` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00577` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00578` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00579` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00580` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00581` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00582` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00583` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00584` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00585` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00586` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00588` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00589` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00590` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00591` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00593` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00594` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00595` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00596` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00597` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00598` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00599` | `resultado_ingresar_o_devolver_is` | `is_resultado_ingresar_o_devolver` | missing is_ prefix; all other roles use is_ convention |
| `00600` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00602` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00603` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00604` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00605` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00606` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00607` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00608` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00609` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00610` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00611` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00612` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00613` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00614` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00615` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00616` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00617` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_operaciones_socios_importe` | ECPN split by sub-section: operaciones_con_socios_o_propietarios |
| `00618` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00619` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00620` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00621` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00622` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00623` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00624` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00625` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00626` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00627` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00628` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00629` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00630` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00631` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00632` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00633` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00634` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00635` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00636` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00637` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00638` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00639` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00640` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00641` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00642` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00643` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00644` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00645` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_saldo_final_importe` | ECPN split by sub-section: saldo_final_del_ejercicio |
| `00646` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00648` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00649` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00651` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00652` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00654` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00655` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00657` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00658` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00660` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00661` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00663` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00664` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00666` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00667` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00669` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00675` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00696` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `00697` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `00699` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00705` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00706` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00707` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00708` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00709` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00710` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00711` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00714` | `is_deduccion_di_interna_rdleg_importe` | `is_deduccion_di_interna_rdleg_detalle` | importe implies uniform monetary; one member (00920) is tipo_gravamen rate, not amount |
| `00715` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00716` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00717` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00718` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00719` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00720` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00721` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00722` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00723` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00724` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00725` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00726` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00727` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00728` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00729` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00730` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00731` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00732` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00733` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00734` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00735` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00736` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00737` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00738` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00739` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00740` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00741` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00742` | `is_estado_cambios_patrimonio_neto_importe` | `is_ecpn_otras_variaciones_importe` | ECPN split by sub-section: otras_variaciones_del_patrimonio_neto |
| `00743` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00747` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00748` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00760` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00761` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00762` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00763` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00770` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00771` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00772` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00776` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `00790` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00791` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00792` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00793` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00794` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00796` | `is_cuenta_perdidas_ganancias_importe` | `is_pyg_importe` | spans P&L I, P&L II, operaciones interrumpidas, cooperativa lines; pyg is cleaner and avoids roman-numeral split implication |
| `00803` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `00804` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `00810` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `00813` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `00829` | `is_deduccion_idi_diferimiento_periodo` | `is_deduccion_idi_diferimiento_aplicado_periodo` | member is aplicado en esta liquidacion; _periodo vague |
| `00831` | `is_deduccion_idi_total` | `is_deduccion_actividades_total_pendiente` | idi prefix wrong; member is grand total for ALL actividades incentivadas (section=total) |
| `00841` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `00843` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `00846` | `is_deduccion_di_interna_rdleg_importe` | `is_deduccion_di_interna_rdleg_detalle` | importe implies uniform monetary; one member (00920) is tipo_gravamen rate, not amount |
| `00847` | `is_deduccion_di_interna_rdleg_importe` | `is_deduccion_di_interna_rdleg_detalle` | importe implies uniform monetary; one member (00920) is tipo_gravamen rate, not amount |
| `00866` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `00881` | `is_deduccion_inversiones_africa_canarias_periodo` | `is_deduccion_inversiones_africa_canarias_pendiente` | label is Pendiente aplicacion periodos futuros, not applied-in-period amount |
| `00896` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00898` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `00920` | `is_deduccion_di_interna_rdleg_importe` | `is_deduccion_di_interna_rdleg_detalle` | importe implies uniform monetary; one member (00920) is tipo_gravamen rate, not amount |
| `00921` | `is_deduccion_di_internacional_rdleg_importe` | `is_deduccion_di_internacional_rdleg_tipo_gravamen` | Tipo gravamen periodo generacion 2013 (decimal rate field), not monetary deduction amount |
| `00925` | `is_compensacion_bases_negativas` | `is_liquidacion_iii_importe` | Liq III BI correction (rentas que no limitan compensacion BINs), not BIN application entry |
| `00926` | `is_deduccion_di_internacional_rdleg_importe` | `is_deduccion_di_internacional_rdleg_tipo_gravamen` | Tipo gravamen periodo generacion 2014 (decimal rate field), not monetary deduction amount |
| `00932` | `is_base_imponible` | `is_base_imponible_cooperativa_ajuste` | cooperativa-specific BI adjustment (reversion deterioro DT16a.8) |
| `00945` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `00946` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `00960` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `00961` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `00966` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `00967` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `00986` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `00991` | `is_correccion_reversion_deterioro_valores_saldo_final` | `is_correccion_reversion_deterioro_valores_pendiente_futuros` | member is pending-future dotaciones carryforward, not a traditional saldo_final balance |
| `01004` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `01006` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01009` | `is_correccion_deterioro_participaciones_dt16_saldo_inicial` | `is_correccion_deterioro_participaciones_dt16_saldo_inicial_neto` | pairs DT16a.3 and DT16a.1/2 aumento+disminucion opening balances; _neto signals bi-directional pairing |
| `01012` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `01013` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01014` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01016` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01019` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `01022` | `is_liquidacion_ii_importe` | `is_liquidacion_ii_detalle_correcciones` | members are correction detail rows, not all Liq-II values; rename clarifies scope |
| `01023` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `01026` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01028` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01029` | `is_liquidacion_ii_importe` | `is_liquidacion_ii_detalle_correcciones` | members are correction detail rows, not all Liq-II values; rename clarifies scope |
| `01032` | `is_base_imponible` | `is_reserva_capitalizacion_importe` | capitalizacion reserve BI deduction - belongs to capitalizacion schedule |
| `01033` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_dotacion` | Liq III ERD nivelacion Aumentos - belongs to dotacion not adicion schedule |
| `01034` | `is_reserva_nivelacion_dotacion` | `is_reserva_nivelacion_deduccion_liquidacion_iii` | Liq III ERD nivelacion Disminuciones - belongs to Liq III deduction step, not dotacion schedule |
| `01037` | `is_base_imponible` | `is_base_imponible_cooperativa_ajuste` | cooperativa-specific BI adjustment (art.11.12 LIS limit disminucion) |
| `01039` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `01040` | `is_deduccion_reversion_medidas_periodo` | `is_liquidacion_iv_importe` | Liq IV summary line amount (DT37a.1 applied), not period-by-period deduccion detail |
| `01041` | `is_deduccion_reversion_medidas_periodo` | `is_liquidacion_iv_importe` | Liq IV summary line amount (DT37a.2 applied), not period-by-period deduccion detail |
| `01042` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `01045` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `01047` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `01048` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `01049` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `01050` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01051` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01052` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01054` | `is_deduccion_di_internacional_generado` | `is_deduccion_di_internacional_lis_pendiente_generado` | _generado imprecise; casilla is pending/generated balance, not the generating event |
| `01055` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01056` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01063` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `01064` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `01066` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `01067` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `01083` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `01098` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01099` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01100` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01101` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01102` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01104` | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | `is_correccion_limite_beneficio_operativo_pendiente_adicion_aplicado` | _dotaciones_aplicadas implies provisioning; actual content is gastos financieros pendientes applied amounts |
| `01105` | `is_correccion_limite_beneficio_operativo_saldo_final` | `is_correccion_limite_beneficio_operativo_pendiente` | members are Pendiente aplicacion periodos futuros, not closing-balance saldo_final entries |
| `01109` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `01111` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `01137` | `is_reserva_capitalizacion_pendiente` | `is_reserva_capitalizacion_derecho_generado` | opening balance / newly generated capitalization right (concept a) |
| `01139` | `is_reserva_capitalizacion_pendiente` | `is_reserva_capitalizacion_pendiente_futuros` | carry-forward pending BI reduction amounts (concept b) |
| `01147` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `01149` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `01163` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `01167` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `01170` | `is_deduccion_reversion_medidas_total` | `is_deduccion_reversion_medidas_dt1_total` | DT 37a.1 LIS total row (base deduccion + importe pendiente) |
| `01171` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `01173` | `is_deduccion_reversion_medidas_total` | `is_deduccion_reversion_medidas_dt1_total` | DT 37a.1 LIS total row (base deduccion + importe pendiente) |
| `01179` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `01182` | `is_deduccion_reversion_medidas_total` | `is_deduccion_reversion_medidas_dt2_total` | DT 37a.2 LIS total row (base deduccion + importe pendiente) |
| `01183` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `01184` | `is_correccion_libertad_amortizacion_vehiculos_saldo_inicial` | `is_correccion_libertad_amortizacion_vehiculos_saldo_inicial_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `01185` | `is_deduccion_reversion_medidas_total` | `is_deduccion_reversion_medidas_dt2_total` | DT 37a.2 LIS total row (base deduccion + importe pendiente) |
| `01188` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01189` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01191` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01193` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01194` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01196` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01198` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01199` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01201` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01202` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01203` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01204` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01205` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01206` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01209` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01210` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01211` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01212` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01213` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01214` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01215` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01216` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01230` | `is_resultado_contable` | `is_correcciones_resultado_contable_grupo_fiscal_aumento` | current name is semantically false; member is grupo fiscal correction to accounting result (aumento), not the resultado contable itself |
| `01231` | `is_correcciones_resultado_contable_impuesto` | `is_correcciones_impuesto_grupo_fiscal_disminucion` | grupo fiscal IS tax correction (disminucion); current name obscures IS and grupo fiscal scope |
| `01234` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `01240` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01241` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01242` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01243` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01244` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01245` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01246` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01247` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01248` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01249` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01250` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01251` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01252` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01253` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01254` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01255` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01256` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01257` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01258` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01259` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01260` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `01270` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01276` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `01285` | `is_base_imponible` | `is_base_imponible_cooperativa_ajuste` | cooperativa-specific BI adjustment (nivelacion converted to cuotas aumentos) |
| `01299` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01300` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01301` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01302` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01303` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01305` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01306` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01307` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01308` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01309` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01310` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01311` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01313` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01314` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01315` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01317` | `is_deduccion_cinematografica_extranjera_total` | `is_deduccion_cinematografica_extranjera_canarias_total` | Canarias-specific art.36.2 LIS + DA 14a Ley 19/1994; mainland art.36.2-only members remain in old role |
| `01318` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01319` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `01321` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `01322` | `is_deduccion_cinematografica_extranjera_total` | `is_deduccion_cinematografica_extranjera_canarias_total` | Canarias-specific art.36.2 LIS + DA 14a Ley 19/1994; mainland art.36.2-only members remain in old role |
| `01330` | `is_base_imponible` | `is_base_imponible_postnivelacion` | BI after nivelacion reserve - summary line |
| `01332` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `01333` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01334` | `is_tributacion_conjunta_cuota` | `is_tributacion_conjunta_abono_idi` | abono deducciones I+D+i insuf. cuota - cash refund mechanism, not cuota differential |
| `01338` | `is_conversion_aid_abono` | `is_tributacion_conjunta_abono_deducciones_cinematograficas` | Tributacion Conjunta abono de deducciones cinematograficas Araba/Alava - not AID conversion abono |
| `01343` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01346` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01348` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01349` | `is_deduccion_di_internacional_tipo_gravamen` | `is_deduccion_di_internacional_tipo_gravamen_periodo_generacion` | clarify field is applicable rate at time of generation, not a current-period rate |
| `01350` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01351` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01353` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01354` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01360` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01361` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01362` | `is_deduccion_di_internacional_tipo_gravamen` | `is_deduccion_di_internacional_tipo_gravamen_periodo_generacion` | clarify field is applicable rate at time of generation, not a current-period rate |
| `01363` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `01364` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `01378` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `01382` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `01393` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01394` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01395` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01396` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01397` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01399` | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | `is_correccion_limite_beneficio_operativo_pendiente_adicion_aplicado` | _dotaciones_aplicadas implies provisioning; actual content is gastos financieros pendientes applied amounts |
| `01400` | `is_correccion_limite_beneficio_operativo_saldo_final` | `is_correccion_limite_beneficio_operativo_pendiente` | members are Pendiente aplicacion periodos futuros, not closing-balance saldo_final entries |
| `01401` | `is_reserva_capitalizacion_pendiente` | `is_reserva_capitalizacion_derecho_generado` | opening balance / newly generated capitalization right (concept a) |
| `01404` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_realizada` | already-realized additions in period (concept b); role is_reserva_nivelacion_adicion_realizada already exists |
| `01407` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `01439` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `01443` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `01448` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `01452` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `01457` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01462` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01463` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01464` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01465` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01466` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01472` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01475` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `01480` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `01482` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `01488` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `01492` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `01497` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `01505` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01509` | `is_compensacion_bases_negativas` | `is_liquidacion_iii_importe` | Liq III BI correction (reversion deterioros DT16a.8 LIS disminuciones), not BIN application entry |
| `01515` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01519` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `01521` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `01522` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01524` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01525` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01526` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01527` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01528` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01529` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01530` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01531` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01532` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01533` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01534` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01535` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01536` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01537` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01538` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01539` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01540` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01541` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01571` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01573` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `01575` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `01576` | `is_base_imponible` | `is_base_imponible_zec_importe` | ZEC naviero BI subject to special shipping regime |
| `01578` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `01583` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `01584` | `is_tributacion_conjunta_rectificacion` | `is_liquidacion_iv_rectificacion_importe` | Liq IV rectificativa devolucion acordada; structurally different from foral joint-taxation rectifications |
| `01585` | `is_tributacion_conjunta_rectificacion` | `is_liquidacion_iv_rectificacion_importe` | Liq IV rectificativa devolucion acordada; structurally different from foral joint-taxation rectifications |
| `01586` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `01587` | `is_tributacion_conjunta_resultado` | `is_liquidacion_iv_importe` | Liq IV resultado D.Forales/Navarra - not in tributacion conjunta schedule |
| `01588` | `is_base_imponible` | `is_fraccionamiento_cambio_residencia_bi` | fraccionamiento art.19.1 LIS BI integrado - Estado |
| `01589` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01590` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01591` | `is_conversion_aid_dt33a_importe` | `is_conversion_activos_impuesto_diferido_dt33a_importe` | expand aid acronym to match registry section name for clarity |
| `01592` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `01594` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `01595` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01597` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01598` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01602` | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_aumento` | `is_correccion_deterioro_participaciones_dt16_all_temporaria_ejercicio_aumento` | covers DT16a.3 and DT16a.1/2 both; all qualifier signals multi-paragraph coverage |
| `01607` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `01608` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `01609` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `01610` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `01611` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `01612` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `01613` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `01617` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `01618` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `01623` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `01627` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `01647` | `is_tributacion_conjunta_fraccionamiento_resultado` | `is_tributacion_conjunta_fraccionamiento_y_rectificativa` | members include both fraccionamiento-result and rectificativa sub-form; rename signals both variants |
| `01648` | `is_tributacion_conjunta_fraccionamiento_resultado` | `is_tributacion_conjunta_fraccionamiento_y_rectificativa` | members include both fraccionamiento-result and rectificativa sub-form; rename signals both variants |
| `01649` | `is_tributacion_conjunta_fraccionamiento_resultado` | `is_tributacion_conjunta_fraccionamiento_y_rectificativa` | members include both fraccionamiento-result and rectificativa sub-form; rename signals both variants |
| `01650` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `01651` | `is_tributacion_conjunta_fraccionamiento_resultado` | `is_tributacion_conjunta_fraccionamiento_y_rectificativa` | members include both fraccionamiento-result and rectificativa sub-form; rename signals both variants |
| `01652` | `is_tributacion_conjunta_fraccionamiento_resultado` | `is_tributacion_conjunta_fraccionamiento_y_rectificativa` | members include both fraccionamiento-result and rectificativa sub-form; rename signals both variants |
| `01653` | `is_tributacion_conjunta_fraccionamiento_resultado` | `is_tributacion_conjunta_fraccionamiento_y_rectificativa` | members include both fraccionamiento-result and rectificativa sub-form; rename signals both variants |
| `01655` | `is_tributacion_conjunta_fraccionamiento_resultado` | `is_tributacion_conjunta_fraccionamiento_y_rectificativa` | members include both fraccionamiento-result and rectificativa sub-form; rename signals both variants |
| `01656` | `is_tributacion_conjunta_fraccionamiento_resultado` | `is_tributacion_conjunta_fraccionamiento_y_rectificativa` | members include both fraccionamiento-result and rectificativa sub-form; rename signals both variants |
| `01657` | `is_tributacion_conjunta_fraccionamiento_resultado` | `is_tributacion_conjunta_fraccionamiento_y_rectificativa` | members include both fraccionamiento-result and rectificativa sub-form; rename signals both variants |
| `01658` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01659` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01660` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01661` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01662` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01663` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01664` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01665` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01666` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01667` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01668` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01669` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01670` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01671` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01672` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01673` | `is_conversion_aid_importe` | `is_conversion_aid_conjunta_importe` | all members in tributacion_conjunta block; bare importe hides conjunta context |
| `01683` | `is_deduccion_idi_otras` | `is_deduccion_acontecimiento_interes_publico_otras` | idi prefix wrong; member is support programme for public-interest events (art.27.3 Ley 49/2002 type) |
| `01684` | `is_deduccion_copa_america_periodo` | `is_deduccion_eventos_especiales_aplicado_periodo` | Copa America name wrong; members are 4 different special-event deductions applied in period |
| `01685` | `is_deduccion_copa_america_total` | `is_deduccion_eventos_especiales_pendiente` | Copa America ended; members are 3 different special-event deducciones pending-future |
| `01722` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `01726` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `01730` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_realizada` | already-realized additions in period (concept b); role is_reserva_nivelacion_adicion_realizada already exists |
| `01731` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `01733` | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_disminucion` | `is_correccion_deterioro_participaciones_capital_dt16_temporaria_ejercicio_disminucion` | add capital qualifier to clarify coverage of participaciones in capital/fondos propios under DT 16a |
| `01736` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01737` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01738` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01739` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01740` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01741` | `is_correccion_libertad_amortizacion_vehiculos_permanente_aumento` | `is_correccion_libertad_amortizacion_vehiculos_aumento` | permanente qualifier inaccurate; role also contains temporaria anteriores member |
| `01751` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `01764` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01765` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01770` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01771` | `is_deduccion_di_internacional_tipo_gravamen` | `is_deduccion_di_internacional_tipo_gravamen_periodo_generacion` | clarify field is applicable rate at time of generation, not a current-period rate |
| `01772` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01773` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01775` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01776` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01806` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `01808` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01811` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `01812` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01814` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01819` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01820` | `is_correccion_libertad_amortizacion_vehiculos_permanente_aumento` | `is_correccion_libertad_amortizacion_vehiculos_aumento` | permanente qualifier inaccurate; role also contains temporaria anteriores member |
| `01824` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `01825` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `01827` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `01828` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01830` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01831` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `01833` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01834` | `is_deduccion_di_internacional_tipo_gravamen` | `is_deduccion_di_internacional_tipo_gravamen_periodo_generacion` | clarify field is applicable rate at time of generation, not a current-period rate |
| `01835` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01836` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `01838` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01839` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `01841` | `is_atribucion_rentas_importe` | `is_correccion_asimetrias_hibridas_atribucion_rentas_importe` | asimetrias hibridas art.15 bis.12 LIS attributions |
| `01846` | `is_atribucion_rentas_importe` | `is_correccion_asimetrias_hibridas_atribucion_rentas_importe` | asimetrias hibridas art.15 bis.12 LIS attributions |
| `01848` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `01849` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `01850` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `01851` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `01856` | `is_atribucion_rentas_importe` | `is_correccion_asimetrias_hibridas_atribucion_rentas_importe` | asimetrias hibridas art.15 bis.12 LIS attributions |
| `01860` | `is_correccion_deterioro_participaciones_dt16_saldo_inicial` | `is_correccion_deterioro_participaciones_dt16_saldo_inicial_neto` | pairs DT16a.3 and DT16a.1/2 aumento+disminucion opening balances; _neto signals bi-directional pairing |
| `01862` | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_aumento` | `is_correccion_deterioro_participaciones_dt16_all_temporaria_ejercicio_aumento` | covers DT16a.3 and DT16a.1/2 both; all qualifier signals multi-paragraph coverage |
| `01865` | `is_correccion_deterioro_participaciones_dt16_saldo_inicial` | `is_correccion_deterioro_participaciones_dt16_saldo_inicial_neto` | pairs DT16a.3 and DT16a.1/2 aumento+disminucion opening balances; _neto signals bi-directional pairing |
| `01867` | `is_correccion_deterioro_participaciones_dt16_temporaria_ejercicio_disminucion` | `is_correccion_deterioro_participaciones_capital_dt16_temporaria_ejercicio_disminucion` | add capital qualifier to clarify coverage of participaciones in capital/fondos propios under DT 16a |
| `01873` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `01874` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `01875` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `01877` | `is_conversion_aid_abono` | `is_tributacion_conjunta_abono_deducciones_cinematograficas` | Tributacion Conjunta abono deducciones producciones extranjeras en Canarias Araba/Alava - not AID abono |
| `01881` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `01884` | `is_correccion_libertad_amortizacion_vehiculos_saldo_inicial` | `is_correccion_libertad_amortizacion_vehiculos_saldo_inicial_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `01887` | `is_compensacion_bases_negativas` | `is_liquidacion_iii_importe` | Liq III BI (naviera shipping regime compensacion BINs actividades especiales), not general BIN schedule |
| `01890` | `is_compensacion_bases_negativas` | `is_liquidacion_iii_importe` | Liq III BI (naviera shipping regime compensacion BINs resto actividades), not general BIN schedule |
| `01892` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `01893` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01906` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `01931` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01932` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01933` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01937` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01938` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01939` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01940` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01942` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01943` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01944` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01946` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01947` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01948` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `01954` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `01958` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `01977` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01978` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01979` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01980` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01981` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `01992` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `01995` | `is_correccion_deterioro_participaciones_dt16_saldo_inicial` | `is_correccion_deterioro_participaciones_dt16_saldo_inicial_neto` | pairs DT16a.3 and DT16a.1/2 aumento+disminucion opening balances; _neto signals bi-directional pairing |
| `02076` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `02079` | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | `is_informacion_adicional_limites_deducciones_canarias_generada` | _base_deduccion not in labels; members are generated amounts for Canarias deduction limits information |
| `02080` | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | `is_informacion_adicional_limites_deducciones_canarias_generada` | _base_deduccion not in labels; members are generated amounts for Canarias deduction limits information |
| `02087` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02091` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02092` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02094` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02095` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02097` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02098` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02109` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02110` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02111` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02120` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `02126` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `02128` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02129` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02130` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02132` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02133` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02134` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02136` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02137` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02138` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02140` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02141` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02142` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02145` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02146` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02148` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02149` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02150` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02152` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02153` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02154` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02156` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02157` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02158` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02160` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02161` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02162` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02164` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02165` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02166` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02168` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02169` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02170` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02172` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02173` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02174` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02176` | `is_correccion_copa_america_barcelona_saldo_inicial` | `is_correccion_copa_america_barcelona_saldo_inicial_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02180` | `is_correccion_copa_america_barcelona_saldo_final` | `is_correccion_copa_america_ley_31_2022_saldo_final` | preserve statutory reference (Ley 31/2022) for specificity |
| `02181` | `is_liquidacion_ii_importe` | `is_liquidacion_ii_detalle_correcciones` | members are correction detail rows, not all Liq-II values; rename clarifies scope |
| `02182` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `02183` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `02184` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `02185` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `02186` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `02187` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `02188` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `02189` | `is_correcciones_disminuciones` | `is_correcciones_disminuciones_liquidacion_detalle` | members from liquidacion I/II detail schedules, distinct from regime-level is_correccion_disminucion |
| `02193` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `02195` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `02196` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `02198` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `02199` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `02201` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `02202` | `is_deduccion_di_internacional_tipo_gravamen` | `is_deduccion_di_internacional_tipo_gravamen_periodo_generacion` | clarify field is applicable rate at time of generation, not a current-period rate |
| `02203` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `02204` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `02206` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `02207` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `02216` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `02221` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `02222` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `02235` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `02253` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02254` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02255` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02256` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02257` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02259` | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | `is_correccion_limite_beneficio_operativo_pendiente_adicion_aplicado` | _dotaciones_aplicadas implies provisioning; actual content is gastos financieros pendientes applied amounts |
| `02265` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `02287` | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | `is_informacion_adicional_limites_deducciones_canarias_generada` | _base_deduccion not in labels; members are generated amounts for Canarias deduction limits information |
| `02288` | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | `is_informacion_adicional_limites_deducciones_canarias_generada` | _base_deduccion not in labels; members are generated amounts for Canarias deduction limits information |
| `02289` | `is_correccion_copa_america_barcelona_saldo_inicial` | `is_correccion_copa_america_barcelona_saldo_inicial_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02292` | `is_correccion_copa_america_barcelona_temporaria_anteriores_disminucion` | `is_correccion_copa_america_ley_31_2022_temporaria_anteriores_disminucion` | preserve statutory reference (Ley 31/2022) for specificity |
| `02293` | `is_correccion_copa_america_barcelona_saldo_final` | `is_correccion_copa_america_ley_31_2022_saldo_final` | preserve statutory reference (Ley 31/2022) for specificity |
| `02294` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02295` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02297` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02298` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02300` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02303` | `is_correccion_detalle_correcciones_resultado_temporaria_ejercicio_aumento` | `is_correccion_detalle_resultado_temporaria_aumento` | _ejercicio qualifier inaccurate; member 02307 covers prior-year temporaries not only current-year |
| `02307` | `is_correccion_detalle_correcciones_resultado_temporaria_ejercicio_aumento` | `is_correccion_detalle_resultado_temporaria_aumento` | _ejercicio qualifier inaccurate; member 02307 covers prior-year temporaries not only current-year |
| `02310` | `is_correccion_detalle_correcciones_resultado_saldo_final_disminucion` | `is_correccion_temporarias_saldo_final_disminuciones_futuras` | member is aggregate future-decrease residual for temporary corrections at period end |
| `02311` | `is_liquidacion_i_importe` | `is_correcciones_aumentos` | detail correction increase row (art.15n LIS autoridades portuarias), not P&L result |
| `02314` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `02316` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `02318` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `02319` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `02321` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `02322` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `02324` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `02325` | `is_deduccion_di_internacional_tipo_gravamen` | `is_deduccion_di_internacional_tipo_gravamen_periodo_generacion` | clarify field is applicable rate at time of generation, not a current-period rate |
| `02326` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `02327` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `02329` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `02330` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `02336` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `02339` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `02342` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `02345` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `02351` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `02354` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02355` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02356` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `02357` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `02368` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `02369` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_limite_art16_calculo` | art.16 LIS computational limit worksheet casillas |
| `02370` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02378` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `02384` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `02388` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `02399` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02400` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02401` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02402` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02403` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02405` | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | `is_correccion_limite_beneficio_operativo_pendiente_adicion_aplicado` | _dotaciones_aplicadas implies provisioning; actual content is gastos financieros pendientes applied amounts |
| `02406` | `is_correccion_limite_beneficio_operativo_saldo_final` | `is_correccion_limite_beneficio_operativo_pendiente` | members are Pendiente aplicacion periodos futuros, not closing-balance saldo_final entries |
| `02407` | `is_tributacion_conjunta_rectificacion` | `is_tributacion_conjunta_estado_forales_rectificacion_importe` | foral joint-taxation rectification/discrepancy amounts |
| `02409` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02410` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `02435` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `02437` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02438` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02442` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02443` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02444` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02448` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02449` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02450` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02461` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02465` | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | `is_correccion_limite_beneficio_operativo_pendiente_adicion_aplicado` | _dotaciones_aplicadas implies provisioning; actual content is gastos financieros pendientes applied amounts |
| `02466` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02467` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `02470` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `02480` | `is_base_imponible` | `is_fraccionamiento_cambio_residencia_bi` | fraccionamiento art.19.1 LIS BI integrado - D.Forales/Navarra |
| `02495` | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | `is_informacion_adicional_limites_deducciones_canarias_generada` | _base_deduccion not in labels; members are generated amounts for Canarias deduction limits information |
| `02496` | `is_correccion_info_adicional_limites_deducciones_importe_base_deduccion` | `is_informacion_adicional_limites_deducciones_canarias_generada` | _base_deduccion not in labels; members are generated amounts for Canarias deduction limits information |
| `02500` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `02514` | `is_correccion_operaciones_a_plazos_art11_4_saldo_inicial` | `is_correccion_operaciones_a_plazos_art11_4_saldo_inicial_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02519` | `is_correccion_operaciones_a_plazos_art11_4_saldo_inicial` | `is_correccion_operaciones_a_plazos_art11_4_saldo_inicial_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02525` | `is_correccion_reversion_deterioro_elementos_saldo_final` | `is_correccion_reversion_deterioro_elementos_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02530` | `is_correccion_reversion_deterioro_elementos_saldo_final` | `is_correccion_reversion_deterioro_elementos_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02535` | `is_correccion_rentas_negativas_art11_9_10_saldo_final` | `is_correccion_rentas_negativas_art11_9_10_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02540` | `is_correccion_rentas_negativas_art11_9_10_saldo_final` | `is_correccion_rentas_negativas_art11_9_10_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02574` | `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial` | `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02579` | `is_deduccion_amortizacion_libre_disminucion` | `is_correccion_amortizacion_libre_30pct_saldo_pendiente` | members are opening/closing balance carryforward for 30% amortisation base-correction art.7 Ley 16/2012 |
| `02580` | `is_deduccion_amortizacion_libre_disminucion` | `is_correccion_amortizacion_libre_30pct_saldo_pendiente` | members are opening/closing balance carryforward for 30% amortisation base-correction art.7 Ley 16/2012 |
| `02591` | `is_correccion_amortizacion_inmovilizado_actividades_economicas_permanente_aumento` | `is_correccion_amortizacion_inmovilizado_idi_permanente_aumento` | actividades_economicas too broad; all members are art.12.3b I+D fixed assets (consistent with batch-1/3 renames) |
| `02592` | `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_ejercicio_aumento` | `is_correccion_amortizacion_inmovilizado_idi_temporaria_ejercicio_aumento` | actividades_economicas too broad; all members are art.12.3b I+D fixed assets (consistent rename family) |
| `02593` | `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_anteriores_aumento` | `is_correccion_amortizacion_inmovilizado_idi_temporaria_anteriores_aumento` | actividades_economicas too broad; all members are art.12.3b I+D fixed assets (consistent rename family) |
| `02594` | `is_correccion_amortizacion_inmovilizado_actividades_economicas_saldo_inicial` | `is_correccion_amortizacion_inmovilizado_idi_saldo_inicial` | actividades_economicas too broad; all members are art.12.3b I+D fixed assets (consistent rename family) |
| `02595` | `is_correccion_amortizacion_inmovilizado_actividades_economicas_saldo_final` | `is_correccion_amortizacion_inmovilizado_idi_saldo_final` | actividades_economicas too broad; section is specifically art.12.3b I+D fixed assets |
| `02596` | `is_correccion_amortizacion_inmovilizado_actividades_economicas_permanente_disminucion` | `is_correccion_amortizacion_inmovilizado_idi_permanente_disminucion` | actividades_economicas too broad; section is specifically art.12.3b I+D fixed assets |
| `02597` | `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_ejercicio_disminucion` | `is_correccion_amortizacion_inmovilizado_idi_temporaria_ejercicio_disminucion` | actividades_economicas too broad; section is specifically art.12.3b I+D fixed assets |
| `02598` | `is_correccion_amortizacion_inmovilizado_actividades_economicas_temporaria_anteriores_disminucion` | `is_correccion_amortizacion_inmovilizado_idi_temporaria_anteriores_disminucion` | actividades_economicas too broad; all members are art.12.3b I+D fixed assets (consistent rename family) |
| `02599` | `is_correccion_amortizacion_inmovilizado_actividades_economicas_saldo_inicial` | `is_correccion_amortizacion_inmovilizado_idi_saldo_inicial` | actividades_economicas too broad; all members are art.12.3b I+D fixed assets (consistent rename family) |
| `02600` | `is_correccion_amortizacion_inmovilizado_actividades_economicas_saldo_final` | `is_correccion_amortizacion_inmovilizado_idi_saldo_final` | actividades_economicas too broad; section is specifically art.12.3b I+D fixed assets |
| `02615` | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_final` | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02620` | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_final` | `is_correccion_libertad_amortizacion_inmovilizado_nuevo_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02625` | `is_correccion_libertad_amortizacion_otros_art12_saldo_final` | `is_correccion_libertad_amortizacion_otros_art12_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02630` | `is_correccion_libertad_amortizacion_otros_art12_saldo_final` | `is_correccion_libertad_amortizacion_otros_art12_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02655` | `is_correccion_deterioro_art13_1_no_afectado_saldo_final` | `is_correccion_deterioro_art13_1_no_afectado_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02660` | `is_correccion_deterioro_art13_1_no_afectado_saldo_final` | `is_correccion_deterioro_art13_1_no_afectado_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02676` | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_disminucion` | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_disminucion` | permanente qualifier inaccurate; role also contains temporaria ejercicio and anteriores members |
| `02677` | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_disminucion` | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_disminucion` | permanente qualifier inaccurate; role also contains temporaria ejercicio and anteriores members |
| `02678` | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_permanente_disminucion` | `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias_disminucion` | permanente qualifier inaccurate; role also contains temporaria ejercicio and anteriores members |
| `02685` | `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_final` | `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02690` | `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_final` | `is_correccion_deterioro_valores_participaciones_art13_2b_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02702` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `02706` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `02721` | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_aumento` | `is_correccion_limite_art11_12_perdidas_deterioro_aumento` | permanente qualifier inaccurate; role also contains temporaria ejercicio and anteriores members |
| `02722` | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_aumento` | `is_correccion_limite_art11_12_perdidas_deterioro_aumento` | permanente qualifier inaccurate; role also contains temporaria ejercicio and anteriores members |
| `02723` | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_aumento` | `is_correccion_limite_art11_12_perdidas_deterioro_aumento` | permanente qualifier inaccurate; role also contains temporaria ejercicio and anteriores members |
| `02726` | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_disminucion` | `is_correccion_limite_art11_12_perdidas_deterioro_disminucion` | permanente qualifier inaccurate; role also contains temporaria ejercicio and anteriores members |
| `02727` | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_disminucion` | `is_correccion_limite_art11_12_perdidas_deterioro_disminucion` | permanente qualifier inaccurate; role also contains temporaria ejercicio and anteriores members |
| `02728` | `is_correccion_limite_art11_12_perdidas_deterioro_permanente_disminucion` | `is_correccion_limite_art11_12_perdidas_deterioro_disminucion` | permanente qualifier inaccurate; role also contains temporaria ejercicio and anteriores members |
| `02745` | `is_correccion_provisiones_no_deducibles_art14_saldo_final` | `is_correccion_provisiones_no_deducibles_art14_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02750` | `is_correccion_provisiones_no_deducibles_art14_saldo_final` | `is_correccion_provisiones_no_deducibles_art14_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02754` | `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial` | `is_correccion_asimetrias_hibridas_art15bis_saldo_inicial_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02764` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02765` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02766` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02767` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02768` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `02770` | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | `is_correccion_limite_beneficio_operativo_pendiente_adicion_aplicado` | _dotaciones_aplicadas implies provisioning; actual content is gastos financieros pendientes applied amounts |
| `02772` | `is_correccion_limite_beneficio_operativo_saldo_final` | `is_correccion_limite_beneficio_operativo_pendiente` | members are Pendiente aplicacion periodos futuros, not closing-balance saldo_final entries |
| `02773` | `is_reserva_capitalizacion_pendiente` | `is_reserva_capitalizacion_derecho_generado` | opening balance / newly generated capitalization right (concept a) |
| `02775` | `is_reserva_capitalizacion_pendiente` | `is_reserva_capitalizacion_pendiente_futuros` | carry-forward pending BI reduction amounts (concept b) |
| `02776` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `02779` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `02805` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `02875` | `is_correccion_deuda_tributaria_ajd_itp_saldo_final` | `is_correccion_deuda_tributaria_ajd_itp_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02880` | `is_correccion_deuda_tributaria_ajd_itp_saldo_final` | `is_correccion_deuda_tributaria_ajd_itp_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02905` | `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_final` | `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02910` | `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_final` | `is_correccion_operaciones_aumento_capital_fondos_propios_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02920` | `is_correcciones_aumentos` | `is_correcciones_disminuciones` | label is Disminuciones; incorrectly placed in aumentos role |
| `02955` | `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_final` | `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02960` | `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_final` | `is_correccion_efectos_valoracion_contable_diferente_fiscal_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `02972` | `is_correccion_limite_beneficio_operativo_saldo_final` | `is_correccion_limite_beneficio_operativo_pendiente` | members are Pendiente aplicacion periodos futuros, not closing-balance saldo_final entries |
| `02981` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `02982` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `02983` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `02984` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `02989` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `02991` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `02992` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `02993` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `02994` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `02999` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `03001` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03002` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03003` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03004` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `03009` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `03011` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03012` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03013` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03014` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `03019` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `03021` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03022` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03023` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03024` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `03029` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `03041` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03057` | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_disminucion` | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_temporaria_ejercicio_disminucion` | label is Temporarias con origen en el ejercicio, not permanente |
| `03058` | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_permanente_disminucion` | `is_correccion_impuesto_extranjero_deduccion_doble_imposicion_temporaria_anteriores_disminucion` | label is Temporarias con origen en ejercicios anteriores, not permanente |
| `03071` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03081` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03091` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03101` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03111` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03117` | `is_ute_imputacion_temporal_disminucion` | `is_ute_imputacion_temporal_correccion_ejercicio_disminucion` | flow: correcciones del ejercicio (temporarias) |
| `03118` | `is_ute_imputacion_temporal_disminucion` | `is_ute_imputacion_temporal_correccion_ejercicio_disminucion` | flow: correcciones del ejercicio (temporarias) |
| `03119` | `is_ute_imputacion_temporal_disminucion` | `is_ute_imputacion_temporal_saldo_pendiente_disminucion` | stock: saldo pendiente inicio/fin ejercicio |
| `03120` | `is_ute_imputacion_temporal_disminucion` | `is_ute_imputacion_temporal_saldo_pendiente_disminucion` | stock: saldo pendiente inicio/fin ejercicio |
| `03131` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03132` | `is_capital_riesgo_ajuste_aumento` | `is_capital_riesgo_correccion_ejercicio_aumento` | flow: correcciones del ejercicio (temporarias) |
| `03133` | `is_capital_riesgo_ajuste_aumento` | `is_capital_riesgo_correccion_ejercicio_aumento` | flow: correcciones del ejercicio (temporarias) |
| `03134` | `is_capital_riesgo_ajuste_aumento` | `is_capital_riesgo_saldo_pendiente_aumento` | stock: saldo pendiente inicio/fin ejercicio |
| `03135` | `is_capital_riesgo_ajuste_aumento` | `is_capital_riesgo_saldo_pendiente_aumento` | stock: saldo pendiente inicio/fin ejercicio |
| `03145` | `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final` | `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `03150` | `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final` | `is_correccion_valoracion_bienes_derechos_regimen_especial_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `03151` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03161` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03167` | `is_hidrocarburos_amortizacion_intangibles_disminucion` | `is_hidrocarburos_amortizacion_intangibles_correccion_ejercicio_disminucion` | flow: correcciones del ejercicio (temporarias) |
| `03168` | `is_hidrocarburos_amortizacion_intangibles_disminucion` | `is_hidrocarburos_amortizacion_intangibles_correccion_ejercicio_disminucion` | flow: correcciones del ejercicio (temporarias) |
| `03169` | `is_hidrocarburos_amortizacion_intangibles_disminucion` | `is_hidrocarburos_amortizacion_intangibles_saldo_pendiente_disminucion` | stock: saldo pendiente inicio/fin ejercicio |
| `03170` | `is_hidrocarburos_amortizacion_intangibles_disminucion` | `is_hidrocarburos_amortizacion_intangibles_saldo_pendiente_disminucion` | stock: saldo pendiente inicio/fin ejercicio |
| `03171` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03172` | `is_tfi_ajuste_aumento` | `is_tfi_correccion_ejercicio_aumento` | flow: correcciones del ejercicio (temporarias) |
| `03173` | `is_tfi_ajuste_aumento` | `is_tfi_correccion_ejercicio_aumento` | flow: correcciones del ejercicio (temporarias) |
| `03174` | `is_tfi_ajuste_aumento` | `is_tfi_saldo_pendiente_aumento` | stock: saldo pendiente inicio/fin ejercicio |
| `03175` | `is_tfi_ajuste_aumento` | `is_tfi_saldo_pendiente_aumento` | stock: saldo pendiente inicio/fin ejercicio |
| `03181` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03182` | `is_erd_libertad_amortizacion_aumento` | `is_erd_libertad_amortizacion_correccion_ejercicio_aumento` | flow: correcciones del ejercicio (temporarias) |
| `03183` | `is_erd_libertad_amortizacion_aumento` | `is_erd_libertad_amortizacion_correccion_ejercicio_aumento` | flow: correcciones del ejercicio (temporarias) |
| `03184` | `is_erd_libertad_amortizacion_aumento` | `is_erd_libertad_amortizacion_saldo_pendiente_aumento` | stock: saldo pendiente inicio/fin ejercicio |
| `03185` | `is_erd_libertad_amortizacion_aumento` | `is_erd_libertad_amortizacion_saldo_pendiente_aumento` | stock: saldo pendiente inicio/fin ejercicio |
| `03191` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03201` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03211` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03221` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03231` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03241` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03242` | `is_liquidacion_iv_importe` | `is_liquidacion_iv_resultado_misc` | importe suffix uninformative for mix of resultado/abono/rectificativa/fraccionamiento entries |
| `03251` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03257` | `is_naviera_tonelaje_ajuste_disminucion` | `is_naviera_tonelaje_correccion_ejercicio_disminucion` | flow: correcciones del ejercicio (temporarias) |
| `03258` | `is_naviera_tonelaje_ajuste_disminucion` | `is_naviera_tonelaje_correccion_ejercicio_disminucion` | flow: correcciones del ejercicio (temporarias) |
| `03259` | `is_naviera_tonelaje_ajuste_disminucion` | `is_naviera_tonelaje_saldo_pendiente_disminucion` | stock: saldo pendiente inicio/fin ejercicio |
| `03260` | `is_naviera_tonelaje_ajuste_disminucion` | `is_naviera_tonelaje_saldo_pendiente_disminucion` | stock: saldo pendiente inicio/fin ejercicio |
| `03271` | `is_correccion_aumento` | `is_correccion_regimenes_especiales_aumento` | special-regime increase correction (AIEs, UTEs, capital-riesgo, naviera, ETVE, etc.) |
| `03272` | `is_entidad_sin_fines_lucrativos_aumento` | `is_entidad_sin_fines_lucrativos_correccion_ejercicio_aumento` | flow: correcciones del ejercicio (temporarias) |
| `03273` | `is_entidad_sin_fines_lucrativos_aumento` | `is_entidad_sin_fines_lucrativos_correccion_ejercicio_aumento` | flow: correcciones del ejercicio (temporarias) |
| `03274` | `is_entidad_sin_fines_lucrativos_aumento` | `is_entidad_sin_fines_lucrativos_saldo_pendiente_aumento` | stock: saldo pendiente inicio/fin ejercicio |
| `03275` | `is_entidad_sin_fines_lucrativos_aumento` | `is_entidad_sin_fines_lucrativos_saldo_pendiente_aumento` | stock: saldo pendiente inicio/fin ejercicio |
| `03291` | `is_reserva_inversiones_canarias_importe` | `is_correccion_ric_permanente` | RIC aumento correction (permanente) - adjustment correction, not RIC materialisation amount |
| `03292` | `is_reserva_inversiones_canarias_ajuste_aumento` | `is_correccion_reserva_inversiones_canarias_aumento` | aligns with is_correccion_* naming convention for regime correction roles |
| `03293` | `is_reserva_inversiones_canarias_ajuste_aumento` | `is_correccion_reserva_inversiones_canarias_aumento` | aligns with is_correccion_* naming convention for regime correction roles |
| `03294` | `is_reserva_inversiones_canarias_ajuste_aumento` | `is_correccion_reserva_inversiones_canarias_aumento` | aligns with is_correccion_* naming convention for regime correction roles |
| `03295` | `is_reserva_inversiones_canarias_ajuste_aumento` | `is_correccion_reserva_inversiones_canarias_aumento` | aligns with is_correccion_* naming convention for regime correction roles |
| `03296` | `is_reserva_inversiones_canarias_importe` | `is_correccion_ric_permanente` | RIC disminucion correction (permanente) - adjustment correction, not RIC materialisation amount |
| `03301` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03302` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03303` | `is_correccion_aumento` | `is_correccion_exencion_aumento` | art.21/22/DA6a exemption increase correction |
| `03304` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `03309` | `is_exencion_transmision_saldo_inicio` | `is_exencion_rentas_ajuste_saldo_inicio` | transmision too narrow; members span art.21, art.22, DA 6a exemptions |
| `03361` | `is_atribucion_rentas_importe` | `is_correccion_atribucion_rentas_extranjero_aumento` | foreign-constituted pass-through entities art.38 TRLIRNR |
| `03366` | `is_atribucion_rentas_importe` | `is_correccion_atribucion_rentas_extranjero_aumento` | foreign-constituted pass-through entities art.38 TRLIRNR |
| `03381` | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_permanente_aumento` | `is_correccion_eliminaciones_pendientes_grupo_permanente_aumento` | cooperativas wrong; member label confirms group fiscal group-exit concept |
| `03382` | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_ejercicio_aumento` | `is_correccion_eliminaciones_pendientes_grupo_temporaria_ejercicio_aumento` | cooperativas wrong; section covers any entity leaving a consolidated group |
| `03383` | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_anteriores_aumento` | `is_correccion_eliminaciones_pendientes_grupo_temporaria_anteriores_aumento` | cooperativas wrong; member labels confirm grupo fiscal group-exit concept |
| `03384` | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_inicial` | `is_correccion_eliminaciones_pendientes_grupo_saldo_inicial` | cooperativas wrong; section covers grupo fiscal group-exit eliminations |
| `03385` | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_final` | `is_correccion_eliminaciones_pendientes_grupo_saldo_final` | cooperativas wrong; member labels confirm grupo fiscal group-exit concept |
| `03386` | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_permanente_disminucion` | `is_correccion_eliminaciones_pendientes_grupo_permanente_disminucion` | cooperativas wrong; section covers any entity leaving a consolidated fiscal group |
| `03388` | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_temporaria_anteriores_disminucion` | `is_correccion_eliminaciones_pendientes_grupo_temporaria_anteriores_disminucion` | cooperativas wrong; section covers grupo fiscal group-exit eliminations |
| `03389` | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_inicial` | `is_correccion_eliminaciones_pendientes_grupo_saldo_inicial` | cooperativas wrong; section covers grupo fiscal group-exit eliminations |
| `03390` | `is_correccion_eliminaciones_pendientes_sociedades_cooperativas_saldo_final` | `is_correccion_eliminaciones_pendientes_grupo_saldo_final` | cooperativas wrong; member labels confirm grupo fiscal group-exit concept |
| `03395` | `is_correccion_otras_correcciones_resultado_saldo_final` | `is_correccion_otras_correcciones_resultado_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `03400` | `is_correccion_otras_correcciones_resultado_saldo_final` | `is_correccion_otras_correcciones_resultado_saldo_final_neto` | paired aumento+disminucion balance fields; _neto suffix makes bi-directional pairing explicit |
| `03401` | `is_liquidacion_i_importe` | `is_correcciones_aumentos` | detail correction increase row (DF 9a Ley 7/2024 bank interest surcharge), not P&L result |
| `03402` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `03404` | `is_bin_pendiente_aplicacion` | `is_bin_detalle_compensacion` | name implies only carry-forward; members include applied-in-period entries |
| `03411` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `03413` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `03414` | `is_deduccion_di_interna_periodo` | `is_deduccion_di_interna_dt231_detalle` | periodo vague; members span DT23.1 LIS pending/applied/generated lifecycle states |
| `03416` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `03417` | `is_deduccion_di_internacional_tipo_gravamen` | `is_deduccion_di_internacional_tipo_gravamen_periodo_generacion` | clarify field is applicable rate at time of generation, not a current-period rate |
| `03418` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `03419` | `is_deduccion_di_internacional_periodo` | `is_deduccion_di_internacional_detalle` | periodo implies current-period only; members span full vintage-level detail (pending, applied, generated) |
| `03421` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `03422` | `is_deduccion_dt24a7_periodo` | `is_deduccion_reinversion_beneficios_dt24a7_periodo` | members span DT24a.7 + Art.42 RDLeg + Art.36ter predecessor reinvestment table |
| `03428` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `03434` | `is_deduccion_inversion_canarias_islas_menores_importe` | `is_deduccion_inversion_canarias_islas_menores_aplicado` | all members are Aplicado en esta liquidacion; importe hides the applied-in-period dimension |
| `03436` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `03437` | `is_deduccion_idi_suma_periodo` | `is_deduccion_cap_iv_tit_vi_suma_periodo` | idi label wrong; members explicitly exclude I+D+i (Cap.IV Tit.VI except IDI and TAP) |
| `03439` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `03440` | `is_deduccion_idi_investigacion_aplicada` | `is_deduccion_idi_investigacion_desarrollo_periodo` | aplicada qualifier wrong; members include generated, applied, and pending lifecycle states |
| `03524` | `is_deduccion_copa_america_periodo` | `is_deduccion_eventos_especiales_aplicado_periodo` | Copa America name wrong; members are 4 different special-event deductions applied in period |
| `03525` | `is_deduccion_copa_america_total` | `is_deduccion_eventos_especiales_pendiente` | Copa America ended; members are 3 different special-event deducciones pending-future |
| `03527` | `is_deduccion_copa_america_periodo` | `is_deduccion_eventos_especiales_aplicado_periodo` | Copa America name wrong; members are 4 different special-event deductions applied in period |
| `03528` | `is_deduccion_copa_america_total` | `is_deduccion_eventos_especiales_pendiente` | Copa America ended; members are 3 different special-event deducciones pending-future |
| `03530` | `is_deduccion_copa_america_periodo` | `is_deduccion_eventos_especiales_aplicado_periodo` | Copa America name wrong; members are 4 different special-event deductions applied in period |
| `03531` | `is_deduccion_copa_america_total` | `is_deduccion_eventos_especiales_pendiente` | Copa America ended; members are 3 different special-event deducciones pending-future |
| `03535` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `03536` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `03537` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `03540` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `03541` | `is_deduccion_cinematografica_extranjera_periodo` | `is_deduccion_cinematografica_extranjera_aplicado_periodo` | _periodo vague; all members are aplicado en esta liquidacion amounts |
| `03568` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |
| `03572` | `is_deduccion_reversion_medidas_dt2_generado` | `is_deduccion_reversion_medidas_dt2_generado_pendiente_apertura` | members carry Importe generado/pendiente principio periodo - combined opening balance + generated, not purely generated |
| `03583` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `03584` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `03585` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `03586` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `03587` | `is_gastos_financieros_limitacion_importe` | `is_gastos_financieros_pendiente_deducir` | carry-forward gastos financieros pendientes by generation year |
| `03589` | `is_correccion_limite_beneficio_operativo_dotaciones_aplicadas` | `is_correccion_limite_beneficio_operativo_pendiente_adicion_aplicado` | _dotaciones_aplicadas implies provisioning; actual content is gastos financieros pendientes applied amounts |
| `03590` | `is_correccion_limite_beneficio_operativo_saldo_final` | `is_correccion_limite_beneficio_operativo_pendiente` | members are Pendiente aplicacion periodos futuros, not closing-balance saldo_final entries |
| `03591` | `is_reserva_capitalizacion_pendiente` | `is_reserva_capitalizacion_derecho_generado` | opening balance / newly generated capitalization right (concept a) |
| `03593` | `is_reserva_capitalizacion_pendiente` | `is_reserva_capitalizacion_pendiente_futuros` | carry-forward pending BI reduction amounts (concept b) |
| `03594` | `is_reserva_capitalizacion_aumento` | `is_reserva_capitalizacion_incremento_plantilla_porcentaje` | member is percentage headcount growth indicator, not a monetary capitalisation reserve increase |
| `03595` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `03598` | `is_reserva_nivelacion_adicion` | `is_reserva_nivelacion_adicion_pendiente` | future-pending adicion amounts (concept a) |
| `03621` | `is_correccion_dotaciones_deterioro_creditos_dotaciones_conversion_activo_diferido` | `is_dotaciones_deterioro_creditos_aplicadas_conversion_aid` | name duplicates dotaciones prefix; cleaner without stutter |
| `2231` | `is_deduccion_reversion_medidas_dt1_generado` | `is_deduccion_reversion_medidas_dt37_1_generado` | DT stem _dt1_ ambiguous; all members reference DT 37a.1 LIS |

---

## Summary

| metric | count |
|---|---|
| Total casillas changing role | 1250 |
| Roles changed (RENAME — all members to one new role) | 92 |
| Roles split (SPLIT — members distributed to 2+ new roles) | 19 |
| Distinct corrected role names assigned | 144 |
| Casillas from RENAME-family roles | 658 |
| Casillas from SPLIT-family roles | 592 |

### Largest structural changes

| change | casillas affected |
|---|---|
| ECPN split (`is_estado_cambios_patrimonio_neto_importe` → 12 sub-roles) | 299 |
| Identificacion flag split (`is_identificacion_flag` → regime / opcion) | 74 |
| `is_correccion_aumento` split (exemption vs special-regime) | 37 |
| `is_gastos_financieros_limitacion_importe` split (3 sub-roles) | 97 |
| P&L rename (`is_cuenta_perdidas_ganancias_importe` → `is_pyg_importe`) | ~70 |
| Actividades-economicas → idi family rename (8 roles) | 10 |
| Eliminaciones-cooperativas → grupo family rename (8 roles) | 9 |

### Data-type integrity

No corrected assignment would group casillas with conflicting data_types. All ECPN sub-roles contain
`money` fields only. The `is_identificacion_flag` split preserves `decimal` for both sub-roles
(both regime checkboxes and option flags use decimal). The `is_naviera_regimen_flag` rename correctly
reclassifies a `decimal` flag field that was misnamed `_importe`.

One data_type concern was noted in batch-1 for `is_reserva_capitalizacion_aumento` (casilla 03594):
the field holds a percentage value but is typed as `money`. This is flagged for a separate type-audit;
the role rename (`is_reserva_capitalizacion_incremento_plantilla_porcentaje`) is semantically correct
regardless.
