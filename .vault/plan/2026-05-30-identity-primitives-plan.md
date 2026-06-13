---
tags:
  - '#plan'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
tier: L3
related:
  - '[[2026-05-30-identity-primitives-adr]]'
  - '[[2026-05-30-identity-primitives-reference]]'
  - '[[2026-05-13-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-21-profile-uuid-identity-adr]]'
  - '[[2026-05-22-schema-hardening-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-20-registry-authority-flow-adr]]'
  - '[[2026-06-04-identity-primitives-research]]'
---


# `identity-primitives` placement rollout plan

## Wave `W01` - relocate BucketId to core/identity

Move the BucketId alias out of the modelo records package into core/identity per Rule 5, update every consumer import path enumerated in the ADR Consequences, and delete the prior declaration. This Wave establishes the precondition for the Wave 5 enforcement test sibling-domain clause. Authorised by the identity-primitives ADR and grounded in the identity-primitives reference.

### Phase `W01.P01` - carve core/identity/_bucket.py

Create the new BucketId module under core/identity, re-export through the core/identity package __init__, and verify import resolution before any consumer migrates. This Phase delivers the new declaration without removing the old one so the codebase stays green during the consumer-import sweep.

- [x] `W01.P01.S01` - create the BucketId alias module per ADR Rule 5 with the StringConstraints(strip_whitespace=True, min_length=1, max_length=128) shape and an __all__ export; `src/aeat/core/identity/_bucket.py`.
- [x] `W01.P01.S02` - re-export BucketId through the core.identity package __all__ per ADR Rule 4 so downstream consumers import it under from aeat.core.identity import BucketId; `src/aeat/core/identity/__init__.py`.
- [x] `W01.P01.S03` - add a real-behavior unit test that constructs a BucketId from a valid value, rejects an empty value, rejects a value longer than 128 characters, and asserts strip_whitespace is applied; `src/aeat/core/identity/test_bucket.py`.

### Phase `W01.P02` - migrate BucketId consumers to core/identity import path

Update every consumer import path enumerated in the ADR Consequences section on aliases that must move, so domain.transactions, domain.invoices, domain.attachments, adapters.persistence.storage.bucket, application services, and CLI payload modules all import BucketId from core.identity rather than from domain.modelos. Steps run sequentially to keep the test suite green between consumer migrations.

- [x] `W01.P02.S04` - switch the BucketId import to from aeat.core.identity import BucketId per ADR Rule 2 and verify the transactions repository test module passes; `src/aeat/domain/transactions/_repository.py`.
- [x] `W01.P02.S05` - switch the BucketId import to from aeat.core.identity import BucketId per ADR Rule 2 and verify the transactions models test module passes; `src/aeat/domain/transactions/_models.py`.
- [x] `W01.P02.S06` - switch the BucketId import to from aeat.core.identity import BucketId per ADR Rule 2 and verify the invoices models test module passes; `src/aeat/domain/invoices/_models.py`.
- [x] `W01.P02.S07` - switch the BucketId import to from aeat.core.identity import BucketId per ADR Rule 2 and verify the attachments models test module passes; `src/aeat/domain/attachments/_models.py`.
- [x] `W01.P02.S08` - switch the BucketId import to from aeat.core.identity import BucketId per ADR Rule 2 and verify the bucket layout test module passes; `src/aeat/adapters/persistence/storage/bucket/_layout.py`.
- [x] `W01.P02.S09` - switch the BucketId import to from aeat.core.identity import BucketId per ADR Rule 2 and verify the bucket export-header test module passes; `src/aeat/adapters/persistence/storage/bucket/_export_header.py`.
- [x] `W01.P02.S10` - switch the BucketId import to from aeat.core.identity import BucketId per ADR Rule 2 and verify the CLI review payloads test module passes; `src/aeat/entrypoints/cli/_review_payloads.py`.
- [x] `W01.P02.S11` - switch the BucketId import to from aeat.core.identity import BucketId per ADR Rule 2 and verify the CLI modelo payloads test module passes; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W01.P02.S12` - switch every BucketId import across the application services (ledger, live, modelo, auth, aggregation, setup, wizard, workflow, review, evidence, filing, storage/calc_sheets) to from aeat.core.identity import BucketId per ADR Rule 2 and verify the application test suite passes sequentially; `src/aeat/application/`.

### Phase `W01.P03` - delete BucketId declaration from domain/modelos/_ids.py

Remove the BucketId alias declaration and its __all__ entry from the modelo records identity module after every consumer has migrated. This Phase closes Wave 1 and removes the sibling-domain inversion the ADR exists to eliminate.

- [x] `W01.P03.S13` - delete the BucketId alias declaration and its __all__ entry per ADR Rule 5 and confirm with ripgrep that no aeat module other than core.identity declares the name; `src/aeat/domain/modelos/_ids.py`.
- [x] `W01.P03.S14` - run the full pytest suite sequentially and confirm no consumer regressed across the BucketId relocation; `src/aeat/`.

## Wave `W02` - promote new typed-id aliases per Rule 6

Promote the six new aliases the ADR Rule 6 approves: ProfileId, SnapshotId, InvoiceId, AttachmentId, BundleId/EvidenceId pair, and VerificationReportId. Each Phase declares one alias in its owner module, re-exports through __all__, migrates every bare-string consumer site enumerated in the ADR Consequences bare-string families section, and pairs a real-behavior roundtrip test exercising the typed constraint. DecisionId is deferred per Rule 6 and is out of scope. Phases in this Wave are independent and may be executed in parallel by separate executors.

### Phase `W02.P04` - promote ProfileId in core/identity/_profile.py

Declare the UUIDv4 ProfileId alias in core/identity per Rule 1 clause (a) and Rule 6, re-export through core/identity, and lift the eighteen bare-string profile_id field sites in application/user_profile, application/state_projection, core/_bucket_pointer, core/config, and adapters/persistence/storage/runtime onto the typed alias.

- [x] `W02.P04.S15` - declare the ProfileId alias with the UUIDv4 constraint shape established by the profile-uuid identity ADR and an __all__ export per ADR Rule 6; `src/aeat/core/identity/_profile.py`.
- [x] `W02.P04.S16` - re-export ProfileId through the core.identity package __all__ per ADR Rule 4; `src/aeat/core/identity/__init__.py`.
- [x] `W02.P04.S17` - lift the eighteen bare-string profile_id field declarations onto ProfileId per ADR Rule 6 and confirm pydantic shape enforcement at construction; `src/aeat/application/user_profile/__init__.py`.
- [x] `W02.P04.S18` - lift the profile_id bare-string declarations onto ProfileId per ADR Rule 6 across the censo-sync and state-projection modules and the bucket-pointer and config modules under core; `src/aeat/application/user_profile/_censo_sync.py`.
- [x] `W02.P04.S19` - lift the profile_id bare-string declaration onto ProfileId per ADR Rule 6 in the state-projection module; `src/aeat/application/state_projection.py`.
- [x] `W02.P04.S20` - lift the profile_id bare-string declaration onto ProfileId per ADR Rule 6 in the bucket-pointer module; `src/aeat/core/_bucket_pointer.py`.
- [x] `W02.P04.S21` - lift the profile_id bare-string declaration onto ProfileId per ADR Rule 6 in the settings module; `src/aeat/core/config.py`.
- [x] `W02.P04.S22` - lift the profile_id bare-string declarations onto ProfileId per ADR Rule 6 across the storage runtime and runtime-repository modules; `src/aeat/adapters/persistence/storage/runtime.py`.
- [x] `W02.P04.S23` - add a real-behavior roundtrip test that populates a UserProfile with a non-default ProfileId, persists through the real SecureObjectRepository against the real SQLite engine, reloads, and asserts strict pydantic equality across the boundary; `src/aeat/application/user_profile/test_profile_roundtrip.py`.

### Phase `W02.P05` - promote SnapshotId in core/identity/_snapshot.py

Declare the hex-64 SnapshotId alias in core/identity per Rule 1 clause (a) and Rule 6, re-export, and lift the bare-string snapshot_id field sites in application/live/_notifications, application/live/_expedientes, and application/user_profile/_censo_sync onto the alias.

- [x] `W02.P05.S24` - declare the SnapshotId alias with the hex-64 StringConstraints shape and an __all__ export per ADR Rule 6 clause (a); `src/aeat/core/identity/_snapshot.py`.
- [x] `W02.P05.S25` - re-export SnapshotId through the core.identity package __all__ per ADR Rule 4; `src/aeat/core/identity/__init__.py`.
- [x] `W02.P05.S26` - lift the snapshot_id bare-string field onto SnapshotId per ADR Rule 6 in the live notifications surface; `src/aeat/application/live/_notifications.py`.
- [x] `W02.P05.S27` - lift the snapshot_id bare-string field onto SnapshotId per ADR Rule 6 in the live expedientes surface; `src/aeat/application/live/_expedientes.py`.
- [x] `W02.P05.S28` - lift the snapshot_id bare-string declarations onto SnapshotId per ADR Rule 6 in the censo-sync surface; `src/aeat/application/user_profile/_censo_sync.py`.
- [x] `W02.P05.S29` - add a real-behavior roundtrip test that populates a snapshot record with a non-default SnapshotId, persists through the real adapter, reloads, and asserts strict pydantic equality; `src/aeat/application/live/test_snapshot_roundtrip.py`.

### Phase `W02.P06` - promote InvoiceId in domain/invoices/_ids.py

Declare the hex-64 InvoiceId alias in the invoice domain identity module per Rule 6 owner-domain placement, re-export, and lift the bare-string invoice_id field sites in domain/invoices/_models, application/ledger, and application/invoices onto the alias.

- [x] `W02.P06.S30` - declare the InvoiceId alias with the hex-64 StringConstraints shape and an __all__ export per ADR Rule 6 owner-domain placement; `src/aeat/domain/invoices/_ids.py`.
- [x] `W02.P06.S31` - lift the invoice_id bare-string field declarations onto InvoiceId per ADR Rule 6 in the invoice records module; `src/aeat/domain/invoices/_models.py`.
- [x] `W02.P06.S32` - lift the invoice_id bare-string field declarations onto InvoiceId per ADR Rule 6 across the ledger application service; `src/aeat/application/ledger/_models.py`.
- [x] `W02.P06.S33` - add a real-behavior roundtrip test that populates an invoice record with a non-default InvoiceId, persists through the real SecureObjectRepository, reloads, and asserts strict pydantic equality; `src/aeat/domain/invoices/test_invoice_roundtrip.py`.

### Phase `W02.P07` - promote AttachmentId in domain/attachments/_ids.py

Declare the hex-64 AttachmentId alias in the attachment domain identity module per Rule 6 owner-domain placement, re-export, and lift the bare-string attachment_id field sites in domain/attachments/_models, application/evidence, and application/ledger onto the alias.

- [x] `W02.P07.S34` - declare the AttachmentId alias with the hex-64 StringConstraints shape and an __all__ export per ADR Rule 6 owner-domain placement; `src/aeat/domain/attachments/_ids.py`.
- [x] `W02.P07.S35` - lift the attachment_id bare-string field declaration onto AttachmentId per ADR Rule 6 in the attachment records module; `src/aeat/domain/attachments/_models.py`.
- [x] `W02.P07.S36` - lift the attachment_id bare-string field declarations onto AttachmentId per ADR Rule 6 across the evidence application service; `src/aeat/application/evidence/_models.py`.
- [x] `W02.P07.S37` - lift the attachment_id bare-string field declarations onto AttachmentId per ADR Rule 6 across the ledger application service; `src/aeat/application/ledger/_models.py`.
- [x] `W02.P07.S38` - add a real-behavior roundtrip test that populates an attachment record with a non-default AttachmentId, persists through the real adapter, reloads, and asserts strict pydantic equality; `src/aeat/domain/attachments/test_attachment_roundtrip.py`.

### Phase `W02.P08` - promote BundleId and EvidenceId in application/evidence/_ids.py

Declare the hex-64 BundleId and EvidenceId aliases in the evidence application service identity module per Rule 6 application-layer placement, re-export, and lift the bare-string bundle_id and evidence_id field sites in application/evidence/_models, application/evidence/_service, and downstream CLI payloads onto the aliases.

- [x] `W02.P08.S39` - declare the BundleId and EvidenceId aliases with the hex-64 StringConstraints shape and an __all__ export per ADR Rule 6 application-layer placement; `src/aeat/application/evidence/_ids.py`.
- [x] `W02.P08.S40` - lift the bundle_id and evidence_id bare-string field declarations onto BundleId and EvidenceId per ADR Rule 6 in the evidence models module; `src/aeat/application/evidence/_models.py`.
- [x] `W02.P08.S41` - lift the bundle_id and evidence_id bare-string parameters onto BundleId and EvidenceId per ADR Rule 6 in the evidence service module; `src/aeat/application/evidence/_service.py`.
- [x] `W02.P08.S42` - add a real-behavior roundtrip test that populates an evidence bundle with non-default BundleId and EvidenceId values, persists through the real adapter, reloads, and asserts strict pydantic equality; `src/aeat/application/evidence/test_evidence_roundtrip.py`.

### Phase `W02.P09` - promote VerificationReportId in domain/modelos/_ids.py

Declare the hex-64 VerificationReportId alias in the modelo records identity module per Rule 6 owner-domain placement (verification reports are part of the modelo-record family by lifecycle and reference), re-export, and lift the bare-string verification_report_id field sites in entrypoints/cli/_modelo_payloads and application/modelo/_actions onto the alias.

- [x] `W02.P09.S43` - declare the VerificationReportId alias with the hex-64 StringConstraints shape and add it to __all__ in the modelo records identity module per ADR Rule 6 owner-domain placement; `src/aeat/domain/modelos/_ids.py`.
- [x] `W02.P09.S44` - lift the verification_report_id bare-string field declarations onto VerificationReportId per ADR Rule 6 in the CLI modelo payload module; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W02.P09.S45` - lift the verification_report_id bare-string parameters onto VerificationReportId per ADR Rule 6 in the modelo application actions module; `src/aeat/application/modelo/_actions.py`.
- [x] `W02.P09.S46` - add a real-behavior roundtrip test that populates a verification-report record with a non-default VerificationReportId, persists through the real adapter, reloads, and asserts strict pydantic equality; `src/aeat/domain/modelos/test_verification_report_roundtrip.py`.

## Wave `W03` - collapse shadow declarations

Delete the duplicated _HEX_*_LENGTH constants, the private re-alias blocks under domain/modelos, the CLI registry private-regex import, and tighten the permissive sede casilla_id field per the ADR Consequences shadow-declarations section. Factor the retained sha-256 fingerprint duplications (Rule 7 exclusion) to a single module-local shape constant where this reduces three-way duplication, without promoting them to identity aliases. Phases are sequenced; the constant-deletion phases must land before the consumer-tightening phases.

### Phase `W03.P10` - delete _HEX_*_LENGTH constants in domain/invoices and domain/modelos

Remove the three _HEX_INVOICE_ID_LENGTH, _HEX_TRANSACTION_ID_LENGTH, and _HEX_WORK_UNIT_ID_LENGTH constants from their non-_ids.py homes per ADR Rule 4 and the Consequences shadow-declarations section, replacing each consumer field with the typed alias from the owning _ids.py module.

- [x] `W03.P10.S47` - delete the _HEX_TRANSACTION_ID_LENGTH constant and replace the consumer field with the typed TransactionId alias per ADR Rule 4; `src/aeat/domain/invoices/_service.py`.
- [x] `W03.P10.S48` - delete the _HEX_TRANSACTION_ID_LENGTH and _HEX_INVOICE_ID_LENGTH constants and replace the consumer fields with the typed TransactionId and InvoiceId aliases per ADR Rule 4; `src/aeat/domain/invoices/_models.py`.
- [x] `W03.P10.S49` - delete the _HEX_WORK_UNIT_ID_LENGTH constant and replace the consumer field with the typed WorkUnitId alias per ADR Rule 4; `src/aeat/domain/modelos/_work_unit.py`.

### Phase `W03.P11` - delete private re-alias blocks under domain/modelos

Remove the private re-aliasing blocks at domain/modelos/_work_unit, domain/modelos/_filing_record, and domain/modelos/_calculation_revision per Rule 4 (cross-package consumers import the alias by its public name, never re-alias under a private name). Modules consume the aliases under their public names.

- [x] `W03.P11.S50` - delete the private re-alias block and rewrite the module to consume the alias under its public name per ADR Rule 4; `src/aeat/domain/modelos/_work_unit.py`.
- [x] `W03.P11.S51` - delete the four private re-alias entries and rewrite the module to consume the aliases under their public names per ADR Rule 4; `src/aeat/domain/modelos/_filing_record.py`.
- [x] `W03.P11.S52` - delete the two private re-alias entries and rewrite the module to consume the aliases under their public names per ADR Rule 4; `src/aeat/domain/modelos/_calculation_revision.py`.

### Phase `W03.P12` - delete the CLI registry private-regex import

Remove the import of _CASILLA_RE and _REF_RE from entrypoints/cli/_modelo per ADR Rule 8. The CLI payload models consume the registry aliases (CasillaId, FormulaId, RevisionId, ModeloId) directly and let pydantic enforce the shape at the model boundary.

- [x] `W03.P12.S53` - delete the private _CASILLA_RE and _REF_RE import per ADR Rule 8 and switch the CLI payload models to consume the registry aliases directly; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W03.P13` - tighten the sede casilla_id declaration

Replace the permissive bare-string casilla_id field on the outbound AEAT sede schema with the typed CasillaId alias per Rule 8 so the registry pattern is enforced at the persistence boundary.

- [x] `W03.P13.S54` - replace the permissive bare-string casilla_id field with the typed CasillaId alias per ADR Rule 8 and confirm the outbound sede roundtrip rejects values outside the registry pattern; `src/aeat/adapters/outbound/aeat/sede/_schema.py`.

### Phase `W03.P14` - factor retained fingerprint shape duplications

Retain the sha-256 hex-64 Field declarations in application/user_profile and core/corpus_manifest under Rule 7 (fingerprints are not identities), but factor each modules three-way duplication to a single module-local shape constant. The shape constant is private to its declaring module and is not promoted to an identity alias.

- [x] `W03.P14.S55` - factor the three-way canonical_hash, stored_hash, current_hash declarations to a single module-local hex-64 shape constant under Rule 7 and confirm the fields retain their bare-str shape; `src/aeat/application/user_profile/__init__.py`.
- [x] `W03.P14.S56` - factor the two repeated hex-64 sha256 / manifest_sha256 declarations to a single module-local hex-64 shape constant under Rule 7; `src/aeat/core/corpus_manifest/__init__.py`.

## Wave `W04` - sweep registry-id bare-string survivors onto existing aliases

Lift the fifty-nine bare-string registry-id field sites enumerated in the identity-primitives reference (casilla_id, formula_id, revision_id, modelo_id across thirty-six files) onto the existing registry aliases declared in domain/calculations/registry/_ids.py per Rule 8. Phases are organised by consumer cluster so independent executors may parallelise. The registry-suite must remain green sequentially after each Phase lands.

### Phase `W04.P15` - lift CLI payload modules onto registry aliases

Replace bare-string casilla_id, formula_id, revision_id, modelo_id field declarations across entrypoints/cli/_modelo_payloads and adjacent CLI payload modules with the existing registry aliases. CLI input crosses a wire boundary and the strict-pydantic discipline forbids bare-string identity surfaces under Rule 8.

- [x] `W04.P15.S57` - replace the fifteen bare-string casilla_id, formula_id, revision_id, and modelo_id field declarations with the typed registry aliases per ADR Rule 8; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P15.S58` - replace the residual bare-string registry-id field declarations across the remaining CLI payload modules with the typed registry aliases per ADR Rule 8; `src/aeat/entrypoints/cli/`.

### Phase `W04.P16` - lift registry validator modules onto registry aliases

Replace bare-string registry-id field declarations across the domain/calculations/registry/_validate_* modules with their typed aliases. The registry validators are downstream consumers of the registry-authority pipeline and must consume the typed contract.

- [x] `W04.P16.S59` - replace the bare-string registry-id field declarations across the registry _validate_* modules with the typed registry aliases per ADR Rule 8 and confirm the registry-suite passes sequentially; `src/aeat/domain/calculations/registry/`.

### Phase `W04.P17` - lift filing schema and record design onto registry aliases

Replace bare-string registry-id field declarations across domain/filing/_schema and the record-design surface with the typed aliases. The filing schema is the persisted boundary for filing draft records and must consume the typed registry identity contract.

- [x] `W04.P17.S60` - replace the four bare-string casilla_id, formula_id, revision_id, and modelo_id field declarations on the filing schema with the typed registry aliases per ADR Rule 8; `src/aeat/domain/filing/_schema.py`.
- [x] `W04.P17.S61` - replace the bare-string registry-id field declarations across the record-design surface with the typed registry aliases per ADR Rule 8; `src/aeat/domain/calculations/registry/_record_design.py`.

### Phase `W04.P18` - lift remaining registry-id survivors across application and adapter layers

Replace the residual bare-string registry-id field declarations across application services and adapter modules with the typed aliases, closing the bare-string registry-id survivor list enumerated in the identity-primitives reference.

- [x] `W04.P18.S62` - replace the residual bare-string registry-id field declarations across application services with the typed registry aliases per ADR Rule 8; `src/aeat/application/`.
- [x] `W04.P18.S63` - replace the residual bare-string registry-id field declarations across adapter modules with the typed registry aliases per ADR Rule 8; `src/aeat/adapters/`.
- [x] `W04.P18.S64` - run ripgrep across src/aeat for bare-string casilla_id, formula_id, revision_id, and modelo_id field declarations on pydantic models and confirm zero occurrences remain outside the registry _ids.py module; `src/aeat/`.

## Wave `W05` - land the Rule 9 enforcement test

Land the structural import-direction test mandated by ADR Rule 9 under the production test surface, so subsequent regressions fail at CI rather than at review. The test is real-behavior: it parses every Python module under src/aeat/ with the standard-library ast module and reports detections in each of the four clauses. Steps in the single Phase implement one clause each plus an anti-tautology demonstration.

### Phase `W05.P19` - implement the four-clause structural enforcement test

Author the import-direction test under src/aeat/diagnostics or src/aeat/.../test_identity_primitive_placement.py (the exact module home is the executor decision so long as the test participates in the default CI gate), with one Step per Rule 9 clause and a final Step that demonstrates the anti-tautology proof.

- [x] `W05.P19.S65` - author the sibling-domain detection clause: parse every module under src/aeat with the standard-library ast module and assert no domain.<a> module imports a name from domain.<b>._ids for any a != b other than the registry-aliases exception per ADR Rule 9; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W05.P19.S66` - author the private-name import detection clause: parse every module under src/aeat with ast and assert no adapter, application, or entrypoint module imports a name beginning with an underscore from any _ids.py module per ADR Rule 9; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W05.P19.S67` - author the _HEX_*_LENGTH constant detection clause: walk the ast of every module under src/aeat and assert no _HEX_<name>_LENGTH constant is declared outside the owning _ids.py module per ADR Rule 9; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W05.P19.S68` - author the bare-string typed-id-field detection clause: walk every pydantic model declaration under src/aeat with ast and assert no field whose name ends in _id uses bare str with only length or pattern constraints when a typed alias for that identity exists in the inventory per ADR Rule 9; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W05.P19.S69` - demonstrate the anti-tautology proof: temporarily re-add a single shadow constant under a scratch path, run the test, observe the failure surfaces the violation with file and line coordinates, revert the experiment, and confirm the test passes again; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
