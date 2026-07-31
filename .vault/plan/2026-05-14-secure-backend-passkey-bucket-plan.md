---
tags:
  - '#plan'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-07-17'
body_hash: 'sha256:f7c5f56fffe61266f5abf6d3d1e17180db5c90f6546c8b93ccd53d631b3d8f48'
tier: L2
related:
  - '[[2026-05-14-secure-backend-passkey-safety-research]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

<!-- RETIRED: P04, P05, P06, P07, P08, P09, P10, P11, S17, S18, S19, S20, S21, S22, S23, S24, S25, S26, S27, S28, S29, S30, S31, S32, S33, S34, S35, S36, S37, S38, S39, S40, S41, S42, S43, S44, S45, S46, S47, S48, S49, S50, S51, S52 -->

# `secure-backend-passkey-safety` plan: `passkey custody + bucket lifecycle execution`

## Status

SUPERSEDED and closed as an execution vehicle by
`2026-05-22-secure-storage-production-hardening-refactor-plan` on 2026-07-10.
This plan retains only `S01` through `S16`: every retained row has historical
execution evidence. The stale `S17` through `S52` rows were structurally retired,
not marked complete. Their identifiers remain in the Vaultspec retirement annotation
and their evidence-led disposition is recorded by
`2026-07-10-secure-backend-passkey-safety-audit`.

The present codebase implements some related custody behavior through the successor's
profile-centric model and different modules. That work is deliberately not credited
to this historical plan. Consequently, this plan has no active or open steps; any
remaining custody hardening belongs to the successor plan. FIDO2 hardware-passkey
custody remains out of scope because the operator declined the hardware.

### Phase `P01` - foundation pydantic v2 record set

Lock down every record, manifest, and envelope as a pydantic v2 strict model before behavioural change so downstream phases consume typed contracts only.

- [x] `P01.S01` - introduce `BucketManifest` pydantic model; `src/aeat/adapters/persistence/storage/bucket/_manifest.py`.
- [x] `P01.S02` - introduce `KdfParams` Argon2id record; `src/aeat/adapters/persistence/storage/master_key/_kdf_params.py`.
- [x] `P01.S03` - introduce `RecoveryRecord` BIP-39 envelope; `src/aeat/adapters/persistence/storage/master_key/_recovery_record.py`.
- [x] `P01.S04` - introduce `BucketPointer` pointer-file record; `src/aeat/application/workflow/_bucket_pointer.py`.
- [x] `P01.S05` - introduce `ExportArchiveHeader` record; `src/aeat/adapters/persistence/storage/bucket/_export_header.py`.
- [x] `P01.S06` - introduce typed error hierarchy; `src/aeat/adapters/persistence/storage/bucket/_errors.py`.

### Phase `P02` - filesystem layout and manifest IO

Materialise the bucket directory model, manifest read/write API, keystore separation contract, pointer-file API, and per-bucket lock primitive before crypto or CLI work.

- [x] `P02.S07` - implement bucket directory provisioning; `src/aeat/adapters/persistence/storage/bucket/_layout.py`.
- [x] `P02.S08` - implement manifest read / write API; `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`.
- [x] `P02.S09` - implement keystore separation contract; `src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py`.
- [x] `P02.S10` - implement pointer-file API; `src/aeat/application/workflow/_bucket_pointer_io.py`.
- [x] `P02.S11` - implement per-bucket `.lock` concurrency primitive; `src/aeat/adapters/persistence/storage/bucket/_lockfile.py`.

### Phase `P03` - cryptographic core

Replace silent minting and process-lifetime key caches with BucketSession-scoped Argon2id KEK derivation, AES-256-GCM DEK wrapping, recovery handling, zeroisation, and idle-timeout enforcement.

- [x] `P03.S12` - implement `BucketSession` instance state; `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`.
- [x] `P03.S13` - implement Argon2id KEK derivation; `src/aeat/adapters/persistence/storage/master_key/_kdf.py`.
- [x] `P03.S14` - implement AES-256-GCM DEK wrap and unwrap; `src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py`.
- [x] `P03.S15` - wire BIP-39 recovery wrap and unwrap; `src/aeat/adapters/persistence/storage/master_key/_recovery.py`.
- [x] `P03.S16` - implement in-memory zeroisation contract; `src/aeat/adapters/persistence/storage/master_key/_zeroise.py`.

## Description

## Steps

## Parallelization

## Verification
