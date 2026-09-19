---
tags:
  - '#reference'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:478960eba35fece74eb51ff52aaf458a79a877e85ff67c3c829a93edaca41c5c'
related:
  - "[[2026-08-08-profile-requirement-grounding-adr]]"
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
  - "[[2026-08-09-profile-requirement-grounding-per-modelo-grounding-inventory-reference]]"
---

# `profile-requirement-grounding` reference: `Registry-binding vs schema.toml legal_refs drift sweep`

## Summary

## Context

## Summary

P08.S25 deliverable: a complete, measured comparison between every registry `source = "profile"` binding's `legal_refs` (unioned per profile key via `build_profile_grounding_index`, which already walks every modelo definition and every revision's bindings across the full registry - not a sample) and the corresponding `schema.toml` field's own `legal_refs`. No code changes in this document.

## Method

```python
from cadrumo.core.resources import resources
from cadrumo.domain.calculations.registry import build_profile_grounding_index

authority = resources().modelos.authority
index = build_profile_grounding_index(authority)  # keyed by profile_key, unions ALL modelos/revisions/bindings
schema = resources().user_profile_schema.singleton
```

For each of the 53 profile keys `build_profile_grounding_index` returns (the full registry-wide `source=profile` binding sweep - see the P05.S15 inventory this reuses), compared `set(grounding.legal_refs)` against `set(schema.field(key).legal_refs)` when the key resolves to a real typed schema field.

## Scope

Every registry `source = "profile"` binding across every modelo and every revision under `_data/registry/aeat/modelos/` (via `build_profile_grounding_index`'s full sweep, not a directory glob or a per-modelo sample), against every corresponding `schema.toml` field.

## Findings

### Agree (6): both sides cite the identical ref set, non-empty

`filing_export.rental_reduccion_art_23_2_tier_2024`, `renta_family.madrid_nacimiento_adopcion_eligible_count`, `renta_family.unidad_familiar_otros_miembros_base`, `renta_taxpayer.marriage_full_year`, `renta_taxpayer.marriage_month_end`, `renta_taxpayer.marriage_month_start`.

### Schema has refs, registry binding has none (0)

None. The registry side is never less-grounded than the schema side for any key both sides declare - consistent with P05.S16's additive-union design (registry grounding is unioned INTO the operator-facing requirement row, never the reverse).

### Registry has refs, schema field has NONE (24) - the concrete drift this sweep exists to find

The schema-authored field carries `legal_refs = []` even though a real, currently-live registry binding consuming that exact profile key cites concrete BOE/AEAT provisions:

| profile_key | registry legal_refs |
|---|---|
| `censo.status` | `orden-eha-1274-2007:art-1`, `orden-eha-1274-2007:art-2`, `rd-1065-2007:art-9`, `rd-1065-2007:art-10`, `rd-1065-2007:art-11` |
| `filing_export.declaration_type` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `identity.name` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `identity.surnames` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `identity.tax_id` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_family.cotizaciones_ss_madre_2024` | `ley-35-2006:art-81` |
| `renta_family.descendants_eu_eea_deduction` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_family.descendientes_count` | `ley-35-2006:art-58` |
| `renta_family.minor_children_in_unit` | `ley-35-2006:art-82`, `ley-35-2006:art-83`, `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_spouse.birth_date` | `ley-35-2006:art-57`, `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_spouse.disability_grade` | `ley-35-2006:art-57`, `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_spouse.eu_eea_country` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_spouse.eu_eea_resident` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_spouse.name` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_spouse.non_resident_irpf` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_spouse.sex` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_spouse.surnames` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_spouse.tax_id` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_taxpayer.birth_date` | `ley-35-2006:art-57`, `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_taxpayer.death_date` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_taxpayer.disability_grade` | `ley-35-2006:art-57`, `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_taxpayer.marital_status` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `renta_taxpayer.sex` | `orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3` |
| `tax_residence.state_attribution_ratio` | `ley-12-2002:art-29`, `ley-37-1992:art-115`, `orden-eha-3786-2008:art-1`, `rd-1624-1992:art-71` |

**Why this matters concretely.** `ProfilePreflightRequirement.legal_refs` (the operator-facing missing-field grounding this campaign built in P01-P06) unions BOTH sides, so an operator reading a preflight refusal already sees these refs today - the union absorbs this gap. But any OTHER surface reading `schema.field(path).legal_refs` directly, bypassing the union (a hypothetical future consumer, or any of the P08.S27/S32 CLI surfaces still on the separate `ProfileKey`-derived mechanism), would see none of these 24 fields' real grounding.

### Both sides have refs but the SETS DIFFER (2) - genuine two-way divergence

**`iva.autoconsumo_promotor_base`**: registry cites `ley-37-1992:art-9`, `ley-37-1992:art-79`, `orden-eha-3786-2008:art-1`, `rd-1624-1992:art-71`; schema cites only `ley-37-1992:art-9`, `ley-37-1992:art-79`. The registry's two extra refs (Orden EHA 3786/2008, the modelo 303 declaration-form order; RD 1624/1992, the IVA reglamento) are plausibly procedural/reporting-mechanics authority layered on top of the schema's substantive-definition citations, not necessarily a defect - not independently verified against the bundled corpus in this no-code-changes step, so no verdict is asserted.

**`taxpayer_type.irpf_income_categories`**: schema cites `ley-35-2006:art-17`, `art-22`, `art-25`, `art-27`, `art-33` (five articles, one per income-category concept the field's enum can select); registry cites only `art-27`, `art-30` (two articles, the ONE binding's own narrower formula-level usage). Neither set is a subset of the other. Plausible explanation: the schema field's citation is deliberately broad (it grounds the FIELD's full enum-value space), while the registry binding's citation is deliberately narrow (it grounds only the specific formula that binding computes) - a scope difference, not necessarily a contradiction. Not independently verified against the bundled corpus in this step; recorded as observed, not adjudicated.

### Derived-selector keys (21): registry-grounded, structurally outside the schema-field comparison

The 21 `renta_family.*` derived-selector keys P05.S15 identified (computed at calculate time, never a `ProfileFieldDefinition`) all carry real registry-side `legal_refs` (LIRPF arts. 58, 61, 64, 81, 81-2, 81-3, plus `madrid-dl-1-2010:art-2` for the autonomico-aggregate family). `ProfileDerivedSelectorDefinition` has no `legal_refs` field of its own to compare against - this is the same structural-asymmetry shape as `ProfileKey`'s missing `legal_refs` field (P08.S24), not a comparable mismatch.

## Recommendations

1. The 24-field "registry has refs, schema has none" list is the clearest, lowest-risk P08.S26 fan-out candidate: each is a mechanical addition of already-known, already-cited provisions into the schema field's `legal_refs` - no new legal research needed, only carrying an existing citation from the binding to the field. Grounding-rule discipline still applies per-field (cross-check against the bundled corpus before adding, per this project's calculation-grounding rule) even though the citation already exists elsewhere in the registry.
2. The two genuine two-way divergences need a human legal-provenance judgment call (which scope is correct, or whether both are correct at their respective scopes) before any value changes - explicitly NOT mechanical, unlike recommendation 1. Scope as a separate, smaller P08.S26 fan-out row.
3. No action recommended for the derived-selector asymmetry or the agreeing-6 set.
