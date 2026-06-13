---
tags:
  - '#reference'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - "[[2026-05-13-identity-adr]]"
  - "[[2026-05-20-registry-casilla-identity-adr]]"
  - "[[2026-05-21-profile-uuid-identity-adr]]"
  - "[[2026-05-22-schema-hardening-adr]]"
  - "[[2026-05-22-secure-storage-production-hardening-architecture-adr]]"
---

# identity-primitives reference: inventory of typed-id aliases, bare-string survivors, and cross-domain identity imports

Read-only audit of identity primitives across src/aeat/ (~1.6k Python files). Scope: every Annotated[str, ...] alias that pins an identity shape; every bare str = Field(min_length=..., max_length=...) declaration on an id-suffix field; every cross-package import of an identity alias; every shadow declaration of the same logical identity.

Discovery used ripgrep over the full tree; counts are total occurrences, not samples. The reference surfaces facts and open questions only; it does not propose answers.

## Findings

### 1. Inventory tables - typed-id aliases in production code

#### 1a. Hex-64 content-addressed identities

Owner package: src/aeat/domain/modelos/_ids.py.

- WorkUnitId (line 29): StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=^[0-9a-f]{64}$). Owner: modelo records. Consumers: low single-digit alias-import sites; domain/modelos, application/ledger, application/modelo, entrypoints/cli/_modelo_payloads.
- CalculationRevisionId (line 35): identical hex-64. Owner: modelo records. Same footprint as WorkUnitId.
- FilingRecordId (line 41): identical hex-64. Owner: modelo records. Consumers: domain/modelos/_filing_record, application/evidence/_models.
- TransactionId (line 47): identical hex-64. Owner: ledger transactions (declared inside modelos). Consumers: domain/transactions/_models, application/ledger/_models.
- BucketId (line 53): StringConstraints(strip_whitespace=True, min_length=1, max_length=128) - not hex-64. Owner: storage / persistence bucket. Consumers: 30+ alias-import sites across application/{ledger,live,modelo,auth,aggregation,setup,wizard,workflow,review,evidence,filing,storage/calc_sheets}, domain/{transactions,invoices,attachments}, adapters/persistence/storage/bucket, entrypoints/cli.

#### 1b. Registry-id family (kebab-ref shape)

Owner package: src/aeat/domain/calculations/registry/_ids.py. Declared as type aliases using Field(min_length=1, max_length=128, pattern=_REF_RE) or max_length=64/160 variants. _REF_RE is ^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$. CasillaId uses _CASILLA_RE = ^[A-Za-z0-9][A-Za-z0-9._:-]*$.

- ModeloId (line 14, max 3): _validate_*, _record_design, _loader, application/storage/calc_sheets, application/filing/runtime, entrypoints/cli/_modelo_payloads.
- RevisionId (line 15, max 128): registry internals + application/storage/calc_sheets.
- CasillaId (line 16, max 64): adapters/inbound/pdf/_shared, adapters/outbound/google/_calc_sheets_pull, application/storage/calc_sheets/*, application/filing/runtime, registry internals.
- FormulaId (line 17, max 128): application/filing/runtime.
- ParameterId (line 18, max 128): application/storage/calc_sheets/*.
- BindingId (line 19, max 128): adapters/outbound/google/_calc_sheets_pull, application/storage/calc_sheets/*.
- RelationId (line 20, max 128): adapters/outbound/google/_calc_sheets_pull, application/storage/calc_sheets/*.
- LegalRefId (line 21, max 160): application/filing/runtime.
- SourceRefId (line 22, max 160): application/filing/runtime.
- ExtractionProfileId .. OracleId (lines 23-36, max 128/160): registry-internal only.

#### 1c. Spanish-tax-identifier alias

- SubjectTaxId (src/aeat/core/identity/__init__.py:56): Annotated[str, AfterValidator(_subject_tax_id_validator)] running NIF/NIE/CIF mod-23 checksum. Owner: core/identity (security primitive). Direct alias consumer: domain/filing/_schema.py:20. The helper validate_spanish_tax_id is more widely imported by adapters/inbound/identity, adapters/inbound/sanitizer/_records, domain/invoices/_models, application/wizard/_widgets, adapters/persistence/storage/master_key/_master_key (lazy function-local).

#### 1d. Enum-shaped identities

- ManualId (src/aeat/domain/manuals/_ids.py:12): closed StrEnum (renta, iva, sociedades). Owner: manuals.
- ManualPart (src/aeat/domain/manuals/_ids.py:20): closed StrEnum. Owner: manuals.
- IdentityDocument (src/aeat/core/identity/_documents.py, re-exported via __init__): closed StrEnum (NIF/NIE/CIF). Owner: core/identity.

#### 1e. Module-local typed strings (not identity surface)

- _DisplayName (src/aeat/domain/user_profile/_values.py:44): StringConstraints(strip_whitespace=True, min_length=1, max_length=160). Profile display label, private.
- _Source (src/aeat/domain/user_profile/_values.py:45): StringConstraints(min_length=1, max_length=80). Profile attribution, private.
- _NifStr (src/aeat/domain/modelos/_row_models.py:39): StringConstraints(strip_whitespace=True, min_length=1, max_length=20). Row-level NIF, no checksum.
- _NameStr (src/aeat/domain/modelos/_row_models.py:40): StringConstraints(strip_whitespace=True, max_length=200). Row-level name.
- _IsoCountryCode (src/aeat/domain/modelos/_row_models.py:41): StringConstraints(strip_whitespace=True, min_length=2, max_length=2). 2-letter country.
- _NonEmptyStr (src/aeat/adapters/inbound/sanitizer/_records.py:78): StringConstraints(min_length=1, strip_whitespace=False). Sanitizer record.

Listed so an ADR sweep does not mis-promote them; intentionally private value-types, not identity aliases.

### 2. Cross-domain import map

Notation: A -> B means package A imports an identity type from package B.

#### From domain.modelos._ids

- domain.transactions._repository -> domain.modelos._ids (BucketId)
- domain.transactions._models -> domain.modelos._ids (BucketId, TransactionId)
- domain.invoices._models -> domain.modelos._ids (BucketId)
- domain.attachments._models -> domain.modelos._ids (BucketId)
- domain.modelos._work_unit -> _ids intra-package, with 'as _BucketId' shadow
- domain.modelos._filing_record -> _ids intra-package, four 'as _*' shadows
- domain.modelos._calculation_revision -> _ids intra-package, two 'as _*' shadows
- application/* (ledger, live, modelo, auth, aggregation, setup, wizard, workflow, review, evidence, filing, storage/calc_sheets) -> domain.modelos._ids
- adapters.persistence.storage.bucket._layout -> domain.modelos._ids (BucketId)
- adapters.persistence.storage.bucket._export_header -> domain.modelos._ids (BucketId)
- entrypoints.cli._review_payloads, entrypoints.cli._modelo_payloads -> domain.modelos._ids

domain.transactions, domain.invoices, domain.attachments, and the adapters.persistence.storage.bucket layer all reach into domain.modelos._ids for BucketId (and for transactions also TransactionId). The docstring in _ids.py justifies this with "BucketId and TransactionId are declared here because the modelo boundary records reference both". Whether this is the correct direction, or whether BucketId belongs in core/ or a new domain/storage/ with modelo importing from there, is the central open question.

#### From domain.calculations.registry._ids

- adapters.inbound.pdf._shared -> registry._ids (CasillaId)
- adapters.outbound.google._calc_sheets_pull -> registry._ids (BindingId, CasillaId, RelationId)
- application.storage.calc_sheets._translator/_records/_parity_harness/_layout -> registry._ids
- application.filing.runtime -> registry._ids (CasillaId, FormulaId, LegalRefId, SourceRefId)
- entrypoints.cli._modelo:57 -> registry._ids; imports PRIVATE regex constants _CASILLA_RE, _REF_RE (type-system escape)
- registry-internal: _export, _parity_tapes, _schema

#### From core.identity

Consumed by adapters.inbound.identity (re-export), adapters.inbound.sanitizer._records, domain.invoices._models, application.wizard._widgets, adapters.persistence.storage.master_key._master_key (lazy function-local), domain.filing._schema (SubjectTaxId).

#### From domain.manuals._ids

domain.manuals._schema and domain.manuals._rule_id only. Package-private in practice.

### 3. Bare-string survivors

Sites where the logical identity exists but the typed alias is not used.

#### 3a. Constraint-on-bare-str (Field(min_length=64, max_length=64))

55+ occurrences across the codebase. Sha-256 fields (content fingerprints, not record identities) dominate; the following id-suffix fields match the hex-64 shape and stay bare-str:

- src/aeat/application/evidence/_models.py:81 bundle_id
- src/aeat/application/evidence/_service.py:52 bundle_id
- src/aeat/application/ledger/_models.py:427,431,440,446,455,552,570,784,790 (split_group_id, bucket_event_id, import_batch_id, transaction_id, id, export_id, sha256)
- src/aeat/application/ledger/_evidence.py:63 source_sha256
- src/aeat/application/live/_verify.py:66 observation_id
- src/aeat/application/live/_notifications.py:73 snapshot_id
- src/aeat/application/live/_expedientes.py:71 snapshot_id
- src/aeat/application/repair_integrity.py:335 decision_id (explicit hex-64 pattern shadows alias shape)
- src/aeat/domain/transactions/_models.py:458,489,522,585 (bucket_event_id, split_group_id)
- src/aeat/domain/transactions/_raw_transaction.py:65 source_sha256
- src/aeat/domain/attachments/_models.py:107,111 (attachment_id, sha256)
- src/aeat/adapters/persistence/storage/sql/secure_objects.py:102,148-152 (expected_revision_id, revision_id, previous_revision_id, previous_payload_hash, payload_hash, ciphertext_hash)
- src/aeat/adapters/persistence/storage/sql/records.py:98 sha256
- src/aeat/adapters/persistence/storage/secret_store/_secret_store.py:126,127 (digest_hex, blob_sha256_plaintext_hex)
- src/aeat/adapters/persistence/storage/blob_store/_blob_store.py:100,123 sha256_plaintext_hex
- src/aeat/adapters/outbound/storage/_records.py:86,90-92,105,117 (object_key_hmac, ciphertext_hash, storage_revision_id, previous_storage_revision_id, latest_revision_id)
- src/aeat/adapters/outbound/aeat/auth/_clave_movil.py:176, _authenticator.py:251 storage_state_sha256
- src/aeat/application/export/_tabular.py:35 sha256
- src/aeat/application/user_profile/__init__.py:254,266,267 (canonical_hash, stored_hash, current_hash; three shadow declarations)
- src/aeat/core/corpus_manifest/__init__.py:64,114 (sha256, manifest_sha256; with explicit pattern)

Sha-256 fields are content hashes, not identity references, and may legitimately stay primitive. The placement question separates record-identity from payload-fingerprint.

#### 3b. Unconstrained bare-str id parameters/fields

Over 1014 occurrences of bare-str id-suffix declarations across 287 files; majority are function parameters (CLI signatures, repository methods, action handlers) rather than pydantic fields. Hot spots:

- src/aeat/application/ledger/_actions.py: 62 occurrences (bare-str bucket_id, transaction_id, attachment_id, object_id).
- src/aeat/application/modelo/_actions.py: 33 occurrences (bucket_id, work_unit_id, calculation_revision_id, filing_record_id, verification_report_id).
- src/aeat/entrypoints/cli/_ledger.py: 48 occurrences (typer arguments).
- src/aeat/application/user_profile/__init__.py: 18 occurrences of profile_id: str = Field(min_length=1, max_length=96) (no alias).
- src/aeat/application/user_profile/_censo_sync.py: 13 occurrences of profile_id / snapshot_id as bare str with Field(min_length=1).
- src/aeat/application/state_projection.py:528,538,540: revision_id and profile_id as bare-str with inline Field.
- src/aeat/core/_bucket_pointer.py:30: bucket_id: str = Field(min_length=1).
- src/aeat/core/config.py:113: bucket_id: str.
- src/aeat/adapters/persistence/storage/runtime.py:95,306, runtime_repository.py:33: bucket_id: str.

profile_id is the largest bare-str identity surface lacking a typed alias. The profile-UUID identity ADR decided the semantic but no ProfileId alias was declared. verification_report_id (_modelo_payloads.py:110,332,430 and _actions.py:3640) is bare-str despite being part of the modelo-record family.

#### 3c. Registry-family bare-string survivors

casilla_id: str / formula_id: str / revision_id: str / modelo_id: str appear unconstrained in 36 files (59 occurrences), particularly in CLI payloads (_modelo_payloads.py: 15), registry validators (_validate_*.py), filing schemas (domain/filing/_schema.py: 4), and _record_design.py. These shadow the typed CasillaId, FormulaId, RevisionId, ModeloId aliases declared and imported elsewhere.

### 4. Shadow declarations

Independent redeclarations of the same logical identity with a different name or local constant:

- Hex-64 transaction id at src/aeat/domain/invoices/_service.py:34: constant _HEX_TRANSACTION_ID_LENGTH = 64; field uses local constant rather than importing TransactionId.
- Hex-64 transaction id duplicate constant at src/aeat/domain/invoices/_models.py:44.
- Hex-64 invoice id at src/aeat/domain/invoices/_models.py:45,322: constant _HEX_INVOICE_ID_LENGTH = 64; field declared inline. No shared InvoiceId alias exists.
- Hex-64 work-unit id at src/aeat/domain/modelos/_work_unit.py:73: constant _HEX_WORK_UNIT_ID_LENGTH = 64 duplicates alias shape.
- Hex-64 decision id at src/aeat/application/repair_integrity.py:335: inline Field with explicit hex-64 pattern and no shared alias.
- Hex-64 sha-256 profile lifecycle at src/aeat/application/user_profile/__init__.py:254,266,267: identical Field repeated three times for canonical_hash, stored_hash, current_hash.
- Hex-64 corpus manifest at src/aeat/core/corpus_manifest/__init__.py:64,114: same inline pattern repeated.
- casilla_id for outbound AEAT sede at src/aeat/adapters/outbound/aeat/sede/_schema.py:189: field pattern is permissive vs _CASILLA_RE and field does not import CasillaId.
- CLI consumer of registry private constants at src/aeat/entrypoints/cli/_modelo.py:57: imports private regex constants _CASILLA_RE, _REF_RE rather than aliases.
- Private re-alias inside domain/modelos at _work_unit.py:77-78, _filing_record.py:39-42, _calculation_revision.py:81-82: private re-aliasing of identity types inside the same package.

### 5. Placement-question summary

Open questions an ADR must resolve. Phrased as choice surfaces, not answers:

1. BucketId home: core/, a new domain/storage/, or remain in domain/modelos/_ids.py? Every other domain (transactions, invoices, attachments) imports it from modelos, an inverted dependency relative to a hexagonal reading where bucket-identity is a persistence-boundary concept upstream of any single record domain.

2. TransactionId home: same shape question. Declared in domain/modelos/_ids.py, consumed by domain/transactions. Should the alias travel with the lifecycle-owner package, or stay in modelos because filing records reference transactions?

3. profile_id typing: the profile-UUID identity ADR declared the semantic but no ProfileId alias exists. 18+ sites declare profile_id: str = Field(min_length=1, max_length=96) independently. Add a typed alias, and place it where?

4. InvoiceId does not exist: _HEX_INVOICE_ID_LENGTH = 64 and bare-str invoice_id fields appear in domain/invoices, application/invoices, application/ledger, CLI. Logical identity is hex-64 same as TransactionId; no alias promoted.

5. SnapshotId, BundleId, EvidenceId, AttachmentId, VerificationReportId, ExportId, SplitGroupId, BucketEventId, ObservationId, DraftId, DecisionId, ImportBatchId, ObjectId, ItemId: all carry hex-64 or min-length-1 shapes inline as bare-str Field. None has a shared alias. The ADR must enumerate which deserve promotion and which legitimately stay primitive at the boundary they appear on.

6. Registry-id alias surface: _ids.py declares 22 aliases yet registry-internal validators and CLI payloads still use bare casilla_id: str / formula_id: str / revision_id: str (59 sites, 36 files). Is the rule every registry id field uses the alias, or registry ids stay bare-str inside the registry package and only cross-package boundary records use aliases?

7. CLI private regex import: _modelo.py:57 imports _CASILLA_RE and _REF_RE (private). Expose a public regex/pattern surface, or require the CLI to consume the aliases themselves and let pydantic enforce the shape?

8. SubjectTaxId vs BucketId placement principle: SubjectTaxId lives in core/identity/ on security grounds (per the identity ADR); BucketId lives in domain/modelos/_ids.py on locality grounds. Both are string identities consumed across multiple domains. Reconcile the two principles or accept both and define the discriminator (security-relevant vs record-shape).

9. Shadow-constant policy: _HEX_WORK_UNIT_ID_LENGTH, _HEX_TRANSACTION_ID_LENGTH, _HEX_INVOICE_ID_LENGTH, and the inline hex-64 pattern literal exist in seven+ modules. Expose hex-64 shape as a single shared Hex256Digest value-type with identity aliases composed on top, or let each identity declare its full constraint independently?

10. Cross-domain import inversion: domain.transactions, domain.invoices, domain.attachments import identity types from domain.modelos. The architecture-boundaries rule speaks to domain-to-adapter, not domain-to-domain. Is modelos the apex aggregate (every other domain depends on it for cross-aggregate identities) or peer to the others (shared identities must live above all of them, e.g. core/identifiers/)?

### 6. Existing rule and ADR citations

Architecture rules that constrain the answer:

- aeat-architecture-boundaries: Expose validated boundary data through pydantic v2 models; do not expose bare dict for persisted records, wire payloads, configuration, CLI input. Identity strings are part of the boundary contract; bare-str id fields with only a length constraint are arguably the string analogue of the dict bare-mapping pattern the rule forbids.
- aeat-architecture-boundaries: Preserve the accepted hexagonal direction; keep domain logic independent from adapters. Silent on domain-to-domain; the inversion question (BucketId in modelos) sits in the silence.
- aeat-architecture-boundaries: Do not introduce shims, compatibility layers, deprecation paths, or duplicate legacy APIs. Private re-aliases and duplicated _HEX_*_LENGTH constants are duplicate-shape declarations that arguably fall under this clause.
- aeat-calculation-grounding: Persist typed envelopes, not flat scalar mappings. Treating identity strings as primitive str at boundary surfaces is the scalar analogue.
- aeat-calculation-grounding: Treat type-system escapes as boundary leaks. The CLI import of private regex constants is a type-system escape under this clause.
- aeat-source-hygiene: Use domain names that remain true after the current project plan changes. The docstring on BucketId encodes a current-project assumption rather than a stable owner rule.
- aeat-registry-authority-flow: positions domain.calculations.registry as a deterministic pipeline. Registry-id aliases are part of the validated authority surface; bare-str registry-id fields in validators and CLI payloads are downstream consumers operating outside the typed-alias contract.

Existing ADRs that touch identity placement:

- `2026-05-13-identity-adr`: decided core/identity/ placement for Spanish tax-id validation as a security primitive. Establishes the security-relevant cross-cutting primitive belongs in core/ precedent. Does not speak to record-shape identities.
- `2026-05-20-registry-casilla-identity-adr`: decided segment-scoped casilla identity inside the registry. Establishes the registry owns its identity space precedent.
- `2026-05-21-profile-uuid-identity-adr`: decided profile identity is a generated UUID, decoupled from display name. Establishes the semantic but does not declare a ProfileId alias.
- `2026-05-22-schema-hardening-adr`: schema-hardening campaign context; promoted many sites from bare-str to typed aliases.
- `2026-05-22-secure-storage-production-hardening-architecture-adr`: secure-storage architecture; consumes BucketId extensively in the persistence layer.
