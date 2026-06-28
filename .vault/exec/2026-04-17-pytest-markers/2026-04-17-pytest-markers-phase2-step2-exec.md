---
tags:
  - "#exec"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-plan]]"
  - "[[2026-04-17-pytest-markers-adr]]"
---

# pytest-markers phase-2 step-2

## implement-pytest-collection-modifyitems

Created shared helper `tests/_marker_hook.py` with:

- Module constants `_LIVE_WRITE_BYPASS_ENV`, `_LIVE_WRITE_CONFIRM_ENV`, `_LIVE_WRITE_CONFIRM_PHRASE`, `_ACCESS_MARKERS`.
- Private `_live_write_bypass_active()` returning True iff all three factors hold (env, confirm phrase, TTY).
- Public `apply(config, items)` enforcing the nine-marker contract: raise `pytest.UsageError` on access-count != 1 or missing domain marker; drop `live_write` items when bypass inactive; emit a session-level warning on first drop.

Created repo-root `conftest.py` delegating to `apply`. Updated `tests/conftest.py` to delegate to the same helper for double-invocation tolerance.

The planning-time probe established that a hook in `tests/conftest.py` alone does NOT reach items collected under `src/aeat/...`; the repo-root conftest is the canonical host.

Files touched:
- `tests/_marker_hook.py` (new)
- `conftest.py` (new repo-root)
- `tests/conftest.py` (rewritten)

## verification

- `uv run pytest --collect-only -m live_write -q` -> 0 items collected.
- `uv run pytest --collect-only -m live_read -q` -> 24 items collected across 14 modules.
- `uv run pytest --collect-only -q` -> no PytestUnknownMarkWarning, no UsageError.
