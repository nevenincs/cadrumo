---
tags:
  - '#audit'
  - '#robust-logging'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:79a7eb96f4602a652061b71ef7316323a7575777f02effff38cb36f882da0e6b'
related:
  - '[[2026-10-27-robust-logging-plan]]'
  - '[[2026-10-27-robust-logging-adr]]'
  - '[[2026-10-27-robust-logging-research]]'
---
# Robust logging integrated review

## Scope

Review S01-S03 against the accepted bounded-diagnostics decision, including source commits `6cbfacbc8b` and `435c13553a` and the final working-tree handler interception/test correction. Trace producer admission through context capture, safe snapshots, redaction, independent sinks, rotation, native event/status capture, panic hooks, worker lease control, counters and bounded shutdown. Operation journals and result/authority contracts remain outside diagnostic delivery.

## Findings

### producer-propagation | high | Resolved foreign logger filters running before admission

Integrated review found that stdlib logger propagation enters root handlers without the project logger filter. Installing a secret filter on each wrapper therefore ran redaction synchronously before its emit method could enqueue. S03 overrides wrapper handle to intercept first; the delivery thread alone reaches handler filters. The complete logging suite passes 101 tests including blocked redaction through both foreign and project logger paths. This finding was fixed while S03 remained open; no unresolved high finding remains.

### replay-memory | medium | Resolved configuration snapshots multiplying queue retention

A count-only native queue could retain a full 512-event replay for every configuration entry. Native admission now charges replay events against the same 4096-event budget as append requests. A state-lock-held regression submits 100 replay requests, confirms bounded retention and explicit drops without blocking, then releases and drains. This is covered by the passing full native suite and clippy.

### diagnostic-death | low | Abrupt termination can lose pending diagnostic records

Best-effort panic delivery follows the accepted policy. Recoverable real-child panics explicitly drain within a finite bound; aborting children are checked for private-payload containment without asserting impossible queued delivery guarantees. Native event-ring facts stay immediate. This is an explicit operational tradeoff rather than a journal durability change.

### platform-evidence | low | Actual Unix fork execution is not available on the Windows validation host

Dispatcher process-change coverage verifies replacing an inherited held guard and closed daemon state, with clean per-process counters and subsequent delivery. Windows handle measurements cover 100 queue lifetimes. Actual fork execution should be exercised on Unix CI; the Windows test establishes reset behavior without pretending to create a real fork.

### storage-latency | low | Workspace volume can delay diagnostic delivery beyond a bounded drain

A heavily loaded Y-volume rerun captured the diagnostic daemon blocked in Windows Path.lstat during settings path validation; finite flush reported incomplete and exposed pending work. Another Y run passed101 with one rotation subprocess timeout. Identical final tests and timeouts using explicitly configured local C temporary storage passed all102 in19.22s. No time limit was increased and no failing test was suppressed. Earlier broad102 failures and source-local pass receipts are retained in research. This is consistent with best-effort sink delivery and independently verified producer isolation.

### shared-authority-lock | high | Resolved diagnostic redaction borrowing application authority

RegistryTaxIdentityAdmission previously reached the shared indexed authority. That owner holds its reader lock during descriptor reads and its construction lock during cold admission. Background redaction could therefore block application authority users indirectly. S03 now scopes queued redaction to the existing conservative lexical fallback with a context-only override; other threads and command/domain redaction retain their gate. A blocked-authority regression fails before and passes after, preserving normal application redaction afterward. This finding is fixed; it is not asserted as the cause of retired documentation workers without their child stacks.

### opaque-inspection | high | Resolved application hooks escaping during record creation

Type-set and isinstance inspection could execute metaclass hashing or instance __class__ hooks, while exception name access could invoke a metaclass property. The stdlib lone-argument Mapping probe executes before logger filters and reproduced an exception escaping the log caller. The factory now snapshots lone opaque operands before that probe; snapshot checks use identity and builtin descriptors. The single-argument regression verifies no such hook executes, records remain deliverable and exception type is retained. All418 expanded tests pass; final strict types and lint/format pass. No unresolved high finding remains in logging.

### buffered-stderr-finalization | high | Resolved diagnostic daemon holding interpreter exit lock

An unread pipe let bounded shutdown return while its diagnostic daemon held stderr BufferedWriter; CPython finalization then froze past20s. Unbuffered control exited normally. Configured stderr and the default fallback now use independently queued raw-stream writes, preserving encoding without taking the finalizer's buffered lock. Both isolated-interpreter unread-pipe regressions pass. Diagnostic write locking resets after fork. Caller-owned custom handlers retain their ownership. No raw record fallback is introduced.

## Recommendations

Use bounded flush only at deliberate test/shutdown boundaries. Inspect delivery counters when diagnosing missing output; overload intentionally rejects finite diagnostic work instead of retaining unbounded memory or blocking application threads. Rebuild the Debug package before attributing these source fixes to the currently running application. The calendar/publication session owns the coordinated rebuild handoff.

Verification: 101 logging tests plus the added process-reset test (8 dispatcher tests independently), five real worker integration tests, 337 native tests plus real-child panic harness, scoped Ruff/ty/rustfmt and CMake clippy pass. Py-spy and healthy/slow/blocked benchmark evidence are recorded in the related research. Full repository check-code remains in progress; crate-wide native formatting is currently blocked solely by another session's person_operations.rs edits. Verdict PENDING these shared-gate receipts; no unresolved critical or high defect in the reviewed logging implementation.

Final review update: repository-wide just check-code passed every configured gate, including complete import, full type, usage and storage write-path checks. Final logging102 passed on local C storage, worker5 and full native337 plus panic harness pass. Large-record benchmark400/400 delivered with p99 86us and no handle growth. Crate-wide rustfmt still reports another session's person_operations.rs, while every owned native path passes scoped rustfmt and the whole crate passes clippy. Registry stale-generation refusal is assigned to the calendar session that owns publication. The remaining required test-gate contract run is still in progress; verdict remains PENDING its receipt.

Handoff receipt: the contract fallback passed217 tests, and the harness passed4 worker-count checks. Only2 sequence-corpus documentation checks refused execution because published registry authority is stale. The calendar session owns its running registry-wide parity assessment, publication and the targeted two-test rerun. S03 remains open and final integrated verdict PENDING that receipt; no logging critical/high finding remains. Debug rebuild has been explicitly cleared and source is stable. All102 logging tests pass on local temporary storage; 32 concurrent producers also delivered8000/8000 with zero losses, p99 64.3us and stable162 handles across100queue lifetimes.

Workspace-storage follow-up: after the competing exhaustive global matrix stopped, the identical complete logging suite passed all102 on the original Y-volume in16.15seconds, with no source or timeout change. Receipt: `var/storage/development/.logs/logging-core-workspace-after-matrix.log`, test-run `20261027T141815.419352Z-pytest-42304-87f6e2c4`. Both C and Y final logging verification now pass. This establishes recovery of the earlier storage-delivery condition without asserting that the competing process alone caused it.

Final source review update: the authority and constructor defects above are repaired in the three scoped Python files. Full check-code passed; final all-platform types and scoped Ruff/format pass after method-body-only refinements with unchanged imports. Final expanded418 and post-isolation worker5 tests pass. Fresh profiling and normal/large/blocked benchmarks pass delivery/memory/handle contracts, with scheduling-sensitive latency recorded rather than claimed as a real-time bound. Registry publication and integrity are now green. The initial Debug bundle passed installer bootstrap. Final integrated verdict remains PENDING the calendar owner's expected golden refresh/quiet documentation checks and refreshed package; source fixes are complete and ready for product-wheel refresh.

Buffered stderr follow-up: scoped Ruff/format/ty/strict basedpyright and both process-exit regressions pass. Normal8000 records all delivered, p9990.9us,156stablehandles; blocked703142calls p9963.2us with bounded loss and eventual drain. Py-spy20Hz --idle1309samples has0errors/no lag; no producer sink/redaction or dispatcher authority frames. Legacy recording-test fixtures migrated to serialized payloads and bounded drain; fresh5/5pass. Full474rerun pending. Verdict remains PENDING shared integration checks. Builds are explicitly held by the user; source proof does not claim deployment.

Completed checkpoint56a77fa7e6: the unchanged expanded474 selection passed54.02s, and all131 recording/observability tests passed11.62s after fixture migration. Store diagnostics pass entry.name as a builtin and preserve trace-identity rejection through exc_info snapshot text, without rendering opaque objects or changing trace storage. Final scoped Ruff/format/ty and strict basedpyright pass; source work is committed and quiet. Latest execution-ledger receipt owns these final results. Repository aggregate and package deployment remain pending; the user explicitly holds new builds.
