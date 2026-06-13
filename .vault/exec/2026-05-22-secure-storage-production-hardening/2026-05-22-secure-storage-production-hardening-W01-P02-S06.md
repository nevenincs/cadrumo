---
tags: ["#exec", "#secure-storage-production-hardening"]
date: "2026-05-22"
modified: '2026-05-22'
step_id: "S06"
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# `secure-storage-production-hardening` `W01.P02.S06`

Centralized expired-session refusal at active key resolution.

- Modified: `src/aeat/adapters/persistence/storage/master_key/_active_session.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/test_idle_timeout.py`

## Description

The active storage key resolver now evaluates the bound `BucketSession` before returning DEK bytes. Expired sessions are closed and refused with the existing bucket-locked error, so column encryption and decryption cannot continue through a stale in-memory session.

The change keeps `activate_session` as the context owner and makes the freshness check live exactly where secure-object encryption obtains key material.

## Tests

Added a real `BucketSession` activation test that opens an already-expired session, calls the active key resolver, and asserts the session is sealed after the bucket-locked refusal.
