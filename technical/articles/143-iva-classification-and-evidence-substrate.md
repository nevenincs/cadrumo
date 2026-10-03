# IVA classification and evidence substrate

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-143` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This chunk covers 16 files in `domain/iva`, totaling 4,953 manifest-counted lines, 215,784 bytes, and 46,717 measured `o200k_base` tokens. All assigned pages and file ranges were read through their ends using the bounded chunk reader. This is static review only: no application imports or execution, no `src/` edits, and no independent verification of the legal interpretations expressed in source comments or registry data.

## Product capabilities

The IVA substrate classifies invoice operations from date-stamped party and transaction facts. Its criteria keep issuer and customer establishment separate from their IVA-identification Member State, and carry customer status, operation kind, invoice direction, optional Art. 69.Dos service, and rate tier. The evaluator projects its ordered rules, aliases, transaction-kind vocabulary, rate/category mapping, and reverse-charge flags from a pinned authority operation; a restricted predicate compiler turns registry expressions into callable conditions. Results identify the category and rate, reverse-charge status, matched rule, consumed party facts, and place-of-supply basis classification criteria and result (`src/cadrumo/domain/iva/classification.py`) dated projection (`src/cadrumo/domain/iva/classification.py`) evaluator (`src/cadrumo/domain/iva/classification.py`) predicate compiler (`src/cadrumo/domain/iva/_classification_predicates.py`).

An establishment resolver turns printed or structured country evidence into a closed territorial scope, or leaves it unresolved. It accepts a VAT prefix only when the identifier body matches the published country format, matches printed names by exact normalized vocabulary lookup, recognizes both alpha-2 and alpha-3 structured codes through a published correspondence, and uses Spanish postal prefixes to distinguish mainland from excluded territories. Unknown country codes do not become third-country treatment; Spain alone remains territorially unresolved from country code because sub-national evidence is needed. A separate resolver may establish which EU Member State a printed VAT number identifies, including a prefixed Spanish tax ID validated under its checksum rules bounded country vocabulary (`src/cadrumo/domain/iva/country_vocabulary.py`) territorial resolution (`src/cadrumo/domain/iva/establishment.py`) Spanish postal resolution (`src/cadrumo/domain/iva/establishment.py`) identification resolution (`src/cadrumo/domain/iva/identification.py`).

The component catalogue describes which base, quota, recargo, and retention components apply to each `(IVA category, invoice direction)` pair, who settles quota, which side receives withholding, and how well each expectation is grounded. It also exposes category projections used by return logic, such as quota-less, evidence-exempt, and cash-accounting-excluded categories. Rows are built from governed fact 0084 rather than hard-coded in this domain; they refuse unrecognized vocabulary, contradictory row keys, unsupported component combinations, and missing grounding references typed row contract (`src/cadrumo/domain/iva/components.py`) catalogue projection (`src/cadrumo/domain/iva/components.py`) row projection (`src/cadrumo/domain/iva/_component_row_projection.py`).

Deduction-fact helpers classify an IVA deduction by a registry-declared source family and required evidence authority. They validate evidence provenance shape, allowed category and flow pairs, investment-asset identity, and rectification linkage and signs. Flow helpers distinguish repercutido, soportado, recipient reverse-charge, and supplier reverse-charge, then project which flows contribute to devengada and/or deducible settlement. The invoice-line bridge builds the standard domestic invoice classification and emits a ledger IVA observation; exceptional regimes require direct construction from the broader classifier deduction validation (`src/cadrumo/domain/iva/deduction_facts.py`) flow derivation (`src/cadrumo/domain/iva/flow.py`) invoice bridge (`src/cadrumo/domain/iva/invoice_classification.py`) observation projection (`src/cadrumo/domain/iva/invoice_classification.py`).

## How it works

`classify_iva` requires a caller-owned pinned authority and validates every supplied token against the vocabulary projected for the transaction date before matching rules in declared order. Rule predicates use a closed set of field names and selectors rather than evaluating arbitrary code. For each match, the engine verifies the category’s published reverse-charge flag, maps rate tiers where the rule delegates category selection, resolves any applicable statutory rate, and attaches a place-of-supply rule. A fallthrough row is a registry-declared result, not a Python default rule projection and match (`src/cadrumo/domain/iva/_classification_engine.py`) result construction (`src/cadrumo/domain/iva/_classification_engine.py`) place-of-supply output (`src/cadrumo/domain/iva/_classification_engine.py`).

Country resolution is intentionally a ladder of bounded lookups. A valid foreign VAT number can name an EU country, but does not alone establish where the business is located. A name can identify a country only if the registry vocabulary contains the normalized phrase and no other country collides with it. Structured codes receive the same membership gate; alpha-3 is looked up, never truncated into alpha-2. Spain returns no territorial scope from `ES`, and the Spanish postal resolver returns no scope for absent or malformed postal evidence instead of defaulting to mainland. Separately, identification reads the VAT prefix as registration evidence; unprefixed Spanish NIF/CIF values do not imply Spanish identification country-code status (`src/cadrumo/domain/iva/establishment.py`) structured country code (`src/cadrumo/domain/iva/establishment.py`) printed name (`src/cadrumo/domain/iva/establishment.py`).

Component rows are decoded from registry mapping entries into immutable typed projections. Their validation enforces role/direction coherence, non-arising pair semantics, quota-settlement consistency, citation uniqueness, and explicit notes where retención expectations are weakly grounded or not expected. The invoice-to-ledger bridge computes the standard domestic category and flow from rate tier and direction, then stores the applied percentage and settlement-side set on the observation for downstream Modelo 303 bindings row invariants (`src/cadrumo/domain/iva/components.py`) invoice observation (`src/cadrumo/domain/iva/invoice_classification.py`).

## Knowledge and data

The legal decision tables, country and territory vocabularies, rate/category relationships, component matrix, deduction families, and flow semantics are registry-owned. The IVA domain supplies their parsing, typed projections, invariant checks, and evaluation mechanics. Source references and `IvaGroundingConfidence` distinguish claims backed by the bundled corpus, claims checked against live sources but not yet bundled, reasoned claims, and explicitly ungrounded areas. A live-source-only row must name pending legal references; bundled-grounded rows must cite legal references. These markers improve traceability but do not independently prove that registry material is current or legally correct grounding levels (`src/cadrumo/domain/iva/components.py`) grounding-reference checks (`src/cadrumo/domain/iva/components.py`).

Deduction provenance retains an authority token, source locator, and content digest, not the underlying document. Classification results carry the branch’s consumed party facts so upstream collection can ask for only the facts that the chosen row uses; if a row omits that declaration, the result defaults toward requiring both facts. Place-of-supply output identifies the registry-declared grounding and is explicitly not an AEAT ruling on the specific transaction deduction evidence pointer (`src/cadrumo/domain/iva/deduction_facts.py`) consumed facts (`src/cadrumo/domain/iva/classification.py`).

## Security and safety

The main safety control in this chunk is conservative evidence handling: unresolved or malformed country evidence stays unresolved, Spain does not default to mainland, and the classifier refuses categories that lack published reverse-charge facts. Registry rows and opaque tokens must be projected through their catalogue; direct construction of a component row without its projected vocabulary fails. Predicate strings are parsed against known axes and selectors, so registry rules cannot call arbitrary Python. The code records evidence digests and locators but contains no encryption, access control, document storage, or network dispatch; those boundaries must be assessed in callers. This layer does not authenticate that a cited source locator belongs to the digest or that a human reviewed it.

## Implementation assessment

The design has clear strengths: the main classifier is first-match but table-driven, operates against one pinned generation, and returns which facts its selected rule consumed. Establishment and identification are distinct facts with different evidence paths. Axis-A components are keyed by both category and invoice direction, and row validation carries explicit grounding confidence and legal-reference distinctions. Typed errors separate invalid values, missing rates, and catalogue failures.

Several boundaries need cross-module review. `category_bears_taxable_base` and `category_cuota_is_zero_by_law` can accept a supplied component catalogue, then compare its row against a component-presence token resolved through the ambient registry scope. If the supplied catalogue and ambient authority are from different generations—or there is no ambient scope—the helper can compare incompatible vocabularies or fail despite having a catalogue helper comparison (`src/cadrumo/domain/iva/components.py`) current-scope token resolver (`src/cadrumo/domain/iva/components.py`). Deduction validation similarly has no effective-date parameter and reads the applicability catalogue using `today_madrid()`, so a historical deduction can be checked against current declarations if fact 0085 changes deduction date resolution (`src/cadrumo/domain/iva/deduction_facts.py`) validator interface (`src/cadrumo/domain/iva/deduction_facts.py`).

The invoice-line-to-observation bridge accepts `issued_at` and passes that date into rate-tier classification and applied-rate resolution, despite invoices carrying a separate operation date. For an invoice issued after the operation, callers cannot supply the devengo date through this bridge, creating a potential date mismatch with invoice-level validation that uses operation date when present bridge date contract (`src/cadrumo/domain/iva/invoice_classification.py`). Also, matched classification projects the transaction year to a supported filing year and refuses when no projection exists, while the fallthrough path passes the raw transaction year to place-of-supply resolution. Confirm the place-of-supply resolver’s behavior for years outside the supported projection range matched projection (`src/cadrumo/domain/iva/_classification_engine.py`) fallthrough year (`src/cadrumo/domain/iva/_classification_engine.py`).

The source itself documents a potential contract gap around Spanish identification: only an `ES`-prefixed identifier is read as a Spanish IVA identification in this path; a valid bare Spanish tax identifier returns no identification state. The implementation explains this as an evidence distinction, while explicitly identifying the question of whether the checksum path should establish that fact as open scope Spanish identification path (`src/cadrumo/domain/iva/identification.py`). No tests are included in this chunk, and static analysis cannot establish the effective dates or factual completeness of the registry tables, the classification callers’ evidence quality, or downstream use of unresolved results.

## Dependencies and follow-up

Synthesis should confirm that callers keep an explicit authority generation aligned across component catalogues, component-token helpers, invoice classifications, and deduction facts. It should trace how the invoice bridge obtains the relevant operation date, how unsupported projection years are handled on fallback, and how missing establishment or identification values reach operator review. Registry provenance should be checked against the compiler/catalogue loaders, and evidence digests against the persistence and source-ingestion layers.

## Complete assigned-file coverage

- iva/__init__.py (`src/cadrumo/domain/iva/__init__.py`)
- iva/_classification_engine.py (`src/cadrumo/domain/iva/_classification_engine.py`)
- iva/_classification_predicates.py (`src/cadrumo/domain/iva/_classification_predicates.py`)
- iva/_component_fact_projection.py (`src/cadrumo/domain/iva/_component_fact_projection.py`)
- iva/_component_row_projection.py (`src/cadrumo/domain/iva/_component_row_projection.py`)
- iva/_component_rows.py (`src/cadrumo/domain/iva/_component_rows.py`)
- iva/_fact_mapping_entries.py (`src/cadrumo/domain/iva/_fact_mapping_entries.py`)
- iva/classification.py (`src/cadrumo/domain/iva/classification.py`)
- iva/components.py (`src/cadrumo/domain/iva/components.py`)
- iva/country_vocabulary.py (`src/cadrumo/domain/iva/country_vocabulary.py`)
- iva/deduction_facts.py (`src/cadrumo/domain/iva/deduction_facts.py`)
- iva/errors.py (`src/cadrumo/domain/iva/errors.py`)
- iva/establishment.py (`src/cadrumo/domain/iva/establishment.py`)
- iva/flow.py (`src/cadrumo/domain/iva/flow.py`)
- iva/identification.py (`src/cadrumo/domain/iva/identification.py`)
- iva/invoice_classification.py (`src/cadrumo/domain/iva/invoice_classification.py`)
<!-- /preserved:article -->
