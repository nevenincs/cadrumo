---
tags:
  - '#plan'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_hash: 'sha256:4117187cbd2b206dc6958ad10252eb0d5809992a6dc05965197ce53bb9df3fdf'
tier: L3
related:
  - '[[2026-07-09-compatibility-lifecycle-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
  - '[[2026-06-10-zero-legacy-purge-research]]'
---

<!-- RETIRED: P02 -->

# `current-schema-only-purge` plan

## Description

Delete every confirmed read-tolerance, missing-marker default, and bare-payload
coercion that permits this pre-release application to hydrate or persist anything
other than its current schemas. The compatibility-lifecycle decision governs exact
current-version refusal and preservation of dormant forward-only lineage controls.
The secure-persistence decision governs fail-closed encrypted parsing and requires
schema mismatches to stop before key derivation or decryption.

This plan does not delete empty upgrader registries, regime gates, durability-floor
checks, or future-version refusal scaffolds because they read no obsolete shape. It
does not reinterpret AEAT regulatory revisions or external-source variability as
application legacy. Workflow action-detail compatibility remains exclusively owned by
the CLI action-envelope plan and is not duplicated here.

Version numbers appearing in this plan's Phase headings and Step rows are the
values this document ASSERTED when it was authored. They are a record of intent,
never an assertion about HEAD, and they must not be read as evidence that the
tree carries them. The profile phase is the worked example and it is worth
stating exactly: the plan says "version 4", the record's field defaulted to 1,
and the canonical user-profile schema in fact declares 5. All three numbers were
different, and the plan's was wrong when it was written -- not stale, wrong.

That is why every implementing change reads the current version from its schema
authority instead of inlining a literal at the call site. Had the remedy been
"set it to 4" the plan's own error would have been compiled into the code. A
literal 5 written today would be the same defect one revision later, and the
gate this plan installs found exactly that shape: hardcoded version literals in
seeded fixtures, refused the moment exact equality replaced the ceiling.

## Steps

## Wave `W01` - Pin domain records to current schema

Eliminate pre-current domain hydration and bare catalogue coercion before tightening
encrypted storage boundaries.

### Phase `W01.P01` - Require User Profile schema v4

Make live profile records and immutable snapshots accept exactly the canonical version
4 schema.

- [x] `W01.P01.S01` - Require exact schema id and schema version 4 for UserProfileRecord and UserProfileSnapshot; `src/cadrumo/domain/user_profile/_values.py`.
- [x] `W01.P01.S02` - Stamp newly created profile records explicitly with the canonical schema version; `src/cadrumo/application/user_profile/_lifecycle.py`.
- [x] `W01.P01.S03` - Prove current profile schema hydration and non-current marker refusal; `src/cadrumo/domain/user_profile/tests/test_payload_schema_identity.py`.
- [x] `W01.P01.S24` - Refuse a persisted profile payload that omits schema_version at both profile read boundaries, rather than making the field required. Required-ness was NOT taken because 229 of the 231 construction sites are in-memory test and harness constructions that are not the defect, while the defect is bytes hydrating as current. What required-ness would still buy, and what this row therefore does not deliver, is making the unstamped state unconstructable in memory as well as unreadable from disk; `src/cadrumo/application/user_profile/_repository.py at both the record load and the snapshot load, never in the shared SecureBoundRepository whose generic path serves other namespaces`.

### Phase `W01.P03` - Pin the active bucket pointer format

Require the exact current active-profile pointer marker at the TOML boundary.

- [x] `W01.P03.S04` - Define and require the exact current BucketPointer schema marker; `src/cadrumo/core/_bucket_pointer.py`.
- [x] `W01.P03.S05` - Prove current BucketPointer round trips and non-current marker refusal; `src/cadrumo/core/tests/test_bucket_pointer.py`.

### Phase `W01.P04` - Remove InvoiceCatalogue bare-payload coercion

Require the canonical invoices wrapper while preserving the explicit construction API.

- [x] `W01.P04.S06` - Delete mapping-without-invoices coercion from InvoiceCatalogue validation; `src/cadrumo/domain/invoices/_models.py`.
- [x] `W01.P04.S07` - Prove serialized catalogues require the canonical invoices wrapper; `src/cadrumo/domain/invoices/tests/test_catalogue.py`.

## Wave `W02` - Require cryptographic and persistence markers

Require every current storage discriminator at parsing time and before cryptographic
use without changing forward-only lineage machinery.

### Phase `W02.P05` - Harden encrypted wrapper markers

Make all encrypted wrapper format claims explicit and exact before key access.

- [x] `W02.P05.S08` - Require and explicitly write the exact current CipherEnvelope marker; `src/cadrumo/adapters/persistence/storage/envelope/_envelope.py`.
- [x] `W02.P05.S09` - Prove CipherEnvelope marker refusal occurs before master-key access; `src/cadrumo/adapters/persistence/storage/envelope/tests/test_cipher_envelope_version_gate.py`.
- [x] `W02.P05.S10` - Require and preflight the exact current WrappedMasterKey marker before decryption; `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`.
- [x] `W02.P05.S11` - Prove wrapped-master-key marker refusal precedes real unwrap; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`.
- [x] `W02.P05.S12` - Require explicit current encrypted-bundle envelope payload and KDF markers; `src/cadrumo/application/user_profile/_bundle_encryption.py`.
- [x] `W02.P05.S13` - Prove encrypted-bundle marker refusal and current passphrase round trip; `src/cadrumo/application/user_profile/tests/test_bundle_export.py`.
- [x] `W02.P05.S25` - Gate the encrypted-bundle kdf_version marker against the current Argon2 version, promoting that version onto the master-key package facade as the precondition; `src/cadrumo/application/user_profile/_bundle_encryption.py and the master-key package facade that must export the Argon2 version constant`.

### Phase `W02.P06` - Harden local custody metadata

Require current index KDF and key-schedule markers on every local custody read and
write.

- [x] `W02.P06.S14` - Require and explicitly write the exact current SecretIndex marker; `src/cadrumo/adapters/persistence/storage/secret_store/_secret_store.py`.
- [x] `W02.P06.S15` - Prove missing and non-current secret-index markers refuse real store operations; `src/cadrumo/adapters/persistence/storage/secret_store/tests/test_secret_index_version_gate.py`.
- [ ] `W02.P06.S16` - Require the exact current KdfParameters version marker; `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py`.
- [ ] `W02.P06.S17` - Stamp current KDF markers during key mint and recovery; `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `W02.P06.S18` - Prove file-fallback key loading refuses missing and non-current KDF markers; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key_file_fallback.py`.
- [ ] `W02.P06.S19` - Make BucketManifest key_schedule mandatory; `src/cadrumo/adapters/persistence/storage/bucket/_manifest.py`.
- [ ] `W02.P06.S20` - Prove real manifest reads require and preserve the current key schedule; `src/cadrumo/adapters/persistence/storage/bucket/tests/test_manifest_io.py`.
- [x] `W02.P06.S26` - Make the master-key KDF preflight model require a real version, replacing the optional-and-defaulting-to-absent field that lets a marker-less file pass the check the preflight exists to perform; `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py preflight model and its single read call site, with no writer or derivation path touched`.

## Wave `W03` - Close the Modelo 303 observation write boundary

Prevent any official Modelo 303 observation from persisting without its resolved typed
result disposition.

### Phase `W03.P07` - Require disposition before persistence

Fail official Modelo 303 observation writes before repository mutation when
`result_disposition` is absent.

- [ ] `W03.P07.S21` - Require result_disposition for applicable official Modelo 303 observation payloads; `src/cadrumo/application/calculations/_observations_repository.py`.
- [x] `W03.P07.S22` - Require Modelo 303 result_disposition before any filing persistence write; `src/cadrumo/application/modelo/_revision_persistence.py`.
- [ ] `W03.P07.S23` - Prove under-declared Modelo 303 observations are refused and current dispositions round trip; `src/cadrumo/application/calculations/tests/test_m303_carry_ingress.py`.

## Parallelization

Waves remain ordered. Within W01, the profile, pointer, and invoice Phases are
file-disjoint and may execute in parallel. Within W02, each encrypted format may be
implemented independently, but every production Step precedes its paired real-behavior
test and KDF record validation precedes KDF minting. W03 waits for the current-schema
domain and storage boundaries so its final integration proof measures the completed
state. No worker may touch workflow action compatibility or dormant lineage machinery.

## Verification

- Parse current serialized records through production loaders and reject missing,
  pre-current, and future markers without coercion.
- Prove cryptographic marker refusal occurs before key derivation or decryption and
  retain real current-format positive round trips.
- Prove an under-declared Modelo 303 write leaves repositories unchanged, followed by
  a successful disposition-bearing round trip.
- Use production imports and real storage adapters; no fakes, mocks, stubs, patches,
  monkeypatches, skips, or expected failures.
- Run focused pytest, path-scoped Ruff and strict BasedPyright, plan and Vault checks,
  and a final semantic plus lexical sweep showing no listed compatibility branch or
  default remains.
- Complete a fresh-context code review before closing the campaign.
