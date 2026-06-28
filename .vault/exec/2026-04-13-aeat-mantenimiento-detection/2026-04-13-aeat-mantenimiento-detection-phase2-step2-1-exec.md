---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase2-step2-1 parsers module

## Intent

Land the three side-effect-free parsers plus an `evaluate_response`
orchestrator under `aeat.status._site_health_parsers`.

## Changes

- `src/aeat/status/_site_health_parsers.py` — implements
  `parse_mantenimiento_banner`, `parse_waf_challenge`,
  `parse_rate_limit_response`, and `evaluate_response`. All four
  share the same keyword-injected
  `rate_limit_retry_after_default: int` to keep the browser session
  hook as the single configuration point.
- Mantenimiento classifier requires two body hits OR one body hit
  plus a title match (`mantenimiento` / `interrupcion`) as specified.
- WAF classifier fires on (403 AND any marker) OR
  (`request blocked` AND `reference id`/`support id`).
- Rate-limit classifier yields to the mantenimiento parser on a 503
  that also matches a maintenance marker.

## Acceptance

Verified by the Phase 3 parametrised fixture tests.

## Deviations

None.
