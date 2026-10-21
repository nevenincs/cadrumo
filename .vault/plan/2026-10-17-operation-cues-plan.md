---
tags:
  - '#plan'
  - '#operation-cues'
date: '2026-10-17'
tier: L1
related:
  - '[[2026-10-17-idle-churn-operation-observation-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:6db107058c9bd5254995526d19721403d9336874e4c772c5c63d28b91d430d3c'
---

<!-- RETIRED: S07 -->

# `operation-cues` plan

Clients wait for running operations on a pushed `operation_changed` cue instead of polling `OperationObserve`.

## Description

Approved 2026-10-17. The operator approved `2026-10-17-idle-churn-operation-observation-adr` and its implementation in this session ("1 - yes"), then its amended producer ("go ahead with the recommendation. amend adr and go").

The governing decision is `2026-10-17-idle-churn-operation-observation-adr`, which extends `2026-10-16-idle-churn-adr`; every Step is in its scope. The profile worker reports each committed operation to the runtime over its existing authorization endpoint (S01). The runtime records which connections observe which non-terminal operations and cues them when a report names one (S02). Clients then wait on the cue or their existing deadline and re-read with the unchanged `OperationObserve`: first the shared settlement helpers and the CLI runner (S03), then the remaining TUI and client loops (S04), and the MCP harness's attendance wait on the existing `attendance_changed` cue (S05). S06 rebuilds and proves the whole path on the packaged stages. Runtime process idle wakes, the profile worker's custody pass and the TUI's own timers belong to the session tui-41 and stay out of this plan.

CADRUMO-BUILD-DEBUG handed the rest of the plan, S06 on Release and the plan-close review, to tui-41 on 2026-10-17. The review found that the operation modal waits with no deadline, so a dropped report could leave it showing a settled operation as running. S09 was added when the operator then ruled "go with recommendation on both": undelivered reports are retried, amending the ADR's "dropped, not retried" constraint, and the Release rebuild waits until the uncommitted provider sign-in change in the working tree is committed.

## Steps

- [x] `S01` - Report each committed operation from the worker's journal to the runtime as a coalesced operations_advanced request on its authorization endpoint; `src/cadrumo/adapters/persistence/operations/durability_router.py, src/cadrumo/entrypoints/operation_composition.py, src/cadrumo_runtime/host/operation_host.py, src/cadrumo_runtime/adapters/worker_authorization_client.py, src/cadrumo_runtime/contracts/worker_authorization.py`.
- [x] `S02` - Record watches from non-terminal observations and publish operation_changed to the watching connections when a worker report names their operation; `src/cadrumo_client/contracts/session_events.py, src/cadrumo_runtime/host/session_events.py, src/cadrumo_runtime/adapters/worker_authorization.py, src/cadrumo_runtime/host/profile_connection_operations.py`.
- [x] `S03` - Wait on the operation_changed cue or the deadline in the client settlement helpers and the CLI runner instead of fixed intervals; `src/cadrumo_client/transport/frontend_client.py, src/cadrumo_client/transport/operation_settlement.py, src/cadrumo_client/commands/registered_operation_observations.py`.
- [x] `S04` - Move the remaining client and TUI observation loops onto the cue; `src/cadrumo_client/transport/operation_controller.py, src/cadrumo/entrypoints/tui/operations/modal.py, src/cadrumo/entrypoints/tui/google_saved_review.py, src/cadrumo_runtime/host/frontend/tui/aeat_sync/runtime_handoff.py, the other OperationObserve poll sites`.
- [x] `S05` - Wait for the person's attendance decision in the MCP harness on an attendance_answered cue the runtime publishes to the asking connection; `src/cadrumo_harness/mcp/runtime_admission.py, src/cadrumo_runtime/host/profile_connection_attendance.py`.
- [x] `S06` - Rebuild both stages and prove concurrent sign-in, backend calls and a live operation settle on the cue; `build/windows-x64/stage, dev/runtime_lifecycle`.
- [x] `S08` - Wake the installed manager and an observing desktop on installation and ownership events instead of the 2 s installation watch and the 30 s discovery deadline, and on a publishing manager's status changes instead of the 1 s external-owner pace, which stays the fallback for a manager that does not publish; `native/manager/src/installation_watch.rs, native/manager/src/cutover_coordinator.rs, native/manager/src/desktop_host.rs, native/manager/src/background.rs, native/manager/src/session/status_cue.rs, native/platform/src/file_changes.rs`.
- [x] `S09` - Retry an operation report the runtime does not take, ahead of later commits, after a backoff from 50 ms to 1 s, and give each pending report one try at close; `src/cadrumo_runtime/host/operation_progress_reporter.py`.

## Parallelization

Strictly sequential. S02 depends on S01's worker action, S03 to S05 consume S02's cue, and S06 verifies the whole path. One session executes every Step; builds and tests are serialized with the other sessions sharing this worktree.

## Verification

- S01: tests show the routed persistence calling its observer after each committed snapshot and settlement and never on a refused commit, and the worker's sender coalescing a burst of commits into one report and dropping, not retrying, an undeliverable one.
- S02: tests show a non-terminal observation recording a watch, a report producing exactly one `operation_changed` on that connection, no cue after a terminal observation, after disconnect or for another profile, and the authorization server refusing a report from anything but its owned worker.
- S03 to S05: each converted loop has a test that fails when the cue path is replaced by the old fixed-interval sleep, and keeps its deadline and `UNKNOWN` semantics.
- S06: Debug and Release `app-payload` rebuilt, the concurrent-sessions and backend probes pass on both, and a packaged CLI operation settles without polling.
- Every Step: ruff, ty and the covering tests on the files it touched; import lint when imports cross packages.
