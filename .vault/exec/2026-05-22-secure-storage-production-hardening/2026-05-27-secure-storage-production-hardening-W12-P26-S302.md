---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S302'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-observability-store-persistence-closeout-audit]]'
---



# `secure-storage-production-hardening` `W12.P26.S302`

Closed the run-context remote-mirror review for AFR-200.

## Changes

- Routed outer `run_context` per-run directory creation through the observability store helper instead of direct `Path.mkdir`.
- Added debug logging for replay marker fallback when settings resolution fails.
- Made successful `run_context` exits fail closed when final `trace.json` persistence fails, while preserving already-propagating body exceptions.
- Removed a stale pragma from the sink detach failure path while preserving warning-level visibility.

## Validation

- `uv run ruff check` on the touched observability and error-registry slice.
- `uv run pytest` on observability store/model/context tests plus error-registry contract tests.
- `uv run python -m aeat.locales audit`
