---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase4-step4-2 browser session unit tests

## Intent

Exercise the navigation probe's classification branch without
Playwright by composing the real helper and fixture bodies.

## Changes

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py` — four new `@pytest.mark.unit`
  tests drive the real `probe_response` helper from real fixture
  HTML and assert the correct `SiteHealthError` is raised for
  mantenimiento, WAF, and rate-limited bodies. An OK fixture must
  not raise.

## Deviations

None.
