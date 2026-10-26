---
tags:
  - '#audit'
  - '#client-concurrency'
date: '2026-10-26'
modified: '2026-10-26'
body_schema: 'body-v2'
body_hash: 'sha256:1b9a39ae8cf29f6fd4ecb158030be0828a1e549a3afd454ed2121f9cc0a83012'
related:
  - "[[2026-10-26-client-concurrency-plan]]"
---
# `client-concurrency` audit: lifecycle, deadlines and scheduling

## Scope

2026-10-26 review of the client-concurrency plan, commits e16357340a and b4ed3d1b3e, and subsequent Python retirement/retry changes. Three Luna 6 Max agents supplied read-only discovery; the principal verified findings and implemented changes alongside the user's concurrent runtime session. Code semantic search was unavailable; targeted searches were used. Decision search succeeded. Verdict: PENDING broad quality completion and final independent read-only review.

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
## Recommendations

Keep cue-before-observation ordering, absolute deadlines and cancellation-complete ownership. Existing idle-churn decisions govern these repairs; no authority or persistence boundary changes. Verification includes overlapping selections of 194 transport tests, 16 native/async tests, 22 async/controller tests, 26 requester/rotation tests, 6 invalidation tests and 4 TUI modal cue tests, configured type checks, focused Ruff checks and native tests/lints. Counts are not additive. Installed-runtime live acceptance is separate and was not run. Record the broad quality result and final review below when complete.


