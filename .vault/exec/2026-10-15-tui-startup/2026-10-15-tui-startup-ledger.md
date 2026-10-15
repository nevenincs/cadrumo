---
tags:
  - '#exec'
  - '#tui-startup'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:02bb257c509675b98c6e4b2516fb435a961b3606be47ae952954c429ecae5dbe'
related:
  - "[[2026-10-15-tui-startup-plan]]"
---


# `tui-startup` ledger

## Changes

- `S01` `A` `src/cadrumo/entrypoints/tui/runtime_initial_root.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/account.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/app.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/app_navigation.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/installed_session.py`
- `S01` `A` `src/cadrumo/entrypoints/tui/tests/test_runtime_initial_root.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_runtime_root_shell.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_installed_session.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/frontend/tui/entrypoints/tui/tests/test_runtime_workbench_native.py`
- `S01` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.json`
- `S01` `verify:` `focused TUI tests 60 plus initial routing 4` -> `pass`
- `S01` `verify:` `native launcher real IPC retry` -> `pass`
- `S01` `verify:` `focused Ruff and ty` -> `pass`
- `S01` `verify:` `just check-registry-gate` -> `pass`
- `S01` `verify:` `just check-code` -> `fail`
- `S02` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S02` `verify:` `desktop-host-unit-test filtered shell::sign_in:: 57 tests` -> `pass`
- `S02` `verify:` `desktop-host-unit-clippy` -> `pass`
- `S02` `verify:` `Python JSON identifier privacy regression` -> `pass`
- `S01` `M` `src/cadrumo/entrypoints/tui/runtime_workbench.py`
- `S01` `verify:` `routing and current-provenance tests 9` -> `pass`
- `S01` `verify:` `final native workbench regression 3` -> `pass`
- `S01` `verify:` `generated import inventory tests 7` -> `pass`
- `S01` `verify:` `just test-gate interrupted after recorded failures` -> `fail`
- `S03` `M` `src/cadrumo/application/user_profile/view_operation.py`
- `S03` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/profile/test_runtime_overview.py`
- `S03` `verify:` `profile-page-fix-tests.txt: 16 focused tests` -> `pass`
- `S03` `verify:` `profile-page-fix-native.txt: real Windows frontend stream test` -> `pass`
- `S03` `verify:` `operation_contract_manifest.generate --check` -> `pass`
- `S03` `verify:` `scoped Ruff lint and format` -> `pass`
- `S03` `verify:` `scoped ty check` -> `pass`

## Notes

- `S01` Implemented; broader verification remains pending amid concurrent source mutations. Source timing and remaining seven-page overview delay are recorded in the feature audit. Shared files include separately owned session-activity and availability changes; do not commit those as startup-only work.
- `S02` Scoped machine identity correction verified. Native file also contains concurrent activity reporting; preserve separate ownership. Full host target refused changing documentation inputs twice; supported backend unit targets passed.
- `S01` Complete-profile startup now revalidates exact profile/revision/digest/setup state before reusing routing overview. Full gate stopped after 8682 passed and 380 failed; serial and harness phases not reached. No package rebuild, clean whole-repository claim, or isolated commit of shared mixed-owner files.
- `S03` Empty synthetic profile: seven pages reduced to five, all 203 items retained under unchanged 20000-byte cap. Direct-reader three-run medians 273.39ms versus 196.56ms; not packaged startup evidence. Existing integrated-gate gaps remain; no staged rebuild or mixed-owner commit.
