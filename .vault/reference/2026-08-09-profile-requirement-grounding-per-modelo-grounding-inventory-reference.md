---
tags:
  - '#reference'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:f86f12e92e61346534813c7882fcf051b9056b79d19ce69b7430a9b8a0a90caf'
related:
  - "[[2026-08-08-profile-requirement-grounding-adr]]"
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# `profile-requirement-grounding` reference: `Grounded per-modelo profile-fact inventory`

## Summary

P05.S15 deliverable: the complete, grounded enumeration of `schema.toml` profile keys that a live registry `source=profile` binding actually consumes, computed via `build_profile_grounding_index(authority)` against the real `ValidatedRegistryAuthority` snapshot (uv run, 2026-08-09). No entry below is inferred or hand-typed; every `modelo` and `legal_refs`/`source_refs` value is exactly what the registry sweep returned. This is the evidence base for P05.S16 (populate `model_selectors` with `modelo_<code>` tokens), which has since consumed this inventory and landed.

## Context

Supersedes the falsified claim in `2026-08-08-profile-requirement-grounding-reference` that shipped `model_selectors` already carried `modelo_<code>` tokens - the 2026-08-09 ADR amendment established that zero such tokens existed. This document is the grounded replacement evidence base, not a hand-edit of the original record.

## Scope

Every `schema.toml` profile key with at least one live registry binding declaring `source = "profile"`, across the full modelo registry - not a sample.

## Method

```python
from cadrumo.core.resources import resources
from cadrumo.domain.calculations.registry import build_profile_grounding_index

authority = resources().modelos.authority
index = build_profile_grounding_index(authority)
schema = resources().user_profile_schema.singleton
```

For each of the 53 returned keys, the field's *current* `required` flag and `model_selectors` tuple were read from the live `schema.toml` via `schema.field(key)`, to determine which fields P05.S16 must touch and which already carry an unrelated semantic selector that the grounded `modelo_<code>` token must be appended to (never replacing an existing selector).

## Findings

53 profile keys carry at least one live `source=profile` registry binding. Every one resolves to exactly one grounded modelo in this sweep (a key never appears twice with two different modelos), and **none** of the 53 already carried a `modelo_<code>`-prefixed token in `model_selectors` before P05.S16 landed - confirming the amendment's finding that the per-modelo axis was universally empty in the shipped schema, not just under-populated for a handful of fields.

### By grounded modelo

- **modelo_036** (censo): `censo.status` - no existing selector, `required=False`.
- **modelo_303** (IVA): `iva.autoconsumo_promotor_base`, `tax_residence.state_attribution_ratio` - neither carried an existing selector, both `required=False`.
- **modelo_100** (Renta): the remaining 50 keys, spanning `identity.*`, `filing_export.*`, `renta_family.*`, `renta_spouse.*`, `renta_taxpayer.*`, `taxpayer_type.irpf_income_categories`.

### `identity.tax_id` - the load-bearing case

`identity.tax_id` is `required=true` and carried `model_selectors = ["tax.id"]`. `"tax.id"` is a semantic dot-token, not a `modelo_100` prefix match, so `_selector_prefix(Modelo.M100)` (`"modelo_100"`) never matched it via `startswith` - this is the exact mechanism the amendment's finding describes. The grounding index confirms modelo 100 has a real binding consuming this profile key (`orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3`), so P05.S16 ADDED `"modelo_100"` to the tuple alongside the existing `"tax.id"` entry - never replacing it, since `"tax.id"` may serve other consumers (wizard flow matching) unrelated to the `ProfilePreflightService` per-operation axis. This is now the one field whose grounded token change flips real preflight behaviour end-to-end (verified live in P05.S16's execution record).

### The 21 `renta_family.*` keys with no typed field are DERIVED, not missing

The initial pass through this inventory (`schema.field(key)` returning `None`/`None`) was misread as a missing schema declaration. It is not. `src/cadrumo/domain/user_profile/_schema.py` declares a separate `ProfileDerivedSelectorDefinition` mechanism, and `schema.toml` (lines 22-58) registers exactly these families under `[[derived_selectors]]`:

- `renta_family.descendientes_minimos_aggregate_{filing_year}` (6 years: 2020-2025)
- `renta_family.descendientes_minimos_aggregate_autonomico_{filing_year}` (6 years)
- `renta_family.anualidades_sin_minimo_descendientes_{filing_year}` (6 years)
- `renta_family.descendientes_guarderia_{filing_year}` (1 year present: 2024)
- `renta_family.gastos_guarderia_reales_{filing_year}` (1 year present: 2024)
- `renta_family.incremento_guarderia_{filing_year}` (1 year present: 2024)

21 keys total (6+6+6+1+1+1), not 11 as first mis-stated. Each carries a docstring-level guarantee: "A derived path is NOT taxpayer data. Its value is computed at calculate time from the source facts named in `derived_from`" - so the schema does not solicit it directly from the operator. The registry binding correctly names these as `source=profile` (the formula layer resolves them through the same profile-key selector plumbing as a raw field), but the operator-facing preflight/requirement axis (`model_selectors`, `required`) is a **request-gating** concept that does not apply to a computed value - there is nothing to ask the operator to supply. `derived_selector_for_path(...)` is the single written-once judgment on whether a path is engine-derived. Confirmed (P05.S16) that `ProfilePreflightService.report()` already only iterates `schema.sections`/`section.fields`, never `derived_selectors` - these 21 keys were never at risk of being surfaced as a missing operator-input requirement, and needed no code change.

This narrowed P05.S16's actionable scope to the **32 keys that are real typed `ProfileFieldDefinition` entries** (53 total minus 21 derived) - all 32 landed.

## Full table

| profile_key | required | existing_selectors (pre-S16) | grounded modelo_ token |
|---|---|---|---|
| censo.status | False | [] | modelo_036 |
| filing_export.declaration_type | False | ['declaration.type'] | modelo_100 |
| filing_export.rental_reduccion_art_23_2_tier_2024 | False | ['renta.rental_reduccion_art_23_2_tier_2024'] | modelo_100 |
| identity.name | False | ['name'] | modelo_100 |
| identity.surnames | False | ['surnames'] | modelo_100 |
| identity.tax_id | True | ['tax.id'] | modelo_100 |
| iva.autoconsumo_promotor_base | False | [] | modelo_303 |
| renta_family.anualidades_sin_minimo_descendientes_2020..2025 (6 keys) | n/a (derived) | n/a (derived) | not applicable - see Findings |
| renta_family.cotizaciones_ss_madre_2024 | False | ['family.cotizaciones_ss_madre_2024'] | modelo_100 |
| renta_family.descendants_eu_eea_deduction | False | ['family.descendants_eu_eea_deduction'] | modelo_100 |
| renta_family.descendientes_count | False | ['RentaFamilyProfile.descendientes_count'] | modelo_100 |
| renta_family.descendientes_guarderia_2024 | n/a (derived) | n/a (derived) | not applicable |
| renta_family.descendientes_minimos_aggregate_2020..2025 (6 keys) | n/a (derived) | n/a (derived) | not applicable |
| renta_family.descendientes_minimos_aggregate_autonomico_2020..2025 (6 keys) | n/a (derived) | n/a (derived) | not applicable |
| renta_family.gastos_guarderia_reales_2024 | n/a (derived) | n/a (derived) | not applicable |
| renta_family.incremento_guarderia_2024 | n/a (derived) | n/a (derived) | not applicable |
| renta_family.madrid_nacimiento_adopcion_eligible_count | False | ['renta_family.madrid_nacimiento_adopcion_eligible_count'] | modelo_100 |
| renta_family.minor_children_in_unit | False | ['family.minor_children_in_unit'] | modelo_100 |
| renta_family.unidad_familiar_otros_miembros_base | False | ['renta_family.unidad_familiar_otros_miembros_base'] | modelo_100 |
| renta_spouse.birth_date | False | ['spouse.birth_date'] | modelo_100 |
| renta_spouse.disability_grade | False | ['spouse.disability_grade'] | modelo_100 |
| renta_spouse.eu_eea_country | False | ['spouse.eu_eea_country'] | modelo_100 |
| renta_spouse.eu_eea_resident | False | ['spouse.eu_eea_resident'] | modelo_100 |
| renta_spouse.name | False | ['spouse.name'] | modelo_100 |
| renta_spouse.non_resident_irpf | False | ['spouse.non_resident_irpf'] | modelo_100 |
| renta_spouse.sex | False | ['spouse.sex'] | modelo_100 |
| renta_spouse.surnames | False | ['spouse.surnames'] | modelo_100 |
| renta_spouse.tax_id | False | ['spouse.tax.id'] | modelo_100 |
| renta_taxpayer.birth_date | False | ['taxpayer.birth_date'] | modelo_100 |
| renta_taxpayer.death_date | False | ['taxpayer.death_date'] | modelo_100 |
| renta_taxpayer.disability_grade | False | ['taxpayer.disability_grade'] | modelo_100 |
| renta_taxpayer.marital_status | False | ['taxpayer.marital_status'] | modelo_100 |
| renta_taxpayer.marriage_full_year | False | ['renta_taxpayer.marriage_full_year'] | modelo_100 |
| renta_taxpayer.marriage_month_end | False | ['renta_taxpayer.marriage_month_end'] | modelo_100 |
| renta_taxpayer.marriage_month_start | False | ['renta_taxpayer.marriage_month_start'] | modelo_100 |
| renta_taxpayer.sex | False | ['taxpayer.sex'] | modelo_100 |
| tax_residence.state_attribution_ratio | False | [] | modelo_303 |
| taxpayer_type.irpf_income_categories | False | ['taxpayer.irpf_income_categories'] | modelo_100 |

## Recommendations

1. Closed by P05.S16: all 32 typed-field keys carry their grounded `modelo_<code>` token, appended (never replacing an existing selector).
2. Closed by P05.S16: confirmed `ProfilePreflightService.report()` iterates only `schema.sections`/`section.fields`, never `derived_selectors` - the 21 derived `renta_family.*` keys structurally cannot be surfaced as a missing operator-input requirement, no guard needed.
3. Only `identity.tax_id` (`required=True`) changes observable preflight behaviour today; the other 31 fields keep `required=False` as shipped (most are conditionally required - spouse/dependent/marriage facts that do not apply to every filer) and their new token is additive wiring with no behavioural effect until a future step grounds and flips their requiredness per field. That flip is out of this inventory's scope and must not be done mechanically.
