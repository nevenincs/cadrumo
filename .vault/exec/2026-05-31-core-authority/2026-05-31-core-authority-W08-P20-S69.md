---
tags:
  - '#exec'
  - '#core-authority'
step_id: S69
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P20.S69 - declare AuthSessionProtocol (SessionStoreProtocol)

## Outcome

Created `src/aeat/application/auth/_protocols.py` with two Protocols:

- `PersistedSessionDataProtocol` — minimal surface the application reads from a persisted
  session record (the `.metadata` attribute).
- `SessionStoreProtocol` — structural interface for the session store with `exists`,
  `load`, and `delete` methods. This is the interface `_sessions.py` depends on instead
  of importing the concrete `adapters/outbound/aeat/auth/_session_store` module directly.

Both are `@runtime_checkable`. The concrete `_session_store` module satisfies
`SessionStoreProtocol` structurally (module attributes match the method signatures).

MIGRATE-001, Rule 8.

## Commit

`c1ab6234d` — refactor(auth): W08.P20.S69+S70

## Files touched

- `src/aeat/application/auth/_protocols.py` — new, SessionStoreProtocol + PersistedSessionDataProtocol

## Verification

7 auth session tests pass (test_persisted_session_metadata.py + test_sessions_storage_state_paths.py).
