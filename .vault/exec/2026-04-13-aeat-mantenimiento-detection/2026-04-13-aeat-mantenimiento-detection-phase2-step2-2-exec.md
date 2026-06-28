---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase2-step2-2 fixture corpus

## Intent

Build the synthetic `tests/fixtures/site_health/` corpus: 5+
mantenimiento positives, 5+ WAF positives, 5+ rate-limit fixtures
(each with a sibling `.headers.json`), and 5+ healthy negative
controls.

## Changes

- `tests/fixtures/site_health/README.md` — per-fixture provenance and
  asserted markers.
- `tests/fixtures/site_health/mantenimiento/*.html` — 5 fixtures:
  interstitial, novedades announcement, sede banner, title-only,
  disculpe-only.
- `tests/fixtures/site_health/waf_challenge/*.html` — 5 fixtures:
  request blocked, reference id, generic WAF, bare 403 support id,
  blocked minimal.
- `tests/fixtures/site_health/rate_limited/*.html` + headers — 5
  fixtures: 429 with/without Retry-After, 503 with/without
  Retry-After, 503 non-mantenimiento.
- `tests/fixtures/site_health/ok/*.html` — 5 negative controls:
  sede landing, expedientes list, notificaciones list, calendario,
  help page.

## Acceptance

Verified by the Phase 3 parametrised fixture tests and the
`TestFixtureCorpusShape` guardrails.

## Deviations

None.
