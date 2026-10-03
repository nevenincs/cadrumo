# Identity, profile sessions, result disposition, and storage taxonomy

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-116` · **Topic:** [Core authority and shared controls](../topics/core-authority-and-shared-controls.md)

<!-- preserved:article -->
## Scope and method

This chunk contains 34 core modules totaling 4,617 lines, 194,620 bytes, and 43,310 measured proxy tokens. I read all nine bounded pages, including complete result-disposition, storage-taxonomy, and tabular-normalization modules. Static inspection only: no application imports, tests, file writes, AEAT/Cl@ve requests, or external legal checks were performed.

## Identity, profile-session, and value boundaries

`ProcessScopedBinding` combines a process-wide value protected by a lock with a context-local override. It supports one authenticated profile session shared across CLI, async and worker-thread entry points while preserving scoped shadowing for a block. `None` remains a meaningful override, nested overrides unwind through context tokens, and close paths can clear only the exact object they observed so a reentrant replacement is not accidentally erased. The binding retains references rather than copying or zeroizing secrets; lifecycle custody stays with the owner. Process-scoped and contextual binding (`src/cadrumo/core/process_binding.py`)

Profile vocabularies distinguish pure discovery results (recognized, concurrent change, degraded), publication reasons (enroll versus restore), persisted-session refusal causes (including expiry, changed custody, tampering, missing keychain data, and unavailable keyring), and an unavailable profile record from ordinary “session required.” These distinctions let callers report retry, repair, logged-out, and unavailable states without collapsing them into an empty profile list. They are contracts, not the session persistence or cryptographic implementation. Discovery outcomes (`src/cadrumo/core/profile_discovery.py`) Publication types (`src/cadrumo/core/profile_publication.py`) Session and record refusal states (`src/cadrumo/core/profile_session.py`)

Other common value contracts separate semantic axes: current positive-result payment election from prior direct-debit retention and negative-result refund election; per-modelo result disposition; presentation notice data; operation progress; and operator action evidence/source/conditionality. Syntax-only `Modelo` and `TaxDomain` identifiers deliberately do not claim catalogue membership, while `RegistryToken` types require registry projection or distinguish projected text from already validated tokens. Spanish postcodes retain leading zeroes and restrict province prefixes to 01–52. This division keeps wire syntax from being mistaken for domain authority. Refund election (`src/cadrumo/core/refund_election.py`) Opaque registry tokens (`src/cadrumo/core/registry_token.py`) Postcode shape (`src/cadrumo/core/spanish_postcode.py`)

The larger result-disposition contract maps per-modelo result casillas and signs into filing codes. It distinguishes refund status (controls carry-forward) from whether an account must be placed in the file (which also includes direct debit), rejects unrelated casilla IDs, and yields `None` for an uncatalogued modelo so consumers must apply an explicit fallback rather than inventing a code. Examples declared here include M303 negative credit as `C`, M130/M131 negative interim-quarter results as `B` but Q4 as `N`, M200 negative as refund `D`, and payment/refund-channel codes kept separate from raw sign derivation. These rules are anchored to bundled record designs/instructions in the source comments but were not independently checked against AEAT. Disposition specification (`src/cadrumo/core/result_disposition.py`) Refund versus account axes (`src/cadrumo/core/result_disposition.py`) Sign derivation and input filtering (`src/cadrumo/core/result_disposition.py`)

## Remote authority, lifecycle evidence, and storage

`remote_authority.py` is a narrow guard helper: it accepts only HTTPS URLs with a bare hostname, rejects user-info and explicit ports rather than stripping them, and compares hostnames at label boundaries so `evilagenciatributaria...` is not admitted as a subdomain. It derives current/legacy AEAT suffixes from centralized constants and treats Cl@ve as a distinct national-IdP allowance whose use is gated separately. These predicates do not themselves define a full request policy or authorize a host for arbitrary data. Canonical hostname parsing (`src/cadrumo/core/remote_authority.py`) Suffix-boundary test (`src/cadrumo/core/remote_authority.py`) Separate Cl@ve allowance (`src/cadrumo/core/remote_authority.py`)

The storage taxonomy is a typed inventory for application-chosen paths. Each `StorageLocation` carries subpath, file/directory kind, root/bucket/keystore scope, override policy, lifecycle, operator grouping, and fingerprint participation, plus either a consuming module or a documented dormant reason. The location table includes profile-capsule and keystore custody files, live-state evidence, logs, caches, generated outputs, bucket paths, and several retired/dormant paths retained for recognition or explicit accounting. Root settings fields are reverse-indexed from the same declaration. Taxonomy axes and locations (`src/cadrumo/core/storage_taxonomy.py`) Strict location record (`src/cadrumo/core/storage_taxonomy.py`) Central location data (`src/cadrumo/core/storage_taxonomy_locations.py`)

Path resolvers distinguish root-scoped from bucket/keystore-scoped entries, keep keystores as siblings of bucket data, and derive storage-tree directories from declared fields rather than a second list. Materialization is explicit: operator-selected overrides must already be directories, while application-owned root/default targets may be created; only the root receives the permission-restriction call in this helper. One security boundary to verify at consumers is bucket ID validation: `bucket_scoped_storage_path` rejects a blank ID but does not itself enforce a path-safe identifier grammar before joining it into the path. Its safety therefore depends on every caller supplying a validated ID. These helpers also do not supply a general containment guarantee for arbitrary paths. Scoped resolvers (`src/cadrumo/core/storage_taxonomy_locations.py`) Bucket path composition (`src/cadrumo/core/storage_taxonomy_locations.py`) Explicit materialization (`src/cadrumo/core/storage_materialization.py`)

`SecureObjectWrite` is a strict frozen DTO between domain repository ports and persistence. It carries classification, schema version, payload, provenance, source event and optional expected revision/CAS value. The module explicitly leaves UTC-aware timestamp enforcement to the storage funnel; a caller that bypassed that funnel would bypass this part of the write contract, so the integration should be traced. Profile custody facts separately represent enrollment/restore, cached-session refusal and record availability. `RevisionReviewStatus` defaults missing governance metadata to pending review, and schema-family disposition treats undeclared empty families as blocked until populated or explicitly justified as not applicable. These are useful fail-closed declarations, but actual enforcement resides in registry loaders/build gates. Secure-object write DTO (`src/cadrumo/core/secure_object_write.py`) Revision review status (`src/cadrumo/core/revision_review.py`) Schema-family disposition (`src/cadrumo/core/schema_family_disposition.py`)

`storage_taxonomy.py` distinguishes retention/rotation/TTL from unbounded evidence, and independently declares what enters the data-root fingerprint. `storage_materialization.py` separates settings reads from filesystem creation. This makes it possible to reason about where application data belongs and what may be reclaimed, but this chunk does not execute cleanup or demonstrate that every destructive consumer honors the lifecycle tags.

## Tabular ingestion, provenance, and local utilities

`tabular.py` normalizes delimited text without interpreting column meaning. It chooses among semicolon, comma, tab, and pipe using whole-file rectangle scores, supports quoted newlines, and decodes bytes through configured preference/fallback encodings while giving UTF-8 BOM decisive priority. It searches only the first 20 parsed rows for a header, preserves cells verbatim with physical start-line numbers, retains preamble and recognized summary rows separately, and emits notices for encoding fallback, ragged/blank rows, and decimal ambiguity. Decimal convention is inferred from numeric-looking cells but is not applied to the stored values; role mapping and type conversion belong downstream. Malformed decoding, no usable rectangle, and missing headers are the main whole-source refusals. Tabular data contract (`src/cadrumo/core/tabular.py`) Decoding and delimiter scoring (`src/cadrumo/core/tabular.py`) Decimal evidence (`src/cadrumo/core/tabular.py`) Normalization flow (`src/cadrumo/core/tabular.py`)

Provenance stamps encode provider transport, reader, model and optional qualifier in a canonical grammar. The parser returns unknown for malformed/non-LLM stamps rather than optimistic `local`, which matters to cloud-data withdrawal surveys. The module itself says producers need a test-suite gate to prevent hand-formatted stamps from bypassing the constructor. Record-design epochs describe the filing year/design family rather than a PDF revision. Register-scoping signals are deliberately hedged: offline option-list comparisons can indicate likely universal or likely NIF-scoped behavior but cannot assert either as fact without an authorized live probe. Stamp constructor/parser (`src/cadrumo/core/provenance_stamp.py`) Epoch grammar (`src/cadrumo/core/record_design_epoch.py`) Hedged scoping signals (`src/cadrumo/core/register_scoping_signal.py`)

`elided_prose` provides total, visible truncation for system-assembled advisory prose, while operator-entered text retains a raising bound. This prevents a long taxpayer-derived advisory from turning a non-blocking warning into a failed workflow, though a cut message still needs enough headroom to preserve its useful remedy. Spanish stemming shares tokenization and bounded stem caching. `TextBounds` centralizes shape constraints for positive counts, months and canonical sorted month sets; `SyncSurface` distinguishes AEAT-to-local declaration sync from the one-way calculation-sheet mirror. Optional prorrata tokens carry structure while the dated facts registry owns membership and legal meaning. Visible elision (`src/cadrumo/core/prose_elision.py`) Shared stemming (`src/cadrumo/core/spanish_stemming.py`) Scalar bounds (`src/cadrumo/core/text_bounds.py`) Sync direction (`src/cadrumo/core/sync_surface.py`)

## Assessment and follow-up

The strongest local design features are the single typed storage-location authority, separations between factual and presentation/action payloads, scope-aware remote-host checks, model/runtime/licence declarations, and structural preservation in tabular imports. Follow-up should trace safe bucket-ID validation into every storage resolver, verify the third-party sink and secure-write-funnel assumptions at their consumers, and exercise CSV dialect/header/decimal edge cases with representative exports. Export dispositions, notification and pension annotations are declared against bundled authority, not independently validated law. Test and production reachability were not assessed in this static chunk.

## Complete assigned-file coverage

- presentation.py (`src/cadrumo/core/presentation.py`) — lines 1–19
- prior_domiciliation_election.py (`src/cadrumo/core/prior_domiciliation_election.py`) — lines 1–21
- process_binding.py (`src/cadrumo/core/process_binding.py`) — lines 1–116
- product_identity.py (`src/cadrumo/core/product_identity.py`) — lines 1–72
- profile_discovery.py (`src/cadrumo/core/profile_discovery.py`) — lines 1–28
- profile_publication.py (`src/cadrumo/core/profile_publication.py`) — lines 1–43
- profile_session.py (`src/cadrumo/core/profile_session.py`) — lines 1–79
- prorrata_exclusions.py (`src/cadrumo/core/prorrata_exclusions.py`) — lines 1–38
- prorrata_register.py (`src/cadrumo/core/prorrata_register.py`) — lines 1–66
- prose_elision.py (`src/cadrumo/core/prose_elision.py`) — lines 1–192
- provenance_stamp.py (`src/cadrumo/core/provenance_stamp.py`) — lines 1–126
- record_design_epoch.py (`src/cadrumo/core/record_design_epoch.py`) — lines 1–51
- refund_election.py (`src/cadrumo/core/refund_election.py`) — lines 1–63
- register_scoping_signal.py (`src/cadrumo/core/register_scoping_signal.py`) — lines 1–56
- registry_token.py (`src/cadrumo/core/registry_token.py`) — lines 1–137
- remote_authority.py (`src/cadrumo/core/remote_authority.py`) — lines 1–132
- renta_declaracion_type.py (`src/cadrumo/core/renta_declaracion_type.py`) — lines 1–13
- repository_id.py (`src/cadrumo/core/repository_id.py`) — lines 1–49
- requirement.py (`src/cadrumo/core/requirement.py`) — lines 1–39
- rescate_type.py (`src/cadrumo/core/rescate_type.py`) — lines 1–43
- result_disposition.py (`src/cadrumo/core/result_disposition.py`) — lines 1–388
- revision_review.py (`src/cadrumo/core/revision_review.py`) — lines 1–75
- schema_family_disposition.py (`src/cadrumo/core/schema_family_disposition.py`) — lines 1–73
- secure_object_write.py (`src/cadrumo/core/secure_object_write.py`) — lines 1–81
- source_locator.py (`src/cadrumo/core/source_locator.py`) — lines 1–46
- spanish_postcode.py (`src/cadrumo/core/spanish_postcode.py`) — lines 1–74
- spanish_stemming.py (`src/cadrumo/core/spanish_stemming.py`) — lines 1–82
- storage_materialization.py (`src/cadrumo/core/storage_materialization.py`) — lines 1–110
- storage_taxonomy.py (`src/cadrumo/core/storage_taxonomy.py`) — lines 1–415
- storage_taxonomy_locations.py (`src/cadrumo/core/storage_taxonomy_locations.py`) — lines 1–972
- sync_surface.py (`src/cadrumo/core/sync_surface.py`) — lines 1–44
- tabular.py (`src/cadrumo/core/tabular.py`) — lines 1–703
- tax_domain.py (`src/cadrumo/core/tax_domain.py`) — lines 1–50
- text_bounds.py (`src/cadrumo/core/text_bounds.py`) — lines 1–121
<!-- /preserved:article -->
