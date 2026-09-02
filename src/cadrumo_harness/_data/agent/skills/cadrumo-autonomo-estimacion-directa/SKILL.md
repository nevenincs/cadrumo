---
name: cadrumo-autonomo-estimacion-directa
description: >-
  Entry itinerary for a self-employed individual (autónomo) under IRPF estimación
  directa (normal or simplificada): actividad económica income, quarterly IVA and
  IRPF instalments, and the annual Renta. Use when the taxpayer profile declares
  `irpf_income_categories` including actividad económica and
  `irpf_estimation_regime` is estimación directa (normal or simplificada). Never
  hard-codes the obligation set; derives it from the overview surface.
applies_when:
  profile_facts:
    - fact: irpf_income_categories
      match: contains
      values: [actividad_economica]
    - fact: irpf_estimation_regime
      match: equals
      values: [directa_normal, directa_simplificada]
---

# Autónomo, estimación directa

Gating predicate: the active `TaxpayerProfile` declares an actividad económica
income category and an estimación directa regime (normal or simplificada) - this
is the LIRPF Arts. 16, 28-31 route (Modelo 130), never the módulos route
(`cadrumo-autonomo-modulos` owns that predicate). This skill is thin: it sequences the
obligations the CLI itself derives and delegates every filing to the per-modelo
skill that owns it. It never enumerates a fixed modelo list.

## Preconditions

- The taxpayer is onboarded (`cadrumo-alta-contribuyente` has run;
  `aeat app overview status` reports an active profile).
- The profile declares the gating facts: actividad económica income category and
  an estimación directa regime. If either is undeclared, route back to the
  onboarding persona to complete the profile before continuing.

## Procedure

1. Derive the applicable obligations - never assume them. Run
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` for the
   filing window in question, and `aeat app overview agenda` for what is next due.
   Read the surfaced modelos and any `coverage_advised` line; an advised obligation
   is an open question, not a "does not apply" signal.
2. Confirm one modelo's applicability explicitly when in doubt:
   `aeat app overview explain <MODELO> --year <YEAR>`. Read `verdict` and
   `rationale`; never assume from memory which modelos an estimación-directa
   autónomo files.
3. Discover the registry-modelled forms this profile can produce:
   `aeat app modelo list`. Cross-reference against what the calendar surfaced.
4. Sequence the itinerary by cadence, in the order the calendar returns them:
   - Ledger stays current before any calculation: hand off to `cadrumo-llevar-libro`,
     then `cadrumo-clasificar`.
   - Quarterly IVA (when the calendar surfaces it): delegate to
     `cadrumo-preparar-modelo-303`.
   - Quarterly IRPF pago fraccionado (when the calendar surfaces it): delegate to
     `cadrumo-preparar-modelo-130`.
   - Any other surfaced modelo (informativas, censo, annual Renta): read its
     `aeat app modelo describe <MODELO> --year <YEAR> --period <PERIOD>` shape and
     drive the same `work create -> calculate -> verify -> export -> reconcile`
     spine the per-modelo skills demonstrate, even where no dedicated Tier-B skill
     yet exists for that modelo.
5. After each filing's local export, hand off to `cadrumo-reconciliar` once the taxpayer
   has filed in the AEAT portal.

## Success assertions

- Every obligation acted on was read from `aeat app overview calendar` /
  `agenda` / `explain`, never assumed from this itinerary's prose.
- A `coverage_advised` entry is surfaced to the taxpayer as an open question, not
  silently dropped.
- No casilla value is computed here; every number is quoted from the delegated
  skill's CLI output.

## Hand off

Each delegated filing follows its own skill's hand-off (verify, export, and
`cadrumo-reconciliar` after the human files). This itinerary's job ends once every
calendar-surfaced obligation for the period has been routed.
