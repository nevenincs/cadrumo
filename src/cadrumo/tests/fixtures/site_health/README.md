# site_health fixture corpus

Synthetic HTML fixtures for the `aeat.browser._site_health_parsers`
parser suite. Every file under this tree is hand-authored to mirror
the real AEAT Sede Electrónica response shapes — no fixture is a
verbatim copy of a production response; see
`src/aeat/tests/fixtures/aeat-pages/README.md` for the project-wide
scrub procedure this corpus follows.

## Layout

- `mantenimiento/*.html` — positive banner / interstitial fixtures
  that must classify as `SiteHealthState.MANTENIMIENTO`.
- `waf_challenge/*.html` — WAF block / challenge fixtures that must
  classify as `SiteHealthState.WAF_CHALLENGE`.
- `rate_limited/*.html` — HTTP 429 / 503 rate-limit response bodies
  that must classify as `SiteHealthState.RATE_LIMITED`. Each file is
  accompanied by a sibling `.headers.json` describing the status code
  and headers a real response would carry.
- `ok/*.html` — healthy AEAT-shaped pages used as negative controls;
  `evaluate_response` must return `None` on every file here.

## Per-fixture provenance and asserted markers

### mantenimiento/

- `interstitial.html` — full-page mantenimiento interstitial.
  Asserts: `mantenimiento`, `disculpe las molestias`.
- `novedades_announcement.html` — *Novedades* announcement carrying
  a scheduled maintenance window.
  Asserts: `horario de interrupciones`, `mantenimiento`.
- `sede_banner.html` — Sede landing page with a highlighted banner.
  Asserts: `mantenimiento`, `interrupcion del servicio`.
- `title_only.html` — body short on markers but title contains
  ``mantenimiento``.
  Asserts: `mantenimiento` (body hit) + `title:mantenimiento`.
- `disculpe_only.html` — marker pair of `mantenimiento` and
  `disculpe las molestias`.
  Asserts: both markers present.

### waf_challenge/

- `request_blocked.html` — classic 403 with "Request blocked" and
  "Reference ID".
- `reference_id.html` — generic WAF body carrying a "Reference ID"
  correlation token alongside "request blocked".
- `generic_waf.html` — "Web Application Firewall" marker plus
  "waf" string under a 403.
- `bare_403_support_id.html` — minimal 403 body with "Support ID".
- `blocked_minimal.html` — body with `request blocked` and
  `support id` on a non-403 status (classifies via the correlation
  branch).

### rate_limited/

- `429_retry_after.html` + `.headers.json` — 429 with
  `Retry-After: 120`.
- `429_no_header.html` + `.headers.json` — 429 without
  `Retry-After`; parser falls back to the injected default.
- `503_retry_after.html` + `.headers.json` — 503 rate limit without
  mantenimiento markers, with `Retry-After: 60`.
- `503_no_header.html` + `.headers.json` — 503 rate limit without
  `Retry-After` and without mantenimiento markers.
- `503_not_mantenimiento.html` + `.headers.json` — generic 503 body
  explicitly distinct from a mantenimiento banner.

### ok/

Five healthy AEAT-shaped pages (Sede landing page, expedientes list,
notifications list, calendario list, and a generic helper page)
used as negative controls: no parser must over-trigger on them.
