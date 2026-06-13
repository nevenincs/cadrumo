---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F13'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W04.F13`

Resolved the false-positive Windows dependency-sync warning in `aeat config repair`.

- Modified: `src/aeat/application/diagnostics.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/__init__.py`

## Description

`uv sync --frozen --dry-run` reported that the project environment would make no changes, and `uv sync --frozen` also completed without changes. The repair diagnostic still warned because the Windows heuristic compared `pyproject.toml` against `.venv/pyvenv.cfg`; uv does not rewrite that marker for a no-op sync.

The repair diagnostic now treats uv's frozen dry-run as the authority when the timestamp heuristic looks stale. If uv reports `Would make no changes`, `runtime.dependency_sync` reports `ok` with a detail line naming the dry-run. If uv is unavailable, times out, or reports a real delta, the existing `uv sync` next action remains.

While verifying the repair command, the current worktree also exposed an import-boundary break: `SecureBoundRepository` imported `SecureObjectUnreadable` from the SQL package public surface, but `sql/__init__.py` did not export it. That export was restored so `aeat config repair` and diagnostics tests can import the storage layer.

No live AEAT operation was performed in this step.

## Tests

- `uv sync --frozen --dry-run` reported `Would make no changes`.
- `uv sync --frozen` completed without package changes.
- `uv run aeat config repair` reported `ok runtime.dependency_sync Venv in sync`.
- `uv run pytest src/aeat/application/test_diagnostics.py src/aeat/application/test_repair_integrity.py -q --disable-warnings` completed with 39 passed.
- `uv run ruff check src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py src/aeat/adapters/persistence/storage/sql/__init__.py` passed.
