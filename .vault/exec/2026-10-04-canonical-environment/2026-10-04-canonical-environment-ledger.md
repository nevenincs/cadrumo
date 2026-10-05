---
tags:
  - '#exec'
  - '#canonical-environment'
date: '2026-10-04'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:949891059d4f0774213da9148122040cd5cd2b988332c6d3e6f855423086d78d'
related:
  - "[[2026-10-04-canonical-environment-plan]]"
---

# `canonical-environment` ledger

## Changes

- `S01` `M` `src/cadrumo/core/storage_environment.py`
- `S01` `M` `src/cadrumo/core/storage_taxonomy.py`
- `S01` `M` `src/cadrumo/core/storage_taxonomy_locations.py`
- `S01` `M` `src/cadrumo/core/config_state_root.py`
- `S01` `M` `src/cadrumo/core/_config_runtime.py`
- `S01` `M` `src/cadrumo/core/config.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/main.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/profile_worker.py`
- `S01` `M` `src/cadrumo/core/tests/test_storage_environment.py`
- `S01` `A` `src/cadrumo/core/tests/test_storage_root_vectors.py`
- `S01` `M` `src/cadrumo/core/tests/test_config_state_root.py`
- `S01` `M` `src/cadrumo/core/tests/test_config.py`
- `S01` `M` `src/cadrumo/core/tests/test_output_dir_state_root.py`
- `S01` `M` `src/cadrumo/core/tests/test_storage_fingerprint_participation_gate.py`
- `S01` `M` `src/cadrumo/core/tests/test_settings_lifecycle_gate.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/tests/test_worker_storage_environment.py`
- `S01` `M` `env/.env.example`
- `S01` `M` `docs/reference/environment-overrides.md`
- `S01` `verify:` `uv run --no-sync python -m pytest src/cadrumo/core/tests src/cadrumo/tests/test_storage_provenance_gate.py (storage, settings, taxonomy, vector and installed-layout tests)` -> `pass`
- `S01` `verify:` `uv run --no-sync python -m pytest kdf supervision, profile worker, worker storage environment, CLI metadata contract, dev/docs env reference, dev/packaging native contract` -> `pass`
- `S01` `verify:` `uv run --no-sync python -m dev.quality.types (ty, pyrefly, basedpyright; no diagnostic in touched files)` -> `pass`
- `S01` `verify:` `dev.quality.import_gate (15 of 15 contracts kept, no finding in touched files)` -> `pass`
- `S01` `verify:` `ruff check and ruff format --check on touched files` -> `pass`
- `S01` `verify:` `WSL Ubuntu python3 installed-copy probe: XDG and HOME defaults, cwd independence, root mode 0o700` -> `pass`
- `S01` `by:` `implementation-engineer-high`
- `S01` `M` `src/cadrumo/core/storage_materialization.py`
- `S01` `M` `src/cadrumo/core/tests/test_ensure_storage_tree.py`
- `S01` `verify:` `WSL Ubuntu venv pytest test_ensure_storage_tree.py and test_storage_root_vectors.py (POSIX root 0o700, installed layout, undeclared platform)` -> `pass`
- `S01` `verify:` `uv run --no-sync python -m pytest storage, settings, ensure-tree, storage-management, worker, KDF and CLI metadata tests plus structural storage gates` -> `pass`
- `S02` `M` `dev/packaging/native/generate.py`
- `S02` `M` `dev/packaging/tests/test_native_storage_environment_contract.py`
- `S02` `M` `src/cadrumo/core/config.py`
- `S02` `M` `src/cadrumo/core/tests/test_storage_environment.py`
- `S02` `M` `native/CMakeLists.txt`
- `S02` `verify:` `95 focused tests incl schema 1 projection, contract.rs leak test, generator literal gate with planted defect` -> `pass`
- `S02` `verify:` `746 consumer tests local_runtime, settings and fingerprint gates, config_state_root, Linux worker launch` -> `pass`
- `S02` `verify:` `native/platform builds and tests against generated contract.rs` -> `pass`
- `S02` `verify:` `ruff, format, ty` -> `pass`
- `S02` `by:` `CADRUMO-BUILD-RUNTIME`
- `S04` `M` `native/desktop/src-tauri/src/python/environment.py`
- `S04` `M` `native/desktop/src-tauri/src/environment.rs`
- `S04` `M` `native/desktop/src-tauri/src/shell/mod.rs`
- `S04` `M` `native/desktop/src-tauri/src/terminal/tests/live.rs`
- `S04` `M` `native/CONTRACT.md`
- `S04` `verify:` `desktop cargo clippy --locked --all-targets -D warnings -D clippy::all, with and without live-package-tests, build/webview-desktop-host snapshot` -> `pass`
- `S04` `verify:` `desktop cargo test --locked without live tests (99, incl. relative webview projection refused)` -> `pass`
- `S04` `verify:` `desktop cargo test --locked --features live-package-tests against a copy of smoke kit app build 1911: 114 of 115, the failure is docs staged_documentation PackageUnavailable because the package has no docs/user` -> `fail`
- `S04` `verify:` `live relocated webview test: explicit root gives root joined with the contract subpath; absolute CADRUMO_WEBVIEW_DIR (operator_overridable) honoured` -> `pass`
- `S04` `verify:` `falsifier: HEAD environment.rs and environment.py (tool-cache join) fail the webview test; a literal storage/webview join fails the override assertion` -> `pass`
- `S04` `verify:` `ruff check and ruff format --check on python/environment.py; rustfmt --check on touched Rust files` -> `pass`
- `S04` `by:` `vaultspec-high-executor`

## Notes

- `S01` Allowlist narrowing deferred to S02 by orchestrator decision: `Settings.storage_env_var_names()` still returns product plus development tool names, because dev/packaging/native/generate.py requires `CADRUMO_TOOL_CACHE_DIR` in it; `development_tool_env_var_names()` and `product_env_var_names()` were added as additive accessors.
- `S01` `child_environment` passes host-inherited pins `CADRUMO_AUTHORITY_ROOT` and, on Windows, `XDG_CACHE_HOME` in both profiles, because the packaged pywin32 patch reads `XDG_CACHE_HOME` until S02 and S03 declare a successor (orchestrator-approved).
- `S01` Outside the S01 file list: the profile worker's owning test, env/.env.example, and the regenerated docs/reference/environment-overrides.md were updated because the new Settings field and the root pin required them.
- `S01` Root creation at mode 0o700 is wired into `prepare_temporary_directory` and `child_environment,` but not yet into `ensure_storage_tree` `(core/storage_materialization.py` is outside the S01 file list).
- `S01` `test_redaction_recorded_sequence_output::test_no_recorded_operator_line_is_rewritten_unless_it_carries_an_identity` exceeds the 300 s pytest timeout under current machine load. It is unrelated to this Step: it touches no storage or Settings code, and it passed at 218 s earlier in this session.
- `S01` Orchestrator rulings applied: outside-list files approved; `ensure_storage_tree` creates the root through `ensure_storage_root` with `STORAGE_ROOT.posix_directory_mode` `(STORAGE_ROOT_MODE` now reads the declaration); development mode resolves on any sys.platform and only the installed default refuses an undeclared platform.
- `S02` `TOOL_CACHE_ENV,` `TOOL_CACHE_DEFAULT` and legacy constants still emitted, now derived from declarations; S03 removes them with the pywin32 cache successor per the recorded packaging constraint
- `S02` CMake dry-run unsupported by the MSBuild generator; regeneration evidence is the build log from the declared `native_contract` OUTPUT and storage DEPENDS glob
- `S02` Committed by CADRUMO-BUILD-RUNTIME as 00f44b5ae1
- `S04` The desktop host no longer reads the development tool cache. HEAD native/platform/src/lib.rs still pins `XDG_CACHE_HOME` to the tool cache (S03 scope). The fixed query still names `STORAGE_ROOT_FIELD` and keeps `storage_root_disagreement;` those S04 items stay open.
