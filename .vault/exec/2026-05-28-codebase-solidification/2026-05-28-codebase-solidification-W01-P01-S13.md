---
step_id: "S13"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S13

**Status**: closed

## What was done

Introduced `BrowserAdapterTypeError(CoreError)` in the existing
`src/aeat/adapters/outbound/aeat/sede/_errors.py`. Added `CoreError`
to the import from `aeat.core.errors`.

Replaced three bare `TypeError` raises at the `BrowserContext.new_page()`
return-type guard in the three sede live-adapter files:

- `_renta_web_open.py` line 158 (inside `_open_renta_web_open_session`)
- `_nif_iva_check.py` line 300 (inside `collect_nif_iva_check_observations`)
- `_groi_check.py` line 279 (inside `collect_groi_observations`)

Each raise now passes `context={"actual_type": type(_raw_page).__name__}`
so the envelope carries the unexpected type name.

Also added `BrowserAdapterTypeError` to the `except (...)` re-raise
clause in all three functions so the typed error propagates without
being swallowed by the generic `SedeNavigationError` wrapper.

Registered the new error under code `ERROR_SEDE_BROWSER_ADAPTER_TYPE`
(category `ERROR`, `retryable=False`) in
`src/aeat/core/errors/registry/_adapters.py`.

Scaffolded locale key `errors.error.error_sede_browser_adapter_type`
via `python -m aeat.locales set` across en, ca, es, and hu.

## Files touched

- `src/aeat/adapters/outbound/aeat/sede/_errors.py` — `BrowserAdapterTypeError(CoreError)` declared
- `src/aeat/adapters/outbound/aeat/sede/_renta_web_open.py` — import + TypeError → BrowserAdapterTypeError + re-raise clause
- `src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py` — import + TypeError → BrowserAdapterTypeError + re-raise clause
- `src/aeat/adapters/outbound/aeat/sede/_groi_check.py` — import + TypeError → BrowserAdapterTypeError + re-raise clause
- `src/aeat/core/errors/registry/_adapters.py` — registry entry
- `src/aeat/locales/en.yml`, `ca.yml`, `es.yml`, `hu.yml` — new locale key

## Commit

`f13c9c0cb`
