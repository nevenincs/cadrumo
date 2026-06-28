---
tags:
  - '#exec'
  - '#core-authority'
step_id: S70
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P20.S70 - remove adapters import from application/auth/_sessions.py

## Outcome

Removed the module-scope import `from ...adapters.outbound.aeat.auth import _session_store`
from `application/auth/_sessions.py` (line 15 — the production application->adapters edge
at ctx:normal classified in the v2 audit). This was the import-time cycle root.

Replaced with:
- `configure_session_store(store: SessionStoreProtocol)` — DI registration function
  exported from `application/auth/__init__.py` so the entrypoints layer can wire in
  the concrete adapter at startup.
- `_get_session_store() -> SessionStoreProtocol` — lazy accessor that auto-wires the
  concrete implementation on first call by importing from the adapter layer at runtime.
- Five `_session_store.` call sites replaced with `_get_session_store().`.

The `SessionStoreProtocol` import comes from `._protocols` (application-layer), so no
adapter import remains at module scope.

MIGRATE-001, RELOC-016, Rule 2, Rule 8.

## Commit

`c1ab6234d` — refactor(auth): W08.P20.S69+S70

## Files touched

- `src/aeat/application/auth/_sessions.py` — removed adapters import, added DI wiring
- `src/aeat/application/auth/__init__.py` — exports configure_session_store

## Before / After

Before: 1 normal-scope application->adapters edge at `_sessions.py:15`.
After: 0 normal-scope module-level application->adapters edges in `_sessions.py`.
(Remaining local_scope edges in _operator.py etc. are addressed in S71.)

## Verification

7 auth session tests pass.
