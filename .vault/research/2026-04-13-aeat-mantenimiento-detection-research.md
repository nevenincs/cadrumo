---
tags:
  - "#research"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
title: "AEAT Mantenimiento / WAF / Rate-Limit Detection Research"
related:
  - "[[2026-04-12-status-reader-adr]]"
  - "[[2026-04-12-playwright-anti-bot-adr]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-12-notifications-inbox-adr]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
---

# aeat-mantenimiento-detection research

Research phase for issue wgergely/aeat#95. Authoritative scope comes from
the handover prompt, which supersedes the issue body.

## 1. scope binding

Handover scope (authoritative), summarised for downstream ADR/plan:

- aeat.status._site_health.SiteHealthStatus: strict pydantic v2 model.
- aeat.status._site_health.SiteHealthState: enum.StrEnum values are
  ok, mantenimiento, waf_challenge, rate_limited, unreachable,
  unknown_error.
- aeat.status._site_health.SiteHealthEvidence: strict pydantic submodel
  carrying (url, http_status, html_fragment, detected_markers).
- Parsers colocated in aeat.status._site_health_parsers:
  parse_mantenimiento_banner, parse_waf_challenge,
  parse_rate_limit_response.
- Browser session hook that raises SiteHealthError(AeatError) on non-OK.
- Workflow engine: pause-and-alert on SiteHealthError, persisted as
  SiteHealthAlert on the run record.
- CLI: aeat browser health [--json] (new sub-app).
- Settings: site_health_probe_url and
  site_health_rate_limit_retry_after_default.
- Fixtures under tests/fixtures/site_health/*.html, 5+ per parser.
- Out of scope: aeat.adapters.outbound.aeat.auth (#94), aeat.application.filing (#93), Track B.

Important deviation from the issue body: #95 originally proposed
src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/aeat_service_health.py plus AeatServiceState. The
handover prompt moves the model and parsers to aeat.status and adds a
thin browser session hook. This research doc follows the handover.

## 2. current aeat site-health handling

### 2.1 grep summary

A case-insensitive ripgrep for mantenimiento, maintenance, waf and
rate-limit across src/aeat/ returns only unrelated hits in
env/.env.example, the LLM client rate-limit helpers, and the proxy
fields in src/aeat/config.py. There is zero existing AEAT-side
service-health logic. The issue Evidence section is accurate: a
mantenimiento page today becomes a parse error during DOM parsing,
looking like a regression rather than a typed AEAT-is-down signal.

### 2.2 existing health surfaces

- src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/health.py exposes run_health_check, a Playwright
  smoke test that navigates to https://example.com to verify the
  evasion patches load. It does not touch AEAT. Not a site-health
  probe; only a browser-install sanity check. No CLI wiring yet.
- src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/evasion.py carries the stealth JS; unrelated but
  shares the same subpackage.

### 2.3 navigation entry points that must grow a probe

Every call site that already calls page.goto against an AEAT URL is
a candidate injection point. Found surfaces:

- src/aeat/status/_reader.py::_fetch_html - single page.goto inside
  StatusReader. Currently raises StatusAuthError on response.status
  >= 400. Primary injection point because it funnels every fetch_*
  surface through one method.
- src/aeat/adapters/outbound/aeat/export/_engine.py delegates navigation to the per-modelo
  submitters in src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py, which
  use a BrowserSessionLike passed in from the engine.
- src/aeat/inbox/_fetcher.py is a composition layer; navigation sits
  behind the NotificacionSource Protocol stub (#43 plumbing).
- src/aeat/application/sync/_runner.py abstracts navigation behind a
  LivePayloadFetcher Protocol, documented as driven by a Playwright
  session in production.

Architectural conclusion: the cleanest chokepoint is
BrowserSession.create_context, or a wrapper around Page.goto on the
session side. Every subpackage already consumes
aeat.adapters.outbound.aeat.browser.BrowserSession, so a session-level hook can raise
SiteHealthError once and every caller inherits the pause-and-alert
contract without editing four subpackages independently.

The _stage_syncing_catalogues, _stage_checking_inbox,
_stage_building_draft, _stage_running_preflight and
_stage_dry_run_submit stages in src/aeat/application/workflow/_engine.py all run
their component calls inside try/except Exception blocks that call
self._record_unhandled(...). That means a new typed SiteHealthError
currently collapses into WorkflowAbortReason.UNHANDLED_EXCEPTION. The
plan must add a dedicated catch arm (see section 5).

## 3. pydantic model conventions to mirror

From src/aeat/status/_models.py and src/aeat/application/workflow/_models.py:

- Shared config: ConfigDict(strict=True, frozen=True, extra=forbid).
  aeat.status defines a private _StatusRecord base with this config -
  SiteHealthStatus and SiteHealthEvidence should subclass it or define
  the same config for consistency.
- Closed catalogues are enum.StrEnum subclasses (AeatStatusKind,
  PayorKind, WorkflowStage, WorkflowAbortReason). SiteHealthState
  fits this pattern exactly.
- URLs use pydantic.AnyHttpUrl with a module-level
  TypeAdapter(AnyHttpUrl) when validating strings (_URL_ADAPTER in
  _reader.py).
- Timestamps use AwareDatetime for frozen records, or datetime with
  explicit UTC in engine code (_utcnow in workflow/_engine.py).
- Trilingual free text uses aeat.core.i18n.Translatable. Evidence is raw
  HTML, so html_fragment is plain str (not Translatable).
- Field(min_length, max_length) guards for all string fields;
  html_fragment should be bounded (e.g. max_length=4096) to avoid
  oversize error logs. detected_markers should be a frozen
  tuple[str, ...] to match the rest of the module - the Expediente
  style uses tuple over list.

## 4. error hierarchy and aeat error flow

src/aeat/errors.py defines only AeatError plus fixture errors. Each
subpackage layers its own base:

- aeat.adapters.outbound.aeat.browser.BrowserError(AeatError) in browser/session.py.
- aeat.status._errors: StatusReaderError(AeatError) then
  StatusAuthError, StatusParseError, StatusNotFoundError.
- aeat.application.workflow._errors.WorkflowComponentError wraps unhandled
  component exceptions.

For #95 the cleanest placement, given the handover keeps the model in
aeat.status, is either:

- aeat.status._errors.SiteHealthError(StatusReaderError), or
- aeat.status._errors.SiteHealthError(AeatError) standalone, re-exported
  from aeat.status.

Standalone is preferred because the browser session hook (in
aeat.adapters.outbound.aeat.browser) must raise the error before any StatusReader call
completes, and aeat.adapters.outbound.aeat.browser must not import from aeat.status. Decision
to be locked in the ADR: hoist SiteHealthError to aeat.core.errors (next to
AeatError) so both aeat.adapters.outbound.aeat.browser and aeat.status can raise it without a
circular import. The pydantic SiteHealthStatus model stays in
aeat.status.

### 4.1 workflow engine catch-arm

WorkflowEngine._drive only catches _AbortError; every stage wraps
component calls with _record_unhandled, which re-raises as
UNHANDLED_EXCEPTION. Plan must:

- Add WorkflowAbortReason.SITE_UNAVAILABLE (or AEAT_DOWN) to the
  closed enum in aeat.application.workflow._models.
- In each stage that calls a Protocol that can raise, special-case
  SiteHealthError before the generic Exception handler, record a
  WorkflowStep carrying the SiteHealthAlert, and raise _AbortError
  with the new reason.
- Extend WorkflowResult (or WorkflowStep.details) with a typed
  site_health_alert: SiteHealthAlert | None field. The details
  dict[str, str] field is documented as the single sanctioned
  dict[str, str] escape hatch - adding a typed optional sibling is
  the right move.

## 5. public aeat marker strings

The live AEAT site was not hit. The following comes from public AEAT
announcement pages and general knowledge of Spanish government
maintenance banners.

### 5.1 mantenimiento (planned downtime)

Canonical AEAT language observed on public novedades pages:

- Interrupcion del servicio en la Sede electronica por operaciones de
  mantenimiento
- Estamos realizando tareas de mantenimiento - the runtime
  interstitial; also appears as Estamos en mantenimiento
- Sede electronica no disponible
- Horario de interrupciones de la sede electronica - appears on the
  sede own status page linked from error pages
- Spanish-specific: Disculpe las molestias - near-universal trailing
  line on Spanish government maintenance pages

Stable DOM anchors (to be confirmed when capturing fixtures):

- title element containing Mantenimiento or Interrupcion
- A top-level div (often class aviso, mensaje-error, or interrupcion)
  carrying the banner text
- Public novedades pages linking to
  /Sede/ayuda/horario-interrupciones-sede-electronica.html

Parser contract: case-insensitive substring match on a curated list of
at least three of the above markers, plus the title heuristic. Any two
hits map to SiteHealthState.mantenimiento.

### 5.2 waf challenge

AEAT infrastructure sits behind a government-operated WAF. Observable
generic markers across WAF products that are signal-rich and
low-false-positive:

- Response body containing Request blocked, Your request was blocked,
  or has been blocked
- Web Application Firewall or WAF in the body or headers
- Reference ID, Support ID, or Request ID alone in a near-empty body
  (classic WAF block signature)
- HTTP status 403 with Content-Length under ~4 KB and no expected
  AEAT navigation DOM
- Generic CAPTCHA markers: g-recaptcha, hcaptcha, cf-challenge
  (unlikely on AEAT but cheap to check)

Parser contract: (status == 403 AND body contains one of the marker
set) OR (body contains Request blocked AND one of Reference ID or
Support ID) maps to SiteHealthState.waf_challenge.

### 5.3 rate limited (429 / 503)

HTTP-level signal. Playwright Response exposes status and headers:

- status == 429 maps unconditionally to rate_limited
- status == 503 AND body lacks the AEAT navigation chrome maps to
  rate_limited candidate; if body also matches a mantenimiento marker,
  classify as mantenimiento (mantenimiento wins over rate-limited)
- Retry-After header is carried verbatim into
  SiteHealthEvidence.detected_markers as retry-after:<value>. Fall
  back to settings.site_health_rate_limit_retry_after_default when
  the header is absent.

### 5.4 unreachable / unknown_error

- DNS, TCP, TLS errors raised by page.goto map to
  SiteHealthState.unreachable.
- status >= 500 without rate-limit or mantenimiento markers maps to
  unknown_error with the full HTML fragment captured.

## 6. tests/fixtures/ organisation

Current layout (see tests/fixtures/aeat-pages/README.md):

- tests/fixtures/aeat-pages/<surface>/<name>.html - e.g.
  aeat-pages/expedientes/sample.html and sample_spanish.html
- tests/fixtures/filing_history/<modelo>/<period>.json
- tests/fixtures/justificantes/*.pdf plus a _generate.py helper

The README documents the PII-scrubbing procedure: strip scripts, styles
and meta; replace tax IDs with a placeholder; scrub URL query tokens.
Parser tests colocate under src/aeat/status/_parsers/ and assert that
a fixture round-trips through the parser plus pydantic model.

Decision for #95: create tests/fixtures/site_health/ (NOT
aeat-pages/maintenance/ as the issue body suggested - the handover
overrides this) with one subdirectory per parser:

- tests/fixtures/site_health/mantenimiento/*.html - 5+ variants
- tests/fixtures/site_health/waf_challenge/*.html - 5+ variants
- tests/fixtures/site_health/rate_limited/*.html - 5+ variants
  (including both 429 and 503)
- tests/fixtures/site_health/ok/*.html - 5+ healthy AEAT pages as
  negative controls

Since no live capture is allowed at research time, the execution phase
will hand-synthesise fixtures using the section 5 markers and the
PII-scrubbing procedure in aeat-pages/README.md. A sibling README.md
inside site_health/ should document each fixture provenance
(synthesised vs. scrubbed live capture) and the marker it asserts.

## 7. cli wiring for aeat browser sub-app

There is no existing aeat browser Typer sub-app - browser is currently
only a Python subpackage. src/aeat/entrypoints/cli/__init__.py wires sub-apps with
the pattern:

- from aeat.entrypoints.cli import casillas as casillas_module
- app.add_typer(casillas_module.app, name=casillas, help=...)

Each sub-app is a module that exports app = typer.Typer(name=..., ...).
Canonical reference is src/aeat/entrypoints/cli/casillas.py (flat-file sub-app,
mirrors aeat.domain.casillas package). For a directory-backed sub-app see
src/aeat/entrypoints/cli/status/__init__.py, src/aeat/entrypoints/cli/submission/__init__.py
and src/aeat/entrypoints/cli/workflow/__init__.py.

Plan: add src/aeat/entrypoints/cli/browser/__init__.py (directory-backed, so
health can live in its own file and a future profile, trace, etc. can
join without churn). Wire in cli/__init__.py:

- from aeat.entrypoints.cli import browser as browser_module
- app.add_typer(browser_module.app, name=browser, help=Playwright
  browser session health probes)

aeat browser health [--json] runs the probe against
settings.site_health_probe_url, prints human text by default, emits
SiteHealthStatus.model_dump(mode=json) with --json, and uses stable
exit codes per state: 0 ok; 2 mantenimiento; 3 waf_challenge;
4 rate_limited; 5 unreachable; 6 unknown_error. Exit-code table must
be ADR-locked.

## 8. settings surface additions

src/aeat/config.py already exposes aeat_base_url (line 110),
aeat_browser_channel (215) and aeat_proxy_* (227-239). Pattern:
lowercase fields map to uppercased env vars, with a .env.example
mirror enforced by tests/test_config.py.

New fields for #95:

- site_health_probe_url: str - default
  https://sede.agenciatributaria.gob.es/
- site_health_rate_limit_retry_after_default: int - default 300, ge=1

Both must land in .env.example with doc strings.

## 9. open questions for the adr phase

- Error placement: hoist SiteHealthError to aeat.core.errors
  (cross-subpackage) vs. duplicate in aeat.adapters.outbound.aeat.browser plus aeat.status.
  Recommended: hoist (see section 4).
- Browser session hook: wrap BrowserSession.create_context to return
  a custom HealthAwarePage proxy, or add an explicit
  navigate_with_health(page, url) helper. Proxy is invisible to
  callers but harder to reason about; explicit helper is idiomatic
  but requires touching every call site. Recommended: explicit helper
  invoked inside _fetch_html and each submitter, because
  status/submission/inbox/sync already go through a single internal
  navigation method.
- Workflow abort reason name: SITE_UNAVAILABLE (neutral) vs.
  AEAT_SERVICE_DOWN. Recommended: SITE_UNAVAILABLE - mirrors the
  SiteHealthState prefix and stays agnostic across the five non-OK
  states.
- CLI exit code table: lock in the ADR.
- Fixture provenance policy: whether synthesised-only fixtures are
  acceptable for v1 or a single real scrubbed capture must be
  attached. The live-test mandate (no mocks) does not apply to unit
  tests; the existing aeat-pages/expedientes/sample*.html fixtures
  are already synthesised/scrubbed.

## 10. sources

- Interrupcion del servicio en la Sede electronica por operaciones de
  mantenimiento (AEAT novedades 2018-12):
  https://www.agenciatributaria.es/AEAT.internet/Inicio/Novedades/2018/Diciembre/Interrupcion_del_servicio_en_la_Sede_electronica_por_operaciones_de_mantenimiento.shtml
- Horario de interrupciones de la sede electronica:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/horario-interrupciones-sede-electronica.html
- Interrupcion del servicio el domingo 27 de octubre 2024:
  https://sede.agenciatributaria.gob.es/Sede/todas-noticias/2024/octubre/22/interrupcion-servicio-domingo-27-octubre.html
- Interrupcion del Servicio de la Sede Electronica (agosto 2017):
  https://www.agenciatributaria.es/AEAT.internet/Inicio/Novedades/2017/Agosto/Interrupcion_del_Servicio_de_la_Sede_Electronica.shtml
