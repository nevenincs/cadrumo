---
tags:
  - '#exec'
  - '#native-modularity'
date: '2026-11-02'
modified: '2026-11-03'
body_schema: 'body-v2'
body_hash: 'sha256:c3c0038c023ad3150423c42efaa2a581da98b1a5a0efca7aa9c3bf94c1973b71'
related:
  - "[[2026-11-02-native-modularity-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `native-modularity` ledger

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

- `S03` `M` `native/desktop/frontend/src/App.tsx`
- `S03` `A` `native/desktop/frontend/src/shell/navigation/useWindowCloseGuard.ts`
- `S03` `A` `native/desktop/frontend/src/shell/usePersistedLayout.ts`
- `S03` `A` `native/desktop/frontend/src/shell/ShellContexts.tsx`
- `S03` `A` `native/desktop/frontend/src/shell/useToastMessage.ts`
- `S03` `A` `native/desktop/frontend/src/shell/useShellMenus.ts`
- `S03` `verify:` `npx eslint src/shell/useShellMenus.ts src/App.tsx` -> `pass`
- `S04` `M` `native/desktop/src-tauri/src/shell/relay.rs`
- `S04` `M` `native/desktop/src-tauri/src/shell/settle.rs`
- `S04` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S04` `M` `native/desktop/src-tauri/src/shell/sign_in/restoration.rs`
- `S04` `M` `native/desktop/src-tauri/src/shell/user_profile/household.rs`
- `S04` `M` `native/desktop/src-tauri/src/shell/user_profile/wire.rs`
- `S04` `M` `native/manager/src/macos/login_start.rs`
- `S04` `M` `native/application/tests/installation.rs`
- `S04` `verify:` `cmake --build build/windows-x64 --config Debug --target desktop-host-unit-clippy` -> `pass`
- `S04` `verify:` `ctest --test-dir build/windows-x64 -C Debug -R manager.rust_or_clippy` -> `pass`
- `S04` `verify:` `ctest --test-dir build/windows-x64 -C Debug -R '^manager\.(rust|clippy)$' --output-on-failure --no-tests=error` -> `pass`
- `S04` `verify:` `ctest --test-dir build/windows-x64 -C Debug -R '^application\.(rust|fmt)$' --output-on-failure --no-tests=error` -> `pass`
- `S04` `verify:` `ctest --test-dir build/windows-x64 -C Debug -R '^application.clippy$' --output-on-failure --no-tests=error` -> `pass`
- `S05` `M` `native/desktop/frontend/package.json`
- `S05` `M` `native/desktop/frontend/package-lock.json`
- `S05` `M` `dev/packaging/native/linux_desktop_runtime.py`
- `S05` `M` `native/desktop/tests/automation/session.test.mjs`
- `S05` `verify:` `cmake --build build/windows-x64 --config Debug --target desktop-native-automation-harness-test` -> `pass`
- `S05` `verify:` `cmake --build build/windows-x64 --config Debug --target desktop-packaged-harness-test` -> `pass`
- `S05` `M` `dev/registry/tests/test_desktop_asset_requests_decode.py`
- `S05` `M` `native/desktop/frontend/tests/support/assetRequests.ts`
- `S05` `verify:` `uv run --no-sync pytest dev/registry/tests/test_desktop_asset_requests_decode.py -q` -> `pass`
- `S05` `verify:` `uv run --no-sync ty check dev/registry/tests/test_desktop_asset_requests_decode.py` -> `pass`
- `S05` `M` `native/cmake/platforms/Windows.cmake`
- `S05` `M` `native/platform/tests/consumer.c`
- `S05` `A` `native/tests/platform_consumer.py`
- `S05` `verify:` `ctest --preset debug -R '^platform\.(static|dll|rust|resolver)$' --output-on-failure` -> `pass`

## Notes

- `S03` Partial App extraction; full frontend verification pending concurrent asset refactor. Earlier App hook changes were included by another concurrent workspace commit; preserve that history.
- `S03` Typecheck reported one intermediate unused Section import in concurrent StockBookForms extraction; owner notified. Full integration remains pending.
- `S04` Partial corrective checkpoint; S04 stays open. Desktop Clippy passes after boxing large error/field payloads, preserving serde wire names. Post-edit shell filter:531 passed. Manager Rust and Clippy passed after platform-native test fixture roots. Application Rust/fmt/Clippy passed after exercising manager-image verification in cancellation fixture. Combined full host run before layout edits:867 passed,1 subprocess fixture ignored. Exact manager CTest regex was `^manager\.(rust|clippy)$;` verification label is a descriptive shorthand. No commits or staging by CHECKS.
- `S04` The preceding `manager.rust_or_clippy` label is not an executed test regex; the exact executed commands are recorded in this entry.
- `S05` S05 remains open. Fresh frontend CMake check:60 tests passed, exit0. Node audit clean after WebdriverIO10.1 and scoped glob14/minimatch11 overrides; repo setup730 packages passed. Harness portability12 tests and packaged harness45 tests passed. Linux default/automation dependency trees reviewed for both architectures; pinned evidence refreshed;64 focused Python tests passed,2 Linux-tool skips. Standalone vendor Wry dev graph retains2 unmaintained advisories, pending operator disposition. Desktop binary and isolated GUI host built, but headless/GUI acceptance has not run: docs compiled+indexed then refused concurrent M130 source/authority drift. Wait for BACKEND explicit settled commit before retrying stage. Agent uv.lock in X:/code/cadrumo-agent was updated to match shared packaging dependencies and uv lock --check passed. CHECKS has committed nothing; working manifests include other sessions uncommitted source, never commit blindly.
- `S05` Asset request decode lane:56 passed, previously51 failures. Node harness now installs canonical backend `ledger_entry_limits` via holdLedgerLimits; production fail-closed parsing unchanged. Python ruff/format and TS prettier pass. Broad full-suite evidence remains unavailable on unsettled M130 source. S05 remains open.
- `S05` C ABI lane repaired:4 platform CTests pass through worker verification. Isolated admitted build scratch holds copied consumers/DLL, with negative cwd-only marker refusal and positive image-local package evidence; full original ABI assertions remain. Ruff/format/ty for native test runner pass. Production Package::installed unchanged; assembled bundle environment conformance still blocked until M130 settles. No commits by worker or coordinator.
- `S05` Additional verification: `ctest --test-dir build/windows-x64 -C Debug --output-on-failure -R '^manager[.]supervision$'` passed 1/1 (119.15s), Rust257 passed/0 failed including43 supervision cases; one existing ignored manual timing benchmark. No worker source changes. Bundle lifecycle and real GUI remain unverified.
- `S05` Chrome declaration cleanup: removed17 keys no longer named by shell, preserving10 disagreement keys. Canonical locale CLI removed16 confirmed orphan keys per locale (64 leaves); desktop.agent.resize retained in catalogue for its other consumer. Exact-key source search and dynamic workspace-prefix review found no live removed keys. Updated contextual product identity inventory for3 retired workspace keys per locale. Desktop chrome24 tests passed, generated chrome target passed, touched declarations/inventory Ruff and ty passed. Requested registry-locale parity plus capital-goods refusal/registered-operation and inventory refusal tests63 passed. Full locale audit tests remain11pass/2fail solely because static discovery misses4 live bienes_inversion constant-map translation keys; dedicated scanner repair in progress, catalogue keys kept. No commits or authority publication.
- `S05` Cross-session M130 assist: reserved12 caller-test files baseline40pass/9fail; five test-only migrations to gastos-deducibles-previos and directa_normal yielded49pass, financial assertions unchanged. Ruff/format/ty passed; no unrelated failures or shared support edits. Per-file findings delivered to BACKEND owner; atomic review/commit belongs to that owner. No source/authority settled notice yet; docs/staging rebuild stays held.

- `S04` Full post-layout desktop host verification: `cmake --build build/windows-x64 --config Debug --target desktop-host-unit-test` passed,867 passed/0 failed/1 existing ignored subprocess fixture,0 filtered,372.06s. Prior shell-only verification is superseded for host unit coverage; this does not prove staged package lifecycle or GUI.
- `S05` Operator-authorized typed-boundary fix committed with `--only` as `00a02c8f35`, exactly two reserved production files plus seven regression cases. All15 basedpyright diagnostics resolved; ty,pyrefly,Ruff pass. Focused requested asset/TUI/credit/publication populations pass; expanded run1031passed/8failed solely new M130 PROFILE_FACT_UNRECORDED test fixture, assigned to M130 owner. No schemas,keys,wording or manifest changed.
- `S05` Standalone vendored Wry lock time0.3.45 updated to0.3.55 with required companions through targeted Cargo resolution, provenance recorded in CADRUMO-PATCH.md. Locked normal Windows tree passes; exact advisory gate verified3->2 findings, still exit1 on dev-only paste and ttf-parser. No exceptions added. Native GUI/package acceptance remains held pending backend atomic source/authority settlement.
- `S05` Locale scanner constants/dictionary fix:61 focused/guard/production checks pass, including fresh-cache actual manager audits. Normal `just check-locales` still exits1: stale shared result misses4live bienes keys and a finite confirmation-block family was unregistered. Canonical enum-derived family registered;2 existing enum-coverage tests and Ruff/ty pass. Separate loaded-code cache-provenance repair in progress; no catalogue live keys removed or gate exclusions.
