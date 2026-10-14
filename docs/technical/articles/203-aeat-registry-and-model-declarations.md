# AEAT registry and model declarations

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-203` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope

The assigned AEAT registry subtree contains 2,140 files totaling 96,400,430 bytes: 2,094 TOML files and 46 JSON files. I used the precomputed registry structure index for complete counts and syntax status, then inspected bounded samples from scopes, year policy, authorization enrollment, temporal facts, formulas, model revisions, deadlines and generated layouts. Semantic review is representative and below the 24,000-token cap; in particular, I did not read the large Modelo 200 generated export-provenance files (about 10.8 MB and 10.9 MB each), nor the full multi-megabyte revisions and layout declarations. The index records 2,141 total AEAT/Cadrumo registry files across this chunk and the separate one-file Cadrumo schema chunk, with 2,095 TOML and 46 JSON parsed and no syntax errors. That validates syntax/metadata inventory, not schemas, formulas, tax correctness or legal applicability ([registry structure index](../evidence/registry-structure.json)).

## Capability and structure

This is a declarative tax and form registry rather than application code. It organizes 58 model directories and 68 named revision directories. Within model revisions the sampled and indexed file families include revision metadata, casillas, formulas, parameters, form/export layouts, filing windows, applicability, cross-references, dependency classifications, and generated exports. The largest model inventories are Modelo 200 (308 files), 303 (124), 390 (99), and 100 (63). Outside the model trees are authorization-scope declarations, facts, legal-source catalogs, IVA territory/catalogue tables, topic indexes, and two records dedicated to the annual Modelo 303 order. The broader layout gives other modules structured fields and source keys to resolve, but no consumer, parser or mutation path is included in this chunk.

The nine apoderamiento scope entries group tax procedures into Spanish/Catalan/English/Hungarian labels and associate selected scopes with model codes. The file documents a versioned “bootstrap” catalogue and describes uppercase codes, repeated `--scope` arguments, and `ALL` as expansion to the union of listed scopes. These are declared interface rules in a data file; the parser and actual AEAT permission semantics are outside this review. A separate `authorization.d` directory has 28 model-specific enrollment records. Samples classify Modelo 100 and 303 as `calculation` evidence and name test-path metadata, but those rows themselves do not grant a real authorization or prove a test ran (scope catalogue (`src/cadrumo/_data/registry/aeat/apoderamientos/scopes.toml`), Modelo 100 enrollment (`src/cadrumo/_data/registry/aeat/authorization.d/100.toml`), Modelo 303 enrollment (`src/cadrumo/_data/registry/aeat/authorization.d/303.toml`)).

## Temporal knowledge and calculations

Temporal selection is explicit in the sampled registry. `supported-filing-years.toml` sets a floor of 2022 and a horizon of 2026. Its comments define the floor as a hard lower gate, but say the horizon is not a gate and that later years may carry forward the newest eligible authored revision; no `hard_ceiling` is declared. The comments also say unresolved prerequisites are enumerated in an audit that remains advisory until a separate enforcement change. This describes intended policy, but whether the runtime refuses pre-floor years or answers post-horizon years as stated depends on the consumer and must be checked there (supported filing-year policy (`src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml`)).

Fact records use typed selectors, legal citations, ownership/review metadata, and effective-date intervals. For example, the IVA rate schedule contains 69 variants and selects on member state, rate kind and rate role along a `devengo_date` axis; historical temporary rates can overlap ordinary tiers and are represented with distinct roles and end dates. A companion recargo fact maps the applied rate to a surcharge and includes legal references. This supports date- and category-sensitive lookup rather than one global constant, but the registry values require legal/source validation outside the static sample (IVA rate schedule (`src/cadrumo/_data/registry/aeat/facts/0062-iva-rate-schedule.toml`), IVA recargo mapping (`src/cadrumo/_data/registry/aeat/facts/0063-iva-recargo-by-applied-rate.toml`)).

The sampled Modelo 100 formula declarations show a small expression language: a capital-gain box subtracts one casilla from another and rounds to two decimal places; other declarations use sums and parameter lookups. A regional minimum formula dispatches on the taxpayer's residence community, with source-citation and `required_text` records alongside formulas. This is a meaningful bridge from box definitions and tax parameters to declaration arithmetic, but the declarations do not execute themselves and this inspection does not verify the calculation engine or formula outputs (Modelo 100 formulas and source citations (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/formulas/0001-declarations.toml`)).

Modelo 303's 2026 revision illustrates how these pieces join. It identifies a predecessor and legal/source references, carries filing schedule and live-cross-reference source references from earlier editions, and has 2026 quarterly and monthly deadline windows, including separate payment cutoffs for some monthly periods. The record says weekend/holiday movement occurs at read time. Its generated form-layout TOML records design-source hashes and casilla-to-box placements. The revision's own review note says coverage was measured after binding derivation, that the revision has no fresh-render reproduction evidence, that the numbers are not attested as legally correct, and that its reviewer token is pending operator sign-off. The source also explicitly says the inherited live references and schedule were not re-grounded against this edition's design. Those disclosures are useful controls on claims: they establish an agent-prepared mapping and its stated limits, not a completed human/legal certification (Modelo 303 2026 revision metadata (`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2026-y-siguientes/revision.toml`), deadline windows (`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2026-y-siguientes/deadline_windows/0001-declarations.toml`), generated form layout (`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2026-y-siguientes/form_layouts/0001-form-layout.toml`)).

Modelo 721's 2024 revision demonstrates an applicability decision separate from filing-format authority. It selects 2024 onward and records the 2024 BOE amendment as applying “for the first time” to 2024 declarations filed in 2025; the `reviewed_by` note interprets this as a continuing, open-ended applicability window. The same note expressly does not claim a complete AEAT service-package, serializer, validation matrix or filing-grade record design because the historic service description is not pair-complete in the bundle. Its separate deadline file carries annual windows through 2026. This is a reasoned registry decision with candid limits, not independent proof of filing-service compatibility (Modelo 721 applicability revision (`src/cadrumo/_data/registry/aeat/modelos/721/revisions/2024/revision.toml`), Modelo 721 deadline windows (`src/cadrumo/_data/registry/aeat/modelos/721/revisions/2024/deadline_windows/0001-declarations.toml`)).

## Security, quality and follow-up

The registry contains model field definitions and authorization-scope vocabulary, but no credentials or customer declarations were identified in the samples. A scope catalog is not an access-control implementation: synthesis should verify the command parser, authorization checks, provider credentials and actual AEAT calls before concluding that a listed scope limits user access. Likewise, `review_status = "agent_reviewed"` is a provenance label, not an external authority; the sampled files make that distinction explicit in their review notes.

One bounded schema question should be checked in the consuming code: the Modelo 303 enrollment record uses the field name `renta_years = [2025, 2026]`, while its model is IVA and its comment describes a cross-Renta compensation-carry calculation. This may be a deliberate generic enrollment key for cross-model calculation cases; the registry alone cannot show whether the loader expects that exact key or whether it changes reachable behavior. Do not treat it as a product defect until the admission path is traced (Modelo 303 enrollment (`src/cadrumo/_data/registry/aeat/authorization.d/303.toml`)).

The main strengths are versioned model coverage, declarative formulas and layouts, effective-date selectors, legal/source links, and review notes that state what their evidence does and does not establish. The open questions are runtime resolution of `floor`/`horizon`, legal sign-off and source coverage for recent revisions, whether inherited references stay valid after layout changes, and whether export/form-layout generators match their checked-in artifacts. Static syntax success alone answers none of those questions. No runtime, tests or live AEAT interaction are part of this chunk.

## Complete assigned-file coverage

The assigned appendix inventories 2,140 unique files totaling 96,400,430 bytes. Its repetitive path-by-path rows are condensed by registry family below. The [registry structure index](../evidence/registry-structure.json) provides the wider indexed tree and syntax inventory.

| Registry family | Files | Bytes |
|---|---:|---:|
| `modelos` | 1,863 | 93,114,346 |
| `facts` | 156 | 1,260,203 |
| `legal` | 70 | 1,325,776 |
| `authorization.d` | 28 | 13,942 |
| `topics` | 14 | 1,684 |
| `iva` | 5 | 82,967 |
| `m303_orden_anual` | 2 | 596,900 |
| `apoderamientos` | 1 | 2,708 |
| `categories` | 1 | 1,904 |

The family counts sum to the assigned 2,140-file inventory. The existing [registry structure index](../evidence/registry-structure.json) covers the wider AEAT/Cadrumo tree, including the separate one-file Cadrumo schema chunk; its 2,141-file count, 2,095 TOML and 46 JSON totals describe that wider snapshot, not this assigned appendix. The index establishes file inventory and syntax status only. Semantic review remains bounded to the representative scopes, years, authorizations, facts, formulas, revisions, deadlines and layouts described above; no claim is made that all 2,140 files were semantically inspected.

<!-- /preserved:article -->
