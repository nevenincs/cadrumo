---
tags:
  - '#exec'
  - '#runtime-manager-architecture'
date: '2026-10-04'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:4b7549b4efbe03ef926a1f78ce446ea3f902fff3d18f64231cd2fd9e78666bd7'
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

## Notes

- `S06` Repo-wide gates failed outside this Step: concurrent writers changed the governed tree mid-run and a hard finding in `test_censo_import_fact_payload.py;` check-types diagnostics name only other files while the shared .venv was being rebuilt. Mixed-owner files staged with only this Step's hunks.
- `S01` Exit reasons apply in every launch mode, not only under --supervised; the supervisor-contract ADR scope line reads 'Without that flag ... unchanged' and needs the operator's confirmation or a supervised gate in a later Step. Import gate could not complete (import-linter exit 127, stale targets, tree changed). Mixed files committed with only this Step's lines; the HEAD `test_login_lifecycle` case was already broken by another writer's pending rename.
- `S06` S06 content landed in commit 345b768233 (another session's commit swept the shared index); content verified identical to the staged Step.
- `S02` Integration residue (8 failures, 3 errors in automation approval, password rotation, refusal detail, projection pages, operation secret, modelo lifecycle) sits in modules carrying another writer's uncommitted custody and operations edits and touches no symbol this Step changed; not provable against HEAD in the shared tree. Heartbeat reports `hosted_profiles` as an upper bound for in-flight operations; exact counts added as a follow-on Step. Windows plain-interpreter dev launcher does not pass pipes through its relaunch; supervised mode targets the packaged single-process host.
- `S03` Import gate failed on stale `import_load_targets` metadata (another writer's uncommitted file), a mid-run tree change and two other workers' test files. Boot record registered as a taxonomy member only (no .runtime directory path definition, which would pull installation.json into scope); creation time is platform-native and can exceed 2^53 on Windows (the manager parses it as u64); package directory is null outside an installed package. Taxonomy files committed with only this Step's hunks.
- `S07` Part A only (crate, standalone Manager.cmake not yet included, identity projection of `manager_id` and `manager_name` with one owner for the Background Services suffix). Step stays open for Part B: include point after `add_subdirectory(application),` packaging declaration shared with the desktop S13 mechanism, assemble/verify/signing inventory, Windows version resource. No platform/application crate dependency until a Step needs it.
