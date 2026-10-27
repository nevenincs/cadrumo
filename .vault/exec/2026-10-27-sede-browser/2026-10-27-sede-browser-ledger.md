---
tags:
  - '#exec'
  - '#sede-browser'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:1dad7883f124d745f37e50cbb0e8d181a3251d1de72bf44ef2f49b71d1eb1d0c'
related:
  - "[[2026-10-27-sede-browser-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `sede-browser` ledger

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

- `S01` `M` `src/cadrumo_client/transport/frame_io.py`
- `S01` `A` `src/cadrumo_client/transport/view_stream.py`
- `S01` `A` `src/cadrumo_client/contracts/view_stream.py`
- `S01` `A` `src/cadrumo_client/contracts/tests/view_stream_vector_source.py`
- `S01` `A` `src/cadrumo_client/contracts/tests/view_stream_vectors.json`
- `S01` `A` `src/cadrumo_client/contracts/tests/test_view_stream_documents.py`
- `S01` `A` `src/cadrumo_client/transport/tests/test_view_stream.py`
- `S01` `M` `dev/quality/metadata/import_load_targets.cadrumo_client.json`
- `S01` `verify:` `uv run --no-sync pytest src/cadrumo_client/transport/tests src/cadrumo_client/contracts/tests` -> `pass`
- `S01` `verify:` `uv run --no-sync python -m cadrumo_client.contracts.tests.view_stream_vector_source --check` -> `pass`
- `S01` `verify:` `ruff check and ruff format --check on touched files` -> `pass`
- `S01` `verify:` `ty check on touched files` -> `pass`
- `S01` `verify:` `uv run --no-sync lint-imports --config .importlinter --no-cache` -> `pass`
- `S01` `by:` `high-implementation`
- `S05` `M` `src/cadrumo/application/auth/sessions.py`
- `S05` `M` `src/cadrumo/application/auth/protocols.py`
- `S05` `M` `src/cadrumo/application/live/session.py`
- `S05` `M` `src/cadrumo/adapters/outbound/aeat/auth/authenticator.py`
- `S05` `M` `src/cadrumo/adapters/outbound/aeat/auth/session_store.py`
- `S05` `A` `src/cadrumo/adapters/outbound/aeat/auth/tests/test_view_session_custody.py`
- `S05` `verify:` `uv run --no-sync pytest src/cadrumo/application/auth/tests src/cadrumo/application/live/tests -k view-or-session` -> `pass`
- `S05` `verify:` `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/auth/tests/test_view_session_custody.py -m all` -> `pass`
- `S05` `verify:` `just check-style` -> `pass`
- `S05` `verify:` `just check-format` -> `pass`
- `S05` `verify:` `lint-imports --config .importlinter --no-cache` -> `pass`
- `S05` `by:` `implementation-engineer-high`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/session.py`
- `S04` `A` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_view_context.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_terminal_preconditions.py`
- `S04` `D` `src/cadrumo/adapters/outbound/aeat/browser/request_guard.py`
- `S04` `D` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_request_guard.py`
- `S04` `D` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_view_context_guard.py`
- `S04` `M` `src/cadrumo/core/remote_authority.py`
- `S04` `M` `src/cadrumo/domain/calculations/registry/tests/test_remote_authority_canonicalisation.py`
- `S04` `M` `dev/quality/metadata/import_load_targets.json`
- `S04` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S04` `verify:` `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/browser/tests src/cadrumo/domain/calculations/registry/tests -k "guard or view"` -> `pass`
- `S04` `verify:` `uv run --no-sync ruff check and ruff format --check on scope` -> `pass`
- `S04` `verify:` `uv run --no-sync ty check on scope` -> `pass`
- `S04` `verify:` `uv run --no-sync lint-imports --config .importlinter --no-cache` -> `pass`
- `S04` `by:` `implementation-engineer-high`
- `S02` `A` `src/cadrumo_runtime/host/view_stream_relay.py`
- `S02` `A` `src/cadrumo_runtime/host/worker_view_stream.py`
- `S02` `A` `src/cadrumo_runtime/host/tests/test_view_stream_relay.py`
- `S02` `M` `src/cadrumo_runtime/host/worker.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_operations.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connections.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_sessions.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_access.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_drain.py`
- `S02` `M` `src/cadrumo_runtime/adapters/server_connection_handling.py`
- `S02` `M` `src/cadrumo_runtime/adapters/worker_native_identity.py`
- `S02` `M` `src/cadrumo_runtime/adapters/profile_worker_lifetime.py`
- `S02` `M` `src/cadrumo_runtime/contracts/profile_host.py`
- `S02` `M` `src/cadrumo_client/contracts/view_stream.py`
- `S02` `M` `src/cadrumo_client/contracts/profile_access.py`
- `S02` `M` `dev/quality/metadata/import_load_targets.cadrumo_runtime.json`
- `S02` `verify:` `uv run --no-sync pytest src/cadrumo_runtime/host/tests/test_view_stream_relay.py -m '' -n 0` -> `pass`
- `S02` `verify:` `uv run --no-sync pytest src/cadrumo_runtime/host/tests -k view -m 'integration and not windows_only'` -> `fail`
- `S02` `verify:` `uv run --no-sync pytest src/cadrumo_runtime/host/tests -k view` -> `fail`
- `S02` `verify:` `just check-style` -> `pass`
- `S02` `verify:` `just check-format` -> `pass`
- `S02` `verify:` `just check-types` -> `fail`
- `S02` `verify:` `just check-import-boundaries` -> `fail`
- `S02` `by:` `implementation-engineer-high`
- `S06` `A` `src/cadrumo/adapters/outbound/aeat/browser/screencast.py`
- `S06` `A` `src/cadrumo/adapters/outbound/aeat/browser/view_input.py`
- `S06` `A` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_screencast.py`
- `S06` `A` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_view_input.py`
- `S06` `A` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_view_adapters_no_script.py`
- `S06` `A` `src/cadrumo/adapters/outbound/aeat/browser/tests/view_page_support.py`
- `S06` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S06` `verify:` `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/browser/tests -k "screencast or input"` -> `pass`
- `S06` `verify:` `ruff check and ruff format --check on the six files` -> `pass`
- `S06` `verify:` `ty check on the six files` -> `pass`
- `S06` `verify:` `lint-imports --config .importlinter --no-cache` -> `pass`
- `S06` `by:` `sonnet-executor`
- `S15` `A` `src/cadrumo_client/contracts/view_transfer.py`
- `S15` `M` `src/cadrumo_client/transport/view_stream.py`
- `S15` `M` `src/cadrumo_client/contracts/tests/view_stream_vector_source.py`
- `S15` `M` `src/cadrumo_client/contracts/tests/view_stream_vectors.json`
- `S15` `M` `src/cadrumo_client/contracts/tests/test_view_stream_documents.py`
- `S15` `M` `src/cadrumo_client/transport/tests/test_view_stream.py`
- `S15` `M` `dev/quality/metadata/import_load_targets.cadrumo_client.json`
- `S15` `verify:` `uv run --no-sync pytest src/cadrumo_client/transport/tests src/cadrumo_client/contracts/tests` -> `pass`
- `S15` `verify:` `uv run --no-sync python -m cadrumo_client.contracts.tests.view_stream_vector_source --check` -> `pass`
- `S15` `verify:` `ruff check and ruff format --check on the five source and test files` -> `pass`
- `S15` `verify:` `ty check on the five files; basedpyright and pyrefly on contracts/view_transfer.py` -> `pass`
- `S15` `verify:` `lint-imports --config .importlinter --no-cache` -> `pass`
- `S15` `verify:` `uv run --no-sync pytest src/cadrumo_runtime/host/tests/test_view_stream_relay.py -m ''` -> `pass`
- `S15` `by:` `implementation-engineer-standard`
- `S07` `A` `src/cadrumo/adapters/outbound/aeat/browser/sede_view.py`
- `S07` `A` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_sede_view_page.py`
- `S07` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_view_adapters_no_script.py`
- `S07` `M` `src/cadrumo/adapters/outbound/aeat/browser/session.py`
- `S07` `M` `src/cadrumo/adapters/outbound/aeat/browser/view_input.py`
- `S07` `M` `src/cadrumo/adapters/outbound/aeat/auth/authenticator.py`
- `S07` `M` `src/cadrumo/application/auth/sessions.py`
- `S07` `A` `src/cadrumo/application/live/sede_view_ports.py`
- `S07` `A` `src/cadrumo/application/live/sede_view_operation.py`
- `S07` `A` `src/cadrumo/application/live/tests/test_sede_view_operation.py`
- `S07` `M` `src/cadrumo/application/operations/access_facts.py`
- `S07` `M` `src/cadrumo/application/operations/person_acts.py`
- `S07` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S07` `M` `src/cadrumo_client/contracts/view_stream.py`
- `S07` `M` `src/cadrumo_client/contracts/view_transfer.py`
- `S07` `M` `src/cadrumo_client/contracts/tests/view_stream_vector_source.py`
- `S07` `M` `src/cadrumo_client/contracts/tests/view_stream_vectors.json`
- `S07` `M` `src/cadrumo_runtime/host/worker_view_stream.py`
- `S07` `M` `src/cadrumo_runtime/host/view_stream_relay.py`
- `S07` `M` `src/cadrumo_runtime/host/operation_host.py`
- `S07` `M` `src/cadrumo_runtime/host/operation_authority.py`
- `S07` `M` `src/cadrumo_runtime/host/worker.py`
- `S07` `M` `src/cadrumo_runtime/host/tests/test_view_stream_relay.py`
- `S07` `M` `src/cadrumo_runtime/host/tests/test_operation_scope_resolution.py`
- `S07` `M` `.vault/adr/2026-10-27-sede-browser-adr.md`
- `S07` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S07` `M` `src/cadrumo_client/contracts/tests/test_view_stream_documents.py`
- `S07` `verify:` `uv run --no-sync pytest src/cadrumo/application/live/tests -k sede_view` -> `pass`
- `S07` `verify:` `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/browser/tests/test_sede_view_page.py src/cadrumo/adapters/outbound/aeat/browser/tests/test_view_adapters_no_script.py` -> `pass`
- `S07` `verify:` `uv run --no-sync pytest src/cadrumo_runtime/host/tests/test_view_stream_relay.py src/cadrumo_runtime/host/tests/test_operation_scope_resolution.py` -> `pass`
- `S07` `verify:` `just check-operation-contract-manifest` -> `pass`
- `S07` `verify:` `just check-style` -> `pass`
- `S07` `verify:` `just check-format` -> `pass`
- `S07` `verify:` `just check-types` -> `pass`
- `S07` `verify:` `just check-import-boundaries` -> `fail`
- `S07` `by:` `implementation-engineer-high`
- `S03` `M` `native/application/src/runtime_client.rs`
- `S03` `M` `native/application/src/lib.rs`
- `S03` `A` `native/application/src/view_stream.rs`
- `S03` `A` `native/application/src/view_stream/attach.rs`
- `S03` `A` `native/application/src/view_stream/chunks.rs`
- `S03` `A` `native/application/src/view_stream/decoder.rs`
- `S03` `A` `native/application/src/view_stream/documents.rs`
- `S03` `A` `native/application/src/view_stream/lane.rs`
- `S03` `A` `native/application/src/view_stream/transfer.rs`
- `S03` `A` `native/application/src/view_stream/vectors.rs`
- `S03` `verify:` `just check-rust` -> `pass`
- `S03` `verify:` `ctest --preset debug -R ^application.rust$ (cargo test of cadrumo-application, 56 view_stream tests over the shared vectors)` -> `pass`
- `S03` `verify:` `just test-native-bundle Debug` -> `fail`
- `S03` `by:` `vaultspec-standard-executor`
- `S07` `M` `src/cadrumo_runtime/host/tests/frontend/cli/test_command_aeat_capability_probe.py`
- `S07` `verify:` `uv run --no-sync pytest src/cadrumo_runtime/host/tests -k 'view or sede'` -> `pass`

## Notes

- `S01` just check-types reports 32 findings in other sessions' files, none in `cadrumo_client;` just check-import-boundaries kept all 30 contracts but was unavailable because the tree changed during the run and the cadrumo load-target set was stale from other sessions' modules
- `S01` The aggregate `dev/quality/metadata/import_load_targets.json` was regenerated with the two new modules but left uncommitted because it carries other sessions' pending changes
- `S05` Most S05 source landed in another session commit 93775feb30, which swept the shared worktree; the S05 commit carries the remaining test change.
- `S05` just check-types: 5 diagnostics outside S05 scope `(browser/request_guard.py,` runtime worker startup test); just check-import-boundaries kept 30 of 30 contracts but reported unavailable because the tree changed during the run.
- `S04` Scope change from the user 2026-10-27 (its a browser, free usage): no request guard, operator-view policy, service worker or WebSocket block on the view context. Guard code first written for this Step was swept into 93775feb30 by another session and removed in a061b2cbce. Step left open for the orchestrator.
- `S02` Relay tests are integration-marked (real native pipes and a child process), so the default unit lane of the plan command selects none of them; they pass under -m ''.
- `S02` Failures outside this Step, reproduced without its changes or in untouched code: `test_runtime_evidence` `(_Controller` test double lacks deadline), `test_drive_attachment_review_journey_cli` KeyError reason, `test_session_hold_presentation` param 4 (passes alone), `test_server_cleanup` `runtime_connection_closed` caplog (fails with HEAD `server_connection_handling` too).
- `S02` check-types: 4 ty diagnostics in untouched `adapters/tests/test_profile_worker_startup.py.` check-import-boundaries: 30/30 contracts kept; 2 REEXPORT findings in another session's `view_transfer` work and a stale aggregate `import_load_targets.json,` not committed here.
- `S02` Person input counting as person activity (application-sign-in amendment 2026-10-27) is not wired in the relay; the window's existing activity path carries it.
- `S06` Rate bound dropped by the user's scope change of 2026-10-27 (free use, no usage limits): the adapter applies no rate limit, throttle or pointer-move coalescing; only the contract's closed variants, size bounds and viewport clamping validate input.
- `S06` Full import gate (python -m `dev.quality.import_gate)` fails outside this Step: `REEXPORT_OR_ALIAS` at `src/cadrumo_client/transport/view_stream.py:79` and load-target metadata files for `cadrumo_client,` `cadrumo_runtime` and the aggregate hold other Steps' modules and stay uncommitted.
- `S15` Transfer documents live in the new `contracts/view_transfer.py` because `contracts/view_stream.py` carried uncommitted P01.S02 hunks; every existing symbol and signature of both codec modules is unchanged and the P01.S02 relay tests pass against the extended codec.
- `S15` `dev.quality.import_gate` reported zero hard findings after the `VIEW_MAX_TRANSFER_ID` alias was removed, then a tool failure from other sessions' concurrent changes (stale cadrumo load-target metadata, source tree changed during the run). The aggregate `dev/quality/metadata/import_load_targets.json` carries the `view_transfer` line beside other sessions' lines and is left for the orchestrator to commit.
- `S07` `contract_manifest.json` and the import load target sets were regenerated but not committed: they carry other sessions' uncommitted edits
- `S07` check-import-boundaries ended unavailable only because the shared source tree changed while it ran; 30 of 30 contracts kept, 0 hard findings, 4965 of 4965 modules load
- `S03` P01.S03 just test-native-bundle Debug stops before any test at the `registry_authority` target: Registry authority is unavailable or stale (the legal sources changed since the indexed generation was published); the target fails alone, apart from this Step; rerun after the registry owner runs just registry-publish-authority
