---
tags:
  - '#exec'
  - '#language-sync'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:8f7d936b1bc29119fc79f42ef36fccad010b8865d75795f37c79f4db13915d54'
related:
  - "[[2026-10-15-language-sync-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `language-sync` ledger

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

- `S02` `M` `native/desktop/src-tauri/src/agent/mod.rs`
- `S02` `M` `native/desktop/src-tauri/src/agent/person.rs`
- `S02` `M` `native/desktop/src-tauri/src/app.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/mod.rs`
- `S02` `A` `native/desktop/src-tauri/src/shell/language.rs`
- `S02` `verify:` `cmake --build build/desktop-windows-x64 --target desktop-host-unit-test --config Release` -> `pass`
- `S02` `verify:` `cmake --build build/desktop-windows-x64 --target desktop-host-clippy --config Release` -> `pass`
- `S02` `verify:` `cmake --build build/desktop-windows-x64 --target desktop-host-build --config Release` -> `pass`
- `S03` `M` `dev/docs/tests/test_docs_desktop_flavor.py`
- `S03` `M` `docs/_static/cadrumo-desktop-bridge.js`
- `S03` `M` `native/desktop/frontend/dev/docs-fixture/plugin.ts`
- `S03` `M` `native/desktop/frontend/src/App.tsx`
- `S03` `M` `native/desktop/frontend/src/components/CommandPalette.tsx`
- `S03` `M` `native/desktop/frontend/src/components/DocsFrame.tsx`
- `S03` `A` `native/desktop/frontend/src/components/LanguageSelect.tsx`
- `S03` `M` `native/desktop/frontend/src/components/Settings.stories.tsx`
- `S03` `M` `native/desktop/frontend/src/components/Settings.tsx`
- `S03` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S03` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S03` `M` `native/desktop/frontend/src/shell/calendar.ts`
- `S03` `M` `native/desktop/frontend/src/shell/host.ts`
- `S03` `M` `native/desktop/frontend/src/shell/layout.ts`
- `S03` `M` `native/desktop/frontend/src/shell/messages.ts`
- `S03` `M` `native/desktop/frontend/src/shell/strings.ts`
- `S03` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S03` `A` `native/desktop/frontend/src/shell/useLanguage.ts`
- `S03` `M` `native/desktop/frontend/tests/desktop.spec.ts`
- `S03` `M` `native/desktop/frontend/tests/scenarios/accessibility.spec.ts`
- `S03` `M` `native/desktop/frontend/tests/scenarios/keyboard.spec.ts`
- `S03` `A` `native/desktop/frontend/tests/scenarios/language.spec.ts`
- `S03` `M` `native/desktop/frontend/tests/scenarios/logs.spec.ts`
- `S03` `M` `native/desktop/frontend/tests/scenarios/profiles.spec.ts`
- `S03` `M` `native/desktop/frontend/tests/scenarios/scenarios.spec.ts`
- `S03` `M` `native/desktop/frontend/tests/support/layout.ts`
- `S03` `verify:` `npm run check (native/desktop/frontend)` -> `pass`
- `S03` `verify:` `npm test -- --workers=2 (593 collected)` -> `fail`
- `S03` `verify:` `npm test -- --last-failed --workers=2 (47 of 49 recovered)` -> `fail`
- `S03` `verify:` `npm test -- --last-failed --workers=1 (remaining 2)` -> `pass`
- `S03` `verify:` `pytest dev/docs/tests/test_docs_desktop_flavor.py (full file, 35 passed and 1 failed)` -> `fail`
- `S03` `verify:` `pytest test_docs_desktop_flavor.py::test_language_switch_waits_for_host_and_preserves_fragment (corrected)` -> `pass`
- `S02` `verify:` `rustfmt --check --edition 2024 --config skip_children=true (five owned Rust files)` -> `pass`
- `S02` `verify:` `desktop-host-test Release filtered logs::tests::live::real_rotation_across_processes_while_tailing` -> `fail`
- `S01` `M` `dev/quality/metadata/import_load_targets.cadrumo_client.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.json`
- `S01` `M` `src/cadrumo_client/contracts/session_events.py`
- `S01` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S01` `A` `src/cadrumo_client/transport/profile_language.py`
- `S01` `A` `src/cadrumo_client/transport/tests/test_profile_language_events.py`
- `S01` `M` `src/cadrumo_client/transport/verified_transport.py`
- `S01` `M` `src/cadrumo_runtime/host/frontend/tui/installed_session.py`
- `S01` `M` `src/cadrumo_runtime/host/frontend/tui/profile/manager_client.py`
- `S01` `M` `src/cadrumo_runtime/host/frontend/tui/runtime_account.py`
- `S01` `M` `src/cadrumo_runtime/host/frontend/tui/runtime_initial_root.py`
- `S01` `M` `src/cadrumo_runtime/host/frontend/tui/runtime_workbench.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_connection_sessions.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_connections.py`
- `S01` `M` `src/cadrumo_runtime/host/session_hold.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/frontend/tui/profile/test_auth_setup_client.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_installed_session.py`
- `S01` `A` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_language_captures.py`
- `S01` `A` `src/cadrumo_runtime/host/tests/test_profile_language_events.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/test_profile_patch_client.py`
- `S01` `M` `src/cadrumo/application/modelo/work_form_localization.py`
- `S01` `M` `src/cadrumo/application/user_profile/fact_write.py`
- `S01` `M` `src/cadrumo/application/user_profile/language_resolver.py`
- `S01` `M` `src/cadrumo/application/user_profile/overview.py`
- `S01` `M` `src/cadrumo/application/user_profile/tests/test_language_resolver_snapshot.py`
- `S01` `M` `src/cadrumo/core/i18n/render.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/account.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/aeat_sync/screens.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/app.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/components/account_chrome.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/components/dialogs.py`
- `S01` `A` `src/cadrumo/entrypoints/tui/components/language.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/components/widgets.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/calendar.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/controller.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/external_details.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/filing_history.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/grouped.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/picker.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/revisions.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/routes.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/tests/test_external_filing_details.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/google_saved_review.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/historical_export.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/home.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/installation/act_screen.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/installation/destination.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/actividad_asset.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/classification.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/controller.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/entries.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/evidence.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/import_flow.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/invoice_entry.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/overview.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/own_accounts.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/reconciliation.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/record_views.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/review.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/routes.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/transaction_views.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/export_result.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/m303_evidence.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/bulk_confirm.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/export.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/factory.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/issues.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/ports.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/result.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/review.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_footer.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_next_step.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen_operation.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/session.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/sources.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_help_freshness_real.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_recorded.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/operations/destination.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/operations/modal.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/operations/run_screen.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/profile/aeat_auth_setup.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/profile/edit_screens.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/profile/overview_interactions.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/profile/plantilla_media.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/reconciliation_export.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/reference/destination.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/reference/read_screen.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/secret/credentials.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/secret/passphrase.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_app.py`
- `S01` `A` `src/cadrumo/entrypoints/tui/tests/test_live_language_refresh.py`
- `S01` `M` `src/cadrumo/locales/ca/common.yml`
- `S01` `M` `src/cadrumo/locales/en/common.yml`
- `S01` `M` `src/cadrumo/locales/es/common.yml`
- `S01` `M` `src/cadrumo/locales/hu/common.yml`
- `S01` `verify:` `dev.quality.quiet ruff check (93 current manifest Python files)` -> `pass`
- `S01` `verify:` `dev.quality.quiet ruff format --check (93 current manifest Python files)` -> `pass`
- `S01` `verify:` `ty check linux win32 darwin (manifest Python files)` -> `pass`
- `S01` `verify:` `just check-types --full (exit0; ten advisory diagnostics outside manifest)` -> `pass`
- `S01` `verify:` `focused language behavior tests (104 scoped cases across corrected runs)` -> `pass`
- `S01` `verify:` `environment precedence regression set (40 tests)` -> `pass`
- `S01` `verify:` `runtime locale capture and adjacent roots (18 tests, final helper)` -> `pass`
- `S01` `verify:` `AEAT auth profile siblings (17 tests)` -> `pass`
- `S01` `verify:` `live language refresh file (10 tests, final)` -> `pass`
- `S01` `verify:` `ExternalFilingDetails integration file (17 tests, final)` -> `pass`
- `S01` `verify:` `change-scoped parallel lane (175 IDs across 147 prior and28 resumed)` -> `pass`
- `S01` `verify:` `just test-pytest-harness (4 tests)` -> `pass`
- `S01` `verify:` `just check-import-boundaries (current generated metadata)` -> `fail`
- `S01` `verify:` `just check-module-reachability` -> `fail`
- `S01` `verify:` `just check-symbol-usage` -> `fail`
- `S01` `verify:` `just check-export-consumption` -> `fail`
- `S01` `verify:` `just test-sequence-goldens-gate (stale registry authority)` -> `fail`

## Notes

- `S02` 335 host unit tests passed; final Release host build includes current frontend. An earlier separate logs-only live-package test passed 58/59: log rotation observed no records; no baseline attribution. Its exact retry was deferred while a foreign Debug target remained active in the same build tree.
- `S03` All 593 frontend test IDs have passing evidence across the full run and fresh retries; final two failures were setup/teardown timeouts and passed with one worker. Documentation full file passed 35 tests; the duplicate-anchor assertion was corrected and its focused real-browser retry passed. Packaged GUI cross-surface acceptance was not run.
- `S02` The supported CMake Release retry of the exact live log-rotation test failed again (0 passed, 1 failed, 351 filtered) with an empty live record list. Read-only tracing shows this fixture constructs Tail directly and bypasses all five language files, Person::hold and session hold. Its environment projection participates in setup; baseline/provenance remains unknown. No further native rerun or unrelated log-reader edit is claimed.
- `S01` S01 verification remains pending. Current import-boundary gate fails with 1144 hard findings, 324 new unapproved occurrences and110 shipped-root occurrences reaching repository-only roots. Candidate inventory0of424intersections with manifest; all93Python diffs add no private import target or dynamic import construct. Full hardfinding paths are not retained by the checker, so absence of every manifest intersection is not claimed. Other three static reports list no manifest files. Sequence goldens fail closed against stale authority while foreign registry edits remain in progress; no authority publication or unrelated repair is performed.
