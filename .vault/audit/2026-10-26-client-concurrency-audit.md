---
tags:
  - '#audit'
  - '#client-concurrency'
date: '2026-10-26'
modified: '2026-10-26'
body_schema: 'body-v2'
body_hash: 'sha256:94692cb7da2c4a5c3f42e8da6bed18ffaf639b6db87d30867ea9e7a4e4e8eb3e'
related:
  - "[[2026-10-26-client-concurrency-plan]]"
---

# `client-concurrency` audit: lifecycle, deadlines and scheduling

## Scope

2026-10-26 review of the client-concurrency plan, commits e16357340a and b4ed3d1b3e, and subsequent Python retirement/retry changes. Three Luna 6 Max agents supplied read-only discovery; the principal verified findings and implemented changes alongside the user's concurrent runtime session. Code semantic search was unavailable; targeted searches were used. Decision search succeeded. Verdict: PASS for the scoped client implementation, independent review, Release bundle, full Windows packaged lifecycle and Rust package acceptance. The aggregate quality run has unrelated unused-core API findings, detailed below; repository-wide quality is not claimed green.

## Findings

### async-cues | medium | Fixed redundant scheduling and stale or missing subscriptions

`src/cadrumo_client/transport/operation_changes.py` coalesces thread-to-loop notifications, discards pre-arm cues and resubscribes after close. All three regressions failed before the fix. Cancellation and a real producer thread are covered. Thirty batches of 1000 cues scheduled 30 callbacks instead of 30000; median batch time fell from 13.566 ms to 0.229 ms. This is a scheduling microbenchmark, not runtime throughput.

### deadlines | high | Fixed Python observation and Rust reply budget overruns

`src/cadrumo_client/transport/operation_controller.py` applies the tighter terminal-wait/controller deadline to wire observations without mutating the original controller. `native/application/src/runtime_client.rs` rejects buffered replies after expiry and uses one remaining-frame deadline across transfer chunks. The concurrent session supplied deadline-aware exchange queueing, shutdown-safe subscriptions and event-driven idle reads. Native application/platform tests and formatting/Clippy/all-feature Clippy passed.

### terminal-wakes | high | Fixed disconnect and session-retirement wakeups

The concurrent session moved `src/cadrumo_client/transport/verified_transport.py` disconnect delivery to every reader exit. Native tests cover explicit close, peer loss, exchange failure and stopped readers. `src/cadrumo_client/transport/frontend_client.py` also wakes operation observers on exact-session retirement while the connection remains open; a failing view callback cannot strand them, and a foreign-session event does not wake them.

### requester-recovery | medium | Removed unnecessary client delay and bounded retry churn

`src/cadrumo_client/transport/automation_requester.py` no longer adds 50 ms after the runtime's bounded long-poll. The initial reviewer estimate of 40 idle wire requests per second was incorrect: `VolatileEnrollmentRecipient.borrow` already waits up to five seconds. Runtime-side 100 ms clock rechecks remain, and are not evidence of that wire rate. `src/cadrumo_client/transport/profile_password_rotation.py` backs off transient admission refusals from 50 ms to a one-second cap, respecting the remaining deadline, closing candidates and never resubmitting the mutation.

### native-benchmark | low | Measured real pipe overhead and idle behavior

Five hundred exchanges from four callers over a real Windows named pipe with verified framing and a synthetic refusal peer completed in 0.250 s: about 1997 exchanges/s, median 1.922 ms, p95 2.368 ms. A 0.5-second idle interval entered one readiness wait and recorded no CPU use at the timer's resolution. The reader stopped after close. Scripts/results live in `.tmp/client-concurrency/`; no session scratch remains in `build/`.

### final-review | low | Client fixes reviewed; broad verification has an outstanding failure

The final working-tree review includes follow-up commit f89cef12fb: the platform idle-read API is committed with its application caller, and the handshake payload retains the caller's original deadline. Read-only Luna review confirms both corrections. The Python opener review also passed: fresh connection attempts receive the remaining password-rotation budget through CLI and TUI, and an opener returning after expiry is closed before admission.

Final focused Python selection: 47 passed, including native readiness and failing-callback cases, rotation, session retirement and CLI/TUI factories (`.tmp/client-concurrency/python-final.log`). Ruff check and format passed for all 16 changed Python files. The final native run passed platform tests, all runtime-client tests and application Clippy; the aggregate application suite had 234 passes, one ignored test and one failure in `provisioning::protocol::tests::the_local_ai_installs_its_program_pulls_each_model_once_and_checks_every_role`: its quick-check timing assertion measured 36.762 seconds (`.tmp/client-concurrency/native-final.log`). This is outside the edited client path; it is recorded as an unresolved aggregate failure, not assumed pre-existing or harmless. The earlier broad quality process lost its result and its log is empty; a new configured type count remains in progress. Integrated verdict remains PENDING those verification gaps. No installed-runtime acceptance claim is made.
### recovery-consumers | medium | Fixed stale recovery opener signatures revealed by full type discovery

The configured type count reported 46 diagnostics. A diagnostic run identified recovery test doubles still using the old no-argument signature. Updated all 12 reported test and harness files to accept the canonical default timeout; lifecycle harnesses that open real clients forward it. Focused ty and Ruff now pass for all 12 files. A fresh whole-project ty run reports only two remaining diagnostics, both in the concurrently edited `dev/quality/tests/test_no_model_definitions.py` (missing override decorator and unsound yield); no client or consumer diagnostics remain. The earlier transient syntax errors in that same external file are no longer present. Evidence: `.tmp/client-concurrency/ty-after-openers.log`.

The native provisioning timing test also fails in isolation at 4.693 seconds (`.tmp/client-concurrency/native-timing-recheck.log`). Client implementation and scoped reviews pass; integrated review remains PENDING external quality/provisioning failures and the unavailable aggregate check-code verdict. S03 stays open for that verification follow-up. Commits f89cef12fb and d85362cbee contain the native and Python fixes respectively, following e16357340a and b4ed3d1b3e.
### live-followup | medium | Fixed failures exposed by expanded native verification

User authorized full live verification and related repairs. The components role's quick status launched hardware-discovery children whose five-second per-query bound exceeded its two-second budget. Commit b3e36b4057 makes quick status use existing measurements or unknown capacity; full checks/setup still measure, and the production desktop supplies measured capacity. The unchanged timing regression, full application Rust tests, formatting and Clippy pass. First desktop measurement remains separate work; this change does not claim to optimize it.

Commit 65fd394de8 moves immutable installation/version/authority metadata reads off the async loop and into the caller's opening deadline before acquiring an endpoint. Cancellation and timeout leave no native resources; an OS metadata timeout retains its unavailability classification. Eighteen opener tests pass.

A real invalid-image launch hung the expanded native test run. The captured py-spy native stack identified CreateProcessW -> NtVdm64RaiseInvalid16BitError -> MessageBoxW. Commit 4c64ce6d85 applies thread-local SEM_FAILCRITICALERRORS only during creation and restores the previous mode; the original creation failure is captured before restoration. Eleven native process tests pass, including Chromium descendant and abrupt-owner-death cases. Microsoft documents this thread-local policy at https://learn.microsoft.com/windows/win32/api/errhandlingapi/nf-errhandlingapi-setthreaderrormode. Restoration of the returned valid mode is tested; its native BOOL failure is not separately reported, a low-probability remaining diagnostic limitation.

The complete transport and runtime wait/cleanup selection now reports 313 passed, no skips (`.tmp/client-concurrency/full-client-fixed.log`). The initial real-runtime rotation run timed out; an unchanged instrumented rerun passed in 29s, followed by all three canonical uninstrumented authentication tests passing (rotation 73.52s, wrong-password refusal 10.27s, sign-in/logout 46.94s). No production timeout or test performance threshold was relaxed. The live Rust client test also passes with zero ignored cases: connect 1ms, password sign-in 526ms, stored receipt resume 136ms, then registered reads, streamed submissions and sign-out (`.tmp/client-concurrency/rust-live.log`). All live roots are disposable. The Rust driver and source sign-in test exercise real native credential storage; the source rotation fixture uses a synthetic native-store port with real profile workers.

Two type findings in the concurrently rewritten model-definition gate were repaired with an override annotation and a cast justified by tomllib's string-key tables. Its 56 tests and whole-project ty passed. The related gate file was committed with its author's larger changes in 2c799994c8. Package assembly/lifecycle acceptance and the final aggregate quality verdict remain pending; the first bundle attempt correctly refused concurrently changing documentation, and the second product snapshot completed without that warning.
### aggregate-quality | informational | Unrelated unused-core API findings remain

The final `just check-code` run passed ten gates: style, formatting, data formatting, types, import boundaries, dependency declarations, secure-store writes, persistence writes, docstring references and operation manifests. Reachability, symbol-use and export-consumption gates reported the uncalled core loopback module and dedicated test, OptionalSourceUrl, and extract_invoice_fields_from_text. Read-only review traced the loopback module to the removed local model adapter and the alias to an unused calendar projection. The public extraction helper is explicitly discussed by the unstructured-ingestion ADR, while current composition uses the injected extractor. These unchanged core APIs are outside client concurrency; no artificial caller or API deletion was introduced to hide the findings. Full quality is not claimed green.

### packaged-progress | informational | Real packaged rotation and consumers passed

Commit dcd447413a adds the packaged password-rotation regression. It passed in 38.574 seconds with generation advancement exactly once, unchanged DEK epoch, old-session refusal, fresh native-store receipt resume, sign-out cleanup, and explicit credential_rejected for the old password. The integrated CLI/TUI/MCP scope scenario passed in 159.493 seconds; login/logout and stale receipts passed in 39.058 seconds. The current debug lifecycle driver built and checked successfully. CTest launch and health prerequisites passed in 44.17 and 65.71 seconds. Four newly included shared agent-service checks also passed; the complete matrix now selects ten cases. The unchanged production ten-minute lease-expiry test remains in progress.

### final-live-verification | informational | Full Windows packaged verification passed

The Release bundle command exited zero after building the MSI/bootstrap kit and passing bundle.installer-bootstrap in 99.72 seconds. The current Debug lifecycle driver build and check also exited zero. Canonical CTest for bundle.runtime-lifecycle and application.package included launch and health fixtures: all four checks passed in 1224.38 seconds. Rust package acceptance passed in 67.69 seconds. The lifecycle JUnit reports ten tests, zero failures, zero errors and zero skips; its isolated scratch was removed by teardown. No production deadline or test timing threshold was relaxed.

The two-crash recovery scenario passed in 628.907 seconds. It continued the same pending operation after the production lease expired, preserved operation history and verified exactly one execution phase. Its recorded metrics were 5.470 ms median and 7.618 ms maximum for twelve authenticated status requests, 35.850/35.111 ms crash detection, 2.563/2.590 seconds verified reconnection, and 598.448 seconds pending-operation lease recovery. Packaged password rotation itself took 16.064 seconds (38.574 seconds for its whole case). Manager-death/successor supervision passed in 51.483 seconds. These are local Windows observations, not cross-platform or load-test throughput claims.

A separate 49.063-second sample during lease recovery measured 0.046875 CPU seconds for the Python test/client process with six threads stable. The two runtime processes used 2.203125 CPU seconds combined. This interval includes the test harness's two-second admission retries and is not a pure-idle benchmark. A captured event-reader stack was parked in native readiness wait. Evidence: `.tmp/client-concurrency/live-lease-cpu-result.json`, `packaged-live.log`, `live-build-final.log`, and CMake-owned `build/windows-x64/testing/Release/lifecycle.xml`. The staged client/rotation files matched source after normalizing line endings. Read-only final review found no regression-test cleanup or authority assertion blocker. Test commit: dcd447413a.

## Recommendations

Keep cue-before-observation ordering, absolute deadlines and cancellation-complete ownership. Existing idle-churn decisions govern these repairs; no authority or persistence boundary changes. Verification includes overlapping selections of 194 transport tests, 16 native/async tests, 22 async/controller tests, 26 requester/rotation tests, 6 invalidation tests and 4 TUI modal cue tests, configured type checks, focused Ruff checks and native tests/lints. Counts are not additive. Direct Rust live acceptance, source authentication, the full Release bundle and all four canonical packaged CTest checks passed. Preserve the unchanged production lease and the distinction between client performance and runtime/backend work.
