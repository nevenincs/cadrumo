---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase3-step3-1 colocated unit tests

## Intent

Drive every fixture through the real parser suite and validate the
pydantic model shapes.

## Changes

- `src/aeat/status/test_site_health.py` — parametrised fixture
  tests (mantenimiento, WAF, rate-limited, ok), dedicated retry-after
  tests, and model-shape tests for `SiteHealthEvidence`,
  `SiteHealthStatus`, and `SiteHealthAlert`. No mocks or patches;
  headers are read from sibling `.headers.json` files.

## Acceptance

`uv run pytest src/aeat/status/test_site_health.py -m unit -q`
passes (verified in Phase 8 gates).

## Deviations

None.
