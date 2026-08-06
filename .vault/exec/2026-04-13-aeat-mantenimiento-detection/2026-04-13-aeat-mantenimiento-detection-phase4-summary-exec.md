---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-07-17'
body_hash: 'sha256:184623a5946610eefdaf22e050c44aa9317fd46c09ab8a7a2239ec431545ac2f'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase4 summary - browser session hook

Phase 4 added `aeat.adapters.outbound.aeat.browser._site_health_probe` and a new
`BrowserSession.navigate(page, url)` async method. `navigate` runs
`page.goto`, collects `http_status`/headers/`page.content()`, then
calls `probe_response` and raises `SiteHealthError(status=...)`
when the response is classified as non-OK. Transport-layer failures
(Playwright `TimeoutError` and generic exceptions) are wrapped as
`SiteHealthStatus(state=UNREACHABLE, http_status=599,
detected_markers=('transport-error:<exc-type>',))`. The
`create_context` contract is untouched.

Unit tests drive the helper with real fixture HTML without a
Playwright runtime. Steps: 4-1, 4-2.
