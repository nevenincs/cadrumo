---
tags:
  - "#adr"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-research]]"
  - "[[2026-04-12-status-reader-adr]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-playwright-anti-bot-adr]]"
---

# aeat-mantenimiento-detection adr: site-health-detection-and-pause-and-alert | (**status:** accepted)

## Problem Statement

Today a planned AEAT mantenimiento banner, a WAF challenge page, or an
HTTP 429/503 rate-limit response collapses into an opaque DOM parse error
inside the status reader or the workflow engine, surfacing as
UNHANDLED_EXCEPTION and looking like a regression. The system needs a
typed, testable detection layer that classifies site-health anomalies at
the navigation chokepoint and a workflow contract that halts the run,
persists a structured alert, and allows the next aeat workflow next
invocation to resume cleanly once AEAT recovers.

Research section 1 binds the scope to a handover prompt that overrides
the issue body: the model and parsers must live under aeat.status, a
thin hook sits in aeat.adapters.outbound.aeat.browser, and the workflow engine must learn a
new typed abort arm. Auth (#94) and filing (#93) subpackages are
strictly out of scope.

## Considerations

- **Single navigation chokepoint.** Research section 2 confirms every
  subpackage that hits AEAT (status reader, submission submitters,
  inbox fetcher, sync runner) goes through BrowserSession. A hook at
  that layer reaches all callers without touching four subpackages
  independently.
- **Cross-subpackage error type.** The hook is raised from
  aeat.adapters.outbound.aeat.browser but must be caught by aeat.application.workflow and surfaced by
  aeat.status. Placing the exception inside either subpackage forces
  an import cycle.
- **Closed-enum discipline.** Project convention (research section 3)
  mandates enum.StrEnum for closed catalogues, strict-frozen-forbid
  pydantic v2 models for wire records, and tuple[str, ...] over list
  for collections on frozen models.
- **Parser isolation.** Three parsers (mantenimiento, waf_challenge,
  rate_limited) must be composable and independently unit-testable
  from HTML fixtures with zero Playwright dependency.
- **Fixture ergonomics.** Existing test fixtures live under
  tests/fixtures/aeat-pages/; a parallel tests/fixtures/site_health/
  tree keeps site-health corpora isolated and discoverable.
- **Workflow resume semantics.** The workflow engine already persists
  WorkflowStep records; the pause-and-alert contract reuses the
  existing _AbortError signal with a new reason and attaches a typed
  alert so a resumed run can inspect the previous halt.
- **CLI discoverability.** No aeat browser Typer sub-app exists yet.
  Adding one as a directory-backed package mirrors aeat.entrypoints.cli.status
  and aeat.entrypoints.cli.workflow and leaves room for future browser commands.

## Constraints

- No edits to aeat.adapters.outbound.aeat.auth/** (owned by #94) or aeat.application.filing/** (owned
  by #93).
- The browser session hook must be additive: the existing
  BrowserSession.create_context behaviour and signature are preserved.
- No mocks, patches, fakes, or stubs in tests. Unit tests drive
  parsers from on-disk HTML fixtures; live tests are optional and
  gated on AEAT_LIVE_TESTS_ENABLED=1.
- All new settings must mirror into env/.env.example and pass
  tests/test_config.py.
- All new data records are pydantic v2 with
  ConfigDict(strict=True, frozen=True, extra="forbid").
- No logging of secrets; HTML fragments are bounded to 4096 chars to
  keep error logs sane.

## Implementation

### Decision 1 - Module placement

The detection model, evidence submodel, state enum, and the three
parsers land inside the status subpackage, not the browser subpackage:

- aeat.status._site_health owns SiteHealthState (StrEnum),
  SiteHealthEvidence, SiteHealthStatus, and SiteHealthAlert.
- aeat.status._site_health_parsers owns parse_mantenimiento_banner,
  parse_waf_challenge, parse_rate_limit_response, each returning
  SiteHealthStatus | None.
- Public re-exports from aeat.status.__init__ expose SiteHealthState,
  SiteHealthStatus, SiteHealthEvidence, SiteHealthAlert, and the
  three parser callables.

Rationale: the handover prompt is authoritative (research section 1);
the status subpackage is already the home of AEAT wire records and
the reader that first discovered the mantenimiento blind spot.
Placing the detection logic in aeat.adapters.outbound.aeat.browser would mix transport
concerns with domain classification and force every marker refresh
into the browser layer.

### Decision 2 - Error hoist to aeat.core.errors

SiteHealthError is hoisted to aeat.core.errors as a direct subclass of
AeatError, alongside existing domain error bases:

- aeat.core.errors.SiteHealthError(AeatError) carries a strict
  status: SiteHealthStatus attribute (pydantic instance).
- aeat.adapters.outbound.aeat.browser.session imports the error from aeat.core.errors only.
- aeat.application.workflow._engine and aeat.status import from aeat.core.errors.

Rationale: research section 4 identifies the circular-import trap if
the error lives in either subpackage. aeat.core.errors already hosts
AeatError and FilingFixtureError; it is the designated neutral ground
and both leaf subpackages already depend on it.

### Decision 3 - Browser session navigation hook

aeat.adapters.outbound.aeat.browser.session gains a health-probe helper invoked after every
successful page.goto:

- A new module-level helper under aeat.adapters.outbound.aeat.browser._site_health_probe
  takes (url, http_status, headers, html) and runs the three parsers
  in a deterministic order: parse_rate_limit_response (cheapest,
  header-only short-circuit), then parse_mantenimiento_banner, then
  parse_waf_challenge.
- The helper returns the first non-None SiteHealthStatus whose state
  is not SiteHealthState.OK; if all parsers pass, it returns None and
  the caller proceeds.
- A non-None, non-OK result is raised as SiteHealthError(status=...)
  from the caller.
- BrowserSession exposes a new navigate(page, url) helper wrapping
  page.goto + probe + raise. Direct page.goto calls remain legal but
  bypass the hook; subpackages that already funnel through a single
  internal fetch method adopt navigate in their implementation
  modules. Call-site migration of StatusReader._fetch_html and the
  modelo130 submitter is an implementation-plan task.

Rationale: research section 2.3 shows four subpackages share a single
navigation layer via BrowserSession. A typed helper is more explicit
than a transparent Page proxy and leaves the existing create_context
contract untouched (additive hook).

### Decision 4 - Workflow pause-and-alert

aeat.application.workflow._engine.WorkflowEngine learns a dedicated catch arm:

- aeat.application.workflow._models.WorkflowAbortReason gains SITE_UNAVAILABLE.
  Name chosen over AEAT_SERVICE_DOWN because it is neutral across
  all five non-OK states (research section 9).
- WorkflowStep gains an optional
  site_health_alert: SiteHealthAlert | None = None field (typed
  sibling of the existing details: dict[str, str] escape hatch).
- Each stage method that currently wraps component calls with
  _record_unhandled grows a prior except SiteHealthError as exc arm
  that calls a new _record_site_unavailable(stage, started, exc,
  steps) helper. The helper appends a failed step carrying
  exc.status as the site_health_alert, then raises
  _AbortError(reason=WorkflowAbortReason.SITE_UNAVAILABLE, ...).
- The new arm is inserted strictly BEFORE the generic
  except Exception handler in each stage, so a SiteHealthError never
  collapses into UNHANDLED_EXCEPTION.
- The existing resume contract is preserved: the next
  aeat workflow next invocation starts a fresh run. No run-level
  persistence schema changes are introduced here.

Rationale: research section 4.1 identifies the precise location of
the collapsing-to-UNHANDLED_EXCEPTION bug. A typed earlier arm
prevents the collapse without perturbing the generic safety net.

### Decision 5 - CLI sub-app

A new aeat.entrypoints.cli.browser directory-backed sub-app exposes
aeat browser health [--json]:

- src/aeat/entrypoints/cli/browser/__init__.py defines app = typer.Typer(...).
- src/aeat/entrypoints/cli/__init__.py wires it with
  app.add_typer(browser_module.app, name="browser", ...).
- The health command opens a BrowserSession, calls navigate against
  settings.site_health_probe_url, and prints a human summary by
  default or SiteHealthStatus.model_dump(mode="json") with --json.
- Exit-code table (ADR-locked):
  - 0 -> SiteHealthState.OK
  - 2 -> SiteHealthState.MANTENIMIENTO
  - 3 -> SiteHealthState.WAF_CHALLENGE
  - 4 -> SiteHealthState.RATE_LIMITED
  - 5 -> SiteHealthState.UNREACHABLE
  - 6 -> SiteHealthState.UNKNOWN_ERROR
- Exit code 1 is reserved for Typer usage errors (unchanged).

### Decision 6 - Settings additions

aeat.core.config.Settings gains two fields:

- site_health_probe_url: str (validated via AnyHttpUrl adapter) with
  default https://sede.agenciatributaria.gob.es/.
- site_health_rate_limit_retry_after_default: int = 300 with ge=1,
  used when a 429/503 response lacks a Retry-After header.

Both mirror into env/.env.example with documenting comments and are
covered by the alignment assertions in tests/test_config.py.

### Decision 7 - Pydantic conventions

All new records follow project conventions (research section 3):

- ConfigDict(strict=True, frozen=True, extra="forbid") via a private
  _SiteHealthRecord base mirroring _StatusRecord.
- SiteHealthState(StrEnum) with values ok, mantenimiento,
  waf_challenge, rate_limited, unreachable, unknown_error.
- SiteHealthEvidence.url: AnyHttpUrl validated via a module-level
  TypeAdapter(AnyHttpUrl) for parser call sites.
- SiteHealthEvidence.http_status: int with ge=100, le=599.
- SiteHealthEvidence.html_fragment: str with max_length=4096.
- SiteHealthEvidence.detected_markers: tuple[str, ...] - frozen
  tuple, each marker bounded by min_length=1, max_length=128.
- SiteHealthStatus composes state + evidence +
  observed_at: AwareDatetime + optional retry_after_seconds: int|None.
- SiteHealthAlert wraps SiteHealthStatus with workflow-side metadata
  (stage: WorkflowStage, correlating run identifiers as required by
  the workflow engine).

### Decision 8 - Fixture layout and test placement

Fixtures under tests/fixtures/site_health/:

- mantenimiento/*.html - 5+ positive variants (interstitial, novedades
  announcement, sede banner, title-only, disculpe-only).
- waf_challenge/*.html - 5+ positive variants covering Request
  blocked, Reference ID, generic WAF body, bare 403 with Support ID,
  and a near-empty blocked body.
- rate_limited/*.html - 5+ variants split across 429 and 503 with
  and without Retry-After.
- ok/*.html - 5+ healthy AEAT-shaped pages as negative controls
  ensuring no parser over-triggers.
- A README.md documents each fixture provenance (synthesised vs.
  scrubbed) and the marker it asserts, per the scrub procedure in
  tests/fixtures/aeat-pages/README.md.

Unit tests are colocated Rust-style:

- src/aeat/status/test_site_health.py - covers model validation and
  the SiteHealthAlert shape.
- A sibling test module for the parsers drives one parametrised case
  per fixture file, each marked @pytest.mark.unit, with at least one
  negative assertion per state using the ok/*.html corpus.
- A single optional live test, @pytest.mark.live gated on
  AEAT_LIVE_TESTS_ENABLED=1, opens BrowserSession.navigate against
  the probe URL and asserts a SiteHealthStatus instance is returned
  (state may legitimately be OK).

No mocks, patches, shadows, fakes, or stubs anywhere; parser tests
drive plain strings from disk.

### Decision 9 - Out-of-scope guards

- Zero edits to src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/**. The browser session hook must not
  import from aeat.adapters.outbound.aeat.auth.
- Zero edits to src/aeat/application/filing/**. The workflow engine catch arm is
  narrowed to SiteHealthError and does not alter filing-side abort
  semantics.
- The browser session hook is strictly additive: the existing
  create_context signature, return type, and exception contract are
  preserved.

## Rationale

The central architectural choice is where the typed detection
boundary lives. Two alternatives were weighed:

- Alternative A - keep detection inside aeat.adapters.outbound.aeat.browser. The issue body
  originally proposed aeat.adapters.outbound.aeat.browser.aeat_service_health plus an
  AeatServiceState. This co-locates the hook and the model, but
  (a) it mixes transport concerns with AEAT-specific domain
  classification, (b) every marker refresh requires a browser-layer
  change, and (c) it contradicts the handover prompt, which is the
  authoritative scope per research section 1.
- Alternative B - detection in aeat.status, thin hook in aeat.adapters.outbound.aeat.browser,
  neutral error in aeat.core.errors. Chosen. It keeps aeat.adapters.outbound.aeat.browser
  responsible only for raising a pre-defined typed error, lets
  aeat.status own the marker corpus and parser suite next to the rest
  of the AEAT wire records, and resolves the circular-import hazard
  identified in research section 4 by hoisting the error to
  aeat.core.errors.

The workflow-engine pause-and-alert shape reuses the existing
_AbortError / WorkflowStep / WorkflowAbortReason machinery documented
in research section 4.1, preferring a typed sibling field
(site_health_alert) over the sanctioned dict[str, str] escape hatch
so callers can rehydrate a strict pydantic record on resume.

The CLI exit-code table is locked in the ADR so operators and future
shell-level automations can depend on stable codes across releases
(research section 7).

The fixture layout mirrors the existing aeat-pages/ convention
(research section 6) while keeping the site-health corpus isolated
so parser regressions are easy to bisect.

## Consequences

- Positive. Mantenimiento / WAF / rate-limit states become first-class,
  typed, and user-visible instead of collapsing into
  UNHANDLED_EXCEPTION. The workflow engine halts cleanly and preserves
  enough evidence for a resumed run to explain the prior halt. A new
  aeat browser health command gives operators a single-shot probe
  independent of the full workflow.
- Call-site migration debt. The hook only runs at call sites that
  adopt BrowserSession.navigate. Initial adopters are
  StatusReader._fetch_html and the modelo130 submitter; the
  submission / inbox / sync migrations are listed explicitly in the
  implementation plan. Call sites that keep raw page.goto will not
  benefit from the hook until they migrate.
- Fixture maintenance. The marker corpus in the parsers is a living
  list. When AEAT changes its banner wording, the positive fixture
  set must be extended. The README.md provenance log makes this
  auditable.
- Enum growth. WorkflowAbortReason gains one value. Downstream
  consumers that exhaustively switch on the enum (none today) would
  need an update.
- No persistence schema change. WorkflowStep.site_health_alert is a
  new optional field; existing persisted runs (if any) stay
  deserialisable because extra="forbid" only rejects unknown keys,
  not missing optional ones. A follow-up ADR may formalise run-level
  persistence once aeat workflow next grows a durable journal.
- Rollback. If a parser over-triggers in production, the rollback is
  (a) flip site_health_probe_url to an unused value to neutralise the
  CLI, and (b) revert the per-call-site navigate adoption while
  leaving the model, parsers, error hoist, and workflow arm in place
  - the hook is dormant unless a call site opts in. Full revert is a
  single-commit revert of the feature branch.
- Traceability. This ADR traces to research sections 1 (scope
  binding), 2.3 (navigation chokepoint), 3 (pydantic conventions),
  4 and 4.1 (error hierarchy and workflow catch arm), 5 (marker
  corpus), 6 (fixture layout), 7 (CLI wiring), 8 (settings), and 9
  (open questions, all resolved above).
