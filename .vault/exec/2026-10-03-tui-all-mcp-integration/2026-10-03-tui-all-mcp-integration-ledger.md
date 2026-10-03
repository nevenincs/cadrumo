---
tags:
  - '#exec'
  - '#tui-all-mcp-integration'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:1f2cb5dc3872d43a5dbe33aea26abaf4add7cc4c7ea2f0a395f55b5886e45171'
related:
  - "[[2026-10-03-tui-all-mcp-integration-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `tui-all-mcp-integration` ledger

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

- `S01` `M` `src/cadrumo/application/command_search/index.py`
- `S01` `M` `src/cadrumo/application/corpus_search/runtime.py`
- `S01` `M` `src/cadrumo_harness/mcp/admitted_operations.py`
- `S01` `M` `src/cadrumo_harness/mcp/protocol_contract.py`
- `S01` `M` `src/cadrumo_harness/mcp/runtime_adapter.py`
- `S01` `M` `docs/how-to/connect-an-agent.md`
- `S01` `A` `src/cadrumo_harness/mcp/corpus_query.py`
- `S01` `A` `src/cadrumo_harness/mcp/operation_search.py`
- `S01` `A` `src/cadrumo_harness/mcp/tests/test_corpus_search_tool.py`
- `S01` `A` `src/cadrumo_harness/mcp/tests/test_operation_search_tool.py`
- `S01` `A` `src/cadrumo_harness/mcp/tests/test_runtime_authority.py`
- `S01` `verify:` `MCP/search discovery and authority-pinning cohort82tests` -> `pass`
- `S01` `verify:` `changed discovery source Ruff and format` -> `pass`
- `S01` `by:` `history`
- `S01` `M` `conftest.py`
- `S01` `D` `src/cadrumo_harness/mcp/tests/conftest.py`
- `S01` `verify:` `MCP82tests after repository fixture relocation` -> `pass`
- `S02` `M` `src/cadrumo/adapters/local_runtime/linux_gnome_installation.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/linux_gnome_lock.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/linux_worker_process.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/macos_coalition.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/macos_process.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/macos_worker_process.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/manager_commands.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/posix.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/posix_channel.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/posix_endpoint.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/profile_worker.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/profile_worker_lifetime.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/profile_worker_transport.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/tests/macos_peer_exec_fixture.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/tests/macos_test_process.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/tests/profile_worker_support.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/tests/test_linux_gnome_installation.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/tests/test_linux_gnome_lock.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/tests/test_macos_coalition.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/tests/test_macos_peer_process_version_native.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/tests/test_macos_process.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/tests/test_macos_process_incarnation.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/tests/test_macos_worker_containment.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/tests/test_macos_worker_process.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/tests/test_posix_peer_liveness.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/tests/test_windows_process_cleanup.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/tests/test_worker_arguments.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/tests/windows_inheritance_fixture.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/worker_arguments.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/worker_authorization_client.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/worker_authorization_lease.py`
- `S02` `A` `src/cadrumo/adapters/local_runtime/worker_environment.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/worker_native_identity.py`
- `S02` `M` `src/cadrumo/adapters/local_runtime/worker_transport.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/_capsule_filesystem.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/_filesystem_records.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_attestation.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_worker_identity.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/automation_control_projection.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/capsule.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/filesystem.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/filesystem_primitives.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/gnome_collection_protection.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py`
- `S02` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/test_atomic_rename_primitives.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_gnome_collection_protection.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py`
- `S02` `M` `src/cadrumo/entrypoints/runtime/linux_worker_guardian.py`
- `S02` `A` `src/cadrumo/entrypoints/runtime/macos_worker_guardian.py`
- `S02` `M` `src/cadrumo/entrypoints/runtime/tests/linux_worker_parent_fixture.py`
- `S02` `A` `src/cadrumo/entrypoints/runtime/tests/macos_worker_parent_fixture.py`
- `S02` `M` `src/cadrumo/entrypoints/runtime/tests/test_linux_worker_launch_contract.py`
- `S02` `A` `src/cadrumo/entrypoints/runtime/tests/test_macos_worker_guardian.py`
- `S02` `M` `src/cadrumo/entrypoints/runtime/tests/test_worker_exit_cleanup.py`
- `S02` `M` `src/cadrumo/entrypoints/runtime/worker.py`
- `S02` `A` `.codex/handoffs/tui-all-mcp-dispositions-platform.json`
- `S02` `verify:` `Mac native containment and peer11tests` -> `pass`
- `S02` `verify:` `Mac final sharedfixture2tests` -> `pass`
- `S02` `verify:` `Mac atomic rename and supervised KDF cohort` -> `pass`
- `S02` `verify:` `Portable platform cohorts120plus130plus79` -> `pass`
- `S02` `verify:` `Platform source Ruff format and ty3platforms` -> `pass`
- `S02` `verify:` `Native locked-Keychain needs-user refusal1test` -> `pass`
- `S02` `by:` `platform`

## Notes

- `S02` Protected Keychain positive round trips unavailable in locked login context; unchanged Keychain provider requires unlocked native verification under S05. No protected-store success claimed.
