---
tags:
  - '#audit'
  - '#desktop-service-installation'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:d777c764f310788753828e77527e630fd9a0ecdec3064159858a837d2d12faad'
related:
  - "[[2026-10-09-desktop-service-installation-plan]]"
  - "[[2026-10-09-desktop-service-installation-adr]]"
---

# `desktop-service-installation` audit: `Scoped desktop provisioning review`

## Scope

Review S01 and S02 against the accepted provisioning ADR, current working-tree changes over d12514012b and the established MSI/supervisor boundaries. Trace kit publication, immutable artifact admission, scoped Tauri IPC, owned installer settlement, catalogue rediscovery and manager dispatch. Other session lifecycle changes already committed on this base remain preserved.

## Findings

### installation-ownership | low | No high or critical implementation defect found

The active desktop links shared installer admission and exposes only a closed user/machine scope through the central shell-token guard. The kit is bound to the running package manifest, compiler-consumed contract, ready inventory, runner PE/hash and both scoped MSI native-owner metadata. File and ancestor custody remain held until the native process settles. The close fence prevents late process creation without cancelling an active MSI transaction. Exit alone cannot claim installation; catalogue/native-registration rediscovery is required before dispatch. Neither a runtime nor the manager is elevated by this code.

### acceptance-coverage | medium | Interactive installation and login remain unverified

PENDING for installed product acceptance. The execution host is Session 0, and both bootstrap and manager refuse that context. No user/machine registration was installed on this development host. A disposable interactive Windows host must test clean first launch without a prestarted runtime, user installation, machine UAC acceptance/cancellation, login opt-out, future TUI/CLI connectivity and restart after the desktop closes. Browser fixtures establish scoped dispatch/readiness presentation only.

### automated-evidence | low | Scoped implementation checks pass

Working tree reviewed after the Windows-only installer addition. The installer library suite passed 30 tests; the full desktop backend passed 215 tests including shell-token admission and unmanaged/closed installer refusal. Application Rust CTest passed. Packaging tests passed 14 cases, including real WiX compilation, decompiled MSI gates, tamper refusal and cleanup. Snapshot tests passed 5 cases. Browser scope/readiness presentation passed 2 cases. Configured frontend type/lint/format, Rust formatting/clippy, scoped Python Ruff/ty and canonical data-file checks passed. Canonical locale authoring wrote all four translations; the first locale audit passed. Linux cargo tree build/runtime feature graphs are identical to the prior accepted graph, supporting the dependency-fence refresh. These results do not prove interactive native installation.

The default standalone yamllint invocation used the tool's unrelated 80-character style and reported existing catalogue lines; the repository's owning dev.quality.data_files check passed with its configured YAML policy.

### native-outcome | low | Ambiguous native completion remains unconfirmed

Review corrected the bootstrap classification of nonzero native exit or failed process waiting: either can follow a native commitment whose publication is pending. These cases now return installation_unsettled instead of claiming an installation failure before any mutation. Fresh catalogue/native-owner admission remains mandatory on success. The installer library suite and clippy pass after this correction.

Follow-up root cause: existing native MSI authoring used an unconditional literal-false LaunchCondition and the native runner refused that gate. Earlier successful authoring/validation did not establish installation capability. Scoped bootstrap now requires owner-backed products authored with a nonblocking launch condition and mandatory, unconditional authenticated native-owner callbacks; unowned/admission-only products remain blocked. Compiled MSI admission validates callback sequence and condition fields. This extends source implementation under the operator's requested install capability; signing and disposable-host acceptance remain required for release readiness.

Build exception: concurrent package refresh and native-installer preparation exposed a temporary missing manifest and failed the nested configuration. No native installation ran. The package refresh completed; rerun the final build sequentially against a stable stage before using its products as evidence.

### native-installation-gate | low | Legacy installation blocker corrected and tamper refusal verified

Owner-backed MSI products now require mandatory authenticated owner callbacks instead of the legacy literal-false launch condition. Unowned products retain their unconditional block. The current Windows MSI/kit test selection passed 46 tests with WiX 5.0.2 and the actual CMake-built DLL/runner. This includes read-only compiled MSI inspection, invalid-role/contract native preflight refusal, and a separately compiled MSI with conditional authentication that database verification refuses. Valid native installation requests were deliberately excluded from this development-host test lane. The CMake installer-flow test passed and verified exact stage services cleanup ownership. Scoped Ruff and ty passed.

### owned-bootstrap-settlement | low | Temporary request closes its writer before custody admission

Review corrected the request writer's lifetime: flush/sync, close the writer, then re-enter the native plan parser and retain read-only custody. This avoids a Windows sharing refusal from the still-open writer. The installer library suite passed 30 tests with one explicitly gated assembled-package test pending; installer clippy passed. Latest desktop tests selected by manager passed 26 tests, and desktop clippy passed with the current shared bootstrap. Final native-kit assembly and its read-only admission still require completion.

### production-kit-build | low | Sequential native installer build completed successfully

The final `cmake --build build/windows-x64 --config Release --target native-installer` completed with exit 0 after rebuilding the current desktop EXE and native runner, preparing the full production payload, compiling and inspecting all four owner-backed MSI products, verifying their receipts, and delivering `build/windows-x64/stage/Release/services/kit.json` with its referenced runner and MSI files. This supersedes the earlier overlapping-build failure as build evidence. No native installation command ran. The assembled-kit read-only Rust admission test is now running against this exact stage and the generated compiler contract.

### concurrent-frontend | low | Installer hunks remain preserved during an independent refactor

The frontend-coherence plan is active in the same worktree and owns unrelated extraction/style changes. Its shared SignIn.tsx extraction preserves both scoped installer controls and installation refusals. Scope staging must include only those two installer hunks, not the independent extraction. The production bundle and frontend installer checks were built from the preceding stable source snapshot; the other plan owns broad verification of its subsequent frontend refactor.

### assembled-native-admission | low | Exact production kit admitted for both scopes

The explicitly selected `assembled_kit_admits_both_scopes_and_refuses_wrong_native_role_without_installing` test passed against `build/windows-x64/stage/Release/app`, its published services kit, and `build/windows-x64/generated/contract.json`. It verified full ready package identity/inventory, the runner's native PE/digest, both native owner-backed MSI pairs, absence of the literal-false legacy gate, wrong-role/runner refusal, owning parser request serialization, and exact temporary request cleanup. The first invocation failed because the test reused a consumed reader; the corrected test reopens a retained reader exactly as production bootstrap already does. The production implementation/artifacts were unchanged by that cfg(test) correction.

### final-code-review | low | Implementation verification passes with installed acceptance pending

Review S01/S02 over d12514012b, including this feature's uncommitted source and subsequent test-only correction. No unresolved high or critical implementation finding remains. Source verification, full native package build, and both-scope read-only production-kit admission pass. Installed acceptance verdict remains PENDING: this Session 0 host cannot establish actual user/machine native commitment, UAC cancellation, login persistence, manager/runtime readiness after a clean installed launch, or future TUI/CLI connectivity after desktop exit. No native products or login registration were installed on the development host. The implementation Steps may close with this explicit acceptance limitation; do not report installed lifecycle acceptance or release readiness as complete.

### shared-recovery-integration | low | Latest backend scope passes after concurrent recovery changes

The concurrent recovery commit e04722abb5 introduced an intent-bearing attempt record and dispatch retry argument while preserving this feature's scoped installation code. Reviewed the current installer diff over that committed baseline: installation dispatch remains ordinary intent and does not acquire explicit runtime Retry authority. Latest `tauri.mjs test-unit manager` passed 28 tests (189 filtered), including installer unmanaged/closed refusal and distinct recovery dispatch/coalescing. Backend clippy passed. S01 is checkpointed as 44a3d2a5a3; S02 includes only this feature's backend/interface changes and the two installer UI hunks in shared SignIn.tsx. Installed acceptance remains PENDING for the previously recorded interactive-host requirements.

### shared-frontend-verification | low | Completed refactor preserves verified installer presentation

The independent frontend-coherence checkpoint cdebe64c0b preserves the installation controls/refusals as this feature's remaining 47-line SignIn.tsx diff. Its audit and execution ledger report passing current-source TypeScript, ESLint, formatting, nine guard tests, production/Storybook builds, and all 382 browser assertions through a full parallel run (380 passed) plus serial rerun of the two environment/timing failures (2 passed), with source inputs unchanged. That reviewed source included the installation UI. Reuse this evidence for its unchanged shared presentation; do not attribute the separate feature's edits or its browser results to native installation acceptance. Unrelated untracked proposal and Python test work remains outside this checkpoint.

## Recommendations

Run the disposable-host acceptance before claiming installed automatic startup works. Retain the complete app plus its companion services directory for unregistered first launch; an isolated EXE cannot replace its runtime/package/installation payload. Reuse existing automated evidence while these inputs remain unchanged.
