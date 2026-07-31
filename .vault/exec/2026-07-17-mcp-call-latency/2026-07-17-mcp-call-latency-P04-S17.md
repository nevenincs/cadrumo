---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:0b6f6c51c899f611f52ba810fa81ac09b4bd2dfc989af99ba1853d46ed0f8b8d'
step_id: 'S17'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# Extend the loop-responsiveness regression to cover the warm path plus a custody test proving idle-lock relock and clean crash restart

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_server_loop_responsiveness.py`

## Description

- Add a warm-path responsiveness test: a warm in-process verb served through the real memory transport while a concurrent `tools/list` is answered mid-flight and the warm call returns non-error - the warm transport shares the same off-loop dispatch wrapper the subprocess gap tests prove keeps the loop free.
- Add the custody test: provision a REAL encrypted profile through the in-process runtime under an env-isolated storage root, drive two session-opening reads (`review.queue`) warm through the server, assert both succeed with the active profile resolved, and assert the long-lived server context holds no bucket session afterward - proving the warm runtime never retains decrypted key material and the per-call open/use/relock cycle strands nothing.
- Add the crash-restart test: after a first warm runtime serves the encrypted state, discard it and prove a fresh instance re-warms and serves the SAME persisted state cleanly with no torn state and no custody carried over.
- Keep the two subprocess gap probes (repointed in S12 to an open-world verb) as the slow-call off-loop proof.

## Outcome

Five tests pass (two subprocess gap probes, the warm-path concurrency test, the custody test, the crash-restart test) against real storage and crypto - no mocks. The custody test drives a real bucket session (profile created in-process, encrypted review state read twice) and confirms `has_active_bucket_session()` is False in the server context after; the crash-restart test confirms a rebuilt server serves the same encrypted profile with `active_profile == operator` and no held session.

## Notes

The warm in-process runtime runs the CLI in a raw worker thread that inherits `os.environ` but NOT context-var overrides, so the custody and crash tests isolate via env vars (`temporary_env`) and provision the profile through the in-process runtime itself, so the create and every later read resolve the same file-backend master key. `temporary_env` rejects a `None` value, so the ambient active-profile is left to the create-written pointer rather than an env unset. A fast warm call cannot demonstrate loop-freedom via a completion gap the way a multi-second subprocess call can, so the warm-path test asserts concurrent service (the mid-flight list is answered) rather than a timing gap; the shared off-loop wrapper's gap behaviour stays covered by the subprocess probes.
