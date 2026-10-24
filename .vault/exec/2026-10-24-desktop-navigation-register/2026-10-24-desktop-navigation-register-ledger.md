---
tags:
  - '#exec'
  - '#desktop-navigation-register'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:3eef40186fb86135f748aac6a45e9d8eac0ffe4a34961b68e2ecffb919ea6be5'
related:
  - "[[2026-10-24-desktop-navigation-register-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `desktop-navigation-register` ledger

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

- `S06` `A` `src/cadrumo_client/contracts/navigation.toml`
- `S06` `A` `src/cadrumo_client/contracts/navigation.py`
- `S06` `A` `src/cadrumo_client/contracts/tests/navigation_vectors.json`
- `S06` `A` `src/cadrumo_client/contracts/tests/test_navigation_register.py`
- `S06` `A` `src/cadrumo_client/contracts/tests/test_navigation_links.py`
- `S06` `M` `pyproject.toml`
- `S06` `M` `dev/tests/test_wheel_content_boundary.py`
- `S06` `M` `dev/locales/manager.py`
- `S06` `M` `src/cadrumo/locales/en/common.yml`
- `S06` `M` `src/cadrumo/locales/es/common.yml`
- `S06` `M` `src/cadrumo/locales/ca/common.yml`
- `S06` `M` `src/cadrumo/locales/hu/common.yml`
- `S06` `verify:` `pytest src/cadrumo_client/contracts/tests/test_navigation_register.py src/cadrumo_client/contracts/tests/test_navigation_links.py` -> `pass`
- `S06` `verify:` `pytest dev/tests/test_wheel_content_boundary.py -k required_functional_members` -> `pass`
- `S06` `verify:` `lint-imports --config .importlinter` -> `pass`
- `S06` `verify:` `ruff check and ruff format --check on touched files` -> `pass`
- `S06` `verify:` `ty, pyrefly and basedpyright on touched files` -> `pass`
- `S06` `verify:` `pytest dev/locales/tests` -> `fail`
- `S07` `M` `src/cadrumo_client/contracts/navigation.py`
- `S07` `M` `src/cadrumo_client/contracts/presentation.py`
- `S07` `M` `src/cadrumo_client/contracts/session_events.py`
- `S07` `M` `src/cadrumo_client/contracts/tests/test_presentation_requests.py`
- `S07` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S07` `M` `src/cadrumo_client/transport/tests/test_presentation_events.py`
- `S07` `M` `src/cadrumo_runtime/host/session_hold.py`
- `S07` `M` `src/cadrumo_runtime/host/profile_connection_sessions.py`
- `S07` `M` `src/cadrumo_runtime/host/tests/test_presentation_routing.py`
- `S07` `M` `src/cadrumo_runtime/host/tests/test_session_hold_presentation.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/presentation.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/app.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/account.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/ledger/routes.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/ledger/entries.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/tests/test_presentation_navigation.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/tests/test_root_waits_for_a_write.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/tests/test_module_arguments.py`
- `S07` `M` `src/cadrumo/application/operations/operation_pages.py`
- `S07` `M` `src/cadrumo/application/operations/tests/test_operation_pages.py`
- `S07` `M` `src/cadrumo/application/auth/setup_handoff.py`
- `S07` `M` `src/cadrumo/application/auth/read_operation.py`
- `S07` `M` `src/cadrumo/application/auth/tests/test_setup_handoff.py`
- `S07` `M` `src/cadrumo_mcp/mcp/admitted_operations.py`
- `S07` `M` `src/cadrumo_mcp/mcp/tests/test_execute_page_link.py`
- `S07` `M` `src/cadrumo_mcp/mcp/tests/test_handshake_free_revision.py`
- `S07` `M` `dev/runtime_lifecycle/tests/test_mcp_attended_adapter.py`
- `S07` `D` `src/cadrumo_client/contracts/tests/test_presentation_links.py`
- `S07` `A` `src/cadrumo_client/contracts/tests/test_presentation_requests.py`
- `S07` `verify:` `pytest touched presentation, routing, session hold, TUI, ledger, handoff, operation pages and MCP page tests (1180 passed)` -> `pass`
- `S07` `verify:` `pytest client, runtime TUI frontend, MCP, auth, operations and locale suites (3606 passed, 9 failed outside the touched code)` -> `fail`
- `S07` `verify:` `ruff check, ruff format --check and ty on touched files` -> `pass`
- `S07` `verify:` `lint-imports --config .importlinter --no-cache (1 broken: cadrumo.tests to application.local_reader, pre-existing uncommitted edit)` -> `fail`
- `S07` `verify:` `pytest presentation contract, client events, runtime routing and session hold tests (53 passed)` -> `pass`
- `S07` `verify:` `ruff check, ruff format --check and ty on the follow-up files` -> `pass`
- `S09` `A` `dev/packaging/native/desktop_navigation.py`
- `S09` `A` `dev/packaging/native/tests/test_desktop_navigation.py`
- `S09` `A` `dev/locales/tests/test_desktop_navigation_labels.py`
- `S09` `M` `dev/locales/desktop_chrome.py`
- `S09` `M` `dev/locales/tests/test_desktop_chrome.py`
- `S09` `M` `native/desktop/CMakeLists.txt`
- `S09` `M` `native/desktop/scripts/tauri.mjs`
- `S09` `M` `native/desktop/src-tauri/build.rs`
- `S09` `M` `native/desktop/src-tauri/src/shell/presentation.rs`
- `S09` `M` `native/desktop/src-tauri/src/agent/person.rs`
- `S09` `M` `native/desktop/src-tauri/src/agent/person/native.rs`
- `S09` `M` `native/desktop/frontend/scripts/dev.mjs`
- `S09` `M` `native/desktop/frontend/vite.config.ts`
- `S09` `M` `native/desktop/frontend/src/content.d.ts`
- `S09` `A` `native/desktop/frontend/src/shell/navigation/register.ts`
- `S09` `A` `native/desktop/frontend/src/shell/navigation/projection.ts`
- `S09` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S09` `M` `native/desktop/frontend/src/shell/host.ts`
- `S09` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S09` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S09` `M` `native/desktop/frontend/src/App.tsx`
- `S09` `M` `native/desktop/frontend/src/components/agent/cadrumoLink.ts`
- `S09` `M` `native/desktop/frontend/src/components/AgentColumn.tsx`
- `S09` `M` `native/desktop/frontend/tests/scenarios/agent-page-links.spec.ts`
- `S09` `M` `native/desktop/frontend/tests/scenarios/user-profile.spec.ts`
- `S09` `M` `src/cadrumo/locales/en/common.yml`
- `S09` `M` `src/cadrumo/locales/es/common.yml`
- `S09` `M` `src/cadrumo/locales/ca/common.yml`
- `S09` `M` `src/cadrumo/locales/hu/common.yml`
- `S09` `verify:` `pytest dev/packaging/native/tests/test_desktop_navigation.py` -> `pass`
- `S09` `verify:` `pytest dev/locales/tests/test_desktop_navigation_labels.py` -> `pass`
- `S09` `verify:` `cmake --target desktop-host-unit-test` -> `pass`
- `S09` `verify:` `tsc --noEmit on S09 index export` -> `pass`
- `S10` `A` `native/desktop/frontend/src/shell/navigation/links.ts`
- `S10` `A` `native/desktop/frontend/src/shell/navigation/resolve.ts`
- `S10` `A` `native/desktop/frontend/src/shell/navigation/windowViews.ts`
- `S10` `A` `native/desktop/frontend/src/shell/navigation/guards.ts`
- `S10` `A` `native/desktop/frontend/src/shell/navigation/focus.ts`
- `S10` `A` `native/desktop/frontend/src/shell/navigation/hooks.ts`
- `S10` `A` `native/desktop/frontend/src/shell/navigation/useNavigator.ts`
- `S10` `A` `native/desktop/frontend/src/components/NavigationPrompt.tsx`
- `S10` `A` `native/desktop/frontend/tests/scenarios/navigation-register.spec.ts`
- `S10` `D` `native/desktop/frontend/src/components/agent/cadrumoLink.ts`
- `S10` `M` `native/desktop/frontend/src/App.tsx`
- `S10` `M` `native/desktop/frontend/src/components/AgentColumn.tsx`
- `S10` `M` `native/desktop/frontend/src/components/agent/Markdown.tsx`
- `S10` `M` `native/desktop/frontend/src/components/ledger/LedgerPage.tsx`
- `S10` `M` `native/desktop/frontend/src/components/ledger/editing/LedgerEditing.tsx`
- `S10` `M` `native/desktop/frontend/src/dev/agentFixtureHost.ts`
- `S10` `M` `native/desktop/frontend/tests/scenarios/agent-page-links.spec.ts`
- `S10` `M` `dev/locales/desktop_chrome.py`
- `S10` `M` `src/cadrumo/locales/en/common.yml`
- `S10` `M` `src/cadrumo/locales/es/common.yml`
- `S10` `M` `src/cadrumo/locales/ca/common.yml`
- `S10` `M` `src/cadrumo/locales/hu/common.yml`
- `S10` `verify:` `playwright scenarios navigation-register and agent-page-links` -> `pass`
- `S10` `verify:` `playwright scenarios ledger-editing ledger-shell user-profile agent-markdown` -> `pass`
- `S10` `verify:` `npm run check tsc and eslint` -> `pass`
- `S10` `verify:` `tsc eslint prettier on S10 index export` -> `pass`
- `S10` `verify:` `pytest desktop chrome and navigation label tests` -> `pass`
- `S10` `verify:` `cmake --target desktop-host-unit-clippy` -> `pass`
- `S08` `A` `src/cadrumo_mcp/mcp/view_register.py`
- `S08` `A` `src/cadrumo_mcp/mcp/record_links.py`
- `S08` `M` `src/cadrumo_mcp/mcp/protocol_contract.py`
- `S08` `M` `src/cadrumo_mcp/mcp/runtime_adapter.py`
- `S08` `M` `src/cadrumo_mcp/mcp/admitted_operations.py`
- `S08` `M` `src/cadrumo_mcp/mcp/surfaces.py`
- `S08` `A` `src/cadrumo_mcp/mcp/tests/test_views_tool.py`
- `S08` `A` `src/cadrumo_mcp/mcp/tests/test_record_links.py`
- `S08` `M` `src/cadrumo_mcp/mcp/tests/test_tool_annotations.py`
- `S08` `M` `src/cadrumo_mcp/mcp/tests/test_mcp_surface_pins.py`
- `S08` `M` `src/cadrumo_mcp/mcp/tests/test_installed_stdio.py`
- `S08` `M` `dev/quality/metadata/import_load_targets.cadrumo_client.json`
- `S08` `M` `dev/quality/metadata/import_load_targets.cadrumo_mcp.json`
- `S08` `M` `dev/quality/metadata/import_load_targets.json`
- `S08` `verify:` `pytest src/cadrumo_mcp and src/cadrumo_client/contracts (724 passed)` -> `pass`
- `S08` `verify:` `ruff check, ruff format --check and ty on S08 files` -> `pass`
- `S08` `verify:` `lint-imports --config .importlinter --no-cache (30 kept)` -> `pass`
- `S08` `verify:` `just check-import-boundaries (contracts kept; fails on other sessions' files: modelo vocabulary import, catalogue intake test syntax, dev registry private imports)` -> `fail`

## Notes

- `S06` dev/locales/tests: 4 failures in `test_desktop_chrome,` `test_dict_constant_naming_convention,` `test_modelo_schema_runtime_localization` and `test_audit` product identity; none names a navigation key; they sit in files other sessions are editing. Locale spelling flags ca Instal·lació and es/ca Python shell for navigation labels exactly as for the existing tui.destination.installation and desktop.rail.python cells.
- `S07` The 9 broader failures are outside S07: `desktop_chrome` and dict-naming and catalogue-identity locale gates over other sessions' edits, and runtime TUI automation-inventory and restored-login settle timeouts; locale key `tui.ledger.entries.selection_absent` landed inside another session's commit 44d85df020
- `S07` Follow-up 7ba285bd05 closes a wire gap the desktop lane found: PresentationDelivered and the session hold's `destination_presented` line now echo the request's params, and the client refuses a reply whose params differ
- `S09` commits e7301548b6 and 70ae70915f; the first was written from an index read before five other commits and dropped their files, the second restores them; the host requires the runtime delivery to echo params, added by the Python lane in 7ba285bd05
- `S10` commit 53098ff2ca; App.tsx committed as HEAD plus only these hunks, another session's provisioning hunks stay uncommitted in the worktree; six scenario specs timed out under concurrent clippy load and passed on rerun at two workers
- `S08` Surface rows updated in place under the orchestrator's ruling (B): no consumer has pinned a release; the views tool is a local read on both surfaces. Record links cover ledger.add, ledger.update, ledger.classify.single, ledger.invoice.add, ledger.invoice.update, ledger.invoice.wizard and ledger.evidence.confirm; ledger.link (two records), ledger.invoice.import and ledger.classify.bulk (several) and ledger.invoice.remove (removed record) carry none
