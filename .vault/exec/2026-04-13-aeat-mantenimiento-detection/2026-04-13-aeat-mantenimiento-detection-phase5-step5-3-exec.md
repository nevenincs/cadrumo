---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase5-step5-3 engine unit test scenario

## Intent

Prove that a real `SiteHealthError` raised by a stage component
terminates the run with `WorkflowAbortReason.SITE_UNAVAILABLE` and
never collapses into `UNHANDLED_EXCEPTION`.

## Changes

- `src/aeat/application/workflow/test_engine.py` — new
  `TestSiteUnavailableArm` test class. The scenario builds a real
  `SiteHealthStatus` from
  `tests/fixtures/site_health/mantenimiento/interstitial.html`,
  wraps it in a real `SiteHealthError`, and assigns it to the fake
  deadline engine. The assertions check the abort reason, the
  final stage, the attached `SiteHealthAlert`, and the run id
  alignment.

## Deviations

None.
