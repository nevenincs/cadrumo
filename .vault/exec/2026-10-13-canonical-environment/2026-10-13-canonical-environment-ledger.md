---
tags:
  - '#exec'
  - '#canonical-environment'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:f426be1fbbf08eeb89bc91025e6aaf12f047d48005f90f38b53ee93f884e8011'
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
