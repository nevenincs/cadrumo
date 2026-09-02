---
name: cadrumo-arrendador
description: >-
  Entry itinerary for a taxpayer with rendimientos del capital inmobiliario
  (rental income): the annual Renta declaration of rental income and, when the
  taxpayer also pays a retención on their own commercial rent, the interaction
  with retenciones. Use when the taxpayer profile declares
  `irpf_income_categories` including capital_inmobiliario. Never hard-codes the
  obligation set; derives it from the overview surface.
applies_when:
  profile_facts:
    - fact: irpf_income_categories
      match: contains
      values: [capital_inmobiliario]
---

# Arrendador (rental income)

Gating predicate: the active `TaxpayerProfile` declares `capital_inmobiliario`
in `irpf_income_categories` (LIRPF Arts. 22-24) - rendimientos del capital
inmobiliario, distinct from actividad económica income even where the taxpayer
also holds actividad económica categories (a landlord with a genuine business
letting operation may match both this itinerary and
`cadrumo-autonomo-estimacion-directa` / `cadrumo-autonomo-modulos`; route both when both facts
are declared). A landlord with no actividad económica income files no quarterly
IRPF instalment - never assume Modelo 130/131 applies from the presence of
rental income alone.

## Preconditions

- The taxpayer is onboarded (`cadrumo-alta-contribuyente` has run;
  `aeat app overview status` reports an active profile).
- The profile declares `capital_inmobiliario` in `irpf_income_categories`. If
  undeclared, route back to onboarding.
- `fiscal_address_cadastral_reference` and `fiscal_address_is_habitual_vivienda`
  are relevant when the rented property is also the taxpayer's own habitual
  residence context; confirm these are current before calculating.

## Procedure

1. Derive the applicable obligations from the CLI - never assume the rental
   taxpayer's obligation set from memory, and never assume a quarterly IRPF
   instalment applies. Run
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` and
   `aeat app overview agenda`. Read any `coverage_advised` line as an open
   question requiring investigation.
2. Confirm applicability explicitly rather than assuming:
   `aeat app overview explain 130 --year <YEAR>` - for a landlord with no
   actividad económica income this typically resolves NOT_APPLICABLE; confirm
   the `verdict` and `rationale` rather than reading the absence of an entry from
   the calendar as ambiguous. `aeat app overview explain 100 --year <YEAR>` for
   the annual Renta declaration that carries the rental income.
3. Discover the registry-modelled forms available: `aeat app modelo list`.
4. Sequence the itinerary:
   - Ledger records every rent receipt and deductible expense (IBI, comunidad,
     seguro, amortización) with its capital_inmobiliario category before any
     calculation: hand off to `cadrumo-llevar-libro`, then `cadrumo-clasificar`.
   - The annual Renta declaration (Modelo 100, when the calendar surfaces it):
     read `aeat app modelo describe 100 --year <YEAR> --period <PERIOD>` and
     drive the shared `work create -> calculate -> verify -> revision review ->
     export -> record marker -> reconcile` spine demonstrated by
     `cadrumo-preparar-modelo-130`, substituting Modelo 100's own casillas.
   - If the profile also declares actividad económica income, hand off to
     `cadrumo-autonomo-estimacion-directa` or `cadrumo-autonomo-modulos` for the quarterly
     instalment obligations that itinerary owns; do not sequence a quarterly
     IRPF instalment here on the strength of rental income alone.
5. After the filing's local export, hand off to `cadrumo-reconciliar` once the taxpayer
   has filed in the AEAT portal.

## Success assertions

- Every obligation acted on was read from `aeat app overview calendar` /
  `agenda` / `explain`, never assumed from this itinerary's prose.
- A `coverage_advised` entry is surfaced to the taxpayer, not silently dropped.
- No casilla value is computed here; every number is quoted from the delegated
  skill's CLI output.

## Hand off

Once the annual Renta filing is routed (and any actividad-económica itinerary
this profile also matches), the reconciler (`cadrumo-reconciliar`) pulls the official
evidence after the human files.
