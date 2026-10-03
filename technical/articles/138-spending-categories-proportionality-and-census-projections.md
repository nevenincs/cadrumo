# Spending categories, proportionality, and census projections

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-138` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 11 modules, 2,074 physical lines, 85,643 bytes, and 18,575 measured `o200k_base` proxy tokens across four bounded pages. It contains spending-category and proportionality vocabularies, category profiles, and an AEAT census-certificate record/projector. The source was inspected statically; no application code or tests were run and no source was changed. The token figure is a measured proxy, not an assertion about model context limits.

## Product capabilities

The category domain can expose filing-year-specific deductible-spending categories and a set of typed rule descriptions to setup, classification, and calculation consumers. The category names and category-to-family assignments are data from the governed `categories.profile` fact, while `SpendingCategoryFamily` retains only coarse mechanical buckets, including home-office groupings. The catalogue preserves authority-authored ordering and rejects unknown tokens, duplicate family membership, references to undeclared categories, and categories left without a family. This keeps the catalogue editable through dated authority data while making the grouping invariant explicit. Dated category catalogue (`src/cadrumo/domain/categories/spending_category_catalogue.py`) Complete family partition (`src/cadrumo/domain/categories/spending_category_catalogue.py`) Mechanical family API (`src/cadrumo/domain/categories/spending_category.py`)

Category profiles describe display labels, a projected proportionality rule, and an optional separate IVA-deductibility hint. The rule vocabulary includes full-deductibility, usage-ratio, statutory-cap, fixed-percentage, non-deductible, and exclusive-use roles. A profile can be resolved for an exact filing year; the latest profile loader also retains the declared cap schedule across supported years. These are typed rule facts and user-facing classification metadata, not a complete expense-import or tax-return calculation flow in this chunk. Profile shape (`src/cadrumo/domain/categories/profile.py`) IVA hint catalogue (`src/cadrumo/domain/categories/iva_hint.py`) Exact-year and latest-profile resolution (`src/cadrumo/domain/categories/registry.py`)

The proportionality model can express fixed percentages, operator-selected usage ratios with an optional statutory multiplier, daily caps, condition-selected cap variants, fixed period caps, and dated amounts whose value changes by filing year. Cap variants fix the unit at the variant and require exactly one amount; annual variants must declare their per-person/accounting period. A scheduled cap cannot silently disagree for a year. `effective_usage_ratio` applies the configured multiplier to the operator's ratio, while cap lookup returns the scheduled or flat amount for a requested year. Rule fields and invariants (`src/cadrumo/domain/categories/proportionality.py`) Cap mode and schedule validation (`src/cadrumo/domain/categories/proportionality.py`) Usage ratio application (`src/cadrumo/domain/categories/proportionality.py`)

The census-certificate model represents the six described certification axes: tax address, residence condition, representatives, tax situation, activities/locations, and periodic obligations. Its projector creates candidate profile facts for the address and every certified activity description and IAE epigraph. It deliberately leaves other axes out where mapping would conflate concepts or invent enum values, and marks emitted facts as evidence from an unverified certificate artefact. This supports operator cotejo/reconciliation while preserving that the model is not an AEAT verification stamp. Certificate fields and NIF validation (`src/cadrumo/domain/censo/certificado.py`) Candidate fact projection and provenance (`src/cadrumo/domain/censo/certificado.py`)

## How the projections work

Catalogue resolvers take an optional effective date and authority; otherwise they use Madrid's current date and the governed-fact scope. Separate selectors on the same `categories.profile` fact distinguish the proportionality vocabulary from the spending-category catalogue. Opaque token constructors are guarded so consumers cannot freely mint category, rule-kind, or cap-period tokens. Catalogue `require` methods then check a value against the vocabulary resolved for that authority/date. Proportionality authority projection (`src/cadrumo/domain/categories/proportionality_catalogue.py`) Category token construction and Pydantic validation (`src/cadrumo/domain/categories/spending_category.py`) Kind token validation (`src/cadrumo/domain/categories/proportionality.py`)

The profile registry enumerates supported filing years from a pinned authority operation. For a specific year, it resolves the category mapping at 31 December of that filing year, then projects category, proportionality kind, IVA hint, citations, variants, and cap facts into strict typed models. Categories with year-referenced caps use the separate dated scalar fact `categories.statutory-cap`; profile loading materializes those figures per supported year as a schedule, while exact-year resolution returns the selected value. Unknown cap-variant fields and invalid model shapes become category validation failures. Profile projection (`src/cadrumo/domain/categories/registry.py`) Dated cap resolution (`src/cadrumo/domain/categories/registry.py`) Variant parsing (`src/cadrumo/domain/categories/registry.py`)

## Knowledge, provenance, and trust boundaries

Category rule citations are typed by source class and checked against official-host constants, with source-kind rules for statutory references versus annual editions. The model requires a citation for every proportionality rule, distinguishes a verbatim grounded quote from unavailable or unverified evidence, and validates that a manual edition's declared year agrees with its validity window. This is a structural provenance check; it does not fetch a source or establish that a quote or legal interpretation is current and correct. Citation fields and source kinds (`src/cadrumo/domain/categories/proportionality.py`) Official host and evidence validation (`src/cadrumo/domain/categories/proportionality.py`) Grounding and edition windows (`src/cadrumo/domain/categories/proportionality.py`)

The certificate model explicitly says its covered axes are not an inventory of the PDF's layout and that no issued specimen establishes document furniture such as issue date or CSV. The code therefore does not infer a start year from a missing date, nor map free-form residence or tax-obligation text into profile facts. Representative NIF values are validated through the shared runtime Spanish tax-ID authority. Unmeasured certificate metadata boundary (`src/cadrumo/domain/censo/certificado.py`) Runtime NIF validation (`src/cadrumo/domain/censo/certificado.py`)

## Security and implementation assessment

The main strengths are the authority/date-scoped projections, immutable typed results, role-dependent rule validation, explicit cap units, and provenance-preserving census candidates. Those controls reduce accidental drift between category names, calculation mechanics, and filing-year law data. The certificate projector avoids promoting unverified document content to verified status and does not conflate legal representatives with a fiscal-representative profile axis.

One local projection weakness is that citation entries are read as `citation.0`, `citation.1`, and so on until the first missing `source` key. A malformed authority mapping with a gap can therefore hide later citation entries; if an earlier citation exists, the resulting rule may still satisfy the nonempty-citation check. Validate contiguous indexes or reject orphaned higher indexes at the schema/projection boundary. Citation iteration (`src/cadrumo/domain/categories/registry.py`) The ratio helper also accepts a raw `Decimal` and only checks that the rule uses the usage-ratio role; it trusts its caller to provide a valid ratio and any domain bounds. This is a conditional integration risk rather than evidence of invalid application calculations. Ratio helper (`src/cadrumo/domain/categories/proportionality.py`)

The certificate and resulting profile facts contain direct identifiers and address/activity information. This chunk validates some fields and tags their source, but does not define authorization, redaction, persistence encryption, or a PDF-byte parser. Their handling depends on the surrounding cotejo, profile, storage, and rendering layers. It is unknown from this chunk whether those layers enforce appropriate access and retention controls. Sensitive certificate fields (`src/cadrumo/domain/censo/certificado.py`) Projector boundary (`src/cadrumo/domain/censo/certificado.py`)

The modules depend on the calculations registry's governed-fact resolution and pinned authority interfaces, shared citation and validity primitives, Madrid clock, Pydantic model boundaries, the user-profile fact model, and runtime tax-ID validation. Follow-up synthesis should connect category rule facts to their consumers and confirm that computed ratios are validated upstream, citation indexes are schema-constrained, and certificate candidates remain visibly unverified through review and persistence. Static inspection does not verify tax correctness, source freshness, integration behavior, or test coverage.

## Coverage appendix

All 11 assigned files were read fully across four bounded pages; no unread ranges remain.

- categories/__init__.py (`src/cadrumo/domain/categories/__init__.py`) — 1–8
- categories/errors.py (`src/cadrumo/domain/categories/errors.py`) — 1–18
- categories/iva_hint.py (`src/cadrumo/domain/categories/iva_hint.py`) — 1–108
- categories/profile.py (`src/cadrumo/domain/categories/profile.py`) — 1–56
- categories/proportionality.py (`src/cadrumo/domain/categories/proportionality.py`) — 1–919
- categories/proportionality_catalogue.py (`src/cadrumo/domain/categories/proportionality_catalogue.py`) — 1–176
- categories/registry.py (`src/cadrumo/domain/categories/registry.py`) — 1–287
- categories/spending_category.py (`src/cadrumo/domain/categories/spending_category.py`) — 1–169
- categories/spending_category_catalogue.py (`src/cadrumo/domain/categories/spending_category_catalogue.py`) — 1–181
- censo/__init__.py (`src/cadrumo/domain/censo/__init__.py`) — 1–8
- censo/certificado.py (`src/cadrumo/domain/censo/certificado.py`) — 1–144
<!-- /preserved:article -->
