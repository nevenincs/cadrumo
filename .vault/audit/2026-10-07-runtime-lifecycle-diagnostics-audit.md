---
tags:
  - '#audit'
  - '#runtime-lifecycle-diagnostics'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:4acee64bd095252f5dcdf9d78a0c82521c28ea4f9340f826628fc1c574ce1304'
related:
  - "[[2026-10-07-runtime-lifecycle-diagnostics-plan]]"
---

# `runtime-lifecycle-diagnostics` audit: desktop startup and process diagnostics

## Scope

Review the uncommitted S01-S04 implementation against the accepted runtime-manager, supervisor-contract, desktop-shell and canonical-environment decisions. Root owns integration and shared native checks; GPT-6.1 Sol xhigh workers own Python diagnostics, native attribution, and log parsing/display. Independent cross-reviews trace the Python producer through the native parser and viewer, and desktop startup through shell dispatch to manager ownership. Existing unrelated edits and the separate session's manager implementation are outside the patch ownership.

Current verdict: PASS for completed logging S01-S03 and the user-requested bounded desktop integration; REVISION REQUIRED before installed lifecycle release. S04 remains open pending canonical version-independent launcher discovery. Passing tests below establish bounded code behavior, not package acceptance or upgrade correctness.

## Findings

### launcher-discovery | high | Current-package dispatch does not satisfy version-independent manager discovery

The candidate `native/desktop/src-tauri/src/manager.rs` verifies and dispatches the manager in the GUI's selected package. An old GUI can therefore request an old manager after a newer complete version is installed. The concurrently implemented `native/manager/src/installed.rs` inspects its own package only. Accepted distribution and manager decisions include archives and require a stable entry point and newest-complete-version selection; no accepted standalone-package exemption or implemented discovery contract was found. S04 is not approved for shipping and stays open until the distribution/manager owner provides the canonical discovery seam. No installer, login registration, or live manager dispatch was performed in this work.

### child-attribution | medium | Helper failure cleanup originally lost attribution and misreported exits

Independent native review found that spawn failure lacked a process role and cleanup errors returned before child-attributed failure emission. Already-exited helpers could be marked terminated. Corrected in `manager.rs`: role-attributed spawn failure, primary error emitted before cleanup, secondary cleanup error retains the process ID, and actual exit versus forced termination is distinguished. Real harmless subprocess tests cover successful acknowledgement, malformed/private output, failed exit, timeout and output flood. Resolved by source review and native tests.

### elevation-admission | medium | Token elevation must use the manager's full-UAC-elevation criterion

The original Python helper tested TokenElevation, which also excludes administrators running with UAC disabled. Changed `python/manager_dispatch.py` to compare TokenElevationType with TokenElevationTypeFull, matching manager admission. The installed pywin32 constants were checked and scoped Ruff passed. No privileged launch was performed.

### multiline-context | medium | Multiline Python messages need metadata on the record header

Cross-review found that appending context after a multiline message puts it on a continuation line while the native parser reads metadata from the header. Producer and parser owners are correcting the physical record layout and adding a genuine multiline-message regression. Until those checks pass, this is unresolved.

### cleanup-observability | high | Diagnostic interruption must not skip mandatory resource cleanup

Independent review found that BaseException raised by a diagnostic handler at TUI cleanup start or runtime listener drain start could prevent mandatory cleanup. Python owner is correcting these paths and adding cancellation/interrupt regression coverage. This must pass before S01 closes.

### verification | low | Native and browser checks pass within their stated test boundaries

Windows pinned Rust 1.96.0 backend runner Unit completed with 167 passed, zero failed or ignored; Clippy completed successfully. These cover parser/tail behavior, native consumer attribution, sign-in secret/EOF/timeout cleanup, manager attempt caching and explicit retry, and manager helper control replies and process cleanup. Native application checks previously passed 19 tests and Clippy. Browser scenarios passed 3 new log scenarios, 6 existing log scenarios and 4 follow-up log/narrow-window scenarios, plus 6 manager scenarios. Frontend TypeScript, ESLint and formatting passed. Browser manager scenarios are synthetic and do not prove live Explorer ancestry or runtime readiness. Read-only Explorer COM traversal succeeded without calling ShellExecute. Package lifecycle acceptance requires a disposable host and remains outstanding.

### follow-up-2026-10-07 | low | Bounded desktop delivery and updated native checks

The user clarified: "Handle the desktop integration here; flag the launcher dependency". Desktop integration is delivered as a bounded change; the high launcher-discovery finding remains a release prerequisite, not an implicit architecture exemption. Private manager-dispatch helper ownership is now fenced and awaited on CloseRequested and run_return; manager/runtime ownership stays independent. A real blocked helper is reaped before close completes and later requests are refused. The updated backend Unit suite passed 172 tests, including all three early-log-location/persistence tests and the genuine multiline-message parser regression. Clippy passed after the equivalent inspect_err instrumentation correction in main.

### early-startup-log | medium | Default-root projection failures now have durable native records

Previously, manifest/interpreter/projection failures happened before diagnostics acquired a file sink. The new `startup_logging.rs` configures it after instance admission using actual executable evidence, the captured canonical root environment and generated default log paths, before package validation. Same-path final configuration does not replay the buffer. Declared nonblank member overrides defer to canonical Settings; invalid or unavailable location authority stays a safe buffered refusal instead of writing to an invented path. Native application tests passed 20 cases and isolated Clippy; backend tests prove projection failure persistence and omission of private error text. This resolves the normal installed-root durability gap.

### checkpoint-lock | low | Existing shared Git index lock prevents selective checkpoint commits

Attempted selective staging failed before changing the index because the worktree's existing index.lock is held or stale. Its timestamp predates this checkpoint; other sessions are active in the shared workspace. The lock was not removed and unrelated work was not staged. Verified code and vault checkpoints remain in the working tree; the native worker's selective environment patch is available for a later checkpoint. No source content was rolled back.

### final-python-review | low | Producer corrections pass focused tests and scoped checks

Multiline context, diagnostic-handler interruption and proof-erasure findings are resolved. The final TUI terminal diagnostic now precedes mandatory shared-authority release, because redaction may itself consult the authority; logging after release had reopened its database. Source review verified ordering and cleanup preservation. The focused Python suite passed 146 tests (configured integration marker deselected one case), followed by 20 final formatter/cleanup/privacy fault tests and three launcher authority-release tests. Three native launch-door integration tests separately passed. Ruff check and format, ty across all 19 touched Python files, and basedpyright on the new formatter module passed. Evidence run IDs are 20261007T050244.952810Z-pytest-7228-77dc5baa, 20261007T050551.666215Z-pytest-37908-1c8d1cb5, 20261007T050441.115516Z-pytest-29968-e7ab88b4, and 20261007T045107.625899Z-pytest-79424-24fd6ca1 under the development test-runs logs. Prior repository-wide type/import gates also found unrelated worktree issues; shared import inventory was regenerated to enroll the new module before the final gate.

### hardening-review | medium | Root-owned lifecycle review exposed concurrency and cancellation defects

S05 follows the user's explicit delegation correction: root owns architectural review and lifecycle implementation; GPT-6.1 Sol workers implement narrowly assigned diagnostics and browser tests. A failing 64-caller retry regression reproduced 64 dispatch attempts. Generation-aware coalescing now shares one in-flight attempt while preserving later explicit retries. A host-owned task retains the attempt guard when an IPC caller is cancelled. Close fences admission, interrupts the private helper and reaps it; the regression blocks a helper for 60 seconds and requires close within three seconds. The independent manager and runtime are never stopped by desktop close.

Each actual dispatch now re-reads the manifest and verifies manager bytes on a blocking worker, rather than caching an executable admission or permanent failure at startup. ABI/platform mismatch, missing/corrupt images, malformed manifests and traversal members are refused; repaired packages can pass a later attempt. Relocation tests use spaces and Unicode without working-directory assumptions. Oversized native images are rejected from open-file metadata before allocation/read, with the existing bounded read retained against subsequent growth. The 128 MiB plus one byte fixture fell from 207,831 to 2,631 microseconds in single local observations; this is not a statistical product benchmark. Three binary admission tests and application Clippy passed.

The changed helper lifecycle passed all 13 focused manager tests. Tests include absent executable/cwd, removed PATH/PYTHONPATH, discarded noisy stderr, cancellation, timeouts, malformed control output, repeated helpers and package recovery. Separately, all 34 existing manager supervision fixture tests passed, covering foreign runtime refusal, competing start claims, hung-runtime recovery, crash backoff, adoption and session-end/Quit handling. Eight platform storage tests passed. These manager tests inspect the other session's implementation without changing it or invoking live installation/registration.

### logging-resource-review | medium | Fixed avoidable formatter allocation and duplicated partial replay

Python diagnostics now inspect a closed metadata allowlist rather than sorting/copying every LogRecord field. Formatting temporarily changes and restores only the rendered message, preserving original record arguments and multiline behavior. Forty-nine focused logging tests and the final 14 diagnostic tests passed, including task/thread correlation, cancellation isolation, handler reuse and large payload bounds; scoped Ruff, ty and basedpyright passed. The five-trial synthetic probe with 100,000 ignored extras reduced single-line peak formatter allocation from 1,601,377 to 953 bytes and median formatting from 197.081 to 0.0854 ms. These exclude record creation, the full scrubber and file I/O. Large multiline allocation remains proportional to rendered text. Evidence: test runs 20261007T052708.600408Z-pytest-48364-58c7d0e1 and 20261007T052857.470722Z-pytest-7852-86660ef1, with rerunnable probe artifacts in the latter.

Native sink recovery reproduced duplicate persisted sequence 1 after a partial configuration replay. A single bounded pending replay cursor now resumes after the last successful record for the same target; changing target resets replay and the old active sink remains usable on failure. Twenty-five native application tests and Clippy passed. The eight-thread stress test produced 2,048 events and one MiB of captured bytes while snapshotting and rotating: 4.715 seconds, 63 snapshots, 11,162 retained file bytes. Existing ring/process/output caps remain 512/128/256 KiB. An append refused by an external file lock remains a surfaced disk gap with sticky failure state; these diagnostics do not promise lossless persistence or replay of evicted records.

### startup-ui-review | medium | A failed readiness request must preserve known unavailability

A rejected status read previously replaced known-down runtime state with the generic unknown projection, exposing the password form. The catch path now preserves the last known availability consistently in state and latestStatus. All ten manager browser scenarios passed against the concurrent session's newer startup UI. The tests cover late replies after remount, ten retry clicks causing one request, continued unavailability after a failed status read, no profile reads while unavailable, no dispatch before explicit retry, and successful recovery. Three representative cases passed again with stronger assertions; scoped frontend checks passed. Browser fixtures do not establish real runtime readiness.

### measured-bounds | low | Measurements establish fixture behavior, not installed acceptance

The isolated 32-sample 64 KiB package verification fixture measured median 4.518 ms and p95 7.134 ms; an integrated suite run measured 6.792/7.825 ms. Twenty-four helper launches measured median 348.826 ms and p95 428.364 ms in the isolated run. A separate psutil observation of helper churn found peak parent RSS 11,296,768 bytes, process-tree RSS 94,699,520 bytes, peak handles 130 and no surviving children among 48 observed helper/console processes. Artifacts are under var/storage/development/build/runtime-hardening/. This finite churn observation is not a long-duration leak proof or GUI startup SLA. Filesystem verification is off the async worker but an OS-stalled read cannot be cancelled by the helper's 15-second timeout. Actual Explorer launch ancestry, installed relocation/upgrade, full packaged memory/startup and profile creation still require a rebuilt package on a disposable host; the stable launcher remains the explicit S04 prerequisite.

Final S05 integrated verification: desktop backend Unit passed 179 tests with no failures or ignores, followed by backend Clippy. Root rustfmt and scoped diff checks passed. Root review approves the bounded hardening changes; the existing launcher-discovery release finding remains unresolved and S04 stays open.

## Recommendations

### manager-diagnostics-follow-up | medium | Lifecycle observations must reach a durable sink

After the operator handed remaining integration to this session, root reviewed the committed manager startup and found supervisor observations discarded by the background owner. S06 now routes typed startup admission, inspection refusal, ownership wait, runtime launch/readiness/exit, restart, shutdown and final outcome into the canonical manager log. The shared native sink retains its rotation, bounded replay and safe error projection. Early admission failures remain buffered/stderr until strict root admission permits a durable sink; no alternate root is invented. Package refusal categories come from owner error variants, not text matching. Dynamic version, boot identity, raw output and private paths are excluded from lifecycle facts.

### manager-shutdown-and-memory | high, resolved | Observer pressure must not stall control or grow queues without bound

Root review required bounded supervisor input (256) and observation (512) queues. Reader backpressure is isolated from control callers; event emission never waits for the log consumer and records a saturating loss count. SessionEnd publishes the existing atomic restart fence before attempting the full input queue. Consuming the supervisor disconnects its receiver on return, releasing blocked readers even when a control handle survives. Real subprocess flood tests cover 8,192 malformed announcements, saturated controls, absent observers and runtime cleanup.

Root also corrected background ordering: request session end and wait for settlement before diagnostic file I/O. Active message-loop polls consume at most 64 events; continuously replenished events therefore cannot keep a drain loop running indefinitely. Final draining after the producer joins consumes the bounded remainder. A timed-out settlement retains cleanup ownership. This bounds queue memory and event work, not the duration of an operating-system-stalled filesystem call.

Final frozen-tree evidence: 65 manager library, 3 manager diagnostic and 37 supervisor tests passed (105 total); all-target manager Clippy with fixture and live-package features, formatting and scoped diff checks passed. Commands, source hashes and logs are in `build/windows-x64/cargo/native/package-acceptance-bounded/verification.json`. Native application checks passed 11 library and 17 diagnostic tests plus Clippy; canonical projection tests passed 6 tests and scoped Ruff/ty. The source review is root-owned; Sol 6.1 workers performed implementation and supporting checks.

### manager-viewer-integration | medium, resolved | Read manager records without accepting arbitrary persisted payloads

S07 carries the canonical fixed manager-log path through the environment projection into the existing tail engine. Python and manager readability states are independent; malformed manager rows are counted without displaying their contents. Complete-line JSON parsing rejects foreign sources, unknown fields and unknown variants. Persisted failure message text is ignored and reconstructed from closed error codes. Actual negative tests exposed Serde's internally tagged unit-variant unknown-field acceptance; empty struct variants now preserve the wire shape while enforcing rejection. Rotation, partial lines, privacy, per-source banners and loss context have regression coverage.

Root reran the complete desktop backend: 187 tests passed, followed by Clippy. Twenty distinct browser log/manager scenarios passed, including corrected source-labelled baseline expectations; TypeScript, scoped ESLint/formatting and 16 locale tests passed. Evidence is under `var/storage/development/build/runtime-release-check/` and `build/desktop-windows-x64/desktop/test-results/manager-logs-check*`.

### empty-root-package-fixture | medium, resolved | A profile acceptance fixture needs a runtime before creating its profile

The packaged sign-in fixture previously attempted profile creation before launching its isolated runtime. It now starts the contained empty-root runtime, verifies the handshake, creates the profile, and waits for canonical profile selection before continuing. Cleanup handles partial creation, closed stdin and failed writes, and clears the stop deadline timer. Nine focused Node tests plus Python/JavaScript formatting and syntax checks passed. Exact commands and hashes are recorded in `build/desktop-windows-x64/desktop/test-results/packaged-fixture-lifecycle/20261007T062535Z-65848.json`.

This host is Windows Session 0. No interactive desktop/profile/login acceptance or live default-root manager launch is claimed. Full package rebuilding is in progress; its documentation compiler executes real CLI sequence witnesses and cannot be bypassed for a release claim. Version-independent launcher discovery and installed upgrade acceptance remain the unresolved S04 release prerequisite explicitly accepted by the user.

Final shared-gate evidence: regenerating finite import-load metadata succeeded and all 4,519 governed non-test modules loaded. The aggregate gate failed: the bare PATH lacked lint-imports, the shared source tree changed during the run, and the subordinate checker reported 15 import-authority findings. Running `.venv/Scripts/lint-imports.exe` directly then passed all 15 graph contracts with zero broken contracts. These findings prevent a repository-wide clean verdict; scoped code checks remain passing. Generated inventory refresh reflects the shared source census and must not be hand-edited to isolate one module.

Resolve launcher discovery with the distribution/manager owner before S04 closes or a binary is shipped. Keep actual manager readiness independent of shell launch acknowledgement. The old packaged executable has not been rebuilt or replaced by this change. Checkpoint the reviewed changes when the shared index lock is released, preserving the unrelated working-tree edits.
