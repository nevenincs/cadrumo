---
tags:
  - '#exec'
  - '#macos-platform'
date: '2026-10-30'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:f93f13bd61e700bce044e016df3be1654d4134a6057e0e7b8b0b32dbd0429bfe'
related:
  - "[[2026-10-30-macos-platform-plan]]"
---

# `macos-platform` ledger

## Changes

- `S02` `M` `native/manager/src/custody/posix.rs`
- `S02` `M` `native/manager/src/main.rs`
- `S02` `M` `native/manager/src/macos/lifecycle/appkit.rs`
- `S02` `A` `native/manager/src/macos/menu/effects.rs`
- `S02` `M` `native/manager/src/lib.rs`
- `S02` `M` `native/platform/src/conformance_tests.rs`
- `S02` `M` `native/cmake/RustQuality.cmake`
- `S02` `M` `native/CMakeLists.txt`
- `S02` `M` `native/application/CMakeLists.txt`
- `S02` `M` `dev/packaging/native/cargo_command.py`
- `S02` `M` `dev/packaging/native/build_fingerprint.py`
- `S02` `verify:` `.tmp/2026-10-30-macos-platform/native/build.sh Debug all` -> `pass`
- `S02` `verify:` `ctest --test-dir build/macos-arm64 -C Debug -R ^manager\.` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `M` `src/cadrumo_runtime/adapters/macos_coalition.py
src/cadrumo_runtime/host/tests/test_worker_exit_cleanup.py
src/cadrumo_runtime/host/worker_service.py
src/cadrumo/adapters/outbound/aeat/browser/tests/test_view_input.py
src/cadrumo/adapters/outbound/aeat/browser/view_input.py
src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_worker_startup_ownership.py
src/cadrumo/application/user_profile/tests/test_language_resolver_snapshot.py
src/cadrumo/core/observability/tests/test_sink.py
src/cadrumo/core/tests/test_bucket_pointer_io.py
src/cadrumo/core/tests/test_output_dir_state_root.py`
- `S03` `verify:` `uv run --no-sync pytest -n 2 rerun of baseline failing files` -> `pass`
- `S03` `M` `dev/packaging/native/platforms/posix.py`
- `S03` `M` `src/cadrumo/core/tests`
- `S03` `M` `src/cadrumo_runtime/adapters/macos_coalition.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests`
- `S03` `M` `src/cadrumo/application/actividad_asset/disposal_calculation.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_filed_register_pass_loads.py`
- `S03` `verify:` `uv run --no-sync pytest --co -q` -> `pass`
- `S03` `verify:` `rerun of 107 baseline failing files: 15 failures, all fixed` -> `pass`
- `S03` `by:` `vaultspec-standard-executor`

## Notes

- `S03` Baseline 396 failures reduced to 15 on rerun; remaining platform and in-progress failures fixed or already fixed by concurrent sessions; Chromium provisioned (581 MB)
