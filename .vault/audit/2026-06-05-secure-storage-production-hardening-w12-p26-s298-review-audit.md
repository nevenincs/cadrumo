---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S298-001 | FIXED | i18n fallback paths swallowed root-cause detail unevenly

`src/aeat/core/i18n/_render.py` had several fallback branches that returned a safe
default but did not consistently leave enough debug context. Locale-load failures now
log with `exc_info=True`, settings-load fallback logs the exception type and traceback,
and interpolation format failures log the translation key and exception type before
returning the partially-rendered value.

## S298-002 | FIXED | Active-profile resolver logging included raw exception text

The active-profile language resolver catch path previously interpolated `exc` directly
into the debug message. That could place resolver exception text into the formatted log
message before downstream consumers inspect it. The message now records only
`type(exc).__name__` and keeps traceback diagnostics in `exc_info=True`, with the
central `SecretScrubbingFilter` still attached through `get_logger`.

## S298-003 | PASS | Settings and localization authority remain centralized

The output-language cache key still reads a narrow raw environment signature, but only
to determine whether the cached value may be stale. Effective language values continue
to resolve through `load_settings()`, active-profile resolver registration, supported
language normalization, and the packaged locale catalogues. No localization key changes
were made; `python -m aeat.locales audit` passes.

## S298-004 | PASS | Tests exercise real renderer behavior

The added tests use the real renderer module, logger, resolver registration hook, and
locale lookup/interpolation paths. They do not shadow business logic or introduce
test-only locale catalogue entries.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/i18n/_render.py src/aeat/core/i18n/test_render_override.py`
- `uv run --no-sync pytest -q src/aeat/core/i18n/test_render_override.py src/aeat/core/i18n/test_placeholder_parity.py src/aeat/core/errors/test_registry.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "core i18n render output_language profile resolver interpolation exception logging secure storage" --type code --port 8766 --max-results 8`
