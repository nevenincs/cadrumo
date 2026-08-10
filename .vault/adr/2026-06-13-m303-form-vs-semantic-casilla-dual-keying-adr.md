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
modified: '2026-08-10'
body_hash: 'sha256:2ca631d8ca7d09a93ef47dda09066144721cbefe03519eb56af56d9f3fdac295'
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
- The reviewed semantic map joins one exact parser anchor to one canonical producer, official-only endpoint, or exact source literal/transport policy. It may not infer by number, label, position, width, neighbouring fields, or legacy layout.
- Repeated official blocks preserve typed row identity and deterministic ordinal projection. They are never flattened into per-slot scalars, parallel selector lists, or export-specific stores.
- Applicability is typed and fail-closed. Blank output is permitted only when the canonical applicability decision says the field is not applicable; an applicable missing or conflicting value refuses the complete export before bytes.
- `classify_official_boxes` is the sole declaration classifier. It answers whether an official box is addressed, represented through a binding, or undefined; it does not decide producer ownership, value arrival, applicability, or completeness.
- Source-declared literals, reserves, and transport checks remain source/codec facts and never become taxpayer or calculation semantics.
- No compatibility alias, alternate resolver, export recomputation, header default, plaintext account path, unsupported-as-filler classification, or legacy read tolerance is permitted.
- The closed producer identity is a public core `StrEnum`. Registry and semantic-map models carry enum members; only canonical TOML loading converts the exact string value. Generic `BeforeValidator` coercion, case folding, normalization, and runtime string hydration are forbidden.
- `producer_key` is the sole payload axis for a producer-backed field. It replaces `header_key`; a field declares exactly one of casilla, binding, literal, producer, draft, or computed payload according to its kind.
- Historical header spellings are migration inputs, never aliases or enum members. Multiple official anchors may project one canonical producer, but no historical spelling survives as an alternate producer identity.
- Filed-artifact observation remains evidence-scoped: `ObservedHeaderFact.header_key` retains constrained raw text and cannot enter the render boundary.
- A source literal, reserve, seal, marker, program version, closing tag, or checksum is classified through literal, filler, computed, or codec policy, never through the producer enum. An AEAT seal may be blank only when the source-bound record design proves AEAT owns that reserve.
- An unimplemented S47-S51 producer remains an explicit gap that refuses before target creation or byte emission. It cannot be admitted temporarily, supplied as a raw string, or reclassified as filler, literal, blank, or zero.
- Renderer input is one immutable `FilingProducerSnapshot`, not `Mapping[str, str]`. Presenter identity has no taxpayer fallback; taxpayer names have distinct typed facts and cannot be recovered through operator-name helpers or an ambiguous `name` key.
- M202 refuses at snapshot construction while its exact producer-gap inventory is nonempty. M303 proceeds only when every applicable producer, source, and applicability axis is admitted.

## Implementation

### Projection architecture

The architecture has three stages:

1. A canonical typed domain or application owner produces each fact.
2. The reviewed semantic map classifies each exact official source anchor against that producer, an official-only canonical endpoint, or an exact source literal/transport policy.
3. The filing renderer projects the value to its numbered casilla, nonnumbered fixed slot, or repeated row only after applicability and whole-export completeness have passed.

The projection stage contains no business fallback. Missing producer authority, row identity, election, secure account, or applicability evidence refuses before target creation or byte emission.

### Producer vocabulary and resolution

The public core producer enum names semantic facts, not record labels. The registry `producer_key` payload and development semantic-map schema import that enum and require one exact member. Canonical TOML loading is the only string-to-enum boundary. Renderer dispatch is an exhaustive enum-keyed table whose keys equal the enum membership; it receives one `FilingProducerSnapshot` and returns the typed value for the exact official projection.

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

S45 owns the core closed producer vocabulary, `producer_key` schema cutover, loader-only TOML conversion, snapshot-only exhaustive resolver, exact-anchor migration, source-fact reclassification, and deletion of aliases and raw mapping surfaces. S45 also closes the S46 taxpayer-name gap atomically in the canonical snapshot owner; any name fact not yet typed remains a refusal. S46 owns the typed profile, filing-instance, presenter, disposition, and secure-account substrate. S47-S50 own the annual-summary, prorrata-activity, differentiated-sector, and simplified-regime projection implementations. S51 owns applicability and whole-export refusal. S52 owns the five-epoch exact-anchor and exactly-once proof, importing `classify_official_boxes` for declaration instead of reproducing it.

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
- Historical header spellings, normalization helpers, aliases, operator-name fallback, taxpayer-as-presenter fallback, and internal filing-id receipt projection become hard failures rather than tolerated inputs.
- Source and transport facts remain outside the producer vocabulary; unsupported future producer gaps remain explicit refusals until their owning steps land.
- M202 cannot create an export artifact while its snapshot is incomplete, and M303 cannot render a layout whose producer/source/applicability inventory is incomplete.
- The semantic map remains meaning-only, the casilla classifier remains declaration-only, and export completeness remains the value-arrival authority.
- The proposed simplified-regime ADR remains non-governing and separate; casilla 48 remains manual until a later accepted completeness decision.
- S45-S52 remain required implementation and proof work and may not be short-circuited by this architectural decision.
