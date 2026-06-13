---
step_id: "S14"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S14

**Status**: closed

## What was done

Created `src/aeat/adapters/outbound/aeat/sede/test_browser_errors.py`
with five real-behavior tests:

- **S14-A**: asserts `ERROR_SEDE_BROWSER_ADAPTER_TYPE` is in `ERROR_REGISTRY`.
- **S14-B**: constructs a `BrowserAdapterTypeError`, calls `build_error_envelope`,
  asserts code, `retryable=False`, and `actual_type` context key.
- **S14-C**: exercises `_open_renta_web_open_session` directly with a hand-rolled
  `_FakeBrowserSession` / `_FakeBrowserContext` whose `new_page()` returns a
  `_NonPageSentinel`; asserts `BrowserAdapterTypeError` is raised with the
  correct `actual_type` context value.
- **S14-D**: monkeypatches `default_browser_session_factory` in `_nif_iva_check`
  with a hand-rolled async factory; calls `collect_nif_iva_check_observations`;
  asserts `BrowserAdapterTypeError` is raised.
- **S14-E**: same pattern for `collect_groi_observations`.

No `unittest.mock` imports. Stand-ins are hand-rolled minimal classes.
`pytest.MonkeyPatch` (built-in fixture, not a mock library) is used for
factory injection in S14-D and S14-E.

All five tests pass (`5 passed in 1.81s`).

## Files touched

- `src/aeat/adapters/outbound/aeat/sede/test_browser_errors.py` — created (5 tests)

## Commit

`f13c9c0cb`
