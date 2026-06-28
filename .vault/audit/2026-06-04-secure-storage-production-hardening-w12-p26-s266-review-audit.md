---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S266]]'
---

# `secure-storage-production-hardening` `W12.P26.S266` Review

## S266-001 | PASS | Resolver is read-only and lazily imports storage dependencies

`src/aeat/application/user_profile/_language_resolver.py` only reads the active profile record and extracts `preferences.output_language`. Workflow persistence and orchestration imports remain deferred inside the resolver body, so package import registers the callback without pulling the storage stack into state-free surfaces.

## S266-002 | PASS | Failure path is centrally logged and falls back

The application resolver itself does not catch exceptions, but `src/aeat/core/i18n/_render.py` wraps the registered callback, logs resolver failures at debug level through `get_logger`, and returns `None` so settings/default language resolution continues. That is the correct boundary: core owns fallback and logging for the callback it invokes.

## S266-003 | OPEN | Existing lazy-boundary test has subprocess lint debt

Including `src/aeat/application/user_profile/test_lazy_boundary.py` in the ruff target reports `S603` on its fresh-interpreter `subprocess.run` helper. The test behavior passes and this was not introduced by S266, but it remains a cleanup item for the broader no-noqa/no-duct-tape lint hardening wave.

## S266-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/user_profile/_language_resolver.py src/aeat/core/i18n/_render.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_lazy_boundary.py src/aeat/core/i18n/test_translatable_contract.py`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

Disposition: close `AFR-164`.
