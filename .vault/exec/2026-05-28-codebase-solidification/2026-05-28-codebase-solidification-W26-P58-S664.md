---
step_id: S664
tags:
  - "#exec"
  - "#codebase-solidification"
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-31-codebase-solidification-audit]]"
---

# codebase-solidification W26.P58.S664 — Session-store Protocol cluster

## Outcome

`SessionStoreProtocol` was already present in `application/auth/_protocols.py`
and already used as the variable annotation on `_session_store_impl` (line 48)
and the `configure_session_store` parameter (line 51).

The two type-ignores at lines 68-69 arose because:
- Line 68: `_impl` is a module object, not a class instance; mypy cannot verify
  module-object protocol conformance without an explicit cast.
- Line 69: after the lazy configure call, `_session_store_impl` is still typed
  as `SessionStoreProtocol | None`; mypy cannot narrow past the `if` branch.

Fix applied:
- `cast(SessionStoreProtocol, _impl)` with `CAST-RATIONALE-MODULE-AS-PROTOCOL` marker
- `assert _session_store_impl is not None` narrows the return type

Both `# type: ignore` lines removed. `cast` added to `typing` import.

Design choice: cast + assert (structural, minimal — no Protocol duplication).

Allowlist paydown: 2 entries removed.
