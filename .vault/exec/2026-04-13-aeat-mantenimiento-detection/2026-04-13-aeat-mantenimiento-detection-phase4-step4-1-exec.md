---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase4-step4-1 browser session navigate hook

## Intent

Add a health-probe helper and a new
`BrowserSession.navigate(page, url)` method that classifies the
response and raises `SiteHealthError` on non-OK states.

## Changes

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/_site_health_probe.py` — new private helper
  re-exporting `evaluate_response` under a `probe_response` shim.
  The module forbids imports from `aeat.adapters.outbound.aeat.auth`, `aeat.application.filing`, and
  `aeat.domain.financial`.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` — new `navigate` async method that
  captures the response / headers / body, calls `probe_response`,
  and raises `SiteHealthError(status=...)` when non-OK. Transport
  failures (timeouts, generic transport errors) are wrapped in a
  synthetic `SiteHealthStatus(state=UNREACHABLE, http_status=599,
  detected_markers=('transport-error:<exc-type>',))`.
- `create_context` signature and behaviour are untouched.

## Acceptance

- `BrowserSession.navigate` exists; direct `page.goto` remains
  callable on a `Page`.
- Verified by the Phase 4.2 unit tests.

## Deviations

- The plan specified raising `SiteHealthError` on `DNS/TCP/TLS/
  PlaywrightTimeoutError` specifically. The implementation wraps
  `PlaywrightTimeoutError` explicitly and catches the generic
  `Exception` to cover DNS/TCP/TLS (Playwright surfaces those as
  generic exceptions in practice). Both paths feed the same
  UNREACHABLE classifier helper.
