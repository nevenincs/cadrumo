---
name: cadrumo-pyme-sociedad
description: >-
  Entry itinerary for a legal entity (sociedad) filing Impuesto sobre Sociedades:
  quarterly IVA, IS pagos fraccionados, and the annual IS return. Use when the
  taxpayer profile declares `entity_type` legal_entity. Never hard-codes the
  obligation set; derives it from the overview surface.
applies_when:
  profile_facts:
    - fact: entity_type
      match: equals
      values: [legal_entity]
---

# Sociedad (pyme)

Gating predicate: the active `TaxpayerProfile` declares `entity_type` is
`legal_entity` (Ley 27/2014 LIS) - a contribuyente del Impuesto sobre Sociedades,
distinct from the natural-person IRPF route the `autonomo-*` itineraries own and
from the `attribution_entity` route (régimen de atribución de rentas, LIRPF
Title X Section 2), which is out of scope for this skill. `legal_entity_form`
(SL, SA, cooperativa, etc.) selects the applicable IS rate schedule but does not
change which modelos apply. This skill is thin: it sequences the obligations the
CLI derives and delegates every filing to the per-modelo skill that owns it.

## Preconditions

- The entity is onboarded (`cadrumo-alta-contribuyente` has run;
  `aeat app overview status` reports an active profile).
- The profile declares `entity_type` legal_entity and, where relevant,
  `legal_entity_form`. If undeclared, route back to onboarding.

## Procedure

1. Derive the applicable obligations from the CLI - never assume a sociedad's
   obligation set from memory. Run
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` for the
   window in question and `aeat app overview agenda` for what is next due. Read
   any `coverage_advised` line as an open question requiring investigation.
2. Confirm each candidate modelo's applicability explicitly:
   `aeat app overview explain 200 --year <YEAR>` for the annual IS return,
   `aeat app overview explain 202 --year <YEAR>` for the IS pago fraccionado,
   `aeat app overview explain 303 --year <YEAR>` for periodic IVA. Read
   `profile_fact` lines rather than assuming from the entity type alone -
   `enrollment.large_company`, INCN volume, and micro-empresa thresholds all
   change which schedule applies.
3. Discover the registry-modelled forms available: `aeat app modelo list`.
4. Sequence the itinerary:
   - Ledger stays current before any calculation: hand off to `cadrumo-llevar-libro`,
     then `cadrumo-clasificar`.
   - Quarterly IVA (when the calendar surfaces it): delegate to
     `cadrumo-preparar-modelo-303`.
   - IS pagos fraccionados (Modelo 202, when the calendar surfaces it): read
     `aeat app modelo describe 202 --year <YEAR> --period <PERIOD>` and drive the
     shared `work create -> calculate -> verify -> revision review -> export ->
     record marker -> reconcile` spine demonstrated by `cadrumo-preparar-modelo-303`,
     substituting Modelo 202's own casillas.
   - The annual IS return (Modelo 200, when the calendar surfaces it, typically
     after the year's pagos fraccionados): drive the same spine against its own
     `aeat app modelo describe` / `casillas` output. A positive resultado
     contable resolving to a zero base or cuota with no declared reduction is
     suspect (see `cadrumo-operator-grounding`); do not treat a clean verify with zero
     findings on positive input as sufficient without confirming with the
     taxpayer.
   - Any other surfaced modelo (informativas, censo): drive the same spine.
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
