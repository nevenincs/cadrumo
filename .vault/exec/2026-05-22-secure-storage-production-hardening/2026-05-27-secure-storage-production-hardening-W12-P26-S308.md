---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S308'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-observability-store-persistence-closeout-audit]]'
---



# `secure-storage-production-hardening` `W12.P26.S308`

Closed the observability store remote-mirror review for AFR-206.

## Changes

- Added `RunTracePersistenceError` for filesystem create/read/write failures in the run-trace store.
- Registered the new error in the central error registry and added locale strings through `python -m aeat.locales`.
- Wrapped store filesystem operations and added debug/warning visibility for skipped `iter_runs` entries.
- Added real filesystem tests for unusable runs roots, unreadable trace files, logged skip paths, successful context persistence failure, and body-error precedence.

## Validation

- `uv run ruff check` on the touched observability and error-registry slice.
- `uv run pytest` on observability store/model/context tests plus error-registry contract tests.
- `uv run python -m aeat.locales audit`
