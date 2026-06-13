---
step_id: S12
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S12 — real-behavior tests for verify BrowserAdapterTypeError

## Outcome

Added three tests to `src/aeat/adapters/outbound/aeat/verify/test_verify.py`:

- `test_build_default_browser_session_raises_browser_adapter_type_error_on_wrong_type`:
  uses `monkeypatch` to replace `default_browser_session_factory` on the real
  browser module with a factory returning a sentinel `_NotASession` instance.
  Calls `_build_default_browser_session()` directly and asserts
  `BrowserAdapterTypeError` is raised with the type name in the message. No
  mocks, no tautology — the raise path is physically exercised.

- `test_browser_adapter_type_error_is_registered`: asserts
  `"ERROR_SEDE_BROWSER_ADAPTER_TYPE"` is present in `ERROR_REGISTRY`.

- `test_browser_adapter_type_error_round_trips_build_error_envelope`: builds
  a `BrowserAdapterTypeError` and calls `build_error_envelope`; asserts
  `code == "ERROR_SEDE_BROWSER_ADAPTER_TYPE"` and `category == "ERROR"`.

## Files touched

- `src/aeat/adapters/outbound/aeat/verify/test_verify.py`

## Verification

All 13 tests pass (was 10 before this step). Commit SHA: d23b1303d.
