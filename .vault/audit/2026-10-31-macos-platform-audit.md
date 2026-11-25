---
tags:
  - '#audit'
  - '#macos-platform'
date: '2026-10-31'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:a6e4c12a4bf44de480106b4b993f0356ef9286ad750f37f4ef74aad4927ac6e4'
related:
  - "[[2026-10-30-macos-platform-plan]]"
---

# `macos-platform` audit: `macOS platform bring-up plan-close review`

## Scope

Plan-close integrated review of the macOS arm64 bring-up, Steps S01 to S19, from the first commit of 2026-10-30 to `ba3168c19b` on `feature/tui`, against the plan's governing decisions and their 2026-10-31 amendments. Review was static: diff and source reading with path-length arithmetic; build, test and packaged-app evidence was taken from the ledger. Verdict: revision required, no critical findings, one high.

## Findings

### linux-instance-socket-length | high | root-scoped Linux desktop socket name exceeds sun_path

`native/desktop/src-tauri/src/shell/single_instance/posix.rs` Linux `names()` and `mod.rs:164-172` `root_key` produce `$XDG_RUNTIME_DIR/<family>.root.<64 hex>.desktop.session.<session>.activate`, about 127 bytes for the stable family against the 108-byte Linux bound, so bind fails and the first Linux launch is refused. Only macOS uses the digest-compact names and the early bound check; Linux tests use short families and S12 verification ran on macOS only. `native/CONTRACT.md` specifies the unshortened Linux names. Reopens S12.

### test-namespace-hooks-in-release | medium | caller-selected transport namespaces compiled into production

`native/platform/src/transport.rs` `DarwinTransport::beneath` became unconditionally public and `native/manager/src/session/instance.rs` `claim_session_beneath` is public without a feature gate, although only tests use them.

### caller-owned-docstring | medium | stale narrative contradicts the amended root decisions

`src/cadrumo_runtime/host/caller_owned.py:3-4` still says the installed manager supervises only the canonical default root.

### startup-outcome-fallback-root | medium | refused-root launch records into the default root with installed vocabulary

`native/desktop/src-tauri/src/startup_outcome.rs` `resolve` and `RootSelection::InstalledDefault` write the record, creating the default root if needed, when the selected root cannot be resolved, and keep installed-mode naming that the no-mode ruling retired.

### windows-uncompiled | medium | Windows changes from S08, S12 and S13 were never compiled

Static reading found no compile error, but Windows lock, mutex and pipe names changed although the contract treats them as cross-version; an older installed manager on the unscoped names can coexist with a new one during cutover.

### adhoc-integrity-channel | low | quarantine-removal guidance has no verifiable integrity channel

`docs/workstation-setup.md` tells users to clear quarantine only for the release channel's copy without naming a checksum to verify against.

### sigterm-absorbed | low | SIGTERM is absorbed while a close is pending

`native/desktop/src-tauri/src/app.rs` `quit_on_signal` replaces the default SIGTERM disposition on every Unix and routes repeats into the same pending close, so a stalled close no longer dies on SIGTERM.

### health-gate-transport-and-stderr | low | runtime-role package gate binds in the real transport directory and discards stderr

`dev/packaging/native/macos_bundle.py` `_serve_until_ready` starts the sealed runtime, which binds in the build host's real per-user transport directory, and sends stderr to DEVNULL.

## Recommendations

- linux-instance-socket-length: give Linux the same digest-compact lock and socket names and early bound check as macOS, state them in the contract, and add a Linux test with a real-length key.
- test-namespace-hooks-in-release: gate both hooks behind a test-support feature that release builds refuse.
- caller-owned-docstring: restate the caller-owned form platform-neutrally as a caller-held lifetime that takes no manager session lock.
- startup-outcome-fallback-root: rename to a neutral channel-default term and decide in the contract whether a refused-root launch may write to the default root, otherwise report on stderr only.
- windows-uncompiled: compile and lint the Windows targets in CI before merge and either accept or test the cutover coexistence of scoped and unscoped names.
- adhoc-integrity-channel: publish SHA-256 checksums beside the DMG and ZIP and point the first-run section at them.
- sigterm-absorbed: add a final watchdog that exits once the close exceeds its declared budget.
- health-gate-transport-and-stderr: capture a bounded stderr tail into the gate's failure and run the gate in an isolated transport namespace.

Resolution 2026-10-31: linux-instance-socket-length fixed in `ae1aa0edd2` (Linux code paths not compiled on this host); test-namespace-hooks-in-release in `872104c9fb`; caller-owned-docstring in `af41de029a`; startup-outcome-fallback-root in `0091422a17`; sigterm-absorbed in `1ccdf4bcf6`; health-gate-transport-and-stderr in `9761d014e5` (stderr tail captured; the transport directory is OS-derived and cannot be redirected, documented at the gate). adhoc-integrity-channel is not a failure and was not pursued. windows-uncompiled is outside this macOS work and remains for its owner.
