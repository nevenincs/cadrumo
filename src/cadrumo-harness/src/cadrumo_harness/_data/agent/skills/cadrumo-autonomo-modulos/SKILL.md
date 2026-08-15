---
name: cadrumo-autonomo-modulos
description: >-
  Entry itinerary for a self-employed individual (autónomo) under IRPF estimación
  objetiva (módulos): signos, índices y módulos net income, quarterly IVA
  (frequently régimen simplificado) and IRPF instalments on Modelo 131. Use when
  the taxpayer profile declares an actividad económica income category and
  `irpf_estimation_regime` is objetiva. Never hard-codes the obligation set;
  derives it from the overview surface.
applies_when:
  profile_facts:
    - fact: irpf_income_categories
      match: contains
      values: [actividad_economica]
    - fact: irpf_estimation_regime
      match: equals
      values: [objetiva]
---

# Autónomo, estimación objetiva (módulos)

Gating predicate: the active `TaxpayerProfile` declares an actividad económica
income category and `irpf_estimation_regime` is objetiva (RIRPF RD 439/2007;
LIRPF Arts. 16, 28-31) - the módulos route (Modelo 131), never the estimación
directa route (`cadrumo-autonomo-estimacion-directa` owns that predicate). The
objective-estimation declared-volume facts on the profile
(`objective_estimation_prior_year_gross_income_eur` and siblings) belong to this
predicate. This skill is thin: it sequences the obligations the CLI derives and
delegates every filing to the per-modelo skill that owns it.

## Preconditions

- The taxpayer is onboarded (`cadrumo-alta-contribuyente` has run;
  `aeat app overview status` reports an active profile).
- The profile declares the gating facts: actividad económica income category and
  `irpf_estimation_regime` objetiva. If undeclared, route back to onboarding.

## Procedure

1. Derive the applicable obligations from the CLI - never assume a módulos
   taxpayer's obligation set from memory. Run
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` for the
   window in question and `aeat app overview agenda` for what is next due. Read
   any `coverage_advised` line as an open question requiring investigation.
2. Confirm one modelo's applicability explicitly when in doubt:
   `aeat app overview explain <MODELO> --year <YEAR>`. Módulos taxpayers are
   frequently, but not always, enrolled in régimen simplificado IVA; confirm the
   IVA regime from the explain payload's `profile_fact` lines rather than
   assuming it.
3. Discover the registry-modelled forms available: `aeat app modelo list`.
   Cross-reference against what the calendar surfaced.
4. Sequence the itinerary by cadence, in the order the calendar returns them:
   - Ledger stays current before any calculation: hand off to `cadrumo-llevar-libro`,
     then `cadrumo-clasificar` (módulos income still needs the ledger classified for IVA
     and expense evidence, even though the IRPF instalment itself derives from
     the objective-estimation volume facts, not the ledger totals).
   - Quarterly IVA (when the calendar surfaces it, e.g. Modelo 303 under régimen
     simplificado): delegate to `cadrumo-preparar-modelo-303`.
   - Quarterly IRPF pago fraccionado on the módulos route (Modelo 131, when the
     calendar surfaces it): delegate to `cadrumo-preparar-modelo-131`.
   - Any other surfaced modelo: drive the same spine against its own
     `aeat app modelo describe` / `casillas` output.
5. After each filing's local export, hand off to `cadrumo-reconciliar` once the taxpayer
   has filed in the AEAT portal.

## Success assertions

- Every obligation acted on was read from `aeat app overview calendar` /
  `agenda` / `explain`, never assumed from this itinerary's prose.
- A `coverage_advised` entry is surfaced to the taxpayer, not silently dropped.
- No casilla value is computed here; every number is quoted from the delegated
  skill's CLI output.

## Hand off

Each delegated filing follows its own skill's hand-off. This itinerary's job
ends once every calendar-surfaced obligation for the period has been routed.
