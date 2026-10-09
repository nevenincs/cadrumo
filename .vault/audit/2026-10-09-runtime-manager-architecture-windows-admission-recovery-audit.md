---
tags:
  - '#audit'
  - '#runtime-manager-architecture'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:c6d098bd7194fa5c6320b225cdb292d23a9a685151d35363b29761eb4eeafc34'
related:
  - "[[2026-10-04-runtime-manager-architecture-plan]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]"
---

# `runtime-manager-architecture` audit: `Windows Session 0 and explicit manager recovery`

## Scope

Review P02.S28 against HEAD and its uncommitted native/manager diff under the operator's 2026-10-09 instruction to fix bootstrap and recovery and verify the Session 0 premise. The concurrent desktop-service-installation session owns installer, package layout and desktop/sign-in bootstrap changes. This audit covers native/manager source only, preserving unrelated edits. Code semantic search was unavailable (unresponsive/crashed service); current named-source inspection and accepted decision discovery provided grounding.

## Findings

### session-zero | low | Windows-defined role boundary, not a universal application refusal

Microsoft's Service Changes for Windows Vista documentation reserves Session 0 for services and other processes outside an interactive user session: https://learn.microsoft.com/en-us/windows/win32/services/service-changes-for-windows-vista. Application code can run there; a desktop or interactive supervisor needs a different role. `native/manager/src/admission.rs` refuses Session 0 only for the interactive manager and separately checks elevation and desktop availability. Arbitrary nonzero sessions are accepted by the session-number policy, subject to the other evidence. `src/cadrumo/adapters/local_runtime/windows_login.py:capture_windows_login` admits same-account clients from any session while binding their authority to the runtime's verified desktop. `native/desktop/src-tauri/src/launch.rs:select` keeps headless CLI paths available without a desktop. The OS session number is not substituted for native owner/login proof.

### explicit-recovery | medium | Recovery activation previously sent Reveal to an existing manager

`native/manager/src/main.rs` previously sent Reveal for every non-sign-in duplicate activation. Explicit Retry must remain distinct from normal GUI launch because it clears failed-version state. P02.S28 adds the closed `--retry` activation, preserves it through job escape and selected-version redispatch, routes it to authenticated manager Retry, and refuses an unavailable recovery acknowledgement. An absent manager's retry selects the newest complete package without modifying failure state before native/session admission; only the admitted owning manager clears failures. No new runtime transport verb or forced stop is introduced. Invocation, admission, failure-record and executable tests cover the changed boundaries. Actual installed, interactive dispatch remains a disposable-host obligation.

### restored-owner | medium | Review corrected retry selection to retain exact-image IPC compatibility

The initial newest-package retry selection described above was revised before checkpoint. Retry now preserves valid failed-version restoration, just as normal activation does, so a compatible restored manager receives the authenticated request. Its existing Retry path clears failures and reassesses installations through the governed idle cutover. Only malformed failure data permits selection without restoration; dispatch still verifies the package and may neither edit the record nor acquire authority before admission. Custody-protected failure replacement remains owner-only and refuses links. Older released manager images without the new activation grammar cannot be assumed to support this flag; cross-release acceptance remains pending and must cover this compatibility boundary.

### configured-clippy | low | Ambient Clippy selected a different compiler from the configured Cargo build

The first isolated Clippy invocation selected ambient Rust 1.99 against artifacts built with configured Rust 1.96 and failed E0514. Explicitly prepending the configured toolchain bin directory selects its cargo-clippy and clippy-driver; the final lint check passes. No source defect or global toolchain change was required.

### configured-toolchain-fix | low | Cargo subprocesses now resolve subcommands from the selected toolchain

P02.S29 fixes the earlier ambient Clippy observation in the canonical `dev/packaging/native/cmake_build.py:run_configured_command` owner. Cleanup and Cargo execution receive a child environment whose PATH starts with the selected Cargo bin; inherited entries and the parent environment are retained. The regression executes a real offline Clippy build with conflicting ambient cargo-clippy and clippy-driver executables and proves that the wrapper selects the configured tools. No global Rust default or toolchain identity schema changes. Independent root verification reran the original configured Rust 1.96 frozen-manager Clippy invocation without its prior temporary PATH override and passed.

### retry-capability | medium | Unsupported historical restoration now refuses redispatch before recovery activation

P02.S30 adds exact silent `--supports-retry` metadata admission before runtime startup. A current dispatcher probes only a different catalogue-verified selected manager, retaining its selection lease. A nonzero legacy/failed exit refuses redispatch without clearing failure state or sending Reveal. Exit polling and metadata-child termination each have a two-second bound; only that child is targeted. Real subprocess tests corroborate exit, timeout cleanup and unchanged failure bytes; actual manager metadata leaves the full scratch directory inventory unchanged. This resolves the new-dispatcher-to-old-restoration boundary, not automatic recovery by all historical binaries.

### supervision-contention | low | Existing short-bound supervision tests required serial verification

The first frozen full run passed activation and preceding suites but failed two unchanged supervision cases during fresh parallel Tauri compilation: one missing graceful session-end exit fact and repeated Hang events instead of one. Source review found no altered supervision argument path; the tests use 500ms readiness/session-end and 600ms heartbeat timing. The same frozen supervision suite rerun serially after compilation passed all 37 cases without expectation or policy changes. This supports contention as an explanation without proving the original scheduling cause. The initial failure remains in verification history.

### desktop-retry-forwarding | medium | Explicit recovery is now distinct from automatic startup and installation

After the operator released the desktop files, P03.S31 threads the existing retry boolean from start through dispatch and admits only optional exact --retry in the Explorer adapter. Retry uses the catalogue-verified versioned `Selection.manager`; ordinary startup and installation use the stable entrypoint. This avoids a legacy stable entrypoint rejecting the new flag before version dispatch. Discovery and the selected package lease remain mandatory; the desktop never supervises or signals the runtime. Native command construction and the actual Python adapter grammar/automation boundary have scoped tests.

### retry-coalescing | medium | Review corrected a lost recovery request behind ordinary startup

The first forwarding implementation retained a prior generation-only deduplication rule, which could share a non-retry outcome with an explicit Retry waiting behind startup or installation. Final code stores the settled attempt's intent privately: normal calls can reuse the cached outcome, while a concurrent Retry shares only a completed Retry. A barrier regression proves that recovery work runs after ordinary settlement; existing overlapping Retry coalescing, abandoned caller and close/cleanup tests continue to pass. Installation is classified as ordinary dispatch.

## Recommendations

The remaining source integration recommendations from this audit are implemented under P02.S29, P02.S30 and P03.S31. Explicit recovery dispatches the verified selected manager with --retry; normal startup and installation use the stable entrypoint. Never interpret Explorer acknowledgement or metadata capability success as recovery completion: runtime readiness remains the authenticated handshake.

Disposable interactive Windows acceptance remains required for a clean unregistered distribution with its companion kit, existing/restored manager recovery, historical unsupported-manager tray recovery, GUI close survival, session end and idle cross-release cutover. Preserve the development host; no service/login registration or user-session transition occurred during these checks.

The manager remains an interactive per-user login background process, not an SCM service. A future SCM host requires separately authorized service-account/session bindings and cannot share the interactive-manager admission unchanged. Merely permitting Session 0 in this manager would violate its desktop and per-user runtime assumptions.

## Verification

PASS for P02.S28 software scope: configured pinned Rust 1.96 Windows x64 test command, locked manifest and static CRT, against the frozen source/contract snapshot at `build/windows-x64/testing/manager-recovery-20261009`, output isolated under `build/windows-x64/cargo/native/manager-recovery-20261009`. The initial default suite passed 167 tests; after the restoration correction, the final full suite with fixture-test-mode passed 205 tests including 37 supervision and one termination test. This covers native Session 0 executable refusal, arbitrary nonzero session-number policy, closed retry parser/redispatch, restoration and malformed failure state, real authenticated IPC, custody, ownership, crash/hang recovery and session-end supervision. `cargo fmt --manifest-path native/manager/Cargo.toml -- --check`, Clippy all-targets with fixture-test-mode and warnings denied, and scoped git diff --check passed. Inspect `command-pinned.json`, `tests-fixture.log` and `clippy.log` in the snapshot directory for configured inputs and output.

PENDING for installed acceptance: native interactive installation, logout, clean GUI bootstrap, cross-release activation and version-cutover acceptance are unverified. The current host runs in Session 0; fixture children can run but cannot establish interactive desktop acceptance. No product registration or user-session mutation occurred. The concurrent session owns combined installer/desktop verification; existing open manager acceptance Steps remain open. No critical or high software finding remains in this scoped review.

P02.S29 PASS: eight focused Cargo/toolchain and build-timing tests passed; scoped Ruff lint/format, configured ty checks on Linux/Windows/macOS, and git diff --check passed. Test log: `var/storage/development/.logs/test-runs/2026-10-09/20261009T073708.909283Z-pytest-33324-612e00fe/run.log`. Root's configured Rust 1.96 manager Clippy check passed without a PATH override; output at `build/windows-x64/testing/recovery-followthrough-20261009/clippy-toolchain.log`. These developer files are outside the configured strict production subset. Desktop forwarding and restored-manager probe follow-through remain in progress under P03.S31 and P02.S30.

P02.S30 PASS for scoped software: frozen source and generated contracts under `build/windows-x64/testing/recovery-followthrough-20261009`; configured Rust 1.96 Windows x64 locked tests with fixture-test-mode, static CRT and isolated native output. The initial run passed 168 tests before supervision failures; all 37 supervision cases subsequently passed serially, and the four termination/version-resource cases passed separately. Final aggregate covers 209 manager cases; no tests were skipped or expectations weakened. Clippy all-targets/fixture-test-mode with warnings denied and configured fmt passed. Inspect `manager-command.json`, `manager-tests.log`, `supervision-serial.log`, `manager-final-tests.log` and `manager-clippy.log`. The new probe can establish grammar compatibility only; actual installed restoration, old-manager tray recovery, GUI launch and authenticated runtime readiness remain pending disposable-host acceptance.

P03.S31 PASS for scoped software: final corrected frozen desktop manager selection passed 22 tests (including real package admission, dispatch cleanup, concurrent calls and the lost-retry barrier regression), and full desktop all-targets Clippy passed with warnings denied under configured Rust 1.96. Eight Python adapter tests passed; scoped Ruff lint/format and ty checks for win32/linux/darwin passed for both adapter and test. Rust fmt and scoped whitespace checks passed. Final Python log: `var/storage/development/.logs/test-runs/2026-10-09/20261009T075519.455490Z-pytest-17488-d16d6489/run.log`. Native records: `desktop-integrated-test.log`, `desktop-integrated-clippy.log` and `desktop-test-command.json` under the follow-through snapshot root.

Commit isolation: external installer/bootstrap changes in desktop manager source remain uncommitted and outside this checkpoint. HEAD-based staging-source variants contain only this recovery correction, command helper and tests; their standalone native manager selection passed 21 tests after explicitly refreshing copied-source timestamps to prevent stale Cargo reuse. Inspect `staging-src`, `desktop-staged-test.log` and `staging-verification-output.log`. Final working-source snapshot is restored to the verified integrated version. Root will commit only isolated recovery blobs, the adapter/test and its own records, preserving the external source diff.

Final review: PASS for P02.S29/P02.S30/P03.S31 software. A GPT-6.1 Sol medium reviewer independently traced the combined flows and raised the coalescing and legacy stable-entry findings; both were corrected and covered by the applicable final checks. Root confirms no outstanding critical/high or unfixed in-scope software defect. Feature vault health has zero errors and two existing whitespace warnings; plan ordering warning is expected from append-only identifiers grouped by phase. Installed acceptance remains PENDING: machine/user installation, interactive GUI/COM launch, old-owner tray recovery, logout and two-release idle cutover were not run on this Session 0 development host. The installer session retains its provisioning and package-assembly verification scope; earlier historical pending statements are superseded only for this audit's software integration.

Repository-wide vault check after the scoped commit failed with two errors and 47 warnings outside this software verification: an unreplaced {title} placeholder in `2026-10-09-desktop-frontend-coherence-audit` and missing grounding references in `2026-10-07-git-free-tooling-adr`. The feature-scoped check remains zero errors; unrelated records and concurrent work were not repaired by this audit continuation. This exception prevents claiming a repository-wide clean vault, but does not invalidate the applicable source/test results or reopen these scoped recovery Steps.
