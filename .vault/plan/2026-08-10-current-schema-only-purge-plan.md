---
tags:
  - '#plan'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_hash: 'sha256:97b1e421bad5b97caaf82e55b27ed81bbe950b8d671455a0398f08f8c826dd47'
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
values the canonical schemas declared when the plan was authored. They are a
record of intent, not an assertion about HEAD, and must never be read as
evidence that the tree already carries them. At authoring time the profile
record in fact defaulted to schema version 1 while the canonical user-profile
schema declared 4, and the identity check was a ceiling that accepted every
pre-current value; the gap between the plan's stated version and the tree's
actual one was the defect, not a typo in the plan. Each implementing change
therefore reads the current version from its schema authority rather than
inlining the literal at the call site, so a later schema advance moves the
behaviour without a sweep through this document.

## Steps

## Wave `W01` - Pin domain records to current schema

Eliminate pre-current domain hydration and bare catalogue coercion before tightening
encrypted storage boundaries.

### Phase `W01.P01` - Require User Profile schema v4

Make live profile records and immutable snapshots accept exactly the canonical version
4 schema.

- [ ] `W01.P01.S01` - Require exact schema id and schema version 4 for UserProfileRecord and UserProfileSnapshot; `src/cadrumo/domain/user_profile/_values.py`.
- [ ] `W01.P01.S02` - Stamp newly created profile records explicitly with the canonical schema version; `src/cadrumo/application/user_profile/_lifecycle.py`.
- [ ] `W01.P01.S03` - Prove current profile schema hydration and non-current marker refusal; `src/cadrumo/domain/user_profile/tests/test_payload_schema_identity.py`.

### Phase `W01.P03` - Pin the active bucket pointer format

Require the exact current active-profile pointer marker at the TOML boundary.

- [ ] `W01.P03.S04` - Define and require the exact current BucketPointer schema marker; `src/cadrumo/core/_bucket_pointer.py`.
- [ ] `W01.P03.S05` - Prove current BucketPointer round trips and non-current marker refusal; `src/cadrumo/core/tests/test_bucket_pointer.py`.

### Phase `W01.P04` - Remove InvoiceCatalogue bare-payload coercion

Require the canonical invoices wrapper while preserving the explicit construction API.

- [ ] `W01.P04.S06` - Delete mapping-without-invoices coercion from InvoiceCatalogue validation; `src/cadrumo/domain/invoices/_models.py`.
- [ ] `W01.P04.S07` - Prove serialized catalogues require the canonical invoices wrapper; `src/cadrumo/domain/invoices/tests/test_catalogue.py`.

## Wave `W02` - Require cryptographic and persistence markers

Require every current storage discriminator at parsing time and before cryptographic
use without changing forward-only lineage machinery.

### Phase `W02.P05` - Harden encrypted wrapper markers

Make all encrypted wrapper format claims explicit and exact before key access.

- [ ] `W02.P05.S08` - Require and explicitly write the exact current CipherEnvelope marker; `src/cadrumo/adapters/persistence/storage/envelope/_envelope.py`.
- [ ] `W02.P05.S09` - Prove CipherEnvelope marker refusal occurs before master-key access; `src/cadrumo/adapters/persistence/storage/envelope/tests/test_cipher_envelope_version_gate.py`.
- [ ] `W02.P05.S10` - Require and preflight the exact current WrappedMasterKey marker before decryption; `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`.
- [ ] `W02.P05.S11` - Prove wrapped-master-key marker refusal precedes real unwrap; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`.
- [ ] `W02.P05.S12` - Require explicit current encrypted-bundle envelope payload and KDF markers; `src/cadrumo/application/user_profile/_bundle_encryption.py`.
- [ ] `W02.P05.S13` - Prove encrypted-bundle marker refusal and current passphrase round trip; `src/cadrumo/application/user_profile/tests/test_bundle_export.py`.

### Phase `W02.P06` - Harden local custody metadata

Require current index KDF and key-schedule markers on every local custody read and
write.

- [ ] `W02.P06.S14` - Require and explicitly write the exact current SecretIndex marker; `src/cadrumo/adapters/persistence/storage/secret_store/_secret_store.py`.
- [ ] `W02.P06.S15` - Prove missing and non-current secret-index markers refuse real store operations; `src/cadrumo/adapters/persistence/storage/secret_store/tests/test_secret_index_version_gate.py`.
- [ ] `W02.P06.S16` - Require the exact current KdfParameters version marker; `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py`.
- [ ] `W02.P06.S17` - Stamp current KDF markers during key mint and recovery; `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `W02.P06.S18` - Prove file-fallback key loading refuses missing and non-current KDF markers; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key_file_fallback.py`.
- [ ] `W02.P06.S19` - Make BucketManifest key_schedule mandatory; `src/cadrumo/adapters/persistence/storage/bucket/_manifest.py`.
- [ ] `W02.P06.S20` - Prove real manifest reads require and preserve the current key schedule; `src/cadrumo/adapters/persistence/storage/bucket/tests/test_manifest_io.py`.

## Wave `W03` - Close the Modelo 303 observation write boundary

Prevent any official Modelo 303 observation from persisting without its resolved typed
result disposition.

### Phase `W03.P07` - Require disposition before persistence

Fail official Modelo 303 observation writes before repository mutation when
`result_disposition` is absent.

- [ ] `W03.P07.S21` - Require result_disposition for applicable official Modelo 303 observation payloads; `src/cadrumo/application/calculations/_observations_repository.py`.
- [ ] `W03.P07.S22` - Require Modelo 303 result_disposition before any filing persistence write; `src/cadrumo/application/modelo/_revision_persistence.py`.
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
