---
tags:
  - '#exec'
  - '#runtime-manager-architecture'
date: '2026-10-04'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:11ee0e020340c68f1ae76dddcd98f2aa9f9551c1ec55dcbd638fab9d3707bcc8'
related:
  - "[[2026-10-04-runtime-manager-architecture-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `runtime-manager-architecture` ledger

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

- `S06` `R` `src/cadrumo/adapters/local_runtime/manager_commands.py` -> `src/cadrumo/adapters/local_runtime/containment_commands.py`
- `S06` `R` `src/cadrumo/adapters/local_runtime/tests/test_manager_command_sync.py` -> `src/cadrumo/adapters/local_runtime/tests/test_containment_command_sync.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/linux_worker_process.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/macos_worker_process.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/tests/test_linux_worker_containment.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/tests/test_macos_worker_containment.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/tests/test_macos_worker_process.py`
- `S06` `M` `src/cadrumo/entrypoints/runtime/tests/linux_worker_parent_fixture.py`
- `S06` `M` `src/cadrumo/entrypoints/runtime/tests/macos_worker_parent_fixture.py`
- `S06` `M` `src/cadrumo/entrypoints/runtime/tests/test_linux_worker_launch_contract.py`
- `S06` `M` `dev/quality/metadata/import_load_targets.json`
- `S06` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S06` `verify:` `focused pytest (5 files) 73 passed 19 platform-skipped` -> `pass`
- `S06` `verify:` `ruff check and format --check on touched files` -> `pass`
- `S06` `verify:` `ty check touched files win32 linux darwin` -> `pass`
- `S06` `verify:` `just check-import-boundaries` -> `fail`
- `S06` `verify:` `just check-types` -> `fail`
- `S01` `M` `dev/packaging/native/generate.py`
- `S01` `A` `dev/packaging/native/runtime_exit_reasons.py`
- `S01` `A` `dev/packaging/tests/test_native_runtime_exit_reasons.py`
- `S01` `M` `native/CMakeLists.txt`
- `S01` `M` `src/cadrumo/application/runtime/contracts.py`
- `S01` `A` `src/cadrumo/application/runtime/tests/test_exit_reason_table.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/main.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/profile_connections.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/shutdown.py`
- `S01` `A` `src/cadrumo/entrypoints/runtime/tests/test_exit_reasons.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_installed_runtime.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_login_lifecycle.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_shutdown_watchdog.py`
- `S01` `verify:` `exit-table, generator projection, watchdog and contracts pytest 51 passed` -> `pass`
- `S01` `verify:` `runtime and packaging unit suites 324 passed 1 skipped` -> `pass`
- `S01` `verify:` `installed runtime exits 67 68 69 71 observed` -> `pass`
- `S01` `verify:` `ruff check and format --check` -> `pass`
- `S01` `verify:` `ty win32 linux darwin; basedpyright and pyrefly on contracts.py` -> `pass`
- `S01` `verify:` `cargo check and cargo test native/platform against generated contract.rs` -> `pass`
- `S01` `verify:` `python -m dev.quality.import_gate` -> `fail`
- `S06` `M` `src/cadrumo/adapters/local_runtime/containment_commands.py`
- `S02` `A` `src/cadrumo/entrypoints/runtime/supervised_protocol.py`
- `S02` `A` `src/cadrumo/entrypoints/runtime/supervised_channel.py`
- `S02` `A` `src/cadrumo/entrypoints/runtime/tests/test_supervised_protocol.py`
- `S02` `A` `src/cadrumo/entrypoints/runtime/tests/test_supervised_channel.py`
- `S02` `A` `src/cadrumo/entrypoints/runtime/tests/test_supervised_runtime.py`
- `S02` `A` `src/cadrumo/entrypoints/runtime/tests/supervised_streams_fixture.py`
- `S02` `M` `src/cadrumo/entrypoints/runtime/main.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/server.py`
- `S02` `M` `src/cadrumo/entrypoints/runtime/profile_connections.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/login_policy.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/tests/test_login_policy.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/tests/test_server.py`
- `S02` `verify:` `focused supervised, server and login-policy pytest 71 passed` -> `pass`
- `S02` `verify:` `installed runtime and exit-reason tests 11 passed 2 platform-skipped` -> `pass`
- `S02` `verify:` `runtime suites -m unit 876 passed 10 skipped` -> `pass`
- `S02` `verify:` `descendant-channel negative control fails with rewiring disabled` -> `pass`
- `S02` `verify:` `ruff check and format --check; ty win32 linux darwin` -> `pass`
- `S02` `verify:` `runtime suites -m integration` -> `fail`
- `S02` `verify:` `just check-import-boundaries` -> `fail`
- `S03` `A` `src/cadrumo/adapters/local_runtime/boot_record.py`
- `S03` `A` `src/cadrumo/adapters/local_runtime/tests/test_boot_record.py`
- `S03` `M` `src/cadrumo/entrypoints/runtime/supervised_channel.py`
- `S03` `M` `src/cadrumo/entrypoints/runtime/main.py`
- `S03` `M` `src/cadrumo/entrypoints/runtime/tests/test_supervised_channel.py`
- `S03` `M` `src/cadrumo/entrypoints/runtime/tests/test_supervised_runtime.py`
- `S03` `M` `src/cadrumo/entrypoints/runtime/tests/test_installed_runtime.py`
- `S03` `M` `src/cadrumo/core/storage_taxonomy.py`
- `S03` `M` `src/cadrumo/core/storage_taxonomy_locations.py`
- `S03` `verify:` `focused boot-record, supervised, installation and storage gate pytest 141 passed 2 skipped` -> `pass`
- `S03` `verify:` `Windows creation time checked against GetProcessTimes` -> `pass`
- `S03` `verify:` `ruff check and format --check; ty win32 linux darwin` -> `pass`
- `S03` `verify:` `just check-persistence-write-paths; just check-module-reachability` -> `pass`
- `S03` `verify:` `just check-import-boundaries` -> `fail`
- `S07` `A` `native/manager/Cargo.toml`
- `S07` `A` `native/manager/Cargo.lock`
- `S07` `A` `native/manager/build.rs`
- `S07` `A` `native/manager/src/lib.rs`
- `S07` `A` `native/manager/src/identity.rs`
- `S07` `A` `native/manager/src/main.rs`
- `S07` `A` `native/manager/tests/entrypoint.rs`
- `S07` `A` `native/cmake/Manager.cmake`
- `S07` `M` `dev/packaging/native/identity.py`
- `S07` `M` `dev/packaging/tests/test_distribution_identity.py`
- `S07` `verify:` `cargo build, test (8), clippy -D warnings, fmt --check in native/manager` -> `pass`
- `S07` `verify:` `windows_manifest check on built exe; dumpbin DependentLoadFlags 0x800 and GUI subsystem` -> `pass`
- `S07` `verify:` `image tests fail on a scratch build without 0x800 or windows_subsystem` -> `pass`
- `S07` `verify:` `identity pytest 69 passed 2 skipped; ruff; ty` -> `pass`
- `S05` `M` `src/cadrumo/entrypoints/runtime/main.py`
- `S05` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py`
- `S05` `M` `src/cadrumo/adapters/outbound/browser_runtime/installer.py`
- `S05` `A` `src/cadrumo/core/child_console.py`
- `S05` `A` `src/cadrumo/adapters/local_runtime/windows_token_elevation.py`
- `S05` `A` `src/cadrumo/core/tests/test_child_console.py`
- `S05` `A` `src/cadrumo/adapters/local_runtime/tests/test_windows_token_elevation.py`
- `S05` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/kdf_console_fixture.py`
- `S05` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_child_console.py`
- `S05` `A` `src/cadrumo/entrypoints/runtime/tests/console_interrupt_fixture.py`
- `S05` `A` `src/cadrumo/entrypoints/runtime/tests/test_console_interrupt.py`
- `S05` `M` `src/cadrumo/adapters/outbound/browser_runtime/tests/test_installer.py`
- `S05` `M` `src/cadrumo/entrypoints/runtime/tests/supervised_streams_fixture.py`
- `S05` `M` `src/cadrumo/entrypoints/runtime/tests/test_supervised_runtime.py`
- `S05` `verify:` `console interrupt and supervised runtime pytest 12 passed` -> `pass`
- `S05` `verify:` `focused child-console, elevation, KDF console pytest 29 passed 1 skipped` -> `pass`
- `S05` `verify:` `Ctrl+C negative control (re-enable removed keeps serving)` -> `pass`
- `S05` `verify:` `ruff check and format --check; ty win32 linux darwin on touched files` -> `pass`
- `S05` `verify:` `just check-module-reachability` -> `pass`
- `S05` `verify:` `just check-types` -> `fail`
- `S05` `verify:` `just check-import-boundaries` -> `fail`
- `S09` `M` `native/manager/Cargo.toml`
- `S09` `M` `native/manager/Cargo.lock`
- `S09` `M` `native/manager/src/lib.rs`
- `S09` `A` `native/manager/src/contract.rs`
- `S09` `A` `native/manager/src/supervision.rs`
- `S09` `A` `native/manager/src/supervision/adoption.rs`
- `S09` `A` `native/manager/src/supervision/boot_record.rs`
- `S09` `A` `native/manager/src/supervision/environment.rs`
- `S09` `A` `native/manager/src/supervision/exit.rs`
- `S09` `A` `native/manager/src/supervision/json.rs`
- `S09` `A` `native/manager/src/supervision/launch.rs`
- `S09` `A` `native/manager/src/supervision/process.rs`
- `S09` `A` `native/manager/src/supervision/protocol.rs`
- `S09` `A` `native/manager/src/supervision/restart.rs`
- `S09` `A` `native/manager/src/supervision/stop.rs`
- `S09` `A` `native/manager/src/supervision/supervisor.rs`
- `S09` `A` `native/manager/src/supervision/windows.rs`
- `S09` `A` `native/manager/tests/supervision.rs`
- `S09` `A` `native/manager/tests/protocol_conformance.rs`
- `S09` `A` `native/manager/tests/protocol_vectors.json`
- `S09` `A` `native/manager/tests/fixture/runtime.rs`
- `S09` `A` `dev/packaging/tests/test_native_manager_protocol.py`
- `S09` `verify:` `cargo fmt --check; build --locked debug and release; clippy -D warnings with and without fixture-test-mode and for linux target` -> `pass`
- `S09` `verify:` `cargo test --locked 35 unit 5 entrypoint 7 conformance` -> `pass`
- `S09` `verify:` `fixture-test-mode supervision tests 21 passed on three consecutive runs` -> `pass`
- `S09` `verify:` `release build with fixture-test-mode refused` -> `pass`
- `S09` `verify:` `negative controls (env_clear, creation-time check, Ctrl+C handler) fail as expected` -> `pass`
- `S09` `verify:` `shared protocol vectors pytest 13 passed; ruff; ty` -> `pass`
- `S07` `M` `native/platforms/windows-x64.json`
- `S07` `M` `native/CMakeLists.txt`
- `S07` `M` `native/CONTRACT.md`
- `S07` `M` `native/cmake/Manager.cmake`
- `S07` `M` `native/manager/build.rs`
- `S07` `A` `native/manager/tests/version_resource.rs`
- `S07` `verify:` `configure stages cadrumo-manager.exe from rust_manager` -> `pass`
- `S07` `verify:` `rust_manager Release build with manifest check; CTest manager.rust and manager.supervision` -> `pass`
- `S07` `verify:` `version-resource falsifiers fail without the resource link or with a wrong ProductName` -> `pass`
- `S07` `verify:` `clippy -D warnings with and without fixture-test-mode; rustfmt --check` -> `pass`
- `S07` `verify:` `application_images pytest 33 passed` -> `pass`
- `S07` `verify:` `verify 13/13 and verify-package (staged, hashed, not startup, CADRUMO Background Services 0.5.1)` -> `pass`

## Notes

- `S06` Repo-wide gates failed outside this Step: concurrent writers changed the governed tree mid-run and a hard finding in `test_censo_import_fact_payload.py;` check-types diagnostics name only other files while the shared .venv was being rebuilt. Mixed-owner files staged with only this Step's hunks.
- `S01` Exit reasons apply in every launch mode, not only under --supervised; the supervisor-contract ADR scope line reads 'Without that flag ... unchanged' and needs the operator's confirmation or a supervised gate in a later Step. Import gate could not complete (import-linter exit 127, stale targets, tree changed). Mixed files committed with only this Step's lines; the HEAD `test_login_lifecycle` case was already broken by another writer's pending rename.
- `S06` S06 content landed in commit 345b768233 (another session's commit swept the shared index); content verified identical to the staged Step.
- `S02` Integration residue (8 failures, 3 errors in automation approval, password rotation, refusal detail, projection pages, operation secret, modelo lifecycle) sits in modules carrying another writer's uncommitted custody and operations edits and touches no symbol this Step changed; not provable against HEAD in the shared tree. Heartbeat reports `hosted_profiles` as an upper bound for in-flight operations; exact counts added as a follow-on Step. Windows plain-interpreter dev launcher does not pass pipes through its relaunch; supervised mode targets the packaged single-process host.
- `S03` Import gate failed on stale `import_load_targets` metadata (another writer's uncommitted file), a mid-run tree change and two other workers' test files. Boot record registered as a taxonomy member only (no .runtime directory path definition, which would pull installation.json into scope); creation time is platform-native and can exceed 2^53 on Windows (the manager parses it as u64); package directory is null outside an installed package. Taxonomy files committed with only this Step's hunks.
- `S07` Part A only (crate, standalone Manager.cmake not yet included, identity projection of `manager_id` and `manager_name` with one owner for the Background Services suffix). Step stays open for Part B: include point after `add_subdirectory(application),` packaging declaration shared with the desktop S13 mechanism, assemble/verify/signing inventory, Windows version resource. No platform/application crate dependency until a Step needs it.
- `S05` check-types failures are in other writers' operations, aggregation and `server_connection_handling` files. Import gate: two foreign private imports and stale `import_load_targets` metadata (shared, held by another writer; needs just generate-import-load-targets to include `core.child_console` and `local_runtime.windows_token_elevation).` A full elevated token is not available on this host; the refusal is proven by a faked token read. The supervised flag reaches spawners through `core.process_binding.ProcessScopedBinding.` Finding for the manager: a runtime launched without -I on Windows relaunches through subprocess.run on the same console, so a Ctrl+C kills it without draining; the manager must launch the packaged single-process host.
- `S09` Exit reasons come from the generated contract.rs via `include!(env!(CADRUMO_CONTRACT_RS));` the CMake build of the manager needs Part B's Manager.cmake wiring (not yet included in native/CMakeLists, so the bundle is unaffected). ADR stop-delivery hypothesis corrected: the Ctrl+C handler must be registered after AttachConsole (a handler installed before attach does not apply to a console-less process), kept for the whole attachment, removed after FreeConsole. `unsafe_code` changed from forbid to deny with allows only in supervision/windows.rs, the POSIX kill module and the fixture. Interim fixed environment allow-list until S08; Windows-only fixture coverage; a foreign runtime is final for run() in this Step.
- `S07` Part B closes the Step. Fixed a Part A Manager.cmake defect that split escaped LIB/INCLUDE semicolons. Fixture target dir is `CADRUMO_PATH_CARGO/manager-fixture` inside the declared cargo output. ProductName is the channel display name (CADRUMO Preview on preview). Signing gap: signed=true is validated only; no signing inventory exists in packaging. CompanyName omitted pending a publisher projection. Desktop packaging path not exercised (docs off).
