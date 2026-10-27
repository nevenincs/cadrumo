---
tags:
  - '#research'
  - '#robust-logging'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:014576f0625fa336b4fbc3b66ea9e6545426f41c4d134438b90d1f31cd59f92c'
related: []
---
# Logging stalls and shared producer paths

## Findings

On 2026-10-27, a real Windows worker probe concurrently queried activity and operation contracts while synthetic leases expired and were reinstalled. It reproduced two activity deadline failures. The extended reproduction had zero queue delay and elapsed 20.010 seconds. Profiling at 20 Hz captured 398 event-loop samples in diagnostic file flush (19.9 seconds), and 227 samples in diagnostic-extra redaction opening registry authority (11.35 seconds). The operation channel then closed. Suppressing ordinary logs completed 32 cycles, 6588 activity and 6498 discovery queries, with worst replies 75 and 90 milliseconds. Sixteen existing native-operation and transport tests passed. Original retired workers' exact historical stacks are unavailable.

## Shared paths and constraints

Logger-attached filters synchronously render and redact in `src/cadrumo/core/logging.py`; `src/cadrumo/core/log_file_handler.py` synchronously appends and flushes. Native `native/application/src/diagnostics/mod.rs` appends while holding the event/status mutex, and panic logging also writes synchronously. Worker logging does not register runtime/client namespaces. These are best-effort diagnostics, distinct from authoritative journals.

Preserve redaction before outputs, emission identity, routing, rotation, thread safety and supervisor stream hygiene. Isolate arbitrary formatting, registry and sink stalls behind bounded queues; measure explicit loss and bound shutdown. Verify blocked sinks/filters, saturation, recursion, threaded writes, exception snapshots, healthy rotation, native worker responsiveness and producer latency. The operator explicitly authorized fixing these defects throughout the codebase and requested benchmarks and py-spy/handle analysis.

## Final measurements

Windows CPython 3.13.15, eight producer threads, synthetic records only. Current reports are in `var/storage/development/.logs/logging-benchmark-{normal,slow,blocked}-current.json`. The normal burst delivered all 8000 application records with zero dropped/failed records or sink writes: 22005 calls/second, median 28.1 microseconds, p95 47.2 and p99 63.6 microseconds. The slow sink burst also delivered 8000 with zero losses, p99 61.9 microseconds. Slow mode releases its artificial 5ms delay after production so drain timing is not a sustained slow-disk estimate.

With the file sink blocked for 25 seconds, 733152 producer calls completed at 29049/second, p99 57.9 microseconds. Finite overload caused explicit counted loss: 707213 rejected record admissions and 17738 file-sink admissions; pending file records remained at most 8193 and retained queue weights below 32MiB per queue. All admitted remaining work drained after release. Sampling is limited to each producer's first 8192 calls; maximum sampled calls of 137-779ms include OS/GIL scheduling under concurrent load, so these results do not claim real-time latency guarantees.

`logging-profile-current-stacks.txt` captured 8415 py-spy samples at 100Hz with thread IDs and idle frames, zero sampling errors. `logging-profile-current-analysis.json` classifies 5896 producer samples, none in redaction, file handling or file flush. The dedicated file sink accounted for 799 samples, 762 waiting inside the deliberately blocked Event; remaining samples include release and drain. Both main dispatch and sink work remain outside application control frames. Native Windows process handles remained 158 before and after 100 dispatcher lifetimes in all final modes.

## Verification and review corrections

The final Python logging suite passes 101 tests, including real concurrent shared-file rotation, blocked redaction for both project and foreign stdlib loggers, independent stderr delivery, finite shutdown, saturation, concurrent flushes, oversized keys/numbers/format requests, safe exception causes and settings/routing identity. All eleven changed Python paths pass Ruff lint/format and ty. Real native worker integration passes all five tests, including 32 control replies while its actual file sink waits; this establishes deadline isolation rather than merely suppressing logs.

The full CMake-owned native application suite with platform support passed 337 tests and the real-process main/thread/task/aborting panic harness; one pre-existing live-runtime test remains explicitly ignored. Diagnostic integration covers 19 tests, plus bounded replay admission and blocked observer handling. Native clippy passes. Scoped rustfmt passes; crate-wide formatting currently reports only concurrent `person_operations.rs` edits outside the logging change. Full repository aggregate verification is owned by this session and its eventual receipt is recorded in the execution ledger/audit.

Integrated review identified and repaired a third-party propagation seam: handler interception now precedes handler filters, preventing synchronous redaction even when a library uses stdlib logging directly. The final source correction has focused lint/type evidence and the complete 101-test logging result. Earlier native helper/WebView tests were changed to wait at explicit bounded flush boundaries before observing disk state. Abrupt process death retains no guaranteed queued panic delivery, as the accepted best-effort policy requires.

The original lease-churn reproduction was repeated after the fix with ordinary logging enabled: all 32 expiry/reinstall cycles passed, 6590 activity and 6530 discovery replies. Worst activity was 89.3ms and discovery 393.1ms, versus the original 20-second failure. The receipt is `var/storage/development/.logs/logging-worker-churn-current.log`; periodic py-spy dumps are in the original crash-analysis directory under `activity-churn-fixed-stacks.txt`. The added process-change test confirms stale held locks and closed daemon state are replaced before admission.

## Sources

Primary source: the actual Windows worker reproduction and py-spy folded stacks in `C:/Users/hello/AppData/Local/Temp/cadrumo-crash-analysis`; synthetic benchmark JSON and raw stacks under `var/storage/development/.logs`; test-run receipts under the same development log root. Implementation locators are `src/cadrumo/core/logging.py`, `src/cadrumo/core/diagnostic_dispatch.py`, `native/application/src/diagnostics/dispatch.rs` and `src/cadrumo_runtime/host/worker.py`.

The repository-wide `just check-code` aggregate finished exit 0. Its import/type/dependency/usage/write-path/docstring/manifest checks all passed. Registry validity and runtime-load passed (58 modelos, 161 revisions); integrity refused the older published authority until the calendar session republishes its changed legal sources. The final change-scoped test gate runs the fixed contract fallback because core logging fans out beyond its 40-target limit.

A later heavily loaded full logging rerun reported five startup/drain timeouts (97 passed). The captured frame is `Path.lstat` in `storage_environment._refuse_links` while diagnostic configuration is on its daemon, not an application thread; records status exposed pending work and a finite flush returned false. This is storage-delivery infrastructure evidence, not a claim of lossless delivery under arbitrary filesystem stalls. Independent reruns of the seven first-record tests and twelve separate deferred-process probes passed without changing time limits. The failure receipt is `test-runs/2026-10-27/20261027T135620.276655Z-pytest-54548-f46607f0/run.log`. Final isolated rerun results belong in the execution ledger.

Final controlled storage comparison used the configured `CADRUMO_LOCAL_STORAGE_ROOT`, `CADRUMO_TEMP_DIR`, `CADRUMO_TEST_LOG_ROOT` and `CADRUMO_DEV_CACHE_ROOT` overrides to the local C temporary filesystem. Identical source, tests and finite timeouts passed all 102 logging tests in 19.22s; receipt `var/storage/development/.logs/logging-core-local-disk.log`. The concurrent Y rerun passed 101 and timed out one rotation subprocess, while the earlier Y rerun captured the actual metadata syscall stall. This distinguishes storage-delivery latency from producer or queue deadlock without relaxing assertions.

The large-record benchmark passed 400 synthetic records across four producers, each including about 10.8KiB text and a mapping: all delivered, zero drops/failures, median31.7us/p95 41.5us/p99 86.0us, maximum sampled4.43ms. Queue retention stayed bounded and handles remained162 before/after100lifetimes. The receipt is `logging-benchmark-large-current.json` beside the other benchmark artifacts.
