---
tags:
  - "#adr"
  - "#identity-primitives"
date: '2026-05-30'
modified: '2026-05-30'
related:
  - "[[2026-05-30-identity-primitives-reference]]"
  - "[[2026-05-13-identity-adr]]"
  - "[[2026-05-20-registry-casilla-identity-adr]]"
  - "[[2026-05-21-profile-uuid-identity-adr]]"
  - "[[2026-05-22-schema-hardening-adr]]"
  - "[[2026-05-22-secure-storage-production-hardening-architecture-adr]]"
  - "[[2026-05-20-registry-authority-flow-adr]]"
  - '[[2026-06-04-identity-primitives-research]]'
---

# `identity-primitives` adr: `typed-id alias placement rule for record-shape, security, and cross-domain identities` | (**status:** `accepted`)

## Problem Statement

The codebase carries identity strings as a mix of typed pydantic aliases (`SubjectTaxId`, `WorkUnitId`, `CalculationRevisionId`, `FilingRecordId`, `TransactionId`, `BucketId`, the 22 registry aliases, and the `ManualId` / `ManualPart` StrEnums) and over a thousand bare-string id-suffix declarations scattered across 287 files.

The placement of the typed aliases that do exist follows no single principle: `SubjectTaxId` lives in `core/identity/` on security grounds; the hex-64 record aliases live in `domain/modelos/_ids.py` on owner-domain grounds; `BucketId` lives in `domain/modelos/_ids.py` despite being consumed by `domain.transactions`, `domain.invoices`, `domain.attachments`, and the persistence adapter layer - a sibling-domain import that inverts the hexagonal direction the project architecture-boundaries rule otherwise preserves. The inventory finding is documented in `2026-05-30-identity-primitives-reference`.

Without a placement rule, every new identity surface is adjudicated ad-hoc: `ProfileId` was specified semantically by `2026-05-21-profile-uuid-identity-adr` but never promoted to an alias, leaving eighteen bare-string `profile_id: str = Field(min_length=1, max_length=96)` declarations shadowed across the application layer; `InvoiceId` is declared inline via a duplicated `_HEX_INVOICE_ID_LENGTH = 64` constant; `BundleId`, `EvidenceId`, `AttachmentId`, `SnapshotId`, `VerificationReportId`, and `DecisionId` repeat the same pattern. The architecture-boundaries rule forbids bare `dict[str, Any]` at persisted-record boundaries; bare-`str` identities with only a length constraint are the string analogue of the same boundary leak, and the calculation-grounding rule clause that type-system escapes are boundary leaks applies directly to the CLI `_modelo.py` import of the registry private `_CASILLA_RE` / `_REF_RE` regex constants.

## Considerations

The four placement options the inventory surfaces are: (1) keep record-shape aliases in each owner domain and let sibling domains import across; (2) promote every cross-domain identity to `core/`; (3) create a new top-level home (`core/identifiers/`, `domain/storage/`) per identity family; (4) compose identities from a small set of shared shape primitives (`Hex256Digest`, `KebabRef`, `SegmentRef`) that live above the alias declarations.

Three principles already govern adjacent decisions and must be reconciled by any rule this ADR sets: the security-primitive precedent (`2026-05-13-identity-adr`) places algorithmic-validation identities in `core/` because every layer needs them and `core/` is the only layer every other layer may import from; the owner-domain precedent (`2026-05-22-schema-hardening-adr`) keeps record-shape aliases with the package that mints and persists the record, on the same strict-pydantic-at-the-load-surface logic that the registry-authority-flow rule applies to the registry compiler; the hexagonal-direction precedent (`aeat-architecture-boundaries`) keeps domain packages independent of one another so each domain remains a self-contained aggregate.

The current `BucketId` placement violates the third precedent: a storage-boundary identity declared inside a record domain forces `domain.transactions`, `domain.invoices`, `domain.attachments`, and the persistence adapter to import from `domain.modelos`. The secure-storage architecture ADR (`2026-05-22-secure-storage-production-hardening-architecture-adr`) treats the bucket as the per-profile container above any single record domain, which makes the inversion semantic, not just topological.

## Constraints

- `core/` may be imported by every other layer; the inverse is forbidden under the project hexagonal direction. Anything placed in `core/` becomes globally reachable.
- Sibling-domain imports are not forbidden by an existing rule text but are the structural shape of an aggregate boundary leak; an alias imported by three sibling domains is the evidence the boundary is drawn in the wrong place.
- The strict-pydantic discipline at boundary surfaces forbids bare `dict[str, Any]`; the same logic forbids bare `str` for identity fields on persisted records, wire payloads, CLI input, and MCP messages.
- The registry-authority-flow rule treats the registry package as a self-contained pipeline; registry identity aliases must remain inside the registry package and the registry private regex constants must not be imported by code outside the registry.
- The source-hygiene rule forbids project-management metadata in identifiers; identity aliases must be named after the entity they identify, not after the campaign that promoted them.
- Existing alias shapes - hex-64 SHA-256 (`WorkUnitId`, `CalculationRevisionId`, `FilingRecordId`, `TransactionId`), 1..128 bucket identity (`BucketId`), the registry `_REF_RE` / `_CASILLA_RE` patterns, and the UUIDv4 profile identity established by `2026-05-21-profile-uuid-identity-adr` - are load-bearing on persisted records and must not be redefined by this rule.

## Implementation

### Rule 1 - placement principle

An identity alias lives at the *lowest* layer that owns its constraint shape and either (a) is imported by code outside the declaring layer, or (b) carries a validator beyond a length / regex constraint. Otherwise the alias stays in the package that owns the record it identifies, in that package `_ids.py` module.

The two clauses correspond to the two existing precedents. Clause (a) covers cross-cutting identities (`BucketId`, `ProfileId`, `SubjectTaxId`): the shape is owned by an infrastructure concept above any single record domain, and more than one consumer needs the alias. Clause (b) covers identities whose constraint embeds domain-validated semantics (the `SubjectTaxId` mod-23 checksum, the `IdentityDocument` closed enum): the validator correctness is a cross-cutting property and the alias must be importable without a layer-boundary crossing.

### Rule 2 - directional rule

Domain packages MAY import identity aliases from `core/`. Domain packages MUST NOT import identity aliases from sibling domain packages. Application packages MAY import identity aliases from any `core/` or `domain/` package they already depend on for behaviour. Adapter packages MAY import identity aliases from `core/` and from the domain packages whose records they persist or transport; adapter packages MUST NOT import identity aliases from application packages. Entrypoint packages MAY import identity aliases from any layer.

Registry aliases declared in `domain/calculations/registry/_ids.py` are the one explicit exception this rule names: they are owned by the registry pipeline and imported by adapters, application, and CLI per the registry-authority-flow precedent. The exception holds because the registry is a self-contained sub-aggregate with its own load surface; no sibling-domain leakage is involved.

### Rule 3 - constraint-shape ownership

The layer that mints an identity owns its constraint shape. Hex-64 content-addressed identities are minted by the modelo records layer and the constraint declaration lives there. UUIDv4 profile identity is minted by the profile lifecycle in the application layer; the constraint declaration lives in `core/identity/` because clause (a) of Rule 1 applies (consumed by adapters, persistence, CLI). Registry ids are minted by the registry compiler; their constraint declarations stay inside the registry package. Bucket identity is minted by the persistence boundary; its constraint declaration moves out of `domain/modelos/_ids.py` (see Rule 5).

A single shared `Hex256Digest` shape primitive is rejected: the four hex-64 record aliases carry distinct semantic roles (a `WorkUnitId` is not assignable to a `FilingRecordId` field) and the type-system separation is the point. Each alias declares its own `Annotated[str, StringConstraints(...)]` and any duplicated literal (`min_length=64, max_length=64, pattern=...`) is repeated deliberately as part of each alias identity contract.

### Rule 4 - naming and module pattern

Every typed-id alias is named `<Owner>Id` and lives in the owner package `_ids.py` module. Every `_ids.py` module exports its aliases through `__all__`. Cross-package consumers import the alias by name (`from aeat.<owner>._ids import <Owner>Id`); they do not import the underlying regex or length constants and they do not re-alias the type under a private name (`as _BucketId`). Inline constraint constants (`_HEX_INVOICE_ID_LENGTH`, `_HEX_TRANSACTION_ID_LENGTH`) are forbidden in modules outside the owning `_ids.py`.

### Rule 5 - `BucketId` home

`BucketId` moves to `core/identity/_bucket.py` and is re-exported by `core/identity/__init__.py`. Bucket identity is a per-profile storage-container identity owned by the persistence boundary, not by any record domain. The current placement in `domain/modelos/_ids.py` is the single instance of a sibling-domain import inversion this rule exists to eliminate. The constraint shape (`min_length=1, max_length=128`, stripped whitespace) is unchanged.

### Rule 6 - promotion verdicts for candidate identities

- `ProfileId`: **promote** to `core/identity/_profile.py`. UUIDv4 shape per `2026-05-21-profile-uuid-identity-adr`; consumed by adapters, persistence, application, and CLI. Clause (a) of Rule 1.
- `InvoiceId`: **promote** to `domain/invoices/_ids.py`. Hex-64 shape, minted by the invoice domain, consumed by `application.ledger` and `application.invoices`. Owner-domain placement under clause (a).
- `AttachmentId`: **promote** to `domain/attachments/_ids.py`. Hex-64 shape, minted by the attachment domain, consumed by `application.evidence` and `application.ledger`.
- `EvidenceId` / `BundleId`: **promote** to `application/evidence/_ids.py`. Hex-64 shape, minted in the evidence application service, with no domain-layer owner. The application layer is the lowest layer that owns the constraint.
- `SnapshotId`: **promote** to `core/identity/_snapshot.py`. Hex-64 shape on the live-snapshot, expedientes-snapshot, and notifications-snapshot surfaces - minted by application services but consumed by adapters and persistence with no single application-layer owner. Clause (a).
- `VerificationReportId`: **promote** to `domain/modelos/_ids.py`. Part of the modelo-record family by lifecycle and reference; same hex-64 shape as `FilingRecordId`. Owner-domain placement.
- `DecisionId`: **defer**. Only one consumer (`application/repair_integrity.py`); fails clause (a) of Rule 1 and carries no validator beyond hex-64. Promotion is permitted but not required by this ADR; if a second consumer appears, the alias is promoted under owner-domain placement (`application/integrity/_ids.py`).

### Rule 7 - sha-256 fingerprint fields stay primitive

Content-fingerprint fields (`sha256`, `payload_hash`, `ciphertext_hash`, `canonical_hash`, `storage_state_sha256`, `manifest_sha256`) are not record identities and remain bare `str = Field(min_length=64, max_length=64, pattern=...)`. The discriminator is referential: an identity is a value another record uses to point at this record; a fingerprint is a value derived from this record contents. Rule 1 does not apply to fingerprints.

### Rule 8 - registry private-regex import

The CLI consumer of the registry private `_CASILLA_RE` and `_REF_RE` constants is a type-system escape under the calculation-grounding rule and is forbidden. The CLI consumes the registry aliases (`CasillaId`, `RevisionId`, etc.) directly and lets pydantic enforce the shape at the model boundary. The registry package exposes no public regex surface; the aliases themselves are the public contract.

### Rule 9 - enforcement test

An import-direction test under `src/aeat/.../test_<name>.py` (the exact module location is a Plan-phase decision; the test participates in the CI gate per the roundtrip-discipline rule) parses every Python module under `src/aeat/` and fails when:

- a `domain.<a>` module imports a name from `domain.<b>._ids` for any `a != b` other than the registry-aliases exception in Rule 2;
- an adapter, application, or entrypoint module imports a private name (leading underscore) from any `_ids.py` module;
- an `_HEX_*_LENGTH` constant is declared in any module other than the owning `_ids.py`;
- a `*_id` field on a pydantic model uses bare `str` with only a length / pattern constraint when a typed alias for that identity exists.

The test existence is mandated by this ADR; its construction is a Plan-phase deliverable.

## Rationale

Rules 1 through 3 reconcile the two existing precedents under a single test. The security-precedent in `2026-05-13-identity-adr` is preserved as clause (b) of Rule 1: `SubjectTaxId` lives in `core/` because its constraint is a checksum, not a length. The owner-domain precedent established by the record-shape aliases is preserved as the default in Rule 1: an alias used only by its owner package stays there. The directional rule in Rule 2 closes the sibling-domain inversion the inventory surfaces and makes the existing `BucketId` placement the one ADR-mandated relocation.

Rule 4 naming convention follows the existing pattern across `domain/modelos/_ids.py`, `domain/calculations/registry/_ids.py`, and `domain/manuals/_ids.py`; no new convention is invented. The forbidden private re-alias pattern (`as _BucketId`) is the inventory shadow-declaration finding made structural.

Rule 5 `BucketId` relocation is the only existing alias that moves under this rule. Every other current alias either already lives at the lowest layer that owns its constraint shape (registry aliases, modelo-record aliases, `SubjectTaxId`) or is correctly package-private (`ManualId`, `ManualPart`).

Rule 6 promotion verdicts apply the same test to every candidate the inventory surfaces. The mixed verdicts - domain placement for `InvoiceId` / `AttachmentId` / `VerificationReportId`, core placement for `ProfileId` / `SnapshotId`, application placement for `EvidenceId` / `BundleId`, defer for `DecisionId` - demonstrate the rule discriminates rather than collapsing every identity to one home.

Rule 7 fingerprint exclusion prevents the rule from triggering on sha-256 hash fields, which carry the same hex-64 shape but are not identities. The referential test (does another record use this value to point at this record) is the discriminator and is mechanically checkable.

Rule 9 enforcement test makes the rule sharp enough that violations are detected at CI time rather than at review time. The four clauses cover the four structural failure modes the inventory surfaces: sibling-domain identity imports, private-constant escapes, duplicated shape constants, and bare-string shadow declarations.

## Alternatives considered

**Place every cross-domain identity in `core/identifiers/` (rejected for the record-shape aliases).** Would move `WorkUnitId`, `CalculationRevisionId`, `FilingRecordId`, `TransactionId`, `InvoiceId`, `AttachmentId`, and `VerificationReportId` out of the domain layer. Rejected: the architecture-boundaries rule keeps domain logic owned by the domain; pulling record-shape identities into `core/` would make `core/` aware of every record type the domain mints and would invert the dependency direction in the other direction. The security-precedent ADR explicitly notes that placing non-shared infrastructure under `core/` would muddy the `domain/` invariant; the same reasoning applies in reverse to record-shape aliases.

**Place every cross-domain identity in a new `domain/storage/_ids.py` (rejected for `BucketId`).** Would create a new domain package whose only content is identity aliases. Rejected: a domain package with no records, no services, and no validators is a directory, not an aggregate. The bucket identity is owned by the persistence boundary, not by a tax-domain record; `core/identity/` already exists as the established home for cross-cutting infrastructure identity and adding a parallel home would split the precedent.

**Leave `BucketId` in `domain/modelos/_ids.py` with a docstring justification (rejected).** Is the current state. Rejected: the docstring claim that the modelo boundary records reference both `BucketId` and `TransactionId` encodes a current-project assumption rather than a stable owner rule, which the source-hygiene rule forbids. The sibling-domain imports the placement requires are the structural evidence the owner-rule the docstring asserts is wrong.

**Compose every identity from a shared `Hex256Digest` primitive (rejected for the record aliases).** Would replace the repeated `min_length=64, max_length=64, pattern=...` literal across the five hex-64 aliases with a single shape primitive. Rejected: the four record aliases carry distinct semantic roles and pydantic nominal typing on `Annotated[str, ...]` aliases is the only mechanism that keeps a `WorkUnitId` un-assignable to a `FilingRecordId` field. Composition would re-introduce the structural-string-equality collapse the separate aliases exist to prevent.

**Expose a public regex surface from the registry package (rejected for the `_CASILLA_RE` import).** Would re-export `_CASILLA_RE` and `_REF_RE` as a public API so the CLI consumer becomes legal. Rejected: the calculation-grounding rule treats raw regex constants as type-system escapes; the public contract of the registry identities is the alias types, not their internal regex. The CLI consumes the aliases directly under Rule 8 and pydantic enforces the shape.

## Consequences

### Aliases that must move

- `BucketId` moves from `domain/modelos/_ids.py` to `core/identity/_bucket.py`, re-exported through `core/identity/__init__.py` `__all__`. Every current importer (`domain.transactions._models`, `domain.transactions._repository`, `domain.invoices._models`, `domain.attachments._models`, `adapters.persistence.storage.bucket._layout`, `adapters.persistence.storage.bucket._export_header`, `entrypoints.cli._review_payloads`, `entrypoints.cli._modelo_payloads`, and the application services enumerated in the inventory) updates its import path.
- `TransactionId` stays in `domain/modelos/_ids.py` only if filing records continue to reference transactions directly; otherwise it moves to `domain/transactions/_ids.py` under owner-domain placement.

### Bare-string families that must promote

- `profile_id` (eighteen sites in `application/user_profile/__init__.py` alone, plus `application/user_profile/_censo_sync.py`, `application/state_projection.py`, `core/_bucket_pointer.py`, `core/config.py`, `adapters/persistence/storage/runtime.py`, `adapters/persistence/storage/runtime_repository.py`) promotes to the new `ProfileId` alias in `core/identity/_profile.py`.
- `invoice_id` (the inline-`_HEX_INVOICE_ID_LENGTH` declarations in `domain/invoices/_models.py` and the bare-string field sites) promotes to the new `InvoiceId` alias in `domain/invoices/_ids.py`.
- `attachment_id` (the bare-string fields at `domain/attachments/_models.py:107,111`) promotes to the new `AttachmentId` alias in `domain/attachments/_ids.py`.
- `bundle_id` (`application/evidence/_models.py:81`, `application/evidence/_service.py:52`) promotes to the new `BundleId` alias in `application/evidence/_ids.py`.
- `snapshot_id` (`application/live/_notifications.py:73`, `application/live/_expedientes.py:71`, and the censo-sync declarations) promotes to the new `SnapshotId` alias in `core/identity/_snapshot.py`.
- `verification_report_id` (`entrypoints/cli/_modelo_payloads.py:110,332,430` and `application/modelo/_actions.py:3640`) promotes to a new `VerificationReportId` alias in `domain/modelos/_ids.py`.
- `casilla_id`, `formula_id`, `revision_id`, `modelo_id` at the fifty-nine bare-string sites across thirty-six files (notably `entrypoints/cli/_modelo_payloads.py`, the registry validators, `domain/filing/_schema.py`, and `_record_design.py`) promote to the existing registry aliases under Rule 8.

### Shadow declarations that must collapse

- `_HEX_TRANSACTION_ID_LENGTH = 64` at `domain/invoices/_service.py:34` and `domain/invoices/_models.py:44` is deleted; the affected fields consume `TransactionId` directly.
- `_HEX_INVOICE_ID_LENGTH = 64` at `domain/invoices/_models.py:45,322` is deleted; the affected fields consume the new `InvoiceId` alias.
- `_HEX_WORK_UNIT_ID_LENGTH = 64` at `domain/modelos/_work_unit.py:73` is deleted; the affected field consumes `WorkUnitId` directly.
- The inline hex-64 pattern at `application/repair_integrity.py:335` is deleted; the field consumes either a promoted `DecisionId` alias if Rule 6 defer verdict is revisited, or stays as a fingerprint-style declaration under Rule 7 if the value is reclassified as a content hash.
- The repeated hex-64 `Field(...)` at `application/user_profile/__init__.py:254,266,267` for `canonical_hash`, `stored_hash`, `current_hash` is retained under Rule 7 (these are content fingerprints, not identities) but factored to a single module-local shape constant to remove the three-way duplication.
- The repeated hex-64 pattern at `core/corpus_manifest/__init__.py:64,114` is retained under Rule 7 and factored the same way.
- The private re-alias blocks at `domain/modelos/_work_unit.py:77-78`, `domain/modelos/_filing_record.py:39-42`, and `domain/modelos/_calculation_revision.py:81-82` are deleted; the modules consume the aliases under their public names.
- The CLI import of `_CASILLA_RE` and `_REF_RE` at `entrypoints/cli/_modelo.py:57` is deleted under Rule 8; the CLI payload models consume the registry aliases.
- The permissive `casilla_id` declaration in the outbound AEAT sede schema at `adapters/outbound/aeat/sede/_schema.py:189` consumes `CasillaId` under Rule 8, tightening the field to the registry pattern.

### Enforcement test that must exist

The import-direction test under Rule 9 lands as a Plan deliverable and participates in the CI gate. Its absence is itself a violation of this ADR.

## References

- `2026-05-30-identity-primitives-reference` - inventory of typed-id aliases, bare-string survivors, and cross-domain identity imports that this ADR resolves.
- `2026-05-13-identity-adr` - security-primitive placement precedent in `core/identity/`.
- `2026-05-20-registry-casilla-identity-adr` - registry-owned identity space precedent.
- `2026-05-21-profile-uuid-identity-adr` - profile UUIDv4 identity semantic, the basis for promoting `ProfileId`.
- `2026-05-22-schema-hardening-adr` - strict-pydantic boundary discipline that the bare-string-identity prohibition extends.
- `2026-05-22-secure-storage-production-hardening-architecture-adr` - secure-storage architecture context for `BucketId` as a persistence-boundary identity.
- `2026-05-20-registry-authority-flow-adr` - registry pipeline boundary that the Rule 2 registry-aliases exception preserves.
