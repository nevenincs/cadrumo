---
name: cadrumo-intra-community-operator
description: >-
  Itinerary for a taxpayer with intra-community operations: reads the obligations
  from the overview, then sequences the Modelo 349 recapitulative declaration, the
  periodic IVA it affects and any OSS filing. Use when the profile declares
  `does_intracomunitario`, or `iva.roi_enrolled`, `iva.oss_enrolled` or
  `iva.intracommunity_operations_exceed_50000_eur` true.
applies_when:
  profile_match: any
  profile_facts:
    - fact: does_intracomunitario
      match: is_true
    - fact: iva.roi_enrolled
      match: is_true
    - fact: iva.oss_enrolled
      match: is_true
    - fact: iva.intracommunity_operations_exceed_50000_eur
      match: is_true
---

# Intra-community operator

Gating predicate: the active profile declares `does_intracomunitario`, or any of
`iva.roi_enrolled`, `iva.oss_enrolled`,
`iva.intracommunity_operations_exceed_50000_eur` (Ley 37/1992 LIVA; RD 1619/2012;
Reglamento (UE) 904/2010 for the OSS one-stop-shop). This applies on top of the
taxpayer's regime skill: a taxpayer here may also match
`cadrumo-autonomo-estimacion-directa`, `cadrumo-autonomo-modulos` or
`cadrumo-pyme-sociedad`, and both sets of obligations apply. This skill sequences
the intra-community obligations the overview derives and sends each filing to the
modelo skill that owns it.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports a profile); if
  not, load `cadrumo-alta-contribuyente`.
- The profile declares at least one gating fact. If it is suspected but not
  declared, ask the person about ROI/VIES enrolment and cross-border volume and
  record the answers as `cadrumo-alta-contribuyente` describes.
- The taxpayer's regime skill (`cadrumo-autonomo-estimacion-directa`,
  `cadrumo-autonomo-modulos` or `cadrumo-pyme-sociedad`) already sequences the
  domestic IVA and income-tax obligations; do not repeat that here.

## Procedure

All of these read local state and contact nobody.

1. Derive the obligations; never assume the intra-community set from memory. Run
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` (operation
   `overview.calendar`) and `aeat app overview agenda` (operation
   `overview.agenda`). Read the coverage report's `advised` entries (the command
   line prints them as `coverage_advised`) as open questions to put to the person,
   in particular for cadence thresholds across periods such as the 50,000 EUR
   intracommunity-operations threshold, which changes Modelo 349 from quarterly to
   monthly.
2. Confirm each candidate modelo explicitly with
   `aeat app overview explain 349 --year <YEAR>` for the recapitulative declaration
   and `aeat app overview explain 303 --year <YEAR>` for the periodic IVA cadence
   the intra-community volume may have shifted (operation `overview.explain`). Read
   the `profile_facts` in the result instead of assuming enrolment status.
3. See which forms Cadrumo models: `aeat app modelo list` (tool server: `authority`
   with query `modelos`).
4. Sequence the work:
   - The ledger's intra-community transactions must carry their counterparty
     country and IVA classification before any calculation: load
     `cadrumo-llevar-libro`, then `cadrumo-clasificar` (it covers `--iva-category`,
     `--counterparty-country` and `--counterparty-identification-state`).
   - The recapitulative declaration (Modelo 349, when the calendar surfaces it):
     load `cadrumo-preparar-modelo-349`.
   - The periodic IVA, whose cadence and cuota the intra-community volume can
     change (Modelo 303, when the calendar surfaces it): load
     `cadrumo-preparar-modelo-303`.
   - An OSS-enrolled cross-border consumer-sales obligation the calendar surfaces
     (Modelo 369): load `cadrumo-preparar-modelo-369`.
5. After a filing's local export, the person files in the AEAT portal; once they
   say they have, load `cadrumo-reconciliar`.

## Success assertions

- Every obligation acted on was read from `overview calendar`, `agenda` or
  `explain`, not assumed from this skill's prose.
- A coverage advisory (for example an undetermined ROI enrolment) was put to the
  taxpayer, not silently dropped.
- No casilla value is computed here; every number is quoted from the tool output of
  the modelo skill that produced it.

## Next

Each filing follows its own skill's steps. This skill is done when every
intra-community obligation the calendar surfaced for the period has been taken up,
alongside whatever the taxpayer's regime skill already sequenced.
