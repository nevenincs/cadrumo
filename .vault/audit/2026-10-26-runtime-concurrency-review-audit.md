---
tags:
  - '#audit'
  - '#runtime-concurrency-review'
date: '2026-10-26'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:66caaa888ccc7ccda914fa056e39afd68f137254d30d4ae4f0c97be2ef69a9cb'
related:
  - "[[2026-10-26-runtime-concurrency-review-plan]]"
---
# `runtime-concurrency-review` audit: `Connection lifetimes, deadlines and idle scheduling`

## Scope

Windows source checkout on 2026-10-26. Reviewed runtime server/session/worker waits, Python client event and async observation, and Rust native client framing/subscriptions/exchange ownership. Principal implemented; Luna agents supplied read-only summaries and reviewed the fixes. Semantic search was unavailable because another process owned the GPU singleton; discovery used scoped source searches and accepted decision records. Preserve concurrent edits in the shared checkout.

## Findings

### python-disconnect | high | Local close and exchange failure omitted subscriber notification

Fixed in `src/cadrumo_client/transport/verified_transport.py`: the sole event reader dispatches disconnect callbacks from its exit path, outside the exchange lock. Native-pipe regressions failed for explicit close and exchange failure before the fix; peer disconnect already passed. All three now notify once and release the reader. Callback failures are isolated at transport and frontend fan-outs so later operation and attendance waiters still wake.

### rust-subscribe-close | high | Subscription could register after the terminal disconnect event

Fixed in `native/application/src/runtime_client.rs`: registration holds the subscriber-list mutex while checking closed state. Concurrent plain and scoped subscription tests receive exactly one terminal event.

### rust-exchange-budget | high | Mutex queueing could exceed a request deadline

Fixed in `native/application/src/runtime_client.rs`: an exchange owns the reply receiver through an RAII claim; other callers wait on a condition variable within their own remaining deadline. Timing out does not close another caller's exchange. Review found that a just-expired claimant could consume a release notification; it now passes that wake to another waiter. Dedicated tests exercise both boundaries. Multi-frame replies retain the exchange deadline.

### rust-idle-read | medium | The native event reader rearmed on a fixed ten-minute timeout

Fixed in `native/platform/src/runtime_pipe.rs` and `native/application/src/runtime_client.rs`: wait without a timer for the first byte or pipe closure, then bound the rest of the frame to five seconds. Partial-frame failure ends the connection instead of attempting another frame. Real named-pipe tests verify close cancels an indefinite read and ordinary deadline reads still time out.

### worker-read-wake | medium | Every operation read scheduled another custody-expiry pass

Fixed in `src/cadrumo_runtime/host/worker_operation_requests.py`: a successful read or contract description leaves expiry asleep when no upload is staged. Mutations, failures and reads while uploads exist retain the wake. Review rejected an unconditional read exemption: custody validation may retire a different expired lease, so staged uploads still require reconciliation, including after wall-clock changes. Regression tests cover idle reads, mutation and staged-upload boundaries.

### existing-event-waits | low | Most Windows idle runtime paths were already event driven

Server acceptance and connection loops wait on native wakes and channel readiness. Session hold/watch and custody expiry use events or known deadlines. Lifecycle intervals for unnotified OS sessions and bounded reconnect retries remain justified exceptions under the accepted idle-churn decision. This review does not claim equivalent OS acceptance evidence for Linux or macOS.

## Benchmarks

`uv run --no-sync pytest src/cadrumo_runtime/adapters/tests/test_runtime_load.py -n 0 -m '' -q -s` measures real native transport/framing without profile work or interpreter startup. Baseline: seven load/recovery tests passed. Expanded benchmark adds event subscribers; combined load/readiness run passed 23 tests.

| Clients | Baseline p50 / p95 ms | Final no-subscriber p50 / p95 ms | Final subscribed p50 / p95 ms |
| --- | --- | --- | --- |
| 1 | 0.597 / 0.740 | 0.432 / 1.027 | 0.645 / 0.814 |
| 8 | 5.359 / 8.232 | 6.003 / 9.513 | 6.290 / 9.668 |
| 24 | 16.325 / 26.527 | 20.639 / 33.758 | 20.577 / 32.357 |

At 24 clients baseline throughput was 1363 requests/s; final results were 1059 without subscribers and 1074 with subscribers. Concurrent compiler and repository checks varied machine load, so this is not a controlled speedup claim. All 500 ms idle samples recorded 0 ms process CPU at the platform clock resolution; this does not establish literal zero CPU or full signed-in desktop performance. The deterministic scheduling gain is removal of the redundant expiry wake for ordinary reads and elimination of the Rust idle rearm.

## Verification

- Python native disconnect/cleanup/settlement: 33 passed at S01; local and exchange regressions failed before implementation.
- Worker read/cleanup/upload suite: 66 passed; final staged-upload/read and frontend-callback review: 20 passed.
- Expanded load/readiness: 23 passed. Native disconnect exception variants passed; final frontend callback tests passed after correcting the test to expect typed unauthenticated session access.
- Rust native pipe tests: 5 passed through the configured CMake Cargo wrapper. Rust client tests: 19 passed in final targeted run. Application/platform format and clippy passed, including the final all-features application clippy.
- Broader `application.rust`: 231 passed, one ignored, one failure in unchanged browser provisioning (`a_full_check_launches_the_headless_build_and_only_a_passing_launch_is_recorded`: Unexpected versus DamagedDownload). No clean broad Rust verdict is claimed.
- Configured `just check-types` passed both initial and final runs. Touched-file Ruff lint and formatting passed after reconciling a duplicate import introduced by concurrent edits.
- Initial registry gate failed with MemoryError; retry and repository-wide code/test gates are tracked below when their final results arrive.

## Review status

PENDING broad verification. Focused behavior review found no unresolved high issue in the implemented changes after the staged-upload and condition-variable wake corrections. Concurrent worker input-executor, async cue-coalescing and additional Rust deadline edits were preserved; they are separate from the principal's changes.

## Final verification updates

- `just check-registry-gate` retry passed valid, runtime-load and integrity: 58 modelos, 161 revisions, 1502 legal references.
- `just test-gate` stopped in CI contracts: 1157 passed, two failed. Failures concern `test-native-provisioning-linux` recipe parity and ambient temporary roots in `dev/env/browser_archive_pins.py` and `native/desktop/frontend/scripts/modelo_fixtures.py`; these are outside the changed runtime paths. Later gate lanes therefore did not run.
- Final focused Rust client run passed 19 tests, including the expired-claimant wake handoff. Final all-features application clippy and format passed.
- Final combined callback/read scheduling review passed 20 tests. Final configured type runner passed.
- Shared worktree commits moved during this run: the native client changes are included in `b4ed3d1b3e`; preserve other sessions' staged work. S01 is committed as `a1209b95ed`.

### broad-gates | low | Shared branch quality gates remain red outside the focused runtime verdict

`just check-code` completed with five of thirteen gates failed: formatting in a concurrently edited client test; import graph unavailable after Windows paging-file exhaustion and concurrent source changes; unrelated reachability, symbol and export findings in `cadrumo.core.loopback_endpoint`, `cadrumo.core.source_locator` and `cadrumo.adapters.outbound.llm.evidence_draft_text`. All 4945 configured modules loaded, all 30 import contracts were kept, and no hard import findings were reported, but the failed subordinate checker cannot prove import conformance. Style, types, dependency declarations, secure-store/persistence write paths, docstring references and operation-contract manifest passed. The import gate needs a quiet tree and sufficient host resources; unrelated findings stay with their owning workstreams.

Final review: PASS for the bounded runtime fixes and their focused verification; full branch acceptance remains PENDING the recorded broad-gate failures. The plan's final Step remains open rather than claiming all required repository checks passed or taking ownership of another session's staged/shared changes.

### windows-close-io-lease | high | Fixed the shutdown race exposed by the temporary soak

The temporary native transport soak reproduced runtime_unavailable twice while requests raced shutdown. The underlying WindowsChannel.read_exact path re-read self._handle after another thread closed it; finish_windows_io received None. Capturing just the integer would still permit OS handle reuse.

WindowsChannel now submits each overlapped operation under the lifecycle lock and retains an active-operation count through its completion/cancellation join. Close marks admission closed, requests CancelIoEx across threads, waits on a condition for outstanding operations to settle, then releases the pipe and peer handles. Blocking I/O waits run outside the lifecycle lock. Peek is serialized with release. Native cancellation cleanup attempts the completion join even if same-thread CancelIo reports an error. The Windows API binding rejects other platforms explicitly.

Real pipe regressions cover pending read, write and idle readiness, refusal of new I/O during close, retained-handle validity before completion, repeated close, and cancellation-error completion joining. The temporary harness and its source snapshot remain outside the repository.

A 24-client fixed-source snapshot run passed 17 restart cycles and 50,905 requests in a 60-second workload. Post-warmup resource deltas were +3 handles, -1 thread and +561,152 RSS bytes, within configured bounds. No shutdown failure or pending request remained. Result: <local-home>/AppData/Local/Temp/cadrumo-soak-20261026-171532/run-20261026-183757-59540/result.json. Production source hashes match that snapshot. An earlier 26-cycle run passed behavior checks but was marked inconclusive because other sessions edited the checkout. An 8-client 60-second run also passed.

The harness initially treated all churn handshake refusals as failures. Instrumentation proved the separate refusal came from the existing 32-slot capacity semaphore. It now records and retries only connection-closed refusals accompanied by an observed capacity rejection, requires continued successful connections, and leaves shutdown assertions unchanged. This is not evidence of a throughput improvement or full authenticated worker/Rust soak coverage.
