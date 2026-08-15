---
name: cadrumo-retenedor-empleador
description: >-
  Entry itinerary for a taxpayer that withholds retención: pays salaries with
  retención (empleador), pays professional fees subject to retención, or pays
  alquiler de local with retención. Covers the quarterly retenciones
  self-assessments and their annual informativas. Use when the taxpayer profile
  declares `has_employees`, `pays_professionals_with_retencion`, or
  `pays_rent_with_retencion` true. Never hard-codes the obligation set; derives
  it from the overview surface.
applies_when:
  profile_match: any
  profile_facts:
    - fact: has_employees
      match: is_true
    - fact: pays_professionals_with_retencion
      match: is_true
    - fact: pays_rent_with_retencion
      match: is_true
---

# Retenedor / empleador

Gating predicate: the active `TaxpayerProfile` declares at least one of
`has_employees` (salaries with retención, LIRPF Arts. 99-101),
`pays_professionals_with_retencion` (professional-fee retención, LIRPF Art.
101.5), or `pays_rent_with_retencion` (alquiler de local retención, LIRPF Art.
101.8). This is a facts-driven overlay: a taxpayer routed here may
simultaneously match `cadrumo-autonomo-estimacion-directa`, `cadrumo-autonomo-modulos`, or
`cadrumo-pyme-sociedad` on their entity-type/regime axis, and both itineraries' obligations
apply. This skill is thin: it sequences the retención-specific obligations the
CLI derives and delegates every filing to the modelo skill that owns it.

## Preconditions

- The taxpayer is onboarded (`cadrumo-alta-contribuyente` has run;
  `aeat app overview status` reports an active profile).
- The profile declares at least one gating fact. If undeclared but suspected
  (the ledger shows salary or professional-fee payments), route back to
  onboarding to confirm before continuing.
- The taxpayer's primary regime itinerary is already sequencing the domestic IVA
  and income-tax obligations; do not duplicate that sequencing here.

## Procedure

1. Derive the applicable obligations from the CLI - never assume the
   retenciones obligation set from memory; the specific modelo depends on which
   retención type (labor, professional, rental) is in play.
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` and
   `aeat app overview agenda`. Read any `coverage_advised` line as an open
   question requiring investigation.
2. Confirm each candidate modelo's applicability explicitly:
   `aeat app overview explain 111 --year <YEAR>` for retenciones on labor and
   professional-fee income, `aeat app overview explain 115 --year <YEAR>` for
   rental retenciones. Read `profile_fact` lines to confirm which retención
   types the profile actually declares rather than assuming all three.
3. Discover the registry-modelled forms available: `aeat app modelo list`.
4. Sequence the itinerary:
   - The ledger must record every withheld payment with its retención category
     and rate before any calculation: hand off to `cadrumo-llevar-libro`, then
     `cadrumo-clasificar`.
   - The quarterly retenciones self-assessment(s) the calendar surfaces (e.g.
     Modelo 111, Modelo 115): read `aeat app modelo describe <MODELO> --year
     <YEAR> --period <PERIOD>` and drive the shared `work create -> calculate ->
     verify -> revision review -> export -> record marker -> reconcile` spine
     demonstrated by `cadrumo-preparar-modelo-303`, substituting the retención modelo's
     own casillas.
   - The annual informativa the calendar surfaces (e.g. Modelo 190 summarising
     the year's Modelo 111 filings, or Modelo 180 summarising Modelo 115): drive
     the same spine against its own `aeat app modelo describe` output once the
     quarterly filings for the full year are complete.
5. After each filing's local export, hand off to `cadrumo-reconciliar` once the taxpayer
   has filed in the AEAT portal.

## Success assertions

- Every obligation acted on was read from `aeat app overview calendar` /
  `agenda` / `explain`, never assumed from this itinerary's prose.
- A `coverage_advised` entry is surfaced to the taxpayer, not silently dropped -
  in particular, an annual informativa the deadline engine has not yet windowed
  is an open question, not evidence the taxpayer need not file it.
- No casilla value is computed here; every number is quoted from the delegated
  skill's CLI output.

## Hand off

Each delegated filing follows its own skill's hand-off. This itinerary's job
ends once every calendar-surfaced retención obligation for the period has been
routed, alongside whatever the taxpayer's primary regime itinerary already
sequenced.
