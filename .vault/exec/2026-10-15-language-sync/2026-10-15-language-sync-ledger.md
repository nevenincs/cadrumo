---
tags:
  - '#exec'
  - '#language-sync'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:0e4563e6df79e831bd78194e19491ac1ae1a3ee9158ba4eed72487ab9d8f3328'
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

## Notes

- `S02` 335 host unit tests passed; final Release host build includes current frontend. An earlier separate logs-only live-package test passed 58/59: log rotation observed no records; no baseline attribution. Its exact retry was deferred while a foreign Debug target remained active in the same build tree.
- `S03` All 593 frontend test IDs have passing evidence across the full run and fresh retries; final two failures were setup/teardown timeouts and passed with one worker. Documentation full file passed 35 tests; the duplicate-anchor assertion was corrected and its focused real-browser retry passed. Packaged GUI cross-surface acceptance was not run.
- `S02` The supported CMake Release retry of the exact live log-rotation test failed again (0 passed, 1 failed, 351 filtered) with an empty live record list. Read-only tracing shows this fixture constructs Tail directly and bypasses all five language files, Person::hold and session hold. Its environment projection participates in setup; baseline/provenance remains unknown. No further native rerun or unrelated log-reader edit is claimed.
