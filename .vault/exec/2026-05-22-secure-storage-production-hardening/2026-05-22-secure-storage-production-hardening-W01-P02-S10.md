---
tags: ["#exec", "#secure-storage-production-hardening"]
date: "2026-05-22"
modified: '2026-05-22'
step_id: "S10"
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# `secure-storage-production-hardening` `W01.P02.S10`

Added route-guard regression tests for root fallback and explicit database URLs.

- Modified: `src/aeat/entrypoints/cli/test_root_fallback_write_guard.py`

## Description

The existing real-entrypoint root-fallback guard tests now also cover explicit database URL refusal for the same guarded mutation verbs. The explicit-route harness builds `Settings` with `aeat_database_url=sqlite:///<root>/explicit.db`, asserts classification as `EXPLICIT_DATABASE_URL`, invokes the actual CLI entrypoint, and verifies the guarded command refuses before creating the explicit database file.

Predicate coverage remains centralized around `_is_root_fallback_guarded_verb`, which is now the shared profile-bound mutation registry for both root fallback and explicit database URL write refusal.

## Tests

Validated with:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_root_fallback_write_guard.py -q`
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py`
