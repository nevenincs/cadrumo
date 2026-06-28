---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S09'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]'
---

# W02.P03.S09 - focused live auth pytest lane

## Scope

Run the focused AEAT auth pytest lane under explicit opt-in and record pass, skip, failure, and external-auth blocker counts without treating skips or operator-mediated Clave timeout as green acceptance.

## Description

- Run the `aeat_live` auth tests under `AEAT_LIVE_TESTS_ENABLED=1`.
- Enable the full Clave Movil live-auth test with `AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH=1`.
- Force QR mode with `AEAT_CLAVE_PREFER_NON_QR=false` so the test uses the browser QR branch.
- Re-run local auth gate and encrypted-session tests to separate backend infrastructure health from external operator completion.

## Outcome

The focused live auth lane selected 6 live auth tests from the auth test package:

- 1 passed: the central Playwright browser reached AEAT's live Clave Movil selector.
- 4 skipped: certificate live tests skipped because certificate env vars are not fully configured; persisted Clave session probe skipped because no persisted encrypted Clave session was available in the pytest-isolated root.
- 1 failed: the full Clave Movil login reached AEAT QR mode, displayed page verification code `S2J`, then timed out after 120 seconds waiting for post-auth landing at `/wlpl/TEWV-CORE/ResumenVlt`.

The failure is an external-auth completion blocker, not a local access-gate or encrypted-session persistence failure. The provider captured encrypted diagnostic id `20260612T182744Z` and confirmed cancellation of the pending Clave request after the timeout.

## Verification

- `AEAT_LIVE_TESTS_ENABLED=1 AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH=1 AEAT_CLAVE_PREFER_NON_QR=false python -m pytest -m aeat_live src/aeat/adapters/outbound/aeat/auth/tests -q -rs --tb=short`: 1 failed, 1 passed, 4 skipped, 139 deselected.
- `python -m pytest -m "unit or integration" src/aeat/adapters/outbound/aeat/auth/tests/test_gate.py -q --tb=short`: 12 passed.
- `python -m pytest -m "unit or integration" src/aeat/adapters/outbound/aeat/auth/tests/test_session_store_roundtrip.py src/aeat/adapters/outbound/aeat/auth/tests/test_resume_behaviour_capture.py -q --tb=short`: 12 passed.

## Notes

`W02.P03.S09` remains open for acceptance. The live selector and local auth substrate are healthy, but the full live-auth lane is not green and skip-free. The next acceptance attempt needs either configured certificate credentials or a completed Clave Movil login that persists an encrypted session in the test root before the persisted-session probe can pass.
