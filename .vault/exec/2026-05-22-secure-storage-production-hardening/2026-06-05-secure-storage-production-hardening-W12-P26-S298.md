---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S298'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S298 - Close AFR-196 for i18n rendering

Scope: close `AFR-196` for `src/aeat/core/i18n/_render.py` with signals
`active-profile, manifest-bucket, sql-route, plain-file`, target
`manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited output-language resolution through settings, active-profile resolver wiring,
  locale catalogue loading, and interpolation fallback behavior.
- Preserved the centralized settings authority: raw environment reads remain limited to
  cache-key invalidation, while effective values still flow through `load_settings()`.
- Replaced silent or low-detail fallback branches with debug breadcrumbs carrying
  exception type and `exc_info=True`.
- Removed raw exception text from the active-profile resolver debug message so
  resolver failures do not place secret-shaped values directly in the log message.
- Added real renderer tests for locale-load failure logging, profile resolver fallback
  logging, and interpolation failure logging without logging interpolation values.
- Closed `W12.P26.S298` through `vaultspec-core vault plan step check` and updated
  the `AFR-196` register status to `closed`.

## Outcome

`AFR-196` is closed. The i18n renderer remains a read-only manifest-discovery and
active-profile participant rather than a persistence authority. Its adverse-path
fallbacks now leave debug-level diagnostics without bypassing centralized settings or
the localization catalogue pipeline.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/i18n/_render.py src/aeat/core/i18n/test_render_override.py`
- `uv run --no-sync pytest -q src/aeat/core/i18n/test_render_override.py src/aeat/core/i18n/test_placeholder_parity.py src/aeat/core/errors/test_registry.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "core i18n render output_language profile resolver interpolation exception logging secure storage" --type code --port 8766 --max-results 8`

## Notes

The renderer still samples a narrow AEAT environment allowlist for cache-key
invalidation. That is not a settings bypass: cache misses still construct the
effective `Settings` object through `load_settings()`.
