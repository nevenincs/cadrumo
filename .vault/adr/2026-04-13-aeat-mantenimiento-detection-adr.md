---
tags:
  - "#adr"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-07-17'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-research]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-playwright-anti-bot-adr]]"
---
# aeat-mantenimiento-detection adr: site-health-detection-and-pause-and-alert | (**status:** `accepted`)

## Context

AEAT maintenance pages, WAF challenges, rate limits, and transport failures must
not collapse into parser errors or look like successful authenticated reads.
Every migrated Sede navigation needs one typed health classification that
workflow and diagnostics can handle without depending on a retired status-reader
package.

## Decision

### Browser adapter owns site-health classification

`src/cadrumo/adapters/outbound/aeat/browser/_site_health.py` defines the strict
site-health records and closed state taxonomy.
`_site_health_parsers.py` classifies rate-limit, mantenimiento, and WAF evidence,
and `_site_health_probe.py::probe_response` applies them in deterministic order.
`BrowserSession.navigate()` performs navigation, collects bounded response
evidence, and raises `core.errors.SiteHealthError` for every non-OK result.

The model and parsers live beside the browser transport because all current
consumers are Sede adapter functions, diagnostics, or workflow callables. There
is no `aeat.status` model, `StatusReader`, or status-reader migration target.

### Core error, application handling

`SiteHealthError` lives in `src/cadrumo/core/errors` and carries a structural
site-health payload without importing the adapter layer. Workflow stages catch
that typed error before their generic exception arm, record a strict
`SiteHealthAlert`, and terminate with the site-unavailable abort reason.
Application diagnostics translate the same error into their typed result.

### Live reads use the Sede boundary

Authenticated read paths live in `src/cadrumo/adapters/outbound/aeat/sede` and
consume a typed `AeatSession`. Workflow wiring injects
`walk_expedientes_tree` and `fetch_notifications_query`; other Sede services
call the same browser health boundary. New live reads must use
`BrowserSession.navigate()` or a Sede stage that already performs equivalent
health probing. Direct `page.goto()` is not an accepted bypass for an AEAT
resource.

### Evidence and safety

Site-health evidence is secret-free and bounded. It may contain the target URL,
HTTP status, detected marker names, retry guidance, and a bounded HTML fragment;
it must not capture cookies, browser storage, certificate material, or taxpayer
payloads. Health detection is read-only and never retries a mutating action.

## Consequences

- Mantenimiento, WAF, rate-limit, unreachable, and unknown failures are typed
  and distinguishable from healthy responses.
- Workflow records preserve a site-unavailable explanation instead of an
  unhandled exception.
- Browser and Sede adapters share one health authority; retired status and sync
  packages are not extension points.
- Every newly added AEAT navigation must prove it participates in the health
  boundary and the no-write surface.

## Verification

Real fixture-driven parser tests cover positive variants and healthy negative
controls. Browser, Sede, workflow, and diagnostics tests verify typed propagation,
abort ordering, bounded evidence, and the absence of mutating actions.
