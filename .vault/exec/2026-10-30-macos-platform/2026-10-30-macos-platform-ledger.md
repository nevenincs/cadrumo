---
tags:
  - '#exec'
  - '#macos-platform'
date: '2026-10-30'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:f80ab2da1240f033bef401cdf706938f2b5114774860e1c52100a50fb5a5e3af'
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
- `S05` `M` `dev/packaging/native/product.py`
- `S05` `M` `native/desktop/scripts/frontend-install.mjs`
- `S05` `M` `dev/packaging/native/platforms/posix.py`
- `S05` `verify:` `build/macos-arm64/stage/Debug/app/bin/aeat --version` -> `pass`
- `S05` `verify:` `stage/Debug/app/cadrumo-manager --version` -> `pass`
- `S05` `by:` `vaultspec-high-executor`
- `S06` `A` `native/desktop/macos/bundle_launcher.c`
- `S06` `M` `native/platforms/macos-arm64.json`
- `S06` `M` `dev/packaging/native/layout.py`
- `S06` `A` `dev/packaging/native/macos_bundle.py`
- `S06` `M` `native/cmake/distribution/CMakeLists.txt`
- `S06` `M` `native/cmake/InstallerFlow.cmake`
- `S06` `verify:` `codesign --verify --strict --deep Cadrumo.app` -> `pass`
- `S06` `verify:` `open -n Cadrumo.app (window opens, LaunchServices md.neve.cadrumo)` -> `pass`
- `S06` `by:` `vaultspec-high-executor`

## Notes

- `S03` Baseline 396 failures reduced to 15 on rerun; remaining platform and in-progress failures fixed or already fixed by concurrent sessions; Chromium provisioned (581 MB)
- `S05` payload stage built by a parallel session's app-payload run in the shared build dir; relocation edits owned by that session
