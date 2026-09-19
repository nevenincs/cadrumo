---
tags:
  - '#plan'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:f41f5f2d15936d2375bdab3e4e60e1780daa07e772b2e3e1cfe47b13560aeae6'
tier: L2
related:
  - '[[2026-06-30-bucket-custody-completeness-adr]]'
  - '[[2026-06-30-bucket-custody-completeness-research]]'
---

# `bucket-custody-completeness` plan

### Phase `P01` - carry-set authority in the namespace registry

Declare a per-namespace custody disposition in the canonical storage namespace registry so the carry set is registry-derived and self-policing.

- [x] `P01.S01` - Add StorageCustodyDisposition enum and a required custody_disposition field to SecureObjectNamespaceDefinition; `src/aeat/adapters/persistence/storage/_namespace_registry.py`.
- [x] `P01.S02` - Declare custody_disposition on every namespace definition in the registry; `src/aeat/adapters/persistence/storage/_namespace_registry.py`.
- [x] `P01.S03` - Add a registry projection helper returning the carry-set namespaces per custody profile; `src/aeat/adapters/persistence/storage/_namespace_registry.py`.

### Phase `P02` - schema bump and extended payload model

Bump the bundle and archive schema versions, delete the old shapes, and extend the portable-export model with the generic carried-object set and coverage manifest.

- [x] `P02.S04` - Add typed CarriedSecureObject and CoverageManifest models; `src/aeat/domain/user_profile/_portable_export.py`.
- [x] `P02.S05` - Bump bundle_schema_version to 3 and add carried_objects and coverage_manifest fields to UserProfilePortableExport; `src/aeat/domain/user_profile/_portable_export.py`.
- [x] `P02.S06` - Bump _ARCHIVE_SCHEMA_VERSION to 2 and narrow SUPPORTED_BUNDLE_SCHEMA_VERSIONS to the single current version, deleting old-shape tolerance; `src/aeat/application/bucket_maintenance/_service.py`.

### Phase `P03` - transport-aware serialise

Serialise the carry set generically per transport custody profile and build the coverage manifest with a fail-closed full-coverage assertion.

- [x] `P03.S07` - Add a CustodyProfile parameter to serialize_profile_bundle and read carry-set secure objects generically through the substrate; `src/aeat/application/user_profile/_bundle.py`.
- [x] `P03.S08` - Build the coverage manifest and apply the fail-closed full-coverage assertion for the sealed profile; `src/aeat/application/user_profile/_bundle.py`.

### Phase `P04` - transport-aware deserialise and import completeness

Re-encrypt and re-save every carried object under the recipient DEK, merge the audit trail idempotently, and rebuild the participation index after import.

- [x] `P04.S09` - Re-save every carried secure object through the substrate save path under the recipient DEK in deserialize_profile_bundle; `src/aeat/application/user_profile/_bundle.py`.
- [x] `P04.S10` - Merge the carried bucket event-history catalogue idempotently and rebuild the participation index after import; `src/aeat/application/user_profile/_bundle.py`.

### Phase `P05` - transport wiring

Wire the sealed archive to the full custody profile with coverage verification and the cleartext bundle to the structured-only profile with a loud not-a-full-backup notice.

- [x] `P05.S11` - Wire BucketMaintenanceService export and import_ to the full custody profile and verify coverage on import; `src/aeat/application/bucket_maintenance/_service.py`.
- [x] `P05.S12` - Wire the cleartext config profile export and import to the structured-only profile and extend the export notice to name the sealed archive as the full backup; `src/aeat/entrypoints/cli/_config/_profile_bundle.py`.

### Phase `P06` - tests and gates

Add roundtrip, anti-tautology, coverage-gate-negative, cleartext-exclusion, and registry-disposition tests per the roundtrip discipline.

- [x] `P06.S13` - Extend the sealed roundtrip to seed every carried store with non-default state and assert strict per-store equality; `src/aeat/application/bucket_maintenance/tests/test_service_import_export.py`.
- [x] `P06.S14` - Add an anti-tautology proof for the carried-object boundary; `src/aeat/application/bucket_maintenance/tests/test_custody_completeness.py`.
- [x] `P06.S15` - Add a coverage-gate negative test where a populated undeclared namespace fails the sealed export; `src/aeat/application/bucket_maintenance/tests/test_custody_completeness.py`.
- [x] `P06.S16` - Add a cleartext structured-only test asserting no FINANCIAL bytes are carried and the not-a-full-backup notice is emitted; `src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py`.
- [x] `P06.S17` - Add a registry test asserting every namespace declares a custody_disposition; `src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py`.

### Phase `P07` - manual persona verification and closeout

Drive a real operator-persona export-import recovery cycle, run a fresh honesty review, and resolve all surfaced and deferred work.

- [x] `P07.S18` - Drive a real operator-persona CLI export then import recovery cycle and verify evidence bytes, audit trail, and cross-period calc inputs survive; `src/aeat/entrypoints/cli`.
- [x] `P07.S19` - Run a fresh-context honesty review, sweep for deferred or unresolved work, and close every surfaced item with verification; `src/aeat`.

## Description

Make per-bucket export/import round-trip the full durable bucket, per the
authorizing ADR. Both transports share one partial builder
(`serialize_profile_bundle`) that drops evidence bytes, the audit trail, and the
cross-period calculation inputs; this plan extends the carry set to every durable
per-bucket secure-object store, re-encrypting each under the recipient bucket DEK
on import, and adds a registry-driven coverage gate so the sealed archive's
full-backup claim is true by construction.

Grounding refinement settled during signature discovery: the secure-object key
HMAC is derived from the per-bucket DEK, so a raw-digest substrate carry would
break reads in the recipient bucket. The carry is therefore **per-store typed** -
each dropped store is read through its own repository's list/iter surface, carried
as its typed domain payload, and re-saved through that repository's save path,
which re-derives the natural object key under the recipient DEK. This honours the
composition discipline (delegate to the single-writer primitive), D2
(decrypted domain payloads, re-encrypt on import), and the typed-boundary rules.
The transports split per the ADR: the sealed archive carries the full set
(including FINANCIAL bytes, AEAD-encrypted at rest); the cleartext bundle carries
the structured cross-period inputs only and emits a loud not-a-full-backup notice.

## Parallelization

The phases carry hard ordering and are executed in sequence: P01 (registry
authority) gates P02 (model), which gates P03 (serialise) and P04 (deserialise),
which gate P05 (wiring). P03 and P04 share `_bundle.py` and are co-developed but
land as distinct steps. P06 tests follow the surface they exercise; the registry
test (P06.S17) may land alongside P01. P07 runs last, after the full suite is
green. Within P01.S02 the per-namespace disposition declarations are a single
coherent edit to one file, not parallelisable.

## Verification

The plan is complete when every Step is closed and:

- The extended sealed export-import roundtrip seeds every carried store with
  non-default state and asserts strict per-store equality after a real
  AEAD + crypto cycle (`test_service_import_export.py`, `test_custody_completeness.py`).
- An anti-tautology proof corrupts an in-archive carried payload and asserts
  refusal or strict inequality.
- The coverage gate refuses a sealed export when a populated namespace is
  undeclared, and the registry test asserts every namespace declares a
  `custody_disposition`.
- The cleartext transport test asserts no FINANCIAL attachment bytes are carried
  and the not-a-full-backup notice is emitted.
- A real operator-persona CLI export then import recovery cycle confirms evidence
  bytes, the audit trail, and the cross-period 303 calc inputs survive.
- `uv run --no-sync pytest src/aeat` is green for the touched surfaces and a
  fresh honesty review surfaces no unresolved or deferred work.
