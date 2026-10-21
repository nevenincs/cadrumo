---
name: cadrumo-autonomo-estimacion-directa
description: >-
  Itinerary for a self-employed individual (autónomo) under IRPF estimación
  directa, normal or simplificada: reads the obligations from the overview, then
  sequences the quarterly IVA and IRPF instalments, other modelos and the annual
  Renta. Use when the profile declares an actividad económica income category and
  `irpf_estimation_regime` is directa_normal or directa_simplificada.
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

Gating predicate: the active profile declares an actividad económica income
category and an estimación directa regime (normal or simplificada) - the LIRPF
Arts. 16, 28-31 route (Modelo 130), never the módulos route (`cadrumo-autonomo-modulos`
owns that predicate). This skill sequences the obligations the overview derives and
sends each filing to the modelo skill that owns it. It never fixes a list of
modelos.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports a profile); if
  not, load `cadrumo-alta-contribuyente`.
- The profile declares the gating facts: an actividad económica income category and
  an estimación directa regime.

## Procedure

All of these read local state and contact nobody.

1. Derive the obligations; never assume them. Run
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` (operation
   `overview.calendar`) for the filing window and `aeat app overview agenda`
   (operation `overview.agenda`) for what is due next. Read the surfaced modelos and
   the coverage report's `advised` entries (the command line prints them as
   `coverage_advised`); an advised obligation is an open question for the person,
   not a sign that it does not apply.
2. Confirm one modelo's applicability when in doubt:
   `aeat app overview explain <MODELO> --year <YEAR>` (operation
   `overview.explain`). Read its `verdict` and `rationale`; never assume from memory
   which modelos an estimación-directa autónomo files.
3. See which forms Cadrumo models: `aeat app modelo list` (tool server: `authority`
   with query `modelos`), and compare with what the calendar surfaced.
4. Sequence the work by cadence, in the order the calendar returns it:
   - Keep the ledger current before any calculation: load `cadrumo-llevar-libro`,
     then `cadrumo-clasificar`.
   - Quarterly IVA, when the calendar surfaces it: load
     `cadrumo-preparar-modelo-303`.
   - Quarterly IRPF pago fraccionado, when the calendar surfaces it: load
     `cadrumo-preparar-modelo-130`.
   - Any other surfaced modelo (retenciones, informativas, annual Renta): load the
     matching `cadrumo-preparar-modelo-<NUMBER>` skill. If none exists for it, read
     its shape with `aeat app modelo describe <MODELO> --year <YEAR> --period <PERIOD>`
     (tool server: `authority` with query `describe`) and tell the person that
     Cadrumo has no prepared workflow for it here.
5. After a filing's local export, the person files in the AEAT portal; once they
   say they have, load `cadrumo-reconciliar`.

## Success assertions

- Every obligation acted on was read from `overview calendar`, `agenda` or
  `explain`, not assumed from this skill's prose.
- A coverage advisory was put to the taxpayer as an open question, not silently
  dropped.
- No casilla value is computed here; every number is quoted from the tool output of
  the modelo skill that produced it.

## Next

Each filing follows its own skill's steps (verify, export with
`cadrumo-exportar-declaracion`, and `cadrumo-reconciliar` once the person has
filed). This skill is done when every obligation the calendar surfaced for the
period has been taken up.
