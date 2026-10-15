---
tags:
  - '#exec'
  - '#packaged-kdf-attestation'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:0823a253a1c4212b1fb37f21b2d7adde0ef9084a1f8a219c0bfc43e38994226b'
related:
  - "[[2026-10-15-packaged-kdf-attestation-plan]]"
---


# `packaged-kdf-attestation` ledger

## Changes

- `S01` `M` `dev/packaging/native/assemble.py`
- `S01` `M` `native/interpreter/bootstrap.py`
- `S01` `M` `native/tests/package_smoke.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py`
- `S01` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_fixed_environment.py`
- `S01` `verify:` `focused custody and native packaging tests (66 tests, final source)` -> `pass`
- `S01` `verify:` `changed-file Ruff lint and format; custody ty` -> `pass`
- `S01` `verify:` `just check-registry-gate` -> `pass`
- `S01` `verify:` `just check-code` -> `fail`
- `S01` `verify:` `just test-gate` -> `fail`
- `S01` `verify:` `cmake --build --preset debug --target app-payload (final source)` -> `fail`
- `S01` `verify:` `final changed-file lint, format, custody types and 2 environment regressions` -> `pass`

## Notes

- `S01` Original Release profile create, readback and cleanup passed after the correction. Final Debug and Release rebuilds remain pending: three Debug attempts rejected concurrently edited source snapshots. Global code and test gates have unrelated failures; see run logs, including overview runtime cleanup and uncontrolled platform-data test root. No guard or security bound weakened.
- `S01` Latest Debug source snapshot and wheel builds succeeded, but wheel installation failed with os error 112: Y drive full. Automatic approval review rejected deletion of the 6.25 GiB Rust incremental caches as blocked by policy. Normal uv cache prune waited on other active uv cache users and was canceled without force. User asked to free at least 10 GiB and pause source edits. Final Release rebuild, package CTests and Claude Haiku API proofs are pending; both Steps remain open.
- `S01` User explicitly requested commit and push before deleting nondefault build directories. Checkpoint the source correction with S01/S02 still open. Root, desktop and distribution CMake preset files declare four existing build directories; preserve all four. Only build/acceptance is unenrolled, has no running process and contains 286 files totaling about 5 MiB. Deleting it will not recover the 10 GiB required for the remaining builds.
