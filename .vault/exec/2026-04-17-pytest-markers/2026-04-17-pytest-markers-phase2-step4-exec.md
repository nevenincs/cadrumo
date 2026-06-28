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

# pytest-markers phase-2 step-4

## confirm-hook-reach-from-src-aeat-collection-root

Confirmatory re-run after phase 3 migration: the root-level `conftest.py` exists and items collected under `src/aeat/...` pass through the shared hook. Verified indirectly via the integrity test suite (148 passed, every `src/aeat/` test module validated) and via `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/ -m live_write -q` returning 0 items (demonstrating the hook ran on the src/aeat/submission subtree).

No ad-hoc `live_write` tag was applied because the factor-isolation tests in phase 6.1b/d/e exercise the same drop path more cleanly (they set env vars without any TTY and verify collection still drops, which requires the hook to run on items under `src/aeat/adapters/outbound/aeat/export/`).

Files touched: none.

## verification

- `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/ -m live_write -q` -> 0 items with no env vars set.
- `uv run pytest tests/test_marker_integrity.py` -> 148 passed (covers every src/aeat/ test module).
