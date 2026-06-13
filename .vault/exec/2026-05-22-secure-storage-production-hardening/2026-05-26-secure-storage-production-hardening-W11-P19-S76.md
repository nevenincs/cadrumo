---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S76'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-model-duplication-audit]]'
---



# `secure-storage-production-hardening` `W11.P19.S76`

Repaired a concrete duplicated secure-storage model contract by centralizing fresh-bucket KDF defaults behind the canonical master-key KDF model.

## Changes

- Added `KdfParams.to_manifest_params()` so the canonical KDF parameter record can produce the bucket-manifest KDF shape directly.
- Updated the profile repository fresh-bucket manifest path to call `KdfParams.default().to_manifest_params()` instead of repeating Argon2id algorithm, version, memory cost, time cost, parallelism, salt length, and output-length literals.
- Kept the manifest conversion local-imported to avoid an import-time cycle between the master-key model and bucket manifest model.
- Added a focused KDF model test proving the canonical parameter record converts into `ManifestKdfParams` without changing field values.
- Left namespace registry and lifecycle enum consolidation deferred to their owning architecture waves because those require broader contract decisions.

## Validation

- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_kdf_params.py src/aeat/application/user_profile/_profile_repository.py src/aeat/adapters/persistence/storage/master_key/test_kdf_params.py src/aeat/application/user_profile/test_profile_repository.py`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/master_key/test_kdf_params.py src/aeat/application/user_profile/test_profile_repository.py -q`

## Review

The targeted S76 review found no issues. It confirmed that the local import avoids a model cycle, that the fresh manifest still emits the same Argon2id security parameters as before, that the added test uses real model behavior without mocks, monkeypatching, skips, or tautological calculation logic, and that the patch added no `noqa`, pragma, or deprecated CLI/config surface.
