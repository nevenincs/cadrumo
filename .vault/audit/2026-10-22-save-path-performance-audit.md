---
tags:
  - '#audit'
  - '#save-path-performance'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:92e7418442e96a97fbe5a0f26dc3e01b3c851ac35ff91d38c475fa8065928966'
related:
  - "[[2026-10-22-save-path-performance-plan]]"
---

# `save-path-performance` audit: `Save path measurement`

## Scope

S07 of `2026-10-22-save-path-performance-plan`: the before and after measurement of the TUI profile save path. An external harness outside the repository ran a caller-owned runtime (`cadrumo-runtime --configured-root`) on a scratch storage root holding an encrypted clone of a real-sized operator profile. It drove `ProfileManagerClientComposition._field` (the TUI's field-save door, mutation then overview re-read) and the installed TUI headless through `launcher.main(headless=True, auto_pilot=...)`. The pre-plan tree (`d25e26839d`) and HEAD (`c9c4ee9e8b`), each exported with `git archive`, ran alternately in one time window with near-pristine probes (audit-hook file events, SQL, frames, per-process CPU; no per-function spans), then once each with full per-function counts. The range also contains other sessions' startup-performance commits, so wall time is the combined effect and the counts attribute it. The host was shared and loaded; medians over 8 saves per run.

## Findings

### save-path-wall | low | A TUI profile save takes about half the wall time of the pre-plan tree

Warm save median: pre-plan 4.04 s and 3.27 s in two rounds; HEAD 1.77 s in both. Mutation round trip about 1.4 s to 0.75 s; overview re-read about 1.7-2.7 s to 0.97 s. Runtime CPU per save 1.20-1.34 s to 0.40-0.43 s; worker 1.57-1.63 s to 1.39-1.41 s. The real TUI save on HEAD, from the save button press to the applied revision, has a median of 1.14 s (1.22 s including paint). Full per-save counts, pre-plan to HEAD: runtime Python calls 618,008 to 33,930; worker-runtime handshakes 74 to 0; runtime frozen-model hash calls 394,903 to 3,849; runtime file events 354 to 78; worker file events 603 to 164. SQL stayed about 140-160 statements and 6-10 ms per save, and fsync about 21 calls and 55 ms, both negligible throughout.

### worker-overview-reread | medium | Worker work for the post-save overview re-read now dominates a save

Worker Python calls per save did not move (176,108 to 179,518). The overview re-read is about 55% of a HEAD save. It runs as five durable profile-view operations, each journaled, and renders localized field views (about 2,160 `tr` calls per save before the plan). `src/cadrumo_runtime/host/frontend/tui/profile/manager_client.py:197` re-reads the whole overview after every field mutation. This path belongs to S09 of `2026-10-22-startup-performance-plan`, which so far changed only Home's first screen (`35934fefa0`).

### frontend-login-observation | medium | Login observation still captures the desktop logon on frontend requests

On the S04 harness run the runtime made about 5,460 `windows_desktop_logon:_sid_text_valid` calls per save, from login observation for frontend requests, not from the worker channel. `_collect_windows_logins` and `windows_desktop_sessions` still accounted for about 0.45 s exclusive per instrumented save after S04. The owner of `2026-10-22-startup-performance-authority-observation-adr` changed holding for logons without a lock surface (`7ab611be90`) and the aged-observation probe. A HEAD measurement after that probe change is still needed.

### pre-plan-tui-run-hang | low | The pre-plan tree's headless TUI run hung before sign-in

The pre-plan run of the TUI driver produced no iteration and was stopped by its 20-minute timeout. The HEAD run completed. Not triaged, and not reproduced on HEAD.

### stale-index-locks | low | Empty worktree index locks were left without a holding process

Four empty `index.lock` files in the shared tui worktree, at about 16:14, 17:37, 19:54 and 19:59, each had no git process holding it. They were removed only after checking. Long-running git calls killed by tool timeouts during hooks are the likely cause. Read-only git now runs with `--no-optional-locks`, and commits run with long timeouts.

### worker-auth-handshake-failure-contains-worker | high | A failed connection handshake contains the worker and latches the authorization server as failed

Plan-close review of S01-S06. In `src/cadrumo_runtime/adapters/worker_authorization.py:198-212` after S04 (`c9c4ee9e8b`), `_connection` runs `_verify_worker_channel` (`:507-523`) under a bare `except Exception` that sets `_failed` and `_stop` and calls `_contain()`. Before S04, a `RefusalError` from verification or the handshake only closed the channel. A scratch probe against the real server reproduced it: a same-user process with the wrong pid, or the expected peer closing before the handshake completes, each caused one `contain()`, and `require_healthy()` and `settle()` then raised `runtime_unavailable`. A worker that abandons a handshake at its deadline, or any same-user process opening the pipe, contains a healthy worker and turns its in-flight operations into UNKNOWN. This contradicts the ADR constraints "Containment unchanged" and "refusal codes unchanged". S04 is reopened.

### incarnation-test-covers-job-membership-only | low | The reuse incarnation test changes only job membership

`src/cadrumo_runtime/adapters/tests/test_worker_authorization_reuse.py:345-357` exercises `_owns_process`. It covers neither the runtime's `require_live_native_peer` pid and creation-time recheck nor the worker's recheck of the runtime (`src/cadrumo_runtime/adapters/worker_authorization_connections.py:101-108`). Both delegate to existing native checks.

### debug-record-cost | medium | Each worker debug record costs about 4 ms, and lock acquire and release lines are the biggest source

Measured by the owner of `2026-10-22-startup-performance-plan` with cProfile on the native workbench test (storage on C:, merged over 16 workbench generations, per generation). `src/cadrumo/core/log_file_handler.py` `_names_descriptor` makes about 212 `os.stat` calls, one per record (about 0.17 s of native stat). A worker debug record costs about 3.9 ms (lock, stat, append announce). The largest record sources are `src/cadrumo/core/locks.py` `held_descriptor_lock` acquire and release lines (about 40 per generation) and `modelos_work_units.load_revisioned` (33). Together they take about 0.33 s of handler time per generation. S02 removed the per-record directory creation and reopens; the per-record identity check and the volume of lock-event records remain. The same measurement found journal settlement at 0.08-0.55 s on C:. On Y:, hardened fsync showed a 0.5 s 90th percentile and one 23.8 s outlier under concurrent load, so measurements with storage on Y: overstate journal cost.

### worker-auth-handshake-fix-review | low | Re-review: the handshake containment finding is resolved by d63d4ac50f

`d63d4ac50f` restores the pre-S04 rule. A refusal during verification, the handshake or an idle wait only closes that channel (`src/cadrumo_runtime/adapters/worker_authorization.py:203-206`). A permit lost while held is still contained inside `_permit_exchange` before a held COMMIT fence drops. A refusal before any permit still answers `AccessRefusal`. A failed approval phase still retires its proof. Faults that are not refusals still latch and contain. The foreign-peer and abandoned-handshake tests fail with the c9c4ee9e8b `_connection` body swapped in and pass at HEAD. The incarnation tests hand the verified pipe to the parent, so only the retained-handle recheck can refuse; this closes incarnation-test-covers-job-membership-only. The probe gives contained 0 and healthy for both cases. Verdict: PASS. No POSIX run.

## Recommendations

- worker-overview-reread: either return the committed overview, or the changed section, with the field mutation result, or keep the re-read off the durable journal. Changing the mutation result is a protocol change that needs an ADR, which S09's owner should weigh.
- frontend-login-observation: re-measure on HEAD after the aged-observation probe. If the cost remains, the authority-observation ADR's owner should decide whether a frontend connection's login capture can be held per connection like the worker's peer identity.
- worker-auth-handshake-failure-contains-worker: in `_connection`, close the channel without containment or a failure latch when verification or the handshake refuses, and add reuse tests for a foreign peer and an aborted handshake. This restores the behaviour the accepted ADR already requires, so no new decision is needed.
- incarnation-test-covers-job-membership-only: add tests for an exited peer handle and a substituted channel peer on both sides.
- debug-record-cost: stop emitting lock acquire and release records at DEBUG on hot paths, or keep them in memory; and replace the per-record path identity stat with the change-witness pattern or a check limited to rotation. Both are implementation within settled decisions.
- pre-plan-tui-run-hang: only reproduce it if a regression on HEAD shows the same symptom.
