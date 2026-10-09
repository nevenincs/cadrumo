---
tags:
  - '#audit'
  - '#runtime-manager-architecture'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:3352874d98705c2f8ca513acd0f450dc23919d0958b116df2151d61634610a77'
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

## Recommendations

Integration handoff: desktop ownership should pass `--retry` only for an explicit recovery action; ordinary bootstrap retains its existing no-argument dispatch. As of this review, `native/desktop/src-tauri/src/manager.rs:start` still dispatches without the flag. That file and its Python Explorer-dispatch adapter remain owned by the concurrent desktop-service-installation session. Installer/bootstrap and end-to-end desktop recovery are not certified by this manager-only checkpoint.

The manager is an interactive per-user login background process, not an SCM service. A future SCM host requires separately authorized service-account/session bindings and cannot share the interactive-manager admission unchanged. Merely permitting Session 0 in this manager would violate its desktop and per-user runtime assumptions.

## Verification

PASS for P02.S28 software scope: configured pinned Rust 1.96 Windows x64 test command, locked manifest and static CRT, against the frozen source/contract snapshot at `build/windows-x64/testing/manager-recovery-20261009`, output isolated under `build/windows-x64/cargo/native/manager-recovery-20261009`. The initial default suite passed 167 tests; after the restoration correction, the final full suite with fixture-test-mode passed 205 tests including 37 supervision and one termination test. This covers native Session 0 executable refusal, arbitrary nonzero session-number policy, closed retry parser/redispatch, restoration and malformed failure state, real authenticated IPC, custody, ownership, crash/hang recovery and session-end supervision. `cargo fmt --manifest-path native/manager/Cargo.toml -- --check`, Clippy all-targets with fixture-test-mode and warnings denied, and scoped git diff --check passed. Inspect `command-pinned.json`, `tests-fixture.log` and `clippy.log` in the snapshot directory for configured inputs and output.

PENDING for installed acceptance: native interactive installation, logout, clean GUI bootstrap, cross-release activation and version-cutover acceptance are unverified. The current host runs in Session 0; fixture children can run but cannot establish interactive desktop acceptance. No product registration or user-session mutation occurred. The concurrent session owns combined installer/desktop verification; existing open manager acceptance Steps remain open. No critical or high software finding remains in this scoped review.

P02.S29 PASS: eight focused Cargo/toolchain and build-timing tests passed; scoped Ruff lint/format, configured ty checks on Linux/Windows/macOS, and git diff --check passed. Test log: `var/storage/development/.logs/test-runs/2026-10-09/20261009T073708.909283Z-pytest-33324-612e00fe/run.log`. Root's configured Rust 1.96 manager Clippy check passed without a PATH override; output at `build/windows-x64/testing/recovery-followthrough-20261009/clippy-toolchain.log`. These developer files are outside the configured strict production subset. Desktop forwarding and restored-manager probe follow-through remain in progress under P03.S31 and P02.S30.

P02.S30 PASS for scoped software: frozen source and generated contracts under `build/windows-x64/testing/recovery-followthrough-20261009`; configured Rust 1.96 Windows x64 locked tests with fixture-test-mode, static CRT and isolated native output. The initial run passed 168 tests before supervision failures; all 37 supervision cases subsequently passed serially, and the four termination/version-resource cases passed separately. Final aggregate covers 209 manager cases; no tests were skipped or expectations weakened. Clippy all-targets/fixture-test-mode with warnings denied and configured fmt passed. Inspect `manager-command.json`, `manager-tests.log`, `supervision-serial.log`, `manager-final-tests.log` and `manager-clippy.log`. The new probe can establish grammar compatibility only; actual installed restoration, old-manager tray recovery, GUI launch and authenticated runtime readiness remain pending disposable-host acceptance.
