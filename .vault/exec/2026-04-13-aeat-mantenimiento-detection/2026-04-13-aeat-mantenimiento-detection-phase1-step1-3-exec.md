---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase1-step1-3 re-export from aeat.status

## Intent

Promote the new site-health models and parser callables to the
subpackage public API so callers outside `aeat.status` can import
them from the package root.

## Changes

- `src/aeat/status/__init__.py` — imports and re-exports
  `SiteHealthState`, `SiteHealthEvidence`, `SiteHealthStatus`,
  `SiteHealthAlert`, plus `evaluate_response`,
  `parse_mantenimiento_banner`, `parse_rate_limit_response`, and
  `parse_waf_challenge`. Additions also applied to `__all__`.

## Acceptance

- `from aeat.status import SiteHealthState, SiteHealthStatus,
  SiteHealthEvidence, SiteHealthAlert` succeeds.

## Deviations

None.
