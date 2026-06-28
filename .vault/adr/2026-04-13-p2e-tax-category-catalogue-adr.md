---
tags:
  - "#adr"
  - "#p2e-tax-category-catalogue"
date: "2026-04-13"
modified: '2026-04-13'
related:
  - "[[2026-04-13-p2e-tax-category-catalogue-research]]"
  - "[[2026-04-13-p2e-tax-category-catalogue-plan]]"
---

# `p2e-tax-category-catalogue` adr: strict category substrate with conservative 2025 codification | (**status:** `accepted`)

This ADR commits the model shape and registry strategy for issue `#77`, TDP
step `T4`. The feature delivers the spending-category taxonomy and
proportionality substrate only. It does not deliver the proportionality engine,
the categorisation engine, or the VAT classifier.

Topic: 2025 spending-category catalogue, proportionality rules, citations, and
casilla mappings for the T4 taxonomy substrate.

Audit surface: `#77`, `#104`, the AEAT 2025 Renta manual, `Ley 35/2006`,
`RD 439/2007`, current `aeat.domain.casillas`, and the root Typer CLI.

Rewrite scope: new `aeat.domain.financial.categories` package, additive CLI wiring,
and the minimum additive casillas-side enum surface needed by the new models.

## Problem statement

The branch needs a stable, explainable taxonomy substrate that downstream
engines can consume immediately. The source material is rich enough to support a
2025 catalogue, but current main has two hard shape constraints:

- `aeat.domain.casillas` exposes only a very small public `130` / `303` surface.
- The requested minimum category list includes some labels that are useful for
  downstream classification even where the current 2025 handbook is weaker than
  the requested name.

The substrate therefore has to be both strict and conservative: strong enough
to power `#78` and `#79`, but honest about source certainty and current-main
mapping limits.

## Considerations

- Every boundary-crossing record must be strict pydantic v2.
- `aeat.domain.financial.vat` is a sibling branch and must remain untouched.
- `aeat.domain.financial.providers` is sibling-owned and must remain untouched.
- Every profile must carry citations so downstream explainability is preserved.
- Current-main `MODELO_303` does not expose a category-specific deductible-input
  surface, so the registry cannot pretend otherwise.

## Constraints

- Public imports must come from `aeat.domain.financial.categories` only.
- Closed catalogues use `enum.StrEnum`.
- No bare dictionaries on the public model surface.
- No hard imports from in-flight sibling branches.
- Every category in the enum must have a complete profile.
- The implementation must stay inside TDP `T4`.

## Implementation

### 1. Package and public API

Implement the feature under `src/aeat/domain/financial/categories/` and expose it as
`aeat.domain.financial.categories`.

Public exports:

- `SpendingCategory`
- `SpendingCategoryFamily`
- `ProportionalityKind`
- `ProportionalityRule`
- `Citation`
- `CategoryProfile`
- `CasillaMapping`
- `CasillaMappingSign`
- `CATEGORY_PROFILES_2025`
- `load_category_profiles_from_manual`

### 2. Model strategy

Use strict, frozen pydantic models for:

- `Citation`
- `ProportionalityRule`
- `CasillaMapping`
- `CategoryProfile`

Keep the category enum and its hierarchy closed and explicit. The hierarchy is a
family/grouping aid for downstream engines and CLI output, not a runtime
deductibility evaluator.

### 3. Citation strategy

Define a local `Citation` model inside `aeat.domain.financial.categories` rather than
reaching into the VAT branch.

Rationale:

- `#85` may legitimately change its citation shape.
- The category substrate must stay stable and self-contained.
- Explainability belongs to the category surface itself, not to a sibling
  implementation detail.

Contract:

- Every `ProportionalityRule` carries at least one citation.
- `notes_es` must explain source caveats whenever a category is conservatively
  codified rather than strongly source-locked.

### 4. Registry and loader strategy

`CATEGORY_PROFILES_2025` is the authoritative frozen registry for this branch.

`load_category_profiles_from_manual(year: int)` should:

- attempt to read the manual corpus through `aeat.domain.manuals`,
- return the year-specific profile set when the corpus is available,
- fall back to `CATEGORY_PROFILES_2025` when the structured manual corpus is
  incomplete or missing.

This keeps the public API usable now without blocking on later corpus work.

### 5. Casilla mapping strategy

`CasillaMapping` carries:

- `modelo`
- `period_type`
- `casilla_code`
- `sign`

The current-main mapping rules are intentionally coarse:

- `MODELO_130:01` is the direct expense sink.
- `MODELO_130:02`, `MODELO_130:03`, and `MODELO_130:18` remain derived or
  result surfaces and are not the primary category hook.
- `MODELO_303:71` is only an aggregate reporting hint for this catalogue.
- No profile should present the current-main `303` mapping as a fine-grained
  input-VAT allocation.

### 6. Proportionality semantics

The registry should use the rule shape that best matches the legal source:

- `full_deductible`
  - ordinary activity expenses that do not need a special ratio.
- `fixed_percentage`
  - reserved for source-backed explicit percentages unrelated to area or a user
    ratio.
- `usage_ratio_personal`
  - categories whose business use is binary or user-ratio driven, such as
    mobile telephony or vehicle families.
- `usage_ratio_home_area`
  - home-office supplies and similar area-prorated costs. The legal `30%`
    multiplier is captured here.
- `statutory_cap`
  - dietas and capped insurance categories.
- `non_deductible`
  - conservative compatibility labels with no clean current-2025 support.

Vehicle families and mobile telephony are not generic percentage rules. Their
profiles should keep that constraint visible in the notes and citations.

### 7. Conservative categories

Keep the following as explicit conservative codifications:

- `cuotas_colegiales`
- `arrendamiento_vivienda_afecto`
- `software_suscripcion`
- `viajes_alojamiento`
- `subcontratacion`

These remain useful for downstream classification, but the notes must state that
the label is being codified conservatively rather than lifted from a strong
current-2025 handbook label.

### 8. CLI surface

Add a read-only `aeat categories` command group:

- `aeat categories list`
- `aeat categories show <category>`
- `aeat categories casillas <modelo>`

The CLI reports the category, proportionality rule, notes, citations, and
casilla mappings. It never evaluates deductibility.

## Rationale

- The strict local model surface gives `#78` and `#79` a stable substrate now.
- A local citation model avoids sibling-branch coupling.
- Coarse `303` mappings are preferable to fabricated fine-grained VAT detail.
- Conservative notes are preferable to overclaiming handbook certainty.

## Consequences

- `aeat.domain.financial.categories` becomes a stable T4 taxonomy substrate for the
  downstream Track B engines.
- The catalogue stays isolated from `aeat.domain.financial.vat` and
  `aeat.domain.financial.providers`.
- The runtime notes will explicitly expose weaker categories and coarse `303`
  mappings.
- A future richer deductible-input VAT surface can be adopted without rewriting
  the category taxonomy itself.
