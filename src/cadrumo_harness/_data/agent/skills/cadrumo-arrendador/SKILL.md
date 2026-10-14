---
name: cadrumo-arrendador
description: >-
  Itinerary for a taxpayer with rental income (rendimientos del capital
  inmobiliario): reads the obligations from the overview, then sequences the
  ledger work, the annual Renta and any retención on the taxpayer's own rent
  payments. Use when the profile declares `irpf_income_categories` including
  capital_inmobiliario.
applies_when:
  profile_facts:
    - fact: irpf_income_categories
      match: contains
      values: [capital_inmobiliario]
---

# Arrendador (rental income)

Gating predicate: the active profile declares `capital_inmobiliario` in
`irpf_income_categories` (LIRPF Arts. 22-24) - rendimientos del capital
inmobiliario, distinct from actividad económica income even where the taxpayer
also holds actividad económica categories (a landlord with a genuine business
letting operation may match both this skill and `cadrumo-autonomo-estimacion-directa`
or `cadrumo-autonomo-modulos`; follow both when both facts are declared). A landlord
with no actividad económica income files no quarterly IRPF instalment - never
assume Modelo 130/131 applies from the presence of rental income alone.

This skill sequences the obligations the overview derives and sends each filing to
the modelo skill that owns it. It does not fix a list of modelos.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports a profile); if
  not, load `cadrumo-alta-contribuyente`.
- The profile declares `capital_inmobiliario` in `irpf_income_categories`. If not,
  ask the person and record it as `cadrumo-alta-contribuyente` describes.
- `fiscal_address_cadastral_reference` and `fiscal_address_is_habitual_vivienda`
  matter when the rented property is also the taxpayer's own habitual residence
  context; check with the person that they are current before calculating.

## Procedure

All of these read local state and contact nobody.

1. Derive the obligations; never assume them from memory. Run
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` (operation
   `overview.calendar`) for the window in question and `aeat app overview agenda`
   (operation `overview.agenda`) for what is due next. Read the coverage report's
   `advised` entries (the command line prints them as `coverage_advised`) as open
   questions to put to the person.
2. Confirm applicability instead of reading an absence as an answer:
   `aeat app overview explain 130 --year <YEAR>` (operation `overview.explain`) -
   for a landlord with no actividad económica income this normally returns
   NOT_APPLICABLE; read its `verdict` and `rationale`. Run
   `aeat app overview explain 100 --year <YEAR>` for the annual Renta that carries
   the rental income.
3. See which forms Cadrumo models: `aeat app modelo list` (tool server:
   `authority` with query `modelos`).
4. Sequence the work:
   - Every rent receipt and deductible expense (IBI, comunidad, seguro,
     amortización) goes into the ledger with its capital_inmobiliario category
     before any calculation: load `cadrumo-llevar-libro`, then `cadrumo-clasificar`.
   - The annual Renta (Modelo 100, when the calendar surfaces it): load
     `cadrumo-preparar-modelo-100`.
   - If the taxpayer pays rent on premises used for an activity and withholds
     retención on it, and the calendar surfaces Modelo 115: load
     `cadrumo-preparar-modelo-115`.
   - If the profile also declares actividad económica income, follow
     `cadrumo-autonomo-estimacion-directa` or `cadrumo-autonomo-modulos` for the
     quarterly instalments; do not sequence a quarterly IRPF instalment here on
     the strength of rental income alone.
5. After a filing's local export, the person files in the AEAT portal; once they
   say they have, load `cadrumo-reconciliar`.

## Success assertions

- Every obligation acted on was read from `overview calendar`, `agenda` or
  `explain`, not assumed from this skill's prose.
- A coverage advisory was put to the taxpayer, not silently dropped.
- No casilla value is computed here; every number is quoted from the tool output of
  the modelo skill that produced it.

## Next

Each filing follows its own skill's steps. Once the annual Renta is sequenced (and
any actividad económica skill this profile also matches), `cadrumo-reconciliar`
pulls the official evidence after the person files.
