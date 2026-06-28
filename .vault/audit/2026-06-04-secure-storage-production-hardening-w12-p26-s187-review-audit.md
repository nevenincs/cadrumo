---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S187]]'
---

# `secure-storage-production-hardening` `W12.P26.S187` Review

## S187-001 | PASS | Engine configuration is centralized through settings

`sql/engine.py` accepts explicit `Settings` or calls `load_settings()` when no settings object is provided. It does not read environment variables directly, and it does not introduce a parallel database-route configuration surface.

## S187-002 | PASS | Engine diagnostics avoid configured path disclosure

Engine creation logs now use `_route_marker()` rather than the database URL or database path. Engine creation failures carry `route_marker` and `error_type` context only, so private local storage paths are not emitted by this slice.

## S187-003 | PASS | SQL route filesystem behavior remains anchored and tested

Relative SQLite URLs are normalized through the core project-path helper before parent directories are created. The focused test suite exercises query round-trip behavior, parent creation, fallback database derivation, project-root anchoring, redacted success logs, and redacted creation failures.

## S187-004 | PASS | Test-policy convention repair avoids monkeypatching

The relative-cwd adversity test now changes cwd directly in a `try`/`finally` block and restores the original cwd before disposal and cleanup. This keeps the real behavior under test without using `monkeypatch`, fakes, stubs, skips, or xfails.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_engine.py` passed with 6 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/engine.py src/aeat/adapters/persistence/storage/sql/test_engine.py` passed.
- `if (rg "monkeypatch|pytest\\.MonkeyPatch" src/aeat/adapters/persistence/storage/sql/test_engine.py) { exit 1 }` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Reviewer note: Gauss review found no issues in the S187 slice. The code path is settings-derived, uses centralized path normalization, preserves hashed route diagnostics, and does not swallow exceptions. Residual risk is limited to the focused slice scope; the reviewer did not run tests, but supervisor validation did.

Disposition: close `AFR-085`.
