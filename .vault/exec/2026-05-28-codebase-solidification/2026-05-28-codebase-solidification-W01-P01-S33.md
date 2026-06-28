---
step_id: S33
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S33 — autocomplete except narrowing

## Outcome

Narrowed the `except Exception: return ()` catch-all in
`_declared_period_tokens` at `src/aeat/entrypoints/cli/_modelo.py` to two
specific arms:
- `except AeatError: return ()` — typed registry failures swallowed silently.
- `except Exception: _log.debug(...); return ()` — unexpected non-AeatError
  exceptions logged at DEBUG via the module-level `_log` observability sink.

Added `AeatError` import from `core.errors`, `get_logger` import from
`core.logging`, and `_log = get_logger(__name__)` module-level logger.

## Files touched

- `src/aeat/entrypoints/cli/_modelo.py` (AeatError + get_logger imports, _log declaration, narrowed catch clause)

## Commit

`07378f2c0`
