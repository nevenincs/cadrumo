---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:11f7a8b2e3bc8fbc59f128c958f58c639aa4dc6058860cd1b69c1cf97d41afff'
step_id: 'S11'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Make the core wheel lane install and exercise a supplied complete cohort

## Scope

- `dev/packaging/smoke_core.py`
- `dev/packaging/tests/test_smoke_core_payload.py`
- `justfile`

## Description

- Accept the command wheel and both mandatory data wheels as one all-or-nothing supplied cohort.
- Validate the named wheel identities, exact companion dependency pins, and one exact version across all three distributions.
- Install all supplied artifacts in one fresh-environment transaction.
- Require the lane to consume a supplied cohort directory; the normal packaging-smoke sequence constructs that directory before invoking the lane.
- Execute the installed grounded Modelo 200 CLI oracle and retain its complete JSON evidence in the lane manifest.

## Outcome

- A supplied Cadrumo `0.2.1` three-wheel cohort installed successfully into a fresh Python 3.13 environment.
- The normal `just packaging-smoke-core` entry point consumed the prebuilt cohort directory and did not invoke wheel construction.
- The installed command completed the full grounded tax-work itinerary with `DP200014:00562=23000.00`, formula `modelo-200-cuota-integra`, persisted revision `d501d7d8592d692acc410238bacc39f6716ba93ecbca9cd26bb2a6794ec575da`, and the expected legal and source references.
- The smoke manifest retains the command wheel, both companion wheels, installed environment, and full tax-oracle evidence.
- Ruff passed; the existing manifest and environment tests passed; the real three-wheel payload test passed after building every wheel; and the normal supplied-cohort lane completed in 331.2 seconds.

## Notes

- Evidence is retained under `var/packaging-smoke/core-20260716T102738Z`.
- Cohort-wide immutable source identity and digest schema remain owned by the later release-cohort steps.
