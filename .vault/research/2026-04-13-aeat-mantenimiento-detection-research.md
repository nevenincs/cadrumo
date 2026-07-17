---
tags:
  - "#research"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-07-17'
title: "AEAT Mantenimiento / WAF / Rate-Limit Detection Research"
related:
  - "[[2026-04-12-playwright-anti-bot-adr]]"
  - "[[2026-04-12-workflow-engine-adr]]"
---
# aeat-mantenimiento-detection research

## Purpose

Re-ground the accepted site-health decision in the current Cadrumo browser,
Sede, workflow, and diagnostics boundaries. Earlier research assumed an
`aeat.status.StatusReader` and a self-healing sync runner; both are deleted and
must not remain semantic extension points.

## Current implementation

- `src/cadrumo/adapters/outbound/aeat/browser/_site_health.py` owns strict
  `SiteHealthState`, `SiteHealthEvidence`, and `SiteHealthStatus` records.
- `_site_health_parsers.py` classifies rate limits, mantenimiento banners, and
  WAF challenges from bounded response evidence.
- `_site_health_probe.py::probe_response` applies the parser order and
  `BrowserSession.navigate()` raises `core.errors.SiteHealthError` for non-OK
  outcomes and transport failures.
- `src/cadrumo/application/workflow/_engine.py` catches the typed error before
  generic exceptions and records a `SiteHealthAlert` with the site-unavailable
  abort reason.
- `src/cadrumo/application/diagnostics.py` consumes the same typed error.
- Authenticated remote reads live in `src/cadrumo/adapters/outbound/aeat/sede`;
  workflow injects the narrow `walk_expedientes_tree` and
  `fetch_notifications_query` operations rather than a reader facade.

## Boundary findings

The browser adapter is the correct classification boundary because it observes
navigation status, headers, and HTML before domain parsing. The core error
remains structurally typed so core does not import the adapter model. Sede and
application layers may catch the error, but must not fork the marker taxonomy or
repeat classification.

A raw AEAT `page.goto()` outside a health-aware Sede stage bypasses this
contract. Each live read therefore needs a real-behavior test showing either
`BrowserSession.navigate()` participation or equivalent typed propagation. The
health path is read-only and must never retry or continue a mutating action.

Evidence must remain bounded and secret-free. URLs, HTTP status, marker names,
and retry guidance are useful; cookies, browser storage, certificate bytes,
passphrases, and taxpayer page payloads are not admissible diagnostics.

## Recommendation

Keep one browser-owned site-health taxonomy and one `SiteHealthError` propagation
path. Extend the existing Sede boundary when a new live surface appears; do not
recreate `StatusReader`, self-healing sync, or a second parser family.

## Sources

- `src/cadrumo/adapters/outbound/aeat/browser/_site_health.py`
- `src/cadrumo/adapters/outbound/aeat/browser/_site_health_parsers.py`
- `src/cadrumo/adapters/outbound/aeat/browser/_site_health_probe.py`
- `src/cadrumo/adapters/outbound/aeat/browser/session.py`
- `src/cadrumo/adapters/outbound/aeat/sede`
- `src/cadrumo/application/workflow/_engine.py`
- `src/cadrumo/application/diagnostics.py`
