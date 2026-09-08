---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:0f3540683c31247804d788382d7f1f236a561c36272ddf248289e04ad8b75085'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S198]]"
---

# `reachability-burndown` audit: `S198 live session count withdrawal review`

## Scope

Independent bounded review of W05.P12.S198: removal of the test-only live-session count, observable replacement proofs, live registration and emergency shutdown callers, cadence guidance, Step Record evidence, and accepted per-profile custody/session-zeroisation decisions.

## Findings

No findings.

The deleted count was explicitly diagnostic/test-only and never controlled encryption or shutdown. `BucketSession` construction still calls `register_live_session`; active-session teardown and the MCP server shutdown path still call `close_all_live_bucket_sessions`. The sweep retains lock-bounded weak-registry snapshotting, closes each live session, zeroises its key buffer through the session owner, tolerates already sealed sessions, and returns the observable number closed.

The rewritten tests are stronger at the behavioral boundary: a cross-thread session is demonstrably sealed and its captured DEK buffer overwritten; repeated sweeps return zero without error; and a real `weakref.ref` becomes empty after the caller drops the session and collection runs. These checks prove emergency zeroisation, idempotence, and non-ownership directly without replacing the deleted diagnostic with another metastate accessor.

The Step Record identifies the exact two Python paths and cadence reference, exact Ruff and two-file focused pytest commands, zero-residue scan, production-metastate result, and contemporaneous reachability findings. The cadence addition generalizes the lesson as an authority-boundary rule without maintaining a module or symbol census. The change is consistent with accepted session custody: keyring/session state is acceleration only and shutdown must retire in-process secrets.

## Recommendations

Approve W05.P12.S198. No code, ADR, test, or Step Record correction is required.
