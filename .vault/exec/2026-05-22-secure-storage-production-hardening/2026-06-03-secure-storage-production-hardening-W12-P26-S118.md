---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S118'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-016 for AEAT browser factory

## Scope

- `src/aeat/adapters/outbound/aeat/browser/_factory.py`
- `src/aeat/adapters/outbound/aeat/browser/test_factory.py`
- `.vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Description

- Centralize the diagnostic profile fallback bucket label and browser teardown resource labels as module constants.
- Replace raw teardown exception logging in the default browser session factory with structured resource labels and exception class names.
- Remove traceback emission from browser factory cleanup paths so profile paths, storage-state filenames, and remote-provider payloads are not serialized by degradation logs.
- Add a real close-path regression test for `DefaultBrowserSession.close()` that proves idempotent teardown and privacy-safe Playwright stop diagnostics.
- Close `AFR-016` and `W12.P26.S118` in the active-profile rollout ledger.

## Outcome

- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/browser/_factory.py src/aeat/adapters/outbound/aeat/browser/test_factory.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/browser/test_factory.py` passed: 1 passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/browser/test_factory.py src/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/adapters/outbound/aeat/browser/test_profile.py` passed: 22 passed.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S118` closed the step row.

## Notes

- The browser factory still depends on Playwright and active-profile resolution, but it does not persist application state directly. This row is closed as a remote-provider/profile factory boundary after removing raw cleanup payloads and keeping the diagnostic fallback profile explicit.
- The next open affected-file rows remain `W12.P26.S119` through `W12.P26.S122` for site health, export format deserialization, record specs, and censo live surfaces.
