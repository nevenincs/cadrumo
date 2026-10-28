---
tags:
  - '#adr'
  - '#profile-field-remap'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:7ce48c7e3cbb0d3ff7ad69cac9686297181649a2570465d543edcb6c3aa38997'
related:
  - "[[2026-10-27-profile-field-remap-iva-home-office-suministros-research]]"
---

# `profile-field-remap` adr: `IVA usage share of mixed-use category expenses` | (**status:** `accepted`)

Accepted 2026-10-27. Basis: user instruction 2026-10-27: fix all deducible rules; orchestrator rulings recorded here.

## Problem Statement

A MIXED ledger row carries one `business_pct`. The IVA ledger multiplies the input cuota by it. Ledger add stamps it from the censo as raw afectación times the IRPF `statutory_multiplier`. For the home-office suministros that multiplier is the LIRPF art. 30.2.5.ª b) factor of 0.30, so the deducted IVA is 30 per cent of the lawful share. For a MIXED mobile phone row the IVA ledger deducts the row share, although LIVA grants nothing for simultaneous private use. The category registry has no datum that states the IVA treatment, so neither error can be corrected without one. Evidence: `2026-10-27-profile-field-remap-iva-home-office-suministros-research`.

## Considerations

- The 30 per cent factor is an IRPF rule only. LIVA art. 95 carries no multiplier (`2026-10-27-profile-field-remap-iva-home-office-suministros-research`).
- The IVA share of suministros of a partly affected dwelling is the degree of use. The basis is LIVA art. 95.Cuatro read with Directive art. 168 bis, as fixed by TEAC RG 00/06654/2022, adopted by DGT V2657-23 and V0796-25, and stated in the Manual práctico IVA from the 2023 edition.
- Floor area is the AEAT's "criterio razonable", not a rule. A proved share wins.
- A mobile phone used for the activity and for private needs at the same time gives no IVA deduction (LIVA art. 95.Dos.2.º; Manual práctico IVA; V0796-25).
- No source names telefonía fija.
- Renta already applies the usage ratio once, through the category rule and the ledger `UsageRatioProfile` store, and passes a MIXED usage-ratio row through whole (`src/cadrumo/application/aggregation/_renta_business_eligibility.py`). The row share therefore feeds IVA only.
- The category citation model admits only AEAT and BOE origins. It bounds every citation by an edition year or a provision span. TEAC and DGT texts have neither a bundled corpus nor an accepted origin.

## Considered options

- **A: an IVA treatment datum on each category variant, with its own citations, read by the IVA ledger through the category rule, plus a row share that means degree of use.** Chosen.
- **B: only change the censo stamp to raw afectación.** Rejected on its own. It fixes suministros but leaves the mixed-use mobile row deducting, and it records the IVA rule nowhere a reader or a gate can check.
- **Reuse `statutory_multiplier` or `iva_hint`.** Rejected. The multiplier is the IRPF factor, and `iva_hint` is a presentation token that cannot carry a share.
- **Date the IVA share from 2023-07-19 or 2023-09-26, or mark 2022 and 2023 advisory.** Rejected; see Rationale.

## Constraints

- The IRPF `statutory_multiplier` never scales IVA. The IVA treatment is a separate datum, cited only by IVA sources (LIVA, Manual práctico IVA).
- A row's `business_pct` is the degree of use. The censo default for the home-office families is raw afectación `office_m2 / total_m2`, with no multiplier. An operator-stated share wins.
- The IRPF factor is applied only by the Renta category rule over the `UsageRatioProfile` store, which keeps `0.30 x afectación` for the suministros family.
- A BUSINESS row deducts in full, except under `vehicle_presumption`. The other category IVA treatments govern MIXED received rows only.
- Every category declares an IVA treatment datum. A category the pinned authority does not declare keeps the row share.
- The `vehicle_presumption` treatment applies its presumed share (LIVA art. 95.Tres.2.ª, 50 per cent) to MIXED and BUSINESS rows alike, because booking the vehicle in the activity is no proof of a higher degree of use (art. 95.Tres.4.ª). The 100 per cent presumption for the six listed uses and a proved degree of use need an operator statement that no ledger or profile datum records yet; until one exists, the presumed share applies.
- A verified Manual práctico citation names its bundled edition as a registry source. The registry build gate checks the quotation against that edition's text through the variant's `source_citations`. A Manual citation whose edition is bundled is not `source_not_bundled`.

## Implementation

We will add an IVA mixed-use treatment to the category proportionality rule and route the IVA ledger through it.

- Registry: each 2022 to 2026 variant of every category in `src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml` declares `iva_mixed_use_share` and `iva_citation.N.*` entries. The treatments are:
  - `degree_of_use`: the home-office suministros, `telefonia_fija`, `arrendamiento_local`, `arrendamiento_vivienda_afecto`, `suministros_local_afecto` and `reparaciones_conservacion`. They cite LIVA art. 95.Tres (the lease of a bien de inversión), 95.Tres.1.ª, and 95.Cuatro or 95.Cuatro.4.º, through the legal entries `ley-37-1992:art-95-3` and `ley-37-1992:art-95-4`.
  - `bien_inversion_degree_of_use`: `hardware_amortizable` and `mobiliario_amortizable`. A MIXED row deducts its share only when its EUR taxable base reaches the bien de inversión value of the governed fact `iva-bien-inversion-escaso-valor-threshold` (LIVA art. 108.Dos.5.º); below it the row deducts nothing. They cite 95.Tres.1.ª and `ley-37-1992:art-108`.
  - `vehicle_presumption` with `iva_presumed_share = 0.50`: `vehiculo_combustible`, `vehiculo_mantenimiento`, `vehiculo_peaje` and `vehiculo_parking`. They cite 95.Tres.2.ª, 95.Cuatro and 95.Tres.4.ª.
  - `not_deductible`: every other category. They cite `ley-37-1992:art-95` (Uno and Dos.2.º). For the exempt and non-subject categories the treatment is moot, since their rows carry no cuota.
  - The `ley-37-1992:art-95` corpus excerpt holds the whole article. The suministros and fija variants of 2023, 2024 and 2025 also cite their own Manual práctico IVA edition, verified against the bundled text.
- Domain: `IvaMixedUseShare` and `IvaMixedUseRule` in `src/cadrumo/domain/categories/`, held as `ProportionalityRule.iva_mixed_use`. `IvaMixedUseRule.presumed_share` is required by `vehicle_presumption` and refused by every other treatment. The citation vocabulary gains `ley_iva` (statutory). `CategoryCitation` gains `source_ref` for a verified annual-edition citation.
- IVA ledger: `iva_category_deductible_proportion` in `src/cadrumo/application/aggregation/iva_ledger.py` returns the share a received row deducts. A MIXED received row whose category grants nothing for its use is excluded under its own issue reason. A `degree_of_use` category keeps the row share. The new issue reason is a review advisory, not a readiness gap, and is not repeated as a source diagnostic.
- Ledger add: the censo default stamps raw afectación.
- Usage-ratio reference: a row that carries `usage_ratio_id` and `business_pct` is checked by carrying the row share through the category's IRPF rule (`effective_usage_ratio`) and comparing the result with the stored profile ratio. The row holds the degree of use; the profile holds the IRPF share.
- The Manual de Renta 2025 citation on the five home-office suministros categories becomes verified against the bundled Parte 1.
- Locale notes of the five home-office suministros categories state the IRPF rule (regla 5.ª b): 30 per cent of the area ratio unless another share is proved) and the IVA rule (degree of use, no 30 per cent factor).

## Rationale

Option A states the IVA rule where the category's IRPF rule already lives, with its own legal basis. The two cannot be confused again, and a gate can read both. It fixes both errors: the 70 per cent under-deduction on suministros and the over-deduction on mixed-use mobile rows.

Dating: the share applies to every supported filing year from 2022. LIVA art. 95 has been unchanged since 1998-01-01. The TEAC criterion reads that existing law; it does not change it. It binds the administration for every period still open (LGT art. 242.4). A finer date axis would encode the publication date of an administrative reading as if it were a change in the law.

Telefonía fija: the category registry has no advisory or capability-grade mechanism at category level. `review_status` records who reviewed a variant. `RegistryAuthorityGrade` grades Modelo revisions, not category facts. The fija treatment therefore stays proportional to use. The reasoning: a fixed line is contracted for the dwelling and is a supply to the property, which is the ground on which V0796-25 separates it from a mobile line. Confidence is low, because no source names it.

Doctrine citations: TEAC and DGT texts are not bundled, and their origin (hacienda.gob.es) is outside the accepted citation origins. They are reached through the Manual práctico IVA, whose verified quotation names the TEAC resolution. Admitting doctrine as its own citation source needs a dated, non-edition citation axis and a wider origin list. That is a separate decision.

## Consequences

- MIXED suministros rows deduct IVA at the degree of use. 40 m2 of 100 m2 with cuota 21.00 deducts 8.40, not 2.52. Renta still deducts 12 per cent of the base.
- MIXED mobile rows no longer enter the IVA deduction. They surface as an advisory issue, like a personal row.
- MIXED rows of the categories that grant nothing for simultaneous use, and MIXED equipment rows below the bien de inversión value, are excluded the same way.
- Vehicle running-cost rows deduct 50 per cent of their cuota, BUSINESS rows included, until an operator statement of a listed use or a proved degree of use can be recorded.
- Rows already stamped with `0.30 x afectación` keep that stored share until the operator restates or reclassifies them. This is pre-release data; no migration is provided.
- Reconsider if the Supreme Court fixes merits doctrine on art. 95.Cuatro, if a source fixes a method other than floor area, or if a source addresses telefonía fija.
