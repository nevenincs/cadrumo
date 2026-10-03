# Profile-worker request staging

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-175` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope and method

This chunk is the single 140-line module `worker_submission_staging.py`, read in full. Its manifest records a small measured token count; this is static analysis only. It was reviewed alongside the already assigned parent/worker submission bridges only to describe the interfaces, without executing them.

## Capability and mechanics

The module holds large request payloads temporarily inside one immutable profile worker, before they become canonical operations. A staged request retains session, frontend, operation definition, subject and idempotency coordinates. It has no operation ID, journal entry or publication effect until `finish()` returns verified text to the canonical operation host. The worker caps staging at two simultaneous uploads, while the parent stream adapter has its own bounded admission slots (`worker_submission_staging.py` (`src/cadrumo/entrypoints/runtime/worker_submission_staging.py`)).

Each `begin` expires stale entries, refuses a closed manager, duplicate upload ID or full staging table, and creates a `SubmissionPayloadBuffer` from the request descriptor. `append` accepts only the upload’s exact upload/connection/session binding; the buffer enforces descriptor-level framing and contiguous chunks. If an append is malformed, the entire staged entry is dropped and its mutable buffer closed. `finish` calls the buffer’s whole-payload validation and drops the entry in a `finally` block even if validation fails; only then does it return a `StagedSubmission` containing the resulting JSON text and original admission coordinates. Canonical model decoding/admission happens in the operation host after this handoff, not here (`worker_submission_staging.py` (`src/cadrumo/entrypoints/runtime/worker_submission_staging.py`)).

An explicit abort is idempotent for a missing upload and, when present, requires the same connection and session. It intentionally does not require that the session still be live, allowing cleanup after retirement. Expiry uses a monotonic clock and removes uploads either after the fixed submission timeout or when an optional current-session inventory no longer includes their session. `close` marks the staging manager unavailable and wipes all incomplete entries (`worker_submission_staging.py` (`src/cadrumo/entrypoints/runtime/worker_submission_staging.py`)).

## Security and implementation assessment

The local controls are clear: worker-local staging, a two-entry cap, exact upload/connection/session binding, finite expiry, early destructive cleanup on malformed chunks, cleanup on failed finish, explicit abort, and shutdown wiping. Staged state is not treated as authority to execute an operation; the canonical host receives the payload only after buffer validation. This module contains no filesystem access, network access, secret parsing or application execution, and no tests are included in the assigned source.

The payload buffer is the critical dependency: its descriptor limits, chunk order/size, digest, UTF-8/JSON acceptance and zeroization need to be verified in the application runtime contract. Parent and worker code must also ensure `begin` binds the exact request descriptor and `finish` cannot be retargeted. The module has no explicit lock; its current caller appears worker-confined, but any future multithreaded caller would need to preserve that confinement or synchronize its dictionary and mutable buffers. Static inspection cannot prove underlying buffer zeroization or that all abandoned uploads are eventually expired if the worker’s periodic sweep stops.

## Dependencies and follow-up

`RuntimeProfileConnections` streams framed bytes through the bounded parent adapter, `ProfileWorker` owns this staging instance, and `ProfileWorkerOperationHost.submit_payload` receives only the finished `StagedSubmission`. Synthesis should trace `SubmissionPayloadBuffer` for exact limits and cleanup behavior, then confirm shutdown/cancellation and session-retirement tests cover partial uploads.

## Complete assigned-file coverage

- `worker_submission_staging.py` (`src/cadrumo/entrypoints/runtime/worker_submission_staging.py`) — lines 1–140, fully read.
<!-- /preserved:article -->
