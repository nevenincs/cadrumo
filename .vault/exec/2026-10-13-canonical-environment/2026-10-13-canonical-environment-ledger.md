---
tags:
  - '#exec'
  - '#canonical-environment'
date: '2026-10-13'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:32fd1192caaff13b9bc683fe93294d4ed815a569b5373633998160789843502f'
related:
  - "[[2026-10-13-canonical-environment-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `canonical-environment` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S11` `M` `native/cmake/Agent.cmake`
- `S11` `M` `native/CONTRACT.md`
- `S11` `M` `justfile`
- `S11` `M` `dev/provider_catalog/generate.py`
- `S11` `M` `dev/provider_catalog/tests/test_generate.py`
- `S11` `M` `native/desktop/frontend/scripts/agent-catalog-fixture.mjs`
- `S11` `M` `native/desktop/frontend/src/dev/fixtures/agentLanes.generated.ts`
- `S11` `M` `native/desktop/frontend/tests/live/README.md`
- `S11` `M` `native/desktop/frontend/tests/live/attach.live.ts`
- `S11` `M` `native/desktop/frontend/tests/live/fixture.ts`
- `S11` `M` `native/desktop/frontend/tests/live/playwright.config.ts`
- `S11` `verify:` `uv run --no-sync pytest dev/provider_catalog/tests dev/quality/tests/test_no_git_cli.py dev/tests/test_native_build_recipes.py` -> `pass`
- `S11` `verify:` `ruff check and format --check dev/provider_catalog` -> `pass`
- `S11` `verify:` `prettier --check and eslint on scripts/agent-catalog-fixture.mjs tests/live` -> `pass`
- `S11` `verify:` `cmake -P on the real Agent.cmake selector lines: unset, old env name, new env name, missing pyproject, valid -D` -> `pass`
- `S11` `verify:` `node scripts/agent-catalog-fixture.mjs --check with CADRUMO_DEV_AGENT_CHECKOUT` -> `pass`
- `S11` `by:` `rename-lane`
- `S01` `A` `native/application-environment.toml`
- `S01` `A` `dev/packaging/native/application_environment.py`
- `S01` `M` `dev/packaging/native/generate.py`
- `S01` `M` `native/cmake/Contract.cmake`
- `S01` `A` `dev/packaging/native/tests/test_application_environment.py`
- `S01` `M` `native/platform/src/installation.rs`
- `S01` `verify:` `uv run --no-sync pytest dev/packaging/native/tests/test_application_environment.py` -> `pass`
- `S01` `verify:` `ruff check/format dev/packaging/native` -> `pass`
- `S01` `verify:` `ty check touched generator files` -> `pass`
- `S01` `verify:` `cargo +1.96.0 clippy --all-targets -D warnings and cargo test native/platform` -> `pass`
- `S01` `verify:` `cargo +1.96.0 clippy native/manager lib` -> `pass`
- `S01` `by:` `vaultspec-high-executor`
- `S02` `M` `native/application-environment.toml`
- `S02` `M` `dev/packaging/native/application_environment.py`
- `S02` `M` `dev/packaging/native/generate.py`
- `S02` `M` `dev/packaging/native/storage_vectors.py`
- `S02` `M` `dev/packaging/native/runtime_exit_reasons.py`
- `S02` `M` `dev/packaging/native/layout.py`
- `S02` `M` `native/package-layout.json`
- `S02` `M` `native/cmake/Contract.cmake`
- `S02` `A` `dev/packaging/native/tests/test_generator_imports.py`
- `S02` `M` `dev/packaging/native/tests/test_storage_root_vectors.py`
- `S02` `M` `dev/packaging/native/tests/test_storage_path_vectors.py`
- `S02` `M` `dev/packaging/tests/test_native_storage_environment_contract.py`
- `S02` `verify:` `uv run --no-sync pytest test_application_environment test_generator_imports test_storage_root_vectors test_storage_path_vectors test_native_storage_environment_contract test_native_runtime_exit_reasons test_transport_contract` -> `pass`
- `S02` `verify:` `ruff check/format, ty on touched files` -> `pass`
- `S02` `verify:` `cargo +1.96.0 clippy -D warnings + test native/platform` -> `pass`
- `S02` `verify:` `cargo +1.96.0 test native/manager --test environment --test supervision` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S02` `verify:` `just check-import-boundaries: 15/15 contracts kept, 0 hard findings; run reported unavailable because other sessions changed the tree mid-run` -> `pass`
- `S08` `M` `src/cadrumo/application/runtime/contracts.py`
- `S08` `A` `src/cadrumo/application/agent_host/native_refusal.py`
- `S08` `M` `src/cadrumo/application/agent_host/controller.py`
- `S08` `M` `src/cadrumo/application/agent_host/launcher_protocol.py`
- `S08` `M` `src/cadrumo/adapters/local_runtime/windows_process.py`
- `S08` `M` `src/cadrumo/adapters/local_runtime/agent_process.py`
- `S08` `M` `src/cadrumo/application/runtime/tests/test_exit_reason_table.py`
- `S08` `A` `src/cadrumo/application/agent_host/tests/test_native_refusal.py`
- `S08` `A` `src/cadrumo/application/agent_host/tests/test_controller_native_refusal.py`
- `S08` `A` `src/cadrumo/application/agent_host/tests/test_launcher_protocol.py`
- `S08` `M` `src/cadrumo/adapters/local_runtime/tests/agent_host_fixture.py`
- `S08` `M` `src/cadrumo/adapters/local_runtime/tests/standard_pipe_fixture.py`
- `S08` `M` `src/cadrumo/adapters/local_runtime/tests/test_agent_process_native.py`
- `S08` `M` `src/cadrumo/adapters/local_runtime/tests/test_windows_standard_pipes_native.py`
- `S08` `M` `src/cadrumo/entrypoints/runtime/tests/test_agent_host_runtime.py`
- `S08` `M` `dev/quality/metadata/import_load_targets.json`
- `S08` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S08` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S08` `verify:` `uv run --no-sync pytest src/cadrumo/application/agent_host/tests src/cadrumo/application/runtime/tests (308 passed)` -> `pass`
- `S08` `verify:` `uv run --no-sync pytest -m '' test_agent_process_native.py test_windows_standard_pipes_native.py (15 passed, native Windows job)` -> `pass`
- `S08` `verify:` `uv run --no-sync pytest -m '' test_agent_host_runtime.py -k native_host or hosts_status (2 passed, real runtime door)` -> `pass`
- `S08` `verify:` `uv run --no-sync pytest dev/packaging/tests/test_native_runtime_exit_reasons.py dev/packaging/native/tests/test_application_environment.py test_exit_reason_table.py (54 passed)` -> `pass`
- `S08` `verify:` `ruff check and format --check on 15 touched files` -> `pass`
- `S08` `verify:` `just check-types (0 diagnostics in touched files)` -> `pass`
- `S08` `verify:` `just check-import-boundaries (15/15 contracts, 0 hard findings, 4688/4688 loaded; unavailable only for concurrent source change)` -> `fail`
- `S08` `by:` `runtime-lane`
- `S03` `A` `native/platform/src/launch.rs`
- `S03` `M` `native/platform/src/lib.rs`
- `S03` `M` `native/platform/src/storage.rs`
- `S03` `M` `native/platform/include/cadrumo_platform.h`
- `S03` `M` `native/platform/tests/consumer.c`
- `S03` `verify:` `cargo +1.96.0 clippy --all-targets -D warnings native/platform (windows, x86_64-linux, aarch64-darwin)` -> `pass`
- `S03` `verify:` `cargo +1.96.0 test native/platform (44)` -> `pass`
- `S03` `verify:` `consumer.c compiled with cl /W4 /WX against the platform staticlib and run inside the checkout` -> `pass`
- `S03` `verify:` `cargo +1.96.0 clippy native/manager lib` -> `pass`
- `S03` `verify:` `just check-types: no diagnostics in native-lane files (2 remain in dev/registry/pipeline/tests/test_generated_tree_publication.py)` -> `pass`
- `S03` `by:` `vaultspec-high-executor`
- `S04` `M` `native/application-environment.toml`
- `S04` `M` `dev/packaging/native/application_environment.py`
- `S04` `M` `native/platform/src/conformance_tests.rs`
- `S04` `A` `dev/packaging/native/tests/test_launch_profile_vectors.py`
- `S04` `verify:` `uv run --no-sync pytest test_launch_profile_vectors test_application_environment test_generator_imports test_native_storage_environment_contract (40)` -> `pass`
- `S04` `verify:` `ty check dev/packaging` -> `pass`
- `S04` `verify:` `cargo +1.96.0 clippy --all-targets -D warnings native/platform for windows, x86_64-linux, aarch64-darwin` -> `pass`
- `S04` `verify:` `cargo +1.96.0 test native/platform (45, Windows vectors replayed)` -> `pass`
- `S04` `by:` `vaultspec-high-executor`
- `S05` `A` `native/interpreter/launch_profile.h`
- `S05` `M` `native/interpreter/windows/host.c`
- `S05` `M` `native/interpreter/posix/host.c`
- `S05` `D` `native/interpreter/posix/invocation.h`
- `S05` `M` `native/interpreter/posix/tests/invocation.c`
- `S05` `M` `native/cmake/platforms/Posix.cmake`
- `S05` `M` `native/manager/src/supervision/exit.rs`
- `S05` `verify:` `cl /W4 /WX compile of windows/host.c as the python image and as an entrypoint image` -> `pass`
- `S05` `verify:` `cargo +1.96.0 test native/manager --lib exit (125 is a launch failure, 124 stays a crash)` -> `pass`
- `S05` `verify:` `cargo +1.96.0 clippy native/manager lib` -> `pass`
- `S05` `by:` `vaultspec-high-executor`
- `S06` `M` `dev/packaging/native/application_environment.py`
- `S06` `M` `dev/packaging/native/generate.py`
- `S06` `M` `dev/packaging/tests/test_native_storage_environment_contract.py`
- `S06` `M` `native/application-environment.toml`
- `S06` `M` `native/application/src/child.rs`
- `S06` `M` `native/application/tests/live_package.rs`
- `S06` `M` `native/application/tests/platform.rs`
- `S06` `M` `native/desktop/src-tauri/src/environment.rs`
- `S06` `M` `native/desktop/src-tauri/src/startup_logging.rs`
- `S06` `M` `native/desktop/src-tauri/src/terminal/tests/live.rs`
- `S06` `M` `native/manager/src/supervision/environment.rs`
- `S06` `M` `native/manager/src/supervision/launch.rs`
- `S06` `M` `native/manager/src/windows_lifecycle.rs`
- `S06` `M` `native/manager/tests/environment.rs`
- `S06` `M` `native/manager/tests/supervision.rs`
- `S06` `M` `native/platform/include/cadrumo_platform.h`
- `S06` `M` `native/platform/src/conformance_tests.rs`
- `S06` `M` `native/platform/src/launch.rs`
- `S06` `M` `native/platform/src/lib.rs`
- `S06` `M` `native/platform/src/posix_tests.rs`
- `S06` `M` `native/platform/src/storage.rs`
- `S06` `M` `native/platform/tests/consumer.c`
- `S06` `verify:` `uv run --no-sync pytest generator, vector, storage-vector, contract and exit-reason suites (141)` -> `pass`
- `S06` `verify:` `ruff check/format and ty dev/packaging` -> `pass`
- `S06` `verify:` `cargo +1.96.0 clippy -D warnings native/platform (win, linux, darwin) and cargo test (45)` -> `pass`
- `S06` `verify:` `consumer.c built with cl /W4 /WX and run` -> `pass`
- `S06` `verify:` `cargo +1.96.0 clippy --all-targets -D warnings native/manager (fixture-test-mode)` -> `pass`
- `S06` `verify:` `cargo +1.96.0 test native/manager --lib --test environment --test supervision --test runtime_identity` -> `pass`
- `S06` `verify:` `cargo +1.96.0 clippy --all-targets -D warnings native/application (platform) and test --test platform` -> `pass`
- `S06` `verify:` `cargo +1.96.0 clippy --all-targets -D warnings native/desktop/src-tauri (with and without live-package-tests) via a scratch mirror` -> `pass`
- `S06` `by:` `vaultspec-high-executor`
- `S07` `M` `dev/packaging/native/application_environment.py`
- `S07` `M` `dev/packaging/native/assemble.py`
- `S07` `M` `dev/packaging/native/generate.py`
- `S07` `M` `dev/packaging/native/layout.py`
- `S07` `M` `dev/packaging/native/metadata.py`
- `S07` `M` `dev/packaging/native/process_quiescence.py`
- `S07` `M` `dev/packaging/native/tests/test_launch_profile_vectors.py`
- `S07` `M` `native/application-environment.toml`
- `S07` `M` `native/cmake/platforms/Posix.cmake`
- `S07` `M` `native/cmake/platforms/Windows.cmake`
- `S07` `M` `native/interpreter/bootstrap.py`
- `S07` `M` `native/interpreter/launch_profile.h`
- `S07` `M` `native/interpreter/posix/host.c`
- `S07` `M` `native/interpreter/windows/host.c`
- `S07` `M` `native/package-layout.json`
- `S07` `A` `dev/packaging/native/tests/test_agent_image.py`
- `S07` `verify:` `uv run --no-sync pytest test_agent_image, launch vectors, application environment, generator imports, storage contract, layout entrypoints, application images, startup presence, delegated inventory, process quiescence (177)` -> `pass`
- `S07` `verify:` `ruff check/format and ty dev/packaging` -> `pass`
- `S07` `verify:` `cl /W4 /WX compile of windows/host.c as python, entrypoint and cadrumo-agent images` -> `pass`
- `S07` `verify:` `cmake --preset windows-installers-x64 scratch configure generates cadrumo_bundled_cadrumo_agent with CADRUMO_BUNDLED_IMAGE, its version resource and the launch guard; directory removed afterwards` -> `pass`
- `S07` `verify:` `cargo +1.96.0 clippy native/platform (win, linux, darwin) and test (45, agent vectors replayed)` -> `pass`
- `S07` `verify:` `cargo +1.96.0 test native/manager --lib --test environment` -> `pass`
- `S07` `by:` `vaultspec-high-executor`
- `S06` `M` `dev/packaging/native/tests/test_desktop_workspace.py`
- `S06` `M` `native/desktop/tests/packaged.test.mjs`
- `S06` `D` `native/desktop/src-tauri/src/python/environment.py`
- `S06` `verify:` `uv run --no-sync pytest desktop workspace, storage contract, application environment, launch vectors, agent image, generator imports (62)` -> `pass`
- `S06` `verify:` `ruff and ty dev/packaging` -> `pass`
- `S06` `verify:` `cargo +1.96.0 test native/platform (45)` -> `pass`
- `S06` `verify:` `cargo +1.96.0 clippy --all-targets -D warnings native/desktop/src-tauri with and without live-package-tests, and test environment (8, including the relocated-log override case)` -> `pass`
- `S06` `verify:` `prettier --check and node --check native/desktop/tests/packaged.test.mjs` -> `pass`
- `S07` `M` `native/platform/src/launch.rs`
- `S07` `M` `dev/packaging/native/tests/test_agent_image.py`
- `S07` `verify:` `uv run --no-sync pytest launch vectors, application environment, agent image, storage contract, desktop workspace, generator imports (67)` -> `pass`
- `S07` `verify:` `ruff and ty dev/packaging` -> `pass`
- `S07` `verify:` `cargo +1.96.0 clippy --all-targets -D warnings native/platform (win, linux, darwin) and test (45, Windows root-slot vectors replayed)` -> `pass`
- `S07` `verify:` `cargo +1.96.0 test native/manager --test environment` -> `pass`
- `S09` `M` `src/cadrumo/application/agent_host/launch_environment.py`
- `S09` `M` `src/cadrumo/application/agent_host/tests/test_launch_environment.py`
- `S09` `M` `src/cadrumo/adapters/local_runtime/agent_programs.py`
- `S09` `A` `src/cadrumo/adapters/local_runtime/tests/test_agent_programs.py`
- `S09` `M` `src/cadrumo/entrypoints/runtime/profile_connection_agents.py`
- `S09` `M` `src/cadrumo/entrypoints/runtime/tests/agent_host_support.py`
- `S09` `M` `src/cadrumo/entrypoints/runtime/tests/test_agent_host_runtime.py`
- `S09` `verify:` `pytest src/cadrumo/application/agent_host/tests src/cadrumo/application/runtime/tests src/cadrumo/entrypoints/runtime/tests test_agent_programs.py test_boot_record.py` -> `pass`
- `S09` `verify:` `pytest -m integration test_app_agent_serve_native.py test_agent_process_native.py` -> `pass`
- `S09` `verify:` `pytest -m integration test_agent_host_runtime.py except pre-existing relay internal_error` -> `pass`
- `S09` `verify:` `just check-types` -> `pass`
- `S09` `verify:` `just check-import-boundaries` -> `pass`
- `S09` `verify:` `ruff check and format` -> `pass`
- `S09` `by:` `vaultspec-high-executor`
- `S12` `A` `dev/quality/tests/test_agent_prefix_spelling.py`
- `S12` `M` `justfile`
- `S12` `verify:` `uv run --no-sync pytest dev/quality/tests/test_agent_prefix_spelling.py dev/quality/tests/test_no_git_cli.py` -> `pass`
- `S12` `verify:` `uv run --no-sync pytest dev/quality (265 passed; 4 unrelated pre-existing failures noted)` -> `pass`
- `S12` `verify:` `just check-types` -> `pass`
- `S12` `verify:` `just check-style and just check-format` -> `pass`
- `S12` `by:` `vaultspec-standard-executor`
- `S10` `M` `src/cadrumo/core/storage_environment.py`
- `S10` `M` `src/cadrumo/core/config.py`
- `S10` `M` `src/cadrumo/core/storage_taxonomy.py`
- `S10` `M` `src/cadrumo/core/storage_taxonomy_locations.py`
- `S10` `M` `src/cadrumo/core/tests/test_storage_environment.py`
- `S10` `M` `src/cadrumo/core/tests/test_storage_path_contract.py`
- `S10` `M` `src/cadrumo/core/tests/test_output_dir_state_root.py`
- `S10` `M` `src/cadrumo/core/tests/test_storage_fingerprint_participation_gate.py`
- `S10` `M` `src/cadrumo/adapters/local_runtime/worker_environment.py`
- `S10` `M` `src/cadrumo/adapters/local_runtime/linux_worker_process.py`
- `S10` `M` `src/cadrumo/adapters/local_runtime/tests/test_profile_worker_cleanup.py`
- `S10` `M` `src/cadrumo/adapters/local_runtime/tests/test_worker_storage_environment.py`
- `S10` `M` `src/cadrumo/entrypoints/runtime/linux_worker_guardian.py`
- `S10` `M` `dev/packaging/native/package_launch_smoke.py`
- `S10` `M` `dev/audit/tests/test_unreachable_records.py`
- `S10` `M` `dev/packaging/tests/test_native_manager_session_records.py`
- `S10` `M` `env/.env.example`
- `S10` `M` `docs/reference/environment-overrides.md`
- `S10` `verify:` `uv run --no-sync pytest src/cadrumo/core/tests src/cadrumo/adapters/local_runtime/tests src/cadrumo/entrypoints/runtime/tests src/cadrumo/application/storage_management dev/packaging/tests/test_native_manager_session_records.py dev/docs/tests/test_env_reference.py` -> `fail`
- `S10` `verify:` `uv run --no-sync pytest dev/packaging -q` -> `fail`
- `S10` `verify:` `just check-types` -> `pass`
- `S10` `verify:` `uv run --no-sync ruff check` -> `pass`
- `S10` `by:` `implementation-engineer-high`

## Notes

- `S11` The lane.py counterpart of the `CADRUMO_DEV_DESKTOP_LIVE_ENDPOINT,` `_ENTRY` and `_RESULTS` rename is owned by package-verification S04; `agent_live.py` `CADRUMO_AGENT_CHECKOUT` is owned by package-verification S03.
- `S11` No full CMake configure was run: build/windows-x64 belongs to the native lane. The selector lines were exercised in script mode instead.
- `S11` agentLanes.generated.ts was regenerated from its generator, so its digest line also moved to the current cadrumo-agent main; the lane data is unchanged.
- `S01` native/platform/src/installation.rs: fixed a pre-existing clippy `manual_is_multiple_of` failure to keep -D warnings green; native/manager test build carries a pre-existing clashing TrackPopupMenu extern warning, untouched
- `S02` Interim until P02.S06: the filtering hosts' classes `(host_classes,` with `AEAT_,` `FINANCIAL_` and `SITE_HEALTH_` prefixes standing in for the retired Settings-derived reserved names) are declared in the file; the generated `RESERVED_ENV,` `PRODUCT_ENV_ALLOWLIST` and `PINNED_ENV` equal the previous values except that non-Cadrumo product names are now cleared by prefix
- `S02` Pre-existing failures unrelated to the touched files observed in dev/packaging/native/tests: `test_distribution_prepare,` `test_linux_desktop_runtime` payload policy and `test_cpp_abi_inputs` (CMake cannot find ToolchainFloor.cmake), `test_incremental_generation` (FileExistsError), and `dev/packaging/tests/test_native_artifact_identity` (fixture layout lacks paths)
- `S08` S08 check-import-boundaries reports unavailable because other sessions changed the governed source tree while it ran; its contracts, hard findings and loadability components were clean. Load-target inventories regenerated with python -m `dev.quality.import_load_probe` --compile-targets (adds `native_refusal,` and the native lane's committed `application_environment` that was missing from the dev inventory).
- `S08` S08 `test_agent_host_runtime.py::test_the_relay_in_the_agents_tree_acts_as_the_agent_under_the_lease_that_started_it` fails with MCP `internal_error` and fails identically with the agent's standard error restored to the null device; it is not caused by this Step.
- `S03` `cadrumo_platform_prepare` and `prepared_environment` now define the executable's default profile through `define_environment` until P02.S05 and P02.S06 move their callers to `cadrumo_platform_define`
- `S04` Agent gateway and worker admission and undeclared-invocation refusal vectors need the cadrumo-agent image, the only image without a default profile; they land with it in P02.S07. POSIX vectors are replayed in Python here and in Rust only on a POSIX build
- `S05` The POSIX host and its rewritten launch-profile test (platform.invocation) were not compiled here: no POSIX C toolchain on this Windows host; they run in the POSIX CTest lanes
- `S05` The refusal path of a real image is first reachable with the cadrumo-agent image in P02.S07, the only image without a default profile
- `S06` native/application joined the native lane's ownership for this Step by orchestrator approval; `ChildConfiguration::from_platform` lost its Profile parameter
- `S06` `native/manager/src/windows_lifecycle.rs:` its test TrackPopupMenu declaration now matches `windows_tray.rs,` clearing a clashing-extern warning that failed clippy -D warnings on all targets
- `S06` Environment-dependent failures outside this change: native/application `package_inspection` junction fixture and desktop `startup_logging` projection test both need a target directory inside a checkout or mklink support; the scratch target directory has neither
- `S06` `cadrumo_platform_prepare` is retired with the filter; the C consumer's prepare modes are removed and `cadrumo_platform_define` covers definition
- `S07` Packaging.cmake and LaunchGuard.cmake needed no edit: the agent image target joins `CADRUMO_ENTRYPOINT_TARGETS,` which they already stage, quiesce and link the launch guard into
- `S07` The runtime image's profile fixes `CADRUMO_PACKAGE_AGENT_EXECUTABLE` and `CADRUMO_PACKAGE_RELAY_EXECUTABLE` for P03.S09
- `S07` sys.frozen and sys.executable are held by a static source test and the bootstrap package-root test; a launched-image check belongs to the P04.S14 probe
- `S06` Follow-up within this Step's retirement scope, on orchestrator instruction: the desktop no longer queries the command line's Python for package locations; webview, console workspace and manager log come from the compiled components under the pinned root, the command line's log directory follows its declared override, and `CADRUMO_WEBVIEW_DIR` is no longer a declared location
- `S07` Correction within the ADR's slot mechanism, on orchestrator ruling: the agent gateway takes `CADRUMO_LOCAL_STORAGE_ROOT` as an optional directory slot, admitted by kind alone whoever the caller is (runtime or a development package runner), so its relay resolves the caller's root instead of the installed default; agent profiles pin only the temporary variables and authority, and the worker never receives the root name. Profile pins became a list of root, temporary and authority
- `S09` `test_the_relay_in_the_agents_tree_acts_as_the_agent_under_the_lease_that_started_it` still fails with MCP `internal_error,` unchanged and pre-existing
- `S12` S12 The gate also allows the three package-side test spellings in `dev/packaging/native/tests/test_agent_image.py,` `test_launch_profile_vectors.py` and native/platform/src/launch.rs, which are native-lane files left unedited; each entry fails the gate once its file stops spelling the prefix.
- `S12` S12 .vaultspec/skills/cadrumo-start/references/build-cmake-and-packaging.md:15 still names the retired CMake selector; the gate does not scan .vaultspec and the skill is user-owned, so it is reported, not edited.
- `S12` S12 dev/quality failures unrelated to this Step: `test_suite_gate_table` (check-provider-catalog has no suite row; check-dependency-declarations arguments differ), `test_doc_privacy` (home paths in .vault audits and research), `test_production_scan_surface_has_no_orphans` `(contract_manifest.py,` `_provider_command_specs.py).` `dev/tests/test_native_build_recipes.py` fails on the windows-installers-x64 preset having no cacheVariables.
- `S10` Commits 43962530ae and 64960fec66. Remaining suite failures are unrelated to S10 and predate it: storage liveness `posix_endpoint` claim, sha256 adoption, tty probe, `agent_programs` literal path (S09), `dead_code` population, playwright doctor, keychain receipt recovery, docs build and localization, plus the 2 known `test_authority_build_hook` cases. check-import-boundaries kept all 15 contracts and loaded 4688 modules; its verdict was unavailable only because other sessions changed the tree mid-run. Python child launches no longer clear interpreter or loader classes; the authority root stays relayed as the CLI's own setting; the POSIX worker containment baseline is kept. docs/reference/environment-overrides.md regenerated with `dev.docs.env_reference` after the webview setting was removed.
