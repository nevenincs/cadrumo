---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S187'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s187-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S187`

Closed `AFR-085` for the SQL engine factory route.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/sql/engine.py` against the `runtime-default` SQL-route and plain-file classification.
- Replaced configured database URL diagnostics with a stable hashed route marker for engine creation logs and creation-failure context.
- Confirmed the engine factory derives configuration through `Settings`, normalizes relative SQLite paths through the core project-path helper, creates SQLite parents, enables SQLite foreign keys, and raises `StorageError` with translated message keys.
- Repaired `src/aeat/adapters/persistence/storage/sql/test_engine.py` so the relative-cwd adversity test no longer uses `monkeypatch`.
- Closed `AFR-085` and `W12.P26.S187`.

## Outcome

`AFR-085` is closed as an engine-route hardening and convention-compliance slice. The engine route still uses centralized settings and core path resolution, and it now avoids disclosing configured SQL routes in debug logs or creation-failure messages.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_engine.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/engine.py src/aeat/adapters/persistence/storage/sql/test_engine.py`
- `if (rg "monkeypatch|pytest\\.MonkeyPatch" src/aeat/adapters/persistence/storage/sql/test_engine.py) { exit 1 }`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The `rg` monkeypatch scan returned no matches. No pragma/noqa suppressions were added.
