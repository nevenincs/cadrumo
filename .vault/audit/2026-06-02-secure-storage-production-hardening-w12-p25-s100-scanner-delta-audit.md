---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
  - '[[2026-05-26-active-profile-storage-runtime-classification-closeout-audit]]'
---

# W12.P25.S100 scanner delta

## Scope

This audit reruns the active-profile storage runtime signal scan for the final rollout
gate. The baseline is the 2026-05-26 active-profile storage runtime discovery audit.
The current scan covers every Python source file under `src/aeat`.

The original audit persisted its category names, counts, and production index, but not
a standalone scanner script. This replay therefore uses the same named category
vocabulary and records the replay vocabulary here so the comparison remains auditable.

## Replay vocabulary

| Category | Replay signals |
| --- | --- |
| `secure_object_repository` | `SecureObjectRepository`, `secure_object_repository_for_` |
| `secure_bound_repository` | `SecureBoundRepository` |
| `storage_runtime` | `StorageRuntime`, `inspect_storage_runtime`, `inspect_bucket_storage_runtime`, `secure_object_repository_for_active_bucket` |
| `active_profile_resolution` | `resolve_active_bucket_id`, `AEAT_ACTIVE_PROFILE`, `aeat_active_profile`, `active_profile`, `active-profile` |
| `pointer_manifest_bucket` | `BucketManifest`, `ProfileBucket`, `read_profile_bucket`, `list_profile_buckets`, `write_profile_bucket`, `read_manifest(`, `write_manifest(`, `BucketPaths`, `BucketLayout`, `bucket_manifest`, `active-profile` |
| `master_key_session` | `master_key`, `MasterKey`, `BucketSession`, `activate_master_key_provider`, `get_master_key_provider`, `KdfParams`, `secret_passphrase`, `wrapped_dek`, `dek` |
| `settings_sql_route` | `aeat_database_url`, `AEAT_DATABASE_URL`, `classify_storage_route`, `StorageRouteKind`, `get_engine(`, `dispose_engine(`, `override_settings`, `Settings(` |
| `plaintext_profile_storage` | `adapters/persistence/profile`, `ProfileInventory`, `ProfileAsset`, `legacy profile persistence`, `profile assets` |
| `jsonl_or_plain_file_state` | `.jsonl`, `write_text(`, `read_text(`, `write_bytes(`, `read_bytes(`, `open(`, `ZipFile`, `storage_path`, `NamedTemporaryFile`, `mkstemp`, `TemporaryDirectory`, `.zip`, `.csv` |
| `outbound_storage_provider` | `StorageProvider`, `GoogleDriveStorageProvider`, `LocalStorageProvider`, `storage_provider`, `GoogleDrive`, `googleapiclient`, `remote mirror`, `mirror_manifest` |

Test files are source files named `test_*.py`, `*_test.py`, `conftest.py`, or under a
`tests` path. All other files are counted as production.

## Scanner totals

| Metric | Baseline | Current | Delta |
| --- | ---: | ---: | ---: |
| Python files scanned | 1415 | 1845 | +430 |
| Files with at least one storage/profile signal | 467 | 715 | +248 |
| Production files with at least one signal | 169 | 236 | +67 |
| Test files with at least one signal | 298 | 479 | +181 |
| Files with no scanner signal | 948 | 1130 | +182 |

## Category delta

| Category | Baseline all | Current all | Delta all | Baseline prod | Current prod | Delta prod | Baseline test | Current test | Delta test |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `secure_object_repository` | 146 | 117 | -29 | 53 | 59 | +6 | 93 | 58 | -35 |
| `secure_bound_repository` | 53 | 20 | -33 | 30 | 16 | -14 | 23 | 4 | -19 |
| `storage_runtime` | 5 | 38 | +33 | 4 | 25 | +21 | 1 | 13 | +12 |
| `active_profile_resolution` | 74 | 166 | +92 | 34 | 61 | +27 | 40 | 105 | +65 |
| `pointer_manifest_bucket` | 83 | 113 | +30 | 41 | 47 | +6 | 42 | 66 | +24 |
| `master_key_session` | 57 | 136 | +79 | 32 | 54 | +22 | 25 | 82 | +57 |
| `settings_sql_route` | 182 | 181 | -1 | 20 | 48 | +28 | 162 | 133 | -29 |
| `plaintext_profile_storage` | 9 | 12 | +3 | 4 | 6 | +2 | 5 | 6 | +1 |
| `jsonl_or_plain_file_state` | 223 | 419 | +196 | 68 | 94 | +26 | 155 | 325 | +170 |
| `outbound_storage_provider` | 15 | 27 | +12 | 10 | 15 | +5 | 5 | 12 | +7 |

## Interpretation

- Runtime adoption is materially visible: production `storage_runtime` signals rose
  from 4 to 25 files, while production `secure_bound_repository` signals fell from 30
  to 16 files.
- The direct secure-object signal is not a pure defect counter. It now includes runtime
  factory and registry surfaces as well as remaining repository implementations. S101
  and S102 must keep distinguishing approved runtime-owned access from raw competing
  constructors.
- The production `settings_sql_route`, `master_key_session`, and
  `active_profile_resolution` increases show that rollout code now carries more
  explicit route/session/bucket policy. That is acceptable only where owned by runtime,
  bootstrap custody, or manifest discovery dispositions.
- The production plain-file count remains a closeout risk. S96 through S99 classified
  side stores, export boundaries, and remote mirrors, but S101/S102 and the W12.P26
  affected-file ledger still need to prove every remaining plain-file signal has one
  accepted disposition.
- The repository grew by 430 Python files since the baseline. The delta therefore
  should be used as a current closeout map, not as a direct one-number success metric.
- The first S100 guard rerun found one new unapproved explicit database-route test
  setup in `src/aeat/application/live/test_iva_wallet_capture_backend.py`. The test was
  migrated to real `isolated_runtime_profile` storage and runtime-bound repository
  injection instead of adding another explicit-route allowlist entry.

## Validation

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`
  - Result: 7 passed.
- `uv run --no-sync pytest -q src/aeat/application/live/test_iva_wallet_capture_backend.py`
  - Result: 4 passed.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`
  - Result: all checks passed.
- `uv run --no-sync ruff check src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`
  - Result: all checks passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
  - Result: existing `PLAN022` monotonicity warning only.

## Required follow-up

- S101 must run the focused storage, profile lifecycle, CLI, workflow, domain
  repository, outbound adapter, and test-runtime gates against this current surface.
- S102 must persist the final accepted-disposition review for direct constructors,
  explicit-route tests, manifest discovery, bootstrap custody, side-store exceptions,
  and remote mirrors.
- W12.P26 remains the affected-file ledger for path-level closure of the residual
  production signals.
