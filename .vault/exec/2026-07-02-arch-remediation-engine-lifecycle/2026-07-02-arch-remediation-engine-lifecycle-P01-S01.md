---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:f04825dc9d256140aa64a9929f1ba0719c0cea5b99b654424e4e0c7c904daa81'
step_id: 'S01'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
---

# Make the bucket-session manager acquire the bucket engine lazily on first storage access within a session, registering the engine handle on the session

## Scope

- `src/aeat/adapters/persistence/storage/runtime.py`

## Description

- Add `BucketSession.acquire_engine` to lazily resolve and register the bucket engine on first storage access.
- Route `StorageRuntime.secure_object_repository` through the active session's `acquire_engine` so the handle is session-owned.

## Outcome

The active bucket session owns its engine handle, acquired lazily; runtime repository construction registers it on the session.

Landed in commit `38e62c216`.

## Notes
