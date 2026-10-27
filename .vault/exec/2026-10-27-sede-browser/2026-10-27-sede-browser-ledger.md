---
tags:
  - '#exec'
  - '#sede-browser'
date: '2026-10-27'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:46e62882bd2d4ba14a5abed3a00dda692870989cdd3add2a9403f9db993f712c'
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
- `S08` `A` `native/desktop/src-tauri/src/shell/sede_view.rs`
- `S08` `A` `native/desktop/src-tauri/src/shell/sede_view/transfer.rs`
- `S08` `A` `native/desktop/src-tauri/src/shell/sede_view/upstream.rs`
- `S08` `A` `native/desktop/src-tauri/src/shell/sede_view/tests.rs`
- `S08` `M` `native/desktop/src-tauri/src/shell/mod.rs`
- `S08` `M` `native/desktop/src-tauri/src/app.rs`
- `S08` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S08` `M` `native/desktop/src-tauri/src/agent/person.rs`
- `S08` `M` `native/desktop/src-tauri/src/agent/person/native.rs`
- `S08` `M` `native/application/src/view_stream/documents.rs`
- `S08` `verify:` `just check-rust` -> `pass`
- `S08` `verify:` `cmake --build --preset debug --target desktop-host-unit-test (full desktop host suite, 675 passed 1 ignored; sede_view filter 47 passed; shell-token dispatch test over all commands passed)` -> `pass`
- `S08` `verify:` `ctest --preset debug -R ^application.rust$` -> `pass`
- `S08` `verify:` `just test-native-bundle Debug` -> `fail`
- `S08` `by:` `vaultspec-standard-executor`
- `S12` `M` `src/cadrumo/application/auth/protocols.py`
- `S12` `M` `src/cadrumo/application/auth/sessions.py`
- `S12` `M` `src/cadrumo/application/live/session.py`
- `S12` `M` `src/cadrumo/application/live/sede_view_ports.py`
- `S12` `M` `src/cadrumo/application/live/sede_view_operation.py`
- `S12` `M` `src/cadrumo/application/live/tests/test_sede_view_operation.py`
- `S12` `M` `src/cadrumo/adapters/outbound/aeat/auth/authenticator.py`
- `S12` `M` `src/cadrumo/adapters/outbound/aeat/auth/clave_movil.py`
- `S12` `M` `src/cadrumo/adapters/outbound/aeat/auth/clave_permanente.py`
- `S12` `M` `src/cadrumo/adapters/outbound/aeat/auth/session_store.py`
- `S12` `M` `src/cadrumo/adapters/outbound/aeat/auth/tests/test_view_session_custody.py`
- `S12` `A` `src/cadrumo/adapters/outbound/aeat/auth/tests/test_view_sign_in.py`
- `S12` `A` `src/cadrumo/adapters/outbound/aeat/auth/tests/view_session_support.py`
- `S12` `M` `src/cadrumo/adapters/outbound/aeat/browser/sede_view.py`
- `S12` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_sede_view_page.py`
- `S12` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/view_page_support.py`
- `S12` `verify:` `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/auth/tests -k 'view or headless' (18 passed)` -> `pass`
- `S12` `verify:` `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/browser/tests src/cadrumo/application/live/tests/test_sede_view_operation.py src/cadrumo/adapters/outbound/aeat/auth/tests (514 passed)` -> `pass`
- `S12` `verify:` `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/auth/tests/test_view_session_custody.py -m '' (8 passed)` -> `pass`
- `S12` `verify:` `uv run --no-sync pytest src/cadrumo/application/auth/tests src/cadrumo/application/live/tests (545 passed)` -> `pass`
- `S12` `verify:` `uv run --no-sync ruff check and ruff format --check on scope` -> `pass`
- `S12` `verify:` `uv run --no-sync python -m dev.quality.types (scope clean; 1 diagnostic in src/cadrumo/application/aggregation/iva_ledger.py outside scope)` -> `pass`
- `S12` `verify:` `uv run --no-sync lint-imports --config .importlinter --no-cache (30 kept)` -> `pass`
- `S12` `by:` `vaultspec-high-executor`
- `S09` `A` `native/desktop/frontend/src/components/browser/BrowserPage.tsx`
- `S09` `A` `native/desktop/frontend/src/components/browser/BrowserPrompts.tsx`
- `S09` `A` `native/desktop/frontend/src/components/browser/BrowserSurface.tsx`
- `S09` `A` `native/desktop/frontend/src/components/browser/BrowserToolbar.tsx`
- `S09` `A` `native/desktop/frontend/src/components/browser/PageDialog.tsx`
- `S09` `A` `native/desktop/frontend/src/components/browser/browserModel.ts`
- `S09` `A` `native/desktop/frontend/src/components/browser/browserWords.ts`
- `S09` `A` `native/desktop/frontend/src/components/browser/useSedeView.ts`
- `S09` `A` `native/desktop/frontend/src/shell/sedeView.ts`
- `S09` `A` `native/desktop/frontend/src/shell/tauriSedeView.ts`
- `S09` `A` `native/desktop/frontend/src/dev/sedeViewFixture.ts`
- `S09` `A` `native/desktop/frontend/tests/sede-view-model.spec.ts`
- `S09` `M` `native/desktop/frontend/src/shell/navigation/windowViews.ts`
- `S09` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S09` `M` `native/desktop/frontend/src/shell/host.ts`
- `S09` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S09` `M` `native/desktop/frontend/src/shell/layout.ts`
- `S09` `M` `native/desktop/frontend/src/components/ui/icon.tsx`
- `S09` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S09` `M` `native/desktop/frontend/eslint.config.js`
- `S09` `M` `dev/locales/desktop_chrome.py`
- `S09` `M` `src/cadrumo/locales/en/common.yml`
- `S09` `M` `src/cadrumo/locales/es/common.yml`
- `S09` `M` `src/cadrumo/locales/ca/common.yml`
- `S09` `M` `src/cadrumo/locales/hu/common.yml`
- `S09` `verify:` `npm run check (native/desktop/frontend)` -> `pass`
- `S09` `verify:` `npx playwright test tests/sede-view-model.spec.ts (15 tests)` -> `pass`
- `S09` `verify:` `page smoke through the scenario fixture in Chromium: draw, credit, pointer, keys, wheel, paste, toolbar, offers, dialog, download, chooser, acquiring, closing guard, unmount close and reopen (temporary harness, removed)` -> `pass`
- `S09` `verify:` `uv run --no-sync pytest dev/locales/tests -k desktop` -> `pass`
- `S09` `verify:` `npx playwright test tests/scenarios/navigation-register.spec.ts tests/scenarios/palette.spec.ts (16 passed, 1 failed)` -> `fail`
- `S09` `verify:` `just check-locales (blocking findings are spelling only)` -> `fail`
- `S09` `by:` `vaultspec-standard-executor`
- `S10` `M` `native/desktop/frontend/src/App.tsx`
- `S10` `M` `native/desktop/frontend/src/components/Rail.tsx`
- `S10` `M` `native/desktop/frontend/src/components/ui/icon.tsx`
- `S10` `M` `native/desktop/frontend/src/shell/layout.ts`
- `S10` `M` `native/desktop/frontend/tests/scenarios/palette.spec.ts`
- `S10` `M` `native/desktop/frontend/tests/scenarios/scenarios.spec.ts`
- `S10` `M` `src/cadrumo_client/contracts/navigation.toml`
- `S10` `M` `src/cadrumo_client/contracts/tests/navigation_shipped_views.json`
- `S10` `M` `src/cadrumo_client/contracts/tests/test_navigation_register.py`
- `S10` `M` `src/cadrumo/locales/en/common.yml`
- `S10` `M` `src/cadrumo/locales/es/common.yml`
- `S10` `M` `src/cadrumo/locales/ca/common.yml`
- `S10` `M` `src/cadrumo/locales/hu/common.yml`
- `S10` `M` `dev/locales/desktop_chrome.py`
- `S10` `verify:` `npm run check (native/desktop/frontend)` -> `pass`
- `S10` `verify:` `npx playwright test -c playwright.scenarios.config.ts tests/scenarios/navigation-register.spec.ts tests/scenarios/palette.spec.ts (18 passed)` -> `pass`
- `S10` `verify:` `npx playwright test -c playwright.scenarios.config.ts tests/scenarios/scenarios.spec.ts -g 'AEAT shortcut|shortcut the host cannot|the rail keeps its order|never restored' (5 passed)` -> `pass`
- `S10` `verify:` `npx playwright test keyboard columns navigation-guards window-close reconnecting specs (67 passed)` -> `pass`
- `S10` `verify:` `uv run --no-sync pytest navigation register, links, presentation, desktop navigation labels, desktop navigation packaging tests (all passed)` -> `pass`
- `S10` `verify:` `uv run --no-sync pytest src/cadrumo_mcp/mcp/tests/test_views_tool.py (2 failed on profile/aeat-access surfaces, none on browser)` -> `fail`
- `S10` `verify:` `just check-locales (exit 1 on baseline findings; none on this Step's keys except en 'maximize' spelling shared with the existing maximize keys)` -> `fail`
- `S10` `verify:` `uv run --no-sync ruff check and ruff format --check on dev/locales/desktop_chrome.py and test_navigation_register.py` -> `pass`
- `S10` `by:` `vaultspec-standard-executor`
- `S11` `A` `native/desktop/frontend/tests/scenarios/sede-browser.spec.ts`
- `S11` `M` `native/desktop/frontend/src/dev/sedeViewFixture.ts`
- `S11` `verify:` `npm run check` -> `pass`
- `S11` `verify:` `npx playwright test -c playwright.scenarios.config.ts tests/scenarios/sede-browser.spec.ts tests/scenarios/navigation-register.spec.ts tests/scenarios/palette.spec.ts` -> `pass`
- `S11` `verify:` `npx playwright test -c playwright.scenarios.config.ts tests/scenarios/accessibility.spec.ts tests/scenarios/scenarios.spec.ts -g rail-and-browser-subset` -> `pass`
- `S11` `by:` `vaultspec-standard-executor`

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
- `S08` P03.S08 just test-native-bundle Debug did not reach any test: `registry_authority` validated this time, but the desktop host build failed on another session's uncommitted custody-recovery edits (Person::native now takes 5 arguments, SignInStatus has no reconnecting field) and the python wheel capture reported that enrolled product source changed while it ran. The Step stays open until that run can complete.
- `S08` P03.S08 person.rs, person/native.rs and `sign_in/mod.rs` also hold another session's uncommitted recovery hunks; the S08 hunks there are the Bridge and Person `view_attach` methods, NativeSession `view_attach` and SignIn `runtime_target.`
- `S08` P03.S08 the host holds the page's origin and path from view.state; the stream carries no query or fragment, so Open in external browser opens the page without them. Raw image messages ride the shell channel interceptor, which evaluates them as a number-array script.
- `S09` navigation-register.spec: the window's table covers exactly the register's window elements fails until P04.S10 adds the browser gui element to the register; windowViews.ts already holds it
- `S09` just check-locales fails on the spelling dictionary alone (21640 findings across the catalogues, e.g. Cadrumo and apostrophe contractions in strings committed earlier); the 58 desktop.browser keys have no missing, drift or translation finding
- `S09` the four locale catalogues and `dev/locales/desktop_chrome.py` hold the 58 desktop.browser keys uncommitted: another session's edits are in the same files
- `S09` contract.ts and scenarioHost.ts were committed whole and carry another session's reconnecting hunks
- `S10` `navigation_shipped_views.json` has no generator: it is an append-only baseline grown by hand with the new id; `test_navigation_register.py` reads it.
- `S10` `desktop_chrome.py` and the four common.yml catalogues also carry another session's uncommitted reconnecting hunks, so they are left uncommitted by pathspec rule; the browser strings declared by P04.S09 sit in the same uncommitted `desktop_chrome.py` hunk.
- `S11` the spec reads the desktop.browser strings from the generated chrome catalogue, which holds them from the uncommitted locale files; the spec is correct only once those catalogues are committed
- `S11` the fixture was extended for the spec: it records inputs and answers, counts images, sends a made-up title, and ends a made-up login when the person's input arrives
