---
name: cadrumo-intra-community-operator
description: >-
  Entry itinerary for a taxpayer conducting operaciones intracomunitarias: ROI/
  VIES enrolment, the Modelo 349 recapitulative declaration, and the interaction
  with periodic IVA. Use when the taxpayer profile declares
  `does_intracomunitario` true, or `iva.roi_enrolled` / `iva.oss_enrolled` /
  `iva.intracommunity_operations_exceed_50000_eur` true. Never hard-codes the
  obligation set; derives it from the overview surface.
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

Gating predicate: the active `TaxpayerProfile` declares `does_intracomunitario`,
or any of `iva.roi_enrolled`, `iva.oss_enrolled`,
`iva.intracommunity_operations_exceed_50000_eur` (Ley 37/1992 LIVA; RD 1619/2012;
Reglamento (UE) 904/2010 for the OSS one-stop-shop). This is a facts-driven
overlay: a taxpayer routed here may simultaneously match
`cadrumo-autonomo-estimacion-directa`, `cadrumo-autonomo-modulos`, or `cadrumo-pyme-sociedad` on their
entity-type/regime axis, and both itineraries' obligations apply. This skill is
thin: it sequences the intra-community-specific obligations the CLI derives and
delegates every filing to the modelo skill that owns it.

## Preconditions

- The taxpayer is onboarded (`cadrumo-alta-contribuyente` has run;
  `aeat app overview status` reports an active profile).
- The profile declares at least one gating fact. If undeclared but suspected,
  route back to onboarding to confirm ROI/VIES enrolment and cross-border
  operation volume before continuing.
- The taxpayer's primary regime itinerary (`cadrumo-autonomo-estimacion-directa`,
  `cadrumo-autonomo-modulos`, or `cadrumo-pyme-sociedad`) is already sequencing the domestic IVA
  and income-tax obligations; do not duplicate that sequencing here.

## Procedure

1. Derive the applicable obligations from the CLI - never assume the
   intra-community obligation set from memory. Run
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` and
   `aeat app overview agenda`. Read any `coverage_advised` line as an open
   question requiring investigation, in particular for cross-period cadence
   thresholds (e.g. the 50,000 EUR intracommunity-operations threshold, which
   changes Modelo 349 from quarterly to monthly).
2. Confirm each candidate modelo's applicability explicitly:
   `aeat app overview explain 349 --year <YEAR>` for the recapitulative
   declaration, and `aeat app overview explain 303 --year <YEAR>` to confirm the
   periodic IVA cadence the intra-community volume may have shifted. Read
   `profile_fact` lines rather than assuming enrolment status.
3. Discover the registry-modelled forms available: `aeat app modelo list`.
4. Sequence the itinerary:
   - Ensure the ledger's intra-community transactions carry their
     counterpart-country and IVA classification before any calculation: hand off
     to `cadrumo-llevar-libro`, then `cadrumo-clasificar`.
   - The recapitulative declaration (Modelo 349, when the calendar surfaces it):
     read `aeat app modelo describe 349 --year <YEAR> --period <PERIOD>` and
     drive the shared `work create -> calculate -> verify -> revision review ->
     export -> record marker -> reconcile` spine demonstrated by
     `cadrumo-preparar-modelo-303`, substituting Modelo 349's own casillas.
   - The periodic IVA declaration, whose cadence and cuota the intra-community
     volume can change (Modelo 303, when the calendar surfaces it): delegate to
     `cadrumo-preparar-modelo-303`.
   - Any OSS-enrolled cross-border consumer-sales obligation the calendar
     surfaces: drive the same spine against its own `aeat app modelo describe`
     output; no dedicated Tier-B skill is assumed to exist yet for every OSS
     form.
5. After each filing's local export, hand off to `cadrumo-reconciliar` once the taxpayer
   has filed in the AEAT portal.

## Success assertions

- Every obligation acted on was read from `aeat app overview calendar` /
  `agenda` / `explain`, never assumed from this itinerary's prose.
- A `coverage_advised` entry (e.g. an undetermined ROI enrolment) is surfaced to
  the taxpayer, not silently dropped.
- No casilla value is computed here; every number is quoted from the delegated
  skill's CLI output.

## Hand off

Each delegated filing follows its own skill's hand-off. This itinerary's job
ends once every calendar-surfaced intra-community obligation for the period has
been routed, alongside whatever the taxpayer's primary regime itinerary already
sequenced.
