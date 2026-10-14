---
name: cadrumo-autonomo-modulos
description: >-
  Itinerary for a self-employed individual (autónomo) under IRPF estimación
  objetiva (módulos): reads the obligations from the overview, then sequences the
  quarterly IVA (often régimen simplificado) and the Modelo 131 instalments. Use
  when the profile declares an actividad económica income category and
  `irpf_estimation_regime` is objetiva.
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

Gating predicate: the active profile declares an actividad económica income
category and `irpf_estimation_regime` is objetiva (RIRPF RD 439/2007; LIRPF
Arts. 16, 28-31) - the módulos route (Modelo 131), never the estimación directa
route (`cadrumo-autonomo-estimacion-directa` owns that predicate). The
objective-estimation declared-volume facts on the profile
(`objective_estimation_prior_year_gross_income_eur` and siblings) belong to this
predicate. This skill sequences the obligations the overview derives and sends each
filing to the modelo skill that owns it.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports a profile); if
  not, load `cadrumo-alta-contribuyente`.
- The profile declares the gating facts: an actividad económica income category and
  `irpf_estimation_regime` objetiva. If not, ask the person and record them as
  `cadrumo-alta-contribuyente` describes.

## Procedure

All of these read local state and contact nobody.

1. Derive the obligations; never assume a módulos taxpayer's obligations from
   memory. Run `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>`
   (operation `overview.calendar`) for the window in question and
   `aeat app overview agenda` (operation `overview.agenda`) for what is due next.
   Read the coverage report's `advised` entries (the command line prints them as
   `coverage_advised`) as open questions to put to the person.
2. Confirm one modelo's applicability when in doubt:
   `aeat app overview explain <MODELO> --year <YEAR>` (operation
   `overview.explain`). Módulos taxpayers are often, but not always, in régimen
   simplificado for IVA; confirm the IVA regime from the `profile_facts` in the
   explain result rather than assuming it.
3. See which forms Cadrumo models: `aeat app modelo list` (tool server: `authority`
   with query `modelos`), and compare with what the calendar surfaced.
4. Sequence the work by cadence, in the order the calendar returns it:
   - Keep the ledger current before any calculation: load `cadrumo-llevar-libro`,
     then `cadrumo-clasificar`. Módulos income still needs the ledger classified
     for IVA and expense evidence, even though the IRPF instalment itself derives
     from the objective-estimation volume facts and not from the ledger totals.
   - Quarterly IVA, when the calendar surfaces it (for example Modelo 303 under
     régimen simplificado): load `cadrumo-preparar-modelo-303`.
   - Quarterly IRPF pago fraccionado on the módulos route (Modelo 131), when the
     calendar surfaces it: load `cadrumo-preparar-modelo-131`.
   - Any other surfaced modelo: load the matching `cadrumo-preparar-modelo-<NUMBER>`
     skill, or if none exists read its shape with `aeat app modelo describe` and
     `aeat app modelo casillas` and tell the person that Cadrumo has no prepared
     workflow for it here.
5. After a filing's local export, the person files in the AEAT portal; once they
   say they have, load `cadrumo-reconciliar`.

## Success assertions

- Every obligation acted on was read from `overview calendar`, `agenda` or
  `explain`, not assumed from this skill's prose.
- A coverage advisory was put to the taxpayer, not silently dropped.
- No casilla value is computed here; every number is quoted from the tool output of
  the modelo skill that produced it.

## Next

Each filing follows its own skill's steps. This skill is done when every obligation
the calendar surfaced for the period has been taken up.
