---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:6f08cd4b679f69549ff409da35674186c54d5a590f85661a57ca225a7ac60d07'
step_id: 'S28'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite profile_session_path as a one-line caller of keystore_sidecar_path, gated by the existing persisted-session suite

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`

## Description

## Outcome

Landed in `3f2f73e465`, confirmed at HEAD. `profile_session_path` in `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py:527-531` is a one-line caller of `keystore_sidecar_path`, gated by the existing persisted-session suite (unchanged call surface, confirmed by the deferred import at line 529 resolving to the bucket-package facade).

## Notes
