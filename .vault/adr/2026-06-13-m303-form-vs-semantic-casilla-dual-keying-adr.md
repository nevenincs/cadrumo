---
tags:
  - '#adr'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
related:
  - '[[2026-06-09-modelo-iva-routing-carry-adr]]'
  - '[[2026-04-17-modelo-303-formulas-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-04-m303-form-vs-semantic-casilla-dual-keying-research]]'
  - '[[2026-06-01-m303-iva-resultado-semantic-casilla-mismatch-research]]'
  - '[[2026-08-07-official-form-coverage-audit]]'
  - '[[2026-08-10-casilla-schema-canonical-derivations-adr]]'
  - '[[2026-07-01-modelo-303-regimen-simplificado-adr]]'
  - '[[2026-07-05-cross-period-prorrata-adr]]'
  - '[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-reference]]'
  - '[[2026-07-07-prorrata-sectores-diferenciados-adr]]'
  - '[[2026-08-11-aeat-export-fragment-generator-authority-s54-sector-source-taxonomy-research]]'
modified: '2026-08-14'
body_hash: 'sha256:e0644992600da466d12d318c2ad000d683c72f8610350629bf8be13f2bcc7133'
---
# `m303-form-vs-semantic-casilla-dual-keying` adr: `M303 semantic homes and exact fixed-slot official projection` | (**status:** `accepted`)

## Problem Statement

Modelo 303 has one business fact graph but several official representations: numbered casillas, nonnumbered fixed-width fields, repeated rows, headers, source literals, reserves, and transport checks. Treating those representations as independent value authorities creates duplicate calculation, persistence, election, account, and export paths.

This amendment completes the accepted dual-key decision. Every M303 fact has exactly one semantic home. Official fields are filing endpoints unless an official-only numbered casilla has no upstream semantic twin, in which case that casilla is itself the canonical endpoint rather than a projection from a shadow identifier.

Nonnumbered producer fields require the same single-home discipline. A raw export-header string and generic mapping boundary would make historical spellings, runtime normalization, and application fallbacks competing authorities. The cross-layer producer axis is therefore a closed core-owned identity resolved exclusively from one immutable filing producer snapshot.

## Considerations

- The accepted dual-key decision already requires semantic values to project to official numbered casillas without a second aggregation path.
- The official-form coverage audit and the dual-keying research ground the missing annual-summary, per-activity prorrata, differentiated-sector, and simplified-regime fixed shapes; they provide evidence rather than architectural ownership.
- The accepted cross-period prorrata decision owns the sole encrypted `ProrrataRegister`, global prorrata calculation, carry, apportionment, settlement, and its activity and sector extension axes.
- The accepted refund, payment, prior-domiciliation, carry, and secure-account decisions continue to own disposition, elections, wallet carry, and account security.
- The casilla-schema canonical-derivations decision owns official-slot declaration only. Producer ownership, applicability, value arrival, and export completeness remain outside that classifier.
- The proposed simplified-regime ADR remains a separate, non-governing calculation-completeness record. It is neither accepted nor superseded by this projection decision.
- The accepted S46 substrate establishes the immutable filing producer snapshot, explicit presenter identity, typed amendment evidence, and disposition-selected secure account boundary that the projection consumes.

## Considered options

- **Make each official slot an independent producer** -- rejected because it duplicates semantic facts across casillas, profiles, elections, repeated rows, and export fields.
- **Use one untyped export payload as the semantic home** -- rejected because it erases provenance, applicability, row identity, sensitivity, and existing domain ownership.
- **Create export-specific activity and sector stores** -- rejected because they would compete with the accepted `ProrrataRegister` and its existing activity and sector axes.
- **Retain raw header keys with runtime normalization or aliases** -- rejected because historical spellings would remain executable producer identities and the mapping boundary could bypass the canonical snapshot.
- **Own the producer enum in the registry or application layer** -- rejected because the identity crosses domain, registry, development generator, and application boundaries; a layer-local enum would be duplicated or imported against the dependency direction.
- **Use one core-owned closed producer key resolved exhaustively from the filing snapshot** -- chosen because it gives every admitted nonnumbered producer one stable identity without making the registry a value authority.
- **Keep one canonical typed owner per fact and project exact official endpoints from it** -- chosen because it preserves established calculation and persistence authority while making every official anchor deterministic and auditable.
- **Create a sibling projection ADR** -- rejected because this accepted dual-key ADR already owns the decision and must remain its single home.

## Constraints

- One fact has one semantic owner and one production path. An official endpoint never binds, aggregates, derives, or persists the same fact independently.
- Semantic casilla identifiers remain calculation keys. Official numbered casillas are downstream endpoints except where an official-only value has no upstream twin; no shadow semantic identifier is created for such a value.
- The reviewed semantic map is the sole source-epoch coordinate authority and joins one exact parser anchor to one canonical producer, official-only endpoint, or exact source literal/transport policy. It carries the exact official `source_ref` and `source_sha256`; revision projection declarations remain coordinate-free admission evidence. It may not infer by number, label, position, width, neighbouring fields, implicit source selection, alternate anchor catalogues, or legacy layout.
- Repeated official blocks preserve typed row identity and deterministic ordinal projection. They are never flattened into per-slot scalars, parallel selector lists, or export-specific stores.
- Applicability is typed and fail-closed. Blank output is permitted only when the canonical applicability decision says the field is not applicable; an applicable missing or conflicting value refuses the complete export before bytes.
- `clasificar_casillas_oficiales` is the sole declaration classifier. It answers whether an official box is addressed, represented through a binding, or undefined; it does not decide producer ownership, value arrival, applicability, or completeness.
- Pre-generation projection admission is owned by one revision-level typed `projection_endpoints` declaration section. Each entry contains exactly one canonical `FilingProjectionRef` plus legal and source evidence; it never contains an export field id, wire coordinate, value, applicability override, or legacy layout key.
- A numbered projection declaration must resolve exactly once to the embedded `projection_only` casilla. Nonnumbered simplified and exonerado declarations remain typed endpoints without inventing shadow casillas. Duplicate, ungrounded, cross-revision, or mismatched declarations refuse snapshot construction.
- Semantic-map validation admits `projection_ref` only from the selected revision's declaration index. It never consults an existing or seed export layout. Generated-layout validation then requires an exact bijection between declarations and generated projection fields, with no missing, duplicate, or undeclared projection field.
- The typed declaration replaces projection admission through duplicated string `casilla.export_refs`. `clasificar_casillas_oficiales` treats a numbered declared projection as addressed while remaining declaration-only; it does not become a producer or value-arrival authority.
- Source-declared literals, reserves, and transport checks remain source/codec facts and never become taxpayer or calculation semantics.
- No compatibility alias, alternate resolver, export recomputation, header default, plaintext account path, unsupported-as-filler classification, or legacy read tolerance is permitted.
- The closed producer identity is a public core `StrEnum`. Registry and semantic-map models carry enum members; only canonical TOML loading converts the exact string value. Generic `BeforeValidator` coercion, case folding, normalization, and runtime string hydration are forbidden.
- `producer_key` is the sole payload axis for a scalar snapshot-backed field and replaces `header_key`. Repeated-row fields, plus the slotless Modelo-347 marker in the atomic thirteen-field DP30304 exonerado block, use the distinct typed `projection_ref` axis; a field declares exactly one payload according to its kind. The marker is not a scalar producer, activity slot, literal, or computed field.
- Historical header spellings are migration inputs, never aliases or enum members. Multiple official anchors may project one canonical producer, but no historical spelling survives as an alternate producer identity.
- Filed-artifact observation remains evidence-scoped: `ObservedHeaderFact.header_key` retains constrained raw text and cannot enter the render boundary.
- A source literal, reserve, seal, marker, program version, closing tag, or checksum is classified through literal, filler, computed, or codec policy, never through the producer enum. An AEAT seal may be blank only when the source-bound record design proves AEAT owns that reserve.
- An unimplemented S47-S51 producer remains an explicit gap that refuses before target creation or byte emission. It cannot be admitted temporarily, supplied as a raw string, or reclassified as filler, literal, blank, or zero.
- Renderer input is one immutable `FilingProducerSnapshot`, not `Mapping[str, str]`. Presenter identity has no taxpayer fallback; taxpayer names have distinct typed facts and cannot be recovered through operator-name helpers or an ambiguous `name` key.
- M202 refuses at snapshot construction while its exact producer-gap inventory is nonempty. M303 proceeds only when every applicable producer, source, and applicability axis is admitted.
- An export layout is one atomic filing-grade unit. It remains active only when every field has an admitted exact payload axis and the complete layout passes producer, source, applicability, and renderability checks.
- A layout containing any unsupported or deferred producer is physically withdrawn with a grounded support-removal decision. The withdrawal cascades through casilla export-field references, construct layout membership, and orphan export application links, schedules, and paths so the registry remains closed and no capability surface redeclares the withdrawn export.
- Support-removal records are the sole non-active lifecycle representation. A retained inactive or legacy-shaped layout representation is forbidden because it would fork authority and could be reactivated accidentally.
- Withdrawing an export layout does not withdraw its calculation casillas, formulas, bindings, legal sources, or official artefacts. Those remain canonical evidence and calculation authority unless independently removed by a grounded decision.

## Implementation

### Projection architecture

The architecture has three stages:

Before those stages, the selected revision supplies the complete typed projection declaration index. This is semantic admission only: the reviewed map may reference it before any layout exists, while the later generated layout must realize it bijectively. A seed layout, a semantic-map-owned declaration, and duplicated casilla export-field strings are forbidden because each would recreate the S19/S20 bootstrap cycle or fork authority.

1. A canonical typed domain or application owner produces each fact.
2. The reviewed semantic map classifies each exact official source anchor against that producer, an official-only canonical endpoint, or an exact source literal/transport policy.
3. The filing renderer projects the value to its numbered casilla, nonnumbered fixed slot, or repeated row only after applicability and whole-export completeness have passed.

The projection stage contains no business fallback. Missing producer authority, row identity, election, secure account, or applicability evidence refuses before target creation or byte emission.

### Projection-only numbered endpoints

An official numbered casilla whose value is owned exclusively by a typed repeated-row
projection uses the closed registry input kind `projection_only`. This is an input-kind
classification, not a free boolean over `manual`, and not a sibling descriptor outside
the canonical casilla graph.

Projection-only casillas remain visible in the selected registry snapshot so their
official identity, legal and source grounding, applicability, and exact export anchor
remain reviewable. They are excluded from initial-value discovery, manual and bound
input maps, and zero seeding. A caller that supplies one directly is rejected explicitly;
the value is never ignored or accepted as a scalar override.

A projection-only casilla cannot declare a formula, binding, alternate binding, or
independent producer. Its producer classification is the distinct `projection_only`
path. For M303 casillas 500 through 524, values arrive only by deterministic slot
projection from the five typed activity-row children of the encrypted
`ProrrataRegister`. Missing, duplicate, over-capacity, or invalid applicable rows refuse
before target creation or byte emission. This refinement does not reactivate a withdrawn
M303 layout and creates no alias, fallback, legacy spelling, or parallel store.

### Differentiated-sector deduction projection

The earlier statement that all calculated values for casillas 700 through 735
already existed was inaccurate. The frozen IVA-ledger observation does not retain
the current-versus-investment or adjustment identities required by the official
rows; the registry selectors do not close REAGP and rectification ownership; and
the bienes-inversion regularisation owner has no accepted transaction or asset
linkage to those observations. An ephemeral projection over those incomplete
inputs would infer or collapse facts and become a second aggregation authority.

Casillas 700 through 735 therefore remain unavailable projection-only endpoints
until a prerequisite decision and implementation name the canonical source for
current versus investment, REAGP and rectification identity, transaction and asset
linkage, adjustment ownership, candidate-to-frozen classification preservation,
and migration, backfill, and refusal behavior. S49 may consume that enriched
immutable authority only after the prerequisite lands.

Until then the complete differentiated-sector population refuses before target
creation. These endpoints cannot become manual or bound scalars, raw mappings,
label- or slot-inferred categories, blanks, zeros, aliases, legacy selectors, or
layout fields. The production M303 layout remains withdrawn.

### Canonical differentiated-sector source taxonomy

The S54 grounding in
`2026-08-11-aeat-export-fragment-generator-authority-s54-sector-source-taxonomy-research`
closes the prerequisite as follows.

`IvaLedgerInputKind` is deleted and replaced by the core/domain-owned closed
`IvaDeductionFactKind`: `domestic_current`, `domestic_investment`,
`import_current`, `import_investment`, `intra_eu_current`,
`intra_eu_investment`, `reagp_compensation`, `rectification`, and
`investment_goods_regularisation`. The first eight may occur on canonical ledger
observations. Investment-goods regularisation is emitted only by its existing
bienes-inversion owner. Category, flow, rate, and prorrata classification remain
orthogonal axes, with exhaustive validation of their legal combinations.

Candidates and frozen observations carry the deduction kind plus immutable typed
classification provenance: authority or source kind, source reference or locator,
and evidence digest. Freezing copies both losslessly and never derives them from
amount, category, label, account, slot, or the removed input kind. All old readers
and writers are deleted atomically; there is no alias, dual read, or dual write.

An investment observation carries a validated `investment_asset_id`. Its canonical
bienes-inversion record carries the reciprocal stable `acquisition_ledger_id` and,
in sectorized scope, `prorrata_sector_id`. Freezing and aggregation require exact
reciprocity, the same secure profile and year, and equal sector identity. Missing,
duplicate, stale, many-to-one, cross-profile, cross-year, or sector-mismatched links
refuse. Non-investment observations cannot carry an asset identifier.

Rectification base and cuota remain signed ledger-observation values with evidence
linking the corrected source fact and are consumed once by the existing resolver.
Investment-goods regularisation remains calculated by the bienes-inversion service,
which exposes immutable per-asset contributions grouped by register-owned sector;
their sum must equal the existing casilla-43 binding result. The aggregate is never
allocated backward and no projection total is persisted.

The secure ledger and bienes-inversion payloads cut over atomically to the new-only
schema. Backfill is permitted only where persisted authoritative evidence proves
the exact deduction kind and reciprocal asset, ledger, and sector links. Otherwise
migration refuses before commit with an itemized remediation or re-import inventory.
There is no default `current`, inference, compatibility loader, retained old shape,
or partial migration. Each secure profile is replaced only after validated post-load.

S54 owns the enum and provenance in core/domain IVA, observation and selector
validation in the calculation registry, lossless freeze and aggregation routing in
application aggregation, per-sector regularisation contributions in the asset
service, and versioned atomic migration in secure adapters. S49 consumes only these
enriched immutable outputs. Missing classification or provenance, illegal
combinations, ungrounded signed adjustment, unresolved asset or sector, observation
reuse, or incomplete migration refuses before calculation, persistence, projection,
target creation, or bytes. No export registry or layout is changed by S54.

For S49, `IvaLedgerObservation.iva_amount` remains the raw supported or charged
cuota and is not a deductible amount already adjusted by prorrata. The canonical
application aggregation service applies each sector's regime and percentage exactly
once, including the existing special-prorrata 100%, 0%, or common-input routing, and
exposes immutable per-sector and per-deduction-kind apportioned outputs. The registry
projection consumes those outputs and only orders, sums, and projects them into the
official endpoints. It never sums raw observation cuota as deductible, multiplies by
a register percentage, or reimplements special-prorrata routing.

S50 may make the five DP30302 source shapes structurally complete without claiming
that the simplified-regime calculation is complete. The canonical filing-year owner
is one ordered, evidence-bearing collection of discriminated agricultural and
non-agricultural IAE activity rows. Agricultural rows carry the official activity
code and their applicable declared and attested row facts. Non-agricultural rows
carry the canonical IAE epigraph and typed module entries keyed and ordered by the
annual Orden module identity, never domain fields named `module1` through `module7`.
The shared annual Orden/IAE substrate owns activity taxonomy, annual module identity,
order, coefficients, and legal evidence; the filing rows own taxpayer-declared
quantities and evidence-backed off-form results. Taxpayer and IVA profiles own only
applicability and enrolment, not module quantities or export-slot values.

Projection packs exactly two agricultural and two non-agricultural activities per
DP30302 record, permits at most six of each across three records, and preserves each
revision's exact source anchors. It does not coerce the 2023 employee-count fields
into later reserved offsets or infer one positional superset across epochs. Missing
applicable facts, unknown annual module identity or order, duplicate or conflicting
activities, over-capacity, wrong-epoch fields, or row-to-census conflicts refuse
before target creation or bytes. Only fields proven non-applicable may project blank.
Casilla 48 remains manual, guarded against silent zero, and compared with the existing
partial formula reference by advisory. S50 does not promote it, synthesize unsupported
facts from the three-slot reference tables, add a second resolver or store, introduce
profile defaults or scalar slot redeclarations, or treat structural completeness as
calculation completeness.

### Producer vocabulary and resolution

The public core producer enum names semantic facts, not record labels. The registry `producer_key` payload and development semantic-map schema import that enum and require one exact member. Canonical TOML loading is the only string-to-enum boundary. Renderer dispatch is an exhaustive enum-keyed table whose keys equal the enum membership; it receives one `FilingProducerSnapshot` and returns the typed value for the exact official projection.

`producer_key` is restricted to scalar facts resolved from the immutable filing snapshot. Repeated-row ownership is represented by `CasillaFieldKind.PROJECTION`, whose sole payload axis is `projection_ref`. That payload is a strict core-owned discriminated `FilingProjectionRef` union, never a string key. Its family-specific members identify a prorrata activity slot and closed field, a differentiated-sector slot and closed field, a simplified-regime cohort, slot and typed activity, fact, or annual-Orden module address, an exonerado activity slot and its activity-code or IAE field, or the distinct slotless `M303Exonerado390OperacionesTercerosProjectionRef`. Where the official endpoint is numbered, the reference also carries that exact casilla.

The slotless exonerado member is discriminated by `m303_exonerado_390_operaciones_terceros` and carries no slot, field selector, or casilla. It consumes only `M303Exonerado390FilingEvidence.operaciones_terceros_declarables` and that evidence branch's immutable reference: `True` renders `X`, `False` renders the legitimate blank, and a missing applicable boolean or evidence reference refuses. It remains part of the one atomic thirteen-field DP30304 exonerado projector and cannot be promoted to `FilingProducerKey`, flattened into an activity field, or reclassified as a source or transport fact.

The record occurrence supplies the repeated DP30302 context. It is ephemeral application-owned render context, never part of `FilingProjectionRef` and never the binding `row_index`. Descriptions, labels, offsets, neighbouring fields, numeric coincidences, section order, and domain names such as `module1` cannot select semantics. A projection reference points to one existing typed row owner and exact endpoint; it is not a producer, store, calculation path, or compatibility alias. Registry and semantic-map loaders, provenance, generator, renderer dispatch, and every M303 row projector consume the same typed union atomically and reject a reference not admitted exactly once by the selected snapshot.

`RegistrySchemaAccessor` retains the exact immutable `RegistrySnapshot` objects from which it derives collections and subviews and exposes the selected snapshot to filing export. The application-owned `FilingRecordRenderContext` carries that snapshot, the snapshot-owned layout and record, and a positive emitted-record occurrence. Non-repeated records use occurrence one; repeated DP30302 occurrences are one-based and bounded by the selected record contract. Projectors return typed `FilingProjectionValue` entries keyed by the actual projection reference, record identity, and occurrence. Snapshot-free render entry points, externally injected equivalent layouts, JSON or string reference identities, and independent registry re-resolution inside applicability, projectors, or rendering are forbidden.

The whole-export preflight selects the authority snapshot once from law-determined modelo, filing year, and period coordinates, checks the draft and any persisted revision stamp against it, selects the layout from that snapshot, and invokes every family projector with the same snapshot and immutable filing producer snapshot. Rendering begins only after every admitted `(record, occurrence, projection_ref)` is complete, unique, applicable, and renderable and every produced value corresponds to exactly one admitted reference. Missing, duplicate, extraneous, wrong-family, wrong-record, out-of-range occurrence, wrong-revision, or wrong-period values refuse the complete export before target creation or byte emission.

`TaxpayerProfile.iva` represents explicit presence, not a manufactured empty IVA profile. A wholly absent IVA block is `None`. Supplying any IVA fact claims the block and requires a complete `ModeloIVAProfile`, including explicit `M303TaxTerritory`; `iva_regime_default` alone does not claim or create the block, and no path backfills common-regime territory. Non-IVA consumers may retain `None`. Every M303 schedule, calculation, applicability, snapshot, account-scrubbing, disposition, and export boundary must narrow to a complete IVA profile or refuse.

### DP30301 scalar ownership

The exact DP30301 identification scalars A16 through A30 close as one reviewed unit:

| Anchor | Canonical owner |
| --- | --- |
| A16 | Required `M303TaxTerritory`, projected as the exclusively-foral boolean. |
| A17 | The existing explicit REDEME enrolment profile fact. |
| A18 | A required closed M303 regime-composition enum that distinguishes general, simplified, and mixed composition. |
| A19 | A filing-instance joint-return election, never a stable taxpayer default. |
| A20 | Explicit cash-accounting-regime enrolment on the IVA profile. |
| A21 | A period-derived supplier-regime observation fact captured immutably in the filing snapshot. |
| A22-A23 | The canonical `ProrrataRegister` transition option or revocation for the filing period; they are mutually exclusive and cannot be profile booleans. |
| A24-A26 | One coupled insolvency filing fact containing the declaration aggregate, judicial-order date, and filing subtype; partial population refuses. |
| A27 | Explicit voluntary-SII membership, distinct from generic `sii_enrolled`. |
| A28 | The resolved exonerado-390 applicability fact owned by S51 and captured by the snapshot. |
| A29 | The S47/S51 annual-volume result derived from canonical annual operations and official endpoint 88; it is not a `FilingProducerKey`. |
| A30 | Explicit hydrocarbon-deposit-regime advance-payment deduction entitlement on the IVA profile. |

Scalar snapshot facts use closed producer keys only where a scalar renderer consumes them. Derived A29 and row/projector facts keep their existing typed owners and cannot be promoted into duplicate profile fields or producer keys. Missing, contradictory, partial, wrong-period, or inapplicable facts refuse before target creation.

### Durable filing-instance evidence

Joint-return and insolvency facts are durable revision evidence, not export-command arguments. The encrypted calculation-revision catalogue owns `filing_instance_evidence: FilingInstanceEvidence | None`. Its M303 branch requires the explicit joint-return election and the atomic insolvency aggregate containing the judicial-order date and filing subtype. A non-M303 revision cannot carry the M303 branch.

The complete applicable evidence is required when the `CalculationRevision` is created and participates in that immutable revision's identity and digest. There is no author-or-replace mutation, including while the revision is `BORRADOR`. Changing filing-instance evidence creates a new calculation revision; verification freezes the already complete evidence. Existing pre-release M303 revisions without this evidence are invalid and must be recalculated. There is no backfill, tolerant read, inferred false value, or mutable compatibility path.

Export and review-package assembly reload the evidence from the selected revision. Quickfile collects it before calculation and supplies it only to immutable revision creation; no later command may mutate it or pass an authoritative duplicate directly to export. The resolved `M303FilingFacts` snapshot projection composes A19 and A24-A26 from revision evidence, A21-A23 from their canonical arrivals, A28 from revision evidence assembled under S51, and A29 from the derived annual-volume observation. The applicability value must equal the resolved revision/export context or assembly refuses.

M303 revision creation, export, and verification refuse missing evidence, a wrong-model branch, a period mismatch, or an S51 disagreement before target creation. Commands may expose typed collection inputs only for immutable revision creation, never as a mutation or export override.

Presenter tax identity, amendment kind and original AEAT receipt, resolved elections, selected secure account, and stable taxpayer/profile facts resolve only from that snapshot. The snapshot carries distinct taxpayer legal, given, surname, and full-name facts wherever official applicability needs them. Bare `name`, presenter-as-taxpayer, internal filing identifiers as receipt numbers, and operator-profile lookups are not producer fallbacks.

Historical record labels are rewritten at their exact semantic-map or registry anchors. Presenter NIF spellings converge on presenter tax identity; complementaria page and numbered spellings converge on the derived complementaria fact; previous-receipt spellings converge on the validated original AEAT receipt. Name-like anchors are adjudicated individually because legal name, given name, surnames, taxpayer full name, and presenter full name are distinct facts.

### Canonical ownership matrix

| Official field family | Canonical semantic home | Fixed-record projection rule |
| --- | --- | --- |
| Calculated and operator-entered tax amounts | The selected revision's semantic casilla graph: binding, formula, or explicitly manual casilla according to its declared input kind | Project through the official numbered endpoint when one exists; otherwise map the exact source anchor directly to the same semantic casilla. Never aggregate again in export. |
| Annual-summary block for the exonerated-390 population | Existing typed upstream facts where they exist; otherwise the official numbered annual-summary casilla itself is the canonical endpoint | Populate the complete applicable block from exact owners. Do not invent shadow semantic identifiers for official-only values. The exoneration flag and every required endpoint form one completeness unit. |
| Five per-activity prorrata rows, official boxes 500-524 | Typed activity-row children of the sole encrypted `ProrrataRegister`, keyed by stable activity identity and carrying the reviewed row facts and evidence | Project exact slots 1-5 from those register children. No second store, projection carrier, per-slot scalar family, or copy of the global prorrata value is allowed. Global provisional/definitive percentage, carry, apportionment, and settlement remain owned by the accepted prorrata decision. |
| Two differentiated-sector rows, official boxes 700-735 | The existing `ProrrataRegister` sector definitions and entries, including their canonical sector identity and calculated values | Project exact slots 1-2 directly from those existing sector entries. No export row store, duplicate sector collection, parallel selector, or recomputed deduction total is allowed. |
| Simplified-regime activities and modules | The existing registry-formula mechanism and shared annual Orden/IAE activity substrate, subject to the separate proposed calculation-completeness record | Project nonnumbered activity/module slots from the canonical typed rows. Casilla 48 remains manual and guarded until a separate accepted decision establishes complete calculation authority. |
| Stable taxpayer and IVA-profile facts | Persisted typed taxpayer and Modelo IVA profile producers, captured in the immutable filing snapshot | Project typed values directly from the snapshot; header dictionaries, operator-name helpers, and semantic-map defaults are not authorities. |
| Refund, payment, amendment, and prior-domiciliation facts | Typed filing-instance evidence and elections, resolved by their accepted owners | Project only the resolved filing facts. Result shape or profile defaults cannot replace missing required elections. |
| Presenter identity | One typed filing-instance presenter producer, distinct from taxpayer identity | Project the presenter value with no taxpayer fallback. |
| Charge and refund accounts | Distinct encrypted secure-profile account producers selected by the resolved disposition | Read only at the secure application boundary and project only the applicable account. Missing required authority refuses; plaintext never enters registry, casilla, semantic-map, execution, or audit artifacts. |
| Constants, record markers, reserves, and checksum | Hash-verified parser IR, source-bound render profile, and the sole transport checksum producer | Emit the exact declared literal/reserve or transport result. These facts have no application producer and cannot mask unsupported semantics. |

### Delivery ownership

S45 owns the core closed producer vocabulary, `producer_key` schema cutover, loader-only TOML conversion, snapshot-only exhaustive resolver, exact-anchor migration, source-fact reclassification, and deletion of aliases and raw mapping surfaces. S45 also closes the S46 taxpayer-name gap atomically in the canonical snapshot owner; any name fact not yet typed remains a refusal. S46 owns the typed profile, filing-instance, presenter, disposition, and secure-account substrate. S47-S50 own the annual-summary, prorrata-activity, differentiated-sector, and simplified-regime projection implementations. S51 owns applicability and whole-export refusal. S59 owns the annual Orden identity, immutable registry projection and snapshot resolver plus only a required closed typed scope input whose not-claimed value is neutral and whose evidence-required value refuses; it owns no positive censo fact, profile derivation, regime-composition enum, or evidence reference. S55 owns the required persisted `ModeloIVAProfile` composition and its exact no-default mapping into that input. S58 consumes S59 to own nominal filing-evidence references, strict evidenced A28 and simplified-regime branches, immutable encrypted M303 evidence creation, positive evidence-bearing applicability, and revision identity. S56 reuses S58's evidence references for its ordered exonerado activity rows. S55 then consumes S58, S56, and durable register owners to close every DP30301 A16-A30 scalar, including explicit IVA-block absence and all M303 narrowing and refusal boundaries. S57 owns the atomic typed projection-reference integration and deletes every regex, slot, section, offset, numeric, or neighbouring-field semantic inference it replaces. S19 may author maps only after S55-S57 land. S52 owns the five-epoch exact-anchor and exactly-once proof, importing `clasificar_casillas_oficiales` for declaration instead of reproducing it.

These delivery steps own implementation, producer availability, value arrival, and acceptance evidence. This ADR decides semantic homes and projection boundaries; it does not claim those later steps are already complete.

## Rationale

One semantic owner followed by exact official projection is the only option consistent with the accepted dual-key, aggregation, prorrata, refund, payment, carry, secure-storage, and official-box decisions. It preserves official structure without converting that structure into a second domain model. Typed children and existing sector entries express genuine repeated facts while keeping the encrypted `ProrrataRegister` as the sole persistence and calculation substrate.

Keeping the proposed simplified-regime record separate avoids converting an unaccepted completeness proposal into governing architecture. Allowing an official-only casilla to be canonical avoids equally artificial shadow identifiers. Exact anchors and fail-closed applicability prevent unsupported facts from appearing as plausible blanks, zeroes, fillers, or defaults.

## Consequences

- Every M303 source anchor must resolve exactly once to a canonical producer, an official-only canonical endpoint, or an exact source/transport fact.
- Numbered casillas remain official endpoints; official-only annual-summary values need no duplicate upstream identifier.
- Five activity rows extend the sole encrypted `ProrrataRegister`, and two differentiated rows reuse its existing sector definitions and entries; no second store or projection carrier is introduced.
- Missing applicable authority becomes a whole-export refusal rather than silent blank or zero output.
- The raw `ExportHeaderKey` and `Mapping[str, str]` render boundary are deleted. Producer vocabulary is a core-owned closed enum, and exact TOML strings hydrate only at the canonical loader boundary.
- Scalar snapshot facts use only `producer_key`; repeated-row fields, plus the slotless Modelo-347 marker in the atomic thirteen-field DP30304 exonerado block, use only the strict core-owned `projection_ref` union and cannot be re-expressed as scalar producers, strings, literals, filler, or inferred slots. DP30302 record occurrence stays outside projection identity as render context.
- Foral and profile scalars, including DP30301 A16, must arrive from canonical tax-territory and profile authority with no constant or non-foral default. The six exonerado activity-code and IAE pairs must arrive from one typed ordered evidence-bearing row owner rather than raw markers or placeholders.
- An absent IVA block is represented only by `None`; constructing a partial or authority-free `ModeloIVAProfile` is impossible, and every M303 consumer narrows or refuses explicitly.
- DP30301 A16-A30 resolve only through the stated profile, filing-instance, observation, prorrata, insolvency, applicability, and annual-volume owners. No scalar bag, duplicated profile boolean, or producer key may replace a derived or register-owned fact.
- Joint-return and insolvency facts are encrypted evidence present at immutable calculation-revision creation and bound into revision identity. BORRADOR mutation, export arguments, defaults, and historical M303 revisions without evidence are not accepted as authority.
- Historical header spellings, normalization helpers, aliases, operator-name fallback, taxpayer-as-presenter fallback, and internal filing-id receipt projection become hard failures rather than tolerated inputs.
- Source and transport facts remain outside the producer vocabulary; unsupported future producer gaps remain explicit refusals until their owning steps land.
- M202 cannot create an export artifact while its snapshot is incomplete, and M303 cannot render a layout whose producer/source/applicability inventory is incomplete.
- Mixed unsupported layouts are withdrawn atomically with their complete dependency cascade; no partial layout or unsupported field survives as a filler, literal, blank, zero, or compatibility path.
- The semantic map remains meaning-only, the casilla classifier remains declaration-only, and export completeness remains the value-arrival authority.
- The proposed simplified-regime ADR remains non-governing and separate; casilla 48 remains manual until a later accepted completeness decision.
- S45-S52 remain required implementation and proof work and may not be short-circuited by this architectural decision.

### Complete simplified-regime value arrival

DP30302 structural coverage is not calculation completeness. The accepted simplified-regime calculation decision owns one reviewed five-epoch semantic field matrix and one calculation-domain per-activity result derived from immutable filing-row evidence plus the exact annual Orden snapshot. Annual parameters, taxpayer statements, calculated results, snapshot arrival, and coordinate-only projection remain distinct canonical homes.

An applicable simplified-regime filing must carry complete attested inputs and exactly one year-, revision-, period-, evidence-, and source-bound calculation result before any endpoint is projected. Projection selects typed values only; it never calculates, infers, defaults, or reads a generic result bag. Missing, extraneous, duplicate, wrong-epoch, or digest-divergent results refuse the whole export before target creation. The partial 34-endpoint assumption and any generic `off_form_result` path replaced by typed results are deleted without aliases or compatibility readers.

## Amendment (2026-08-14): S63 coordinate-free DP30302 endpoint axes

S72's reviewed, source-hash-bound five-epoch DP30302 field matrix establishes a declaration shape that the existing simplified-regime reference members do not fully express. The closed fact address decided above is therefore refined, not replaced: a simplified fact reference carries the existing `cohort` and activity `slot`, one closed semantic fact member, and a positive `sub_index` only when that semantic fact is a source-declared repeating family. The emitted record occurrence remains application-owned render context and never enters the reference. An annual-Orden `module_order` remains the one-based ordinal of an activity's canonical module and is never reused as the sub-index of a source-only repeated fact.

The sub-index is semantic multiplicity within one typed fact family, not a wire coordinate. For each activity slot, the source-bound semantic-map authoring pass assigns the dense `1..N` run by exact official source order and proves it against the selected hash-pinned record-design. Source ordinal, offset, description, printed operand letter or number, and neighbouring fields are authoring evidence only; none enters `FilingProjectionRef`, a projection declaration, the projector, or persisted filing evidence. A singleton fact carries no sub-index. A repeating fact requires exactly one sub-index in its admitted dense domain. Missing, zero, out-of-domain, duplicate, or unnecessary sub-indices refuse compilation.

The closed repeated families and epoch domains are exact. `mesas_capacidad`, `mesas_dias_cuarto_trimestre`, and `mesas_numero` each admit sub-indices 1 through 4 in both non-agricultural activity slots in every 2023, 2024-early, 2024-late, 2025, and 2026 source epoch: eight declarations per family and epoch. `superficie_horno_dias_cuarto_trimestre` is a singleton without sub-index through 2024-late and admits sub-indices 1 through 4 in both slots for 2025 and 2026. `superficie_horno_cuarto_trimestre` is absent through 2024-late and admits sub-indices 1 through 4 in both slots for 2025 and 2026. No other fact acquires multiplicity without another reviewed amendment grounded in a refreshed matrix.

Every nonnumbered simplified anchor receives one declaration and every declaration receives one exact anchor. The simplified declaration cardinalities are therefore 134, 130, 140, 142, and 142 for 2023, 2024-early, 2024-late, 2025, and 2026 respectively. Retaining the 74 already closed prorrata, differentiated-deduction, and exonerado declarations makes the complete revision declaration-index cardinalities 208, 204, 214, 216, and 216. These counts are source-epoch invariants, not a licence to generate endpoints from a count or to preserve an endpoint after its source anchor disappears.

The other DP30302 axes stay disjoint and closed. Activity identity uses the typed activity field member. The generic `module N` unit and amount anchors use the applicable annual Orden's exact `module_order` 1 through 7 plus a closed module-value member. All remaining agricultural and non-agricultural anchors use closed semantic fact members whose value homes are explicit: immutable filing-row evidence for declared or attested inputs, the exact annual Orden snapshot for regulatory parameters, and the immutable per-activity calculation result for calculated outputs. The projector only selects the typed value at that address. It performs no calculation, annual lookup by label, aggregation, default, fallback, open-string fact lookup, generic result-bag access, or coordinate recovery.

Each simplified declaration cites `ley-37-1992:art-122` and `ley-37-1992:art-123`, the exact selected record-design source, and the filing-year annual Orden source admitted by that revision. More specific annual-Orden legal references retained by the typed source value remain part of that value's provenance; the declaration does not copy coefficients or become a second regulatory-value catalogue. Cross-year Orden citations, design-epoch-only identity, a declaration without the exact record-design, or any source outside the selected revision refuse registry construction.

This is a narrow amendment because the accepted decision already owns coordinate-free projection admission, typed simplified activity/fact/module addresses, source-bound semantic maps, and selection-only projection. It did not decide how a single source description repeated four times inside one activity slot remains both coordinate-free and bijective. S72 measures that multiplicity but, as a plan artefact, cannot create a runtime identity axis. The closed optional sub-index above fills only that gap; it does not authorize a second projector family, ad hoc endpoint kinds, per-slot scalars, semantic-map or layout leakage, or printed-number inference.

## Amendment (2026-08-14): closed M303 rectificativa-motive authority

The hash-pinned 2024-late Modelo 303 record design changes the amendment region from complementaria to rectificativa and declares two distinct unnumbered motive checkboxes. They are not aliases for the rectificativa marker. One immutable M303-specific closed enum owns their meaning: `M303RectificativaMotive.RECTIFICACIONES`, with persisted value `rectificaciones`, and `M303RectificativaMotive.DISCREPANCIA_CRITERIO_ADMINISTRATIVO`, with persisted value `discrepancia_criterio_administrativo`.

The enum belongs to the calculation-revision amendment lifecycle. `CalculationRevision` persists an optional `m303_rectificativa_motive`. The sole nullable amendment identity payload contains the amendment kind, the amended filing-record identity, and that typed motive; it participates in the canonical calculation-revision identity and digest. Free-text `amendment_reason` remains operator explanation outside content identity. The amendment service must resolve the motive before deriving the revision id. Changing the motive, amendment kind, or amended filing target therefore creates a distinct revision; no BORRADOR mutation, backfill, tolerant read, export override, or default is permitted.

Motive applicability is a contextual invariant and is not decided by an isolated `CalculationRevision`. The authoritative construction and encrypted-load boundary resolves the referenced `WorkUnit` and validates the revision as one context-bound aggregate before returning it. That aggregate requires exact agreement between `CalculationRevision.work_unit_id` and the parent, the parent Modelo 303 identity, the parent period and registry revision, and the period, registry revision, record-design source, digest, and epoch already retained by the immutable M303 filing-instance evidence. A motive-bearing revision without that parent context refuses construction or load. Modelo, period, and registry-revision axes remain owned once by `WorkUnit`; they are not copied onto `CalculationRevision` or the motive.

The reviewed applicability set is closed and source-bound: the exact hash-pinned 2024-late, 2025, and 2026 Modelo 303 amendment regions admit the motive. There is no lexical epoch comparison, filing-year shortcut, or generic "2024-late or later" rule. A future epoch remains inapplicable until its exact amendment region and source digest are reviewed and this decision is amended. Within the admitted set the motive is required exactly for `CalculationRevisionAmendmentKind.RECTIFICATIVA`. It is forbidden for an ordinary filing, another amendment kind, another modelo, a pre-cutover M303 revision, or an unreviewed future epoch.

The two enum values are mutually exclusive. An applicable rectificativa carries exactly one, so the two official checkboxes project as `(selected, unselected)` and never both selected or both absent. Outside their applicability set both values are absent. The legitimate unselected checkbox is rendered through the reviewed checkbox value policy; absence cannot manufacture an applicable unselected value.

`AmendmentEvidence` and the immutable `FilingProducerSnapshot` carry the exact persisted enum value. Export constructs that evidence from the persisted revision and the amended filing's authoritative AEAT receipt; an export command is not a motive or receipt authority. If a command surface temporarily carries amendment evidence, every field must equal the persisted evidence exactly or export refuses before snapshot construction.

The same authoritative aggregate construction and encrypted-load boundary resolves the amendment identity's `amends_filing_record_id` to exactly one `ModeloRecord`. The resolved record id, `work_unit_id`, Modelo, filing period, and registry context through its referenced WorkUnit must agree exactly with the amendment revision and parent aggregate. The target must be the authoritative AEAT-accepted filing, carry `ExternalEvidence`, and its `reference_id` must resolve to matching persisted `Justificante` metadata for the same taxpayer, Modelo, filing year, and period. Its non-null `presentation_id` is the sole original-AEAT-receipt producer value. A missing, arbitrary, duplicated, cross-work-unit, cross-modelo, cross-period, cross-registry-context, non-accepted, evidence-free, unresolvable, mismatched, or receipt-less target refuses aggregate construction and encrypted load. Export repeats the joined-authority validation and derives the receipt only from that validated `Justificante`; it never trusts the identifier payload alone.

The snapshot validates the persisted motive against its Modelo, M303 filing period, and the same retained record-design coordinate before exposing producer values. The closed `FilingProducerKey` vocabulary gains two separate scalar identities, one for rectificaciones and one for discrepancia de criterio administrativo. The exhaustive producer resolver returns opposite booleans for an applicable motive and `None` for both keys when the fields are inapplicable. The existing rectificativa marker key continues to own only the general rectificativa indicator; it cannot supply either motive field.

Free-text amendment reason remains operator explanation, not classification authority. The motive may not be inferred from that text, changed casillas, result direction, the prior receipt, the prior-domiciliation election, the discrepancy-only other-adjustments amount, any numbered casilla value, source description, neighbouring field, wire coordinate, epoch ordering, or filing year. Missing, contradictory, context-free, or command-substituted motive evidence refuses revision load, snapshot construction, or export before target creation.

For the 2024-late DP30303 amendment region, the semantic homes are exact: the rectificativa marker uses the existing rectificativa producer; the prior receipt uses the existing original-AEAT-receipt producer; the prior-domiciliation action uses its existing filing election; the other-adjustments and rectification amounts retain their own typed casilla or calculation owners; the AEAT reserve remains a source reserve; and the two motive checkboxes use the two new producer keys. Neither motive may be mapped to `is_rectificativa`, a literal, filler, blank default, or the other motive's producer.

This is a narrow amendment of the accepted single-home and closed-producer decision. It does not create another amendment engine, projection family, generic motive bag, duplicated context stamp, or semantic-map inference surface. Implementation must land before the 2024-late semantic map is authored and must prove guarded persistence and reload, refusal of context-free deserialization, aggregate axis mismatch refusal, complete amendment-identity divergence, period, kind, source, digest, and epoch applicability, snapshot exhaustiveness, the complete applicable and inapplicable truth table, command-evidence substitution refusal, exact source-anchor ownership, both emitted wire alternatives, and adversarial refusal of missing, dual, inferred, defaulted, wrong-model, wrong-revision, wrong-period, or unreviewed-future motives. The unchanged 2023 and 2024-early complementaria mappings remain separate regression obligations.
