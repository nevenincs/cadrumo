---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S94'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s94-explicit-route-guard-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P23.S94` Explicit Route Guard

## Description

- Add AST guard coverage that rejects new unapproved explicit database-route test setup in tests and shared test helpers.
- Keep the existing production raw secure-object construction guard in the same convention guard file.
- Seed the approved-route allowlist from current low-level SQL/runtime, route-classification, and refusal-contract test surfaces discovered during S93 cleanup.

## Changed Surface

- `src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`

## Outcome

Closed for the explicit-route guard portion of S94.

The guard now scans all `src/aeat` test surfaces and shared test helpers for `aeat_database_url`, `AEAT_DATABASE_URL`, and matching executable string constants. It ignores docstring-only narrative mentions. Any new executable hit outside the approved low-level/refusal/classification allowlist fails the convention suite.

## Verification

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py` - 7 passed.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py` - all checks passed.
- `git diff --check -- src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py` - no whitespace errors.

## Notes

S95 must persist the human-readable inventory explaining each approved explicit-route surface and its owning classification/refusal behavior.
