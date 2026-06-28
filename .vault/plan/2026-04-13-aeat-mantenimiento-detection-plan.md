---
tags:
  - "#plan"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-adr]]"
  - "[[2026-04-13-aeat-mantenimiento-detection-research]]"
---

# aeat-mantenimiento-detection implementation plan

Phased, ordered, testable plan to deliver the site-health detection,
pause-and-alert workflow contract, and `aeat browser health` CLI as
specified in the ADR. Every step is self-contained and verifiable; the
executor follows them verbatim. No edits outside the modules listed.

## Proposed Changes

Implement a typed AEAT site-health detection layer inside `aeat.status`,
hoist a neutral `SiteHealthError` into `aeat.core.errors`, wire a thin
navigation-time probe into `aeat.adapters.outbound.aeat.browser.session`, add a dedicated
`except SiteHealthError` arm in `aeat.application.workflow._engine` before the
generic exception catch, expose `aeat browser health` via a new
directory-backed CLI sub-app, extend `aeat.core.config.Settings` with two
fields, and land a fixture corpus under `tests/fixtures/site_health/`.

All new records are strict-frozen-forbid pydantic v2 models; the closed
state catalogue is an `enum.StrEnum`. No edits to `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/**`,
`src/aeat/application/filing/**`, or `src/aeat/domain/financial/**`. No live tests without
`AEAT_LIVE_TESTS_ENABLED=1`. No mocks, patches, fakes, or stubs.

## Tasks

### Phase 1 - Errors and models

- Step 1.1 - Hoist `SiteHealthError`
  - Files: `src/aeat/errors.py`
  - Add `class SiteHealthError(AeatError)` carrying a
    `status: "SiteHealthStatus"` attribute under a
    `TYPE_CHECKING` guard to avoid a circular import. The constructor
    accepts a required keyword-only `status` argument and stores it as
    a public attribute; the string message mirrors
    `status.state.value`.
  - Acceptance: `python -c "from aeat.core.errors import SiteHealthError"`
    succeeds; `SiteHealthError` is a direct subclass of `AeatError`.
  - Gate: Phase 8 `just lint && just typecheck`.

- Step 1.2 - Create `_site_health` module with models
  - Files: `src/aeat/status/_site_health.py` (new)
  - Contents:
    - `class SiteHealthState(StrEnum)` with members `OK = "ok"`,
      `MANTENIMIENTO = "mantenimiento"`,
      `WAF_CHALLENGE = "waf_challenge"`,
      `RATE_LIMITED = "rate_limited"`,
      `UNREACHABLE = "unreachable"`,
      `UNKNOWN_ERROR = "unknown_error"`.
    - Private `_SiteHealthRecord(BaseModel)` base with
      `ConfigDict(strict=True, frozen=True, extra="forbid")`.
    - `SiteHealthEvidence(_SiteHealthRecord)` fields: `url: AnyHttpUrl`,
      `http_status: int = Field(ge=100, le=599)`,
      `html_fragment: str = Field(max_length=4096)`,
      `detected_markers: tuple[str, ...]` with each item bounded by
      `min_length=1, max_length=128` (validator).
    - `SiteHealthStatus(_SiteHealthRecord)` fields:
      `state: SiteHealthState`,
      `evidence: SiteHealthEvidence`,
      `observed_at: AwareDatetime`,
      `retry_after_seconds: int | None = Field(default=None, ge=1)`.
    - `SiteHealthAlert(_SiteHealthRecord)` fields:
      `stage: WorkflowStage` (imported from `aeat.application.workflow`),
      `status: SiteHealthStatus`,
      `run_id: str = Field(min_length=1, max_length=128)`.
    - Module-level `_URL_ADAPTER = TypeAdapter(AnyHttpUrl)` for parser
      call sites.
  - Acceptance: Each model instantiates from a valid kwargs dict and
    rejects an unknown key with `ValidationError`.
  - Gate: Phase 3 unit tests; Phase 8 typecheck.

- Step 1.3 - Re-export from `aeat.status`
  - Files: `src/aeat/status/__init__.py`
  - Add `SiteHealthState`, `SiteHealthStatus`, `SiteHealthEvidence`,
    `SiteHealthAlert` plus the three parser callables (landed in
    Phase 2) to `__all__` and re-export them.
  - Acceptance:
    `python -c "from aeat.status import SiteHealthState, SiteHealthStatus, SiteHealthEvidence, SiteHealthAlert"`
    succeeds.
  - Gate: Phase 8 `just lint`.

### Phase 2 - Parsers and fixtures

- Step 2.1 - Create `_site_health_parsers` module
  - Files: `src/aeat/status/_site_health_parsers.py` (new)
  - Contents:
    - `parse_rate_limit_response(url, http_status, headers, html) -> SiteHealthStatus | None`
      short-circuits on `http_status in {429, 503}`; extracts
      `Retry-After` from `headers` (case-insensitive); encodes it as
      `retry-after:<value>` in `detected_markers`; sets
      `retry_after_seconds` from the header or
      `settings.site_health_rate_limit_retry_after_default`. If
      `http_status == 503` and the body also matches any mantenimiento
      marker, returns `None` so the mantenimiento parser wins.
    - `parse_mantenimiento_banner(url, http_status, headers, html) -> SiteHealthStatus | None`
      runs a case-insensitive substring scan over a curated marker
      tuple (`"mantenimiento"`, `"interrupcion del servicio"`,
      `"estamos realizando tareas de mantenimiento"`,
      `"sede electronica no disponible"`, `"disculpe las molestias"`,
      `"horario de interrupciones"`). Two or more hits, OR a `<title>`
      match containing `mantenimiento`/`interrupcion`, classifies as
      `MANTENIMIENTO`.
    - `parse_waf_challenge(url, http_status, headers, html) -> SiteHealthStatus | None`
      triggers on (`http_status == 403` AND any of `"request blocked"`,
      `"your request was blocked"`, `"web application firewall"`,
      `"waf"`, `"reference id"`, `"support id"`) OR (body contains
      `"request blocked"` AND one of `"reference id"`/`"support id"`).
    - `evaluate_response(url, http_status, headers, html) -> SiteHealthStatus | None`
      runs, in order: rate-limit, mantenimiento, waf_challenge. Returns
      the first non-None non-OK status; `None` means healthy.
  - Each parser builds a `SiteHealthStatus` with bounded
    `html_fragment` (first 4096 chars), `observed_at=_utcnow()`, and a
    frozen `detected_markers` tuple recording the exact matched
    substrings.
  - The module takes a required keyword `rate_limit_retry_after_default: int`
    injected by the browser session hook (Phase 4); it does not import
    `aeat.core.config` directly.
  - Acceptance: `evaluate_response` returns a pydantic
    `SiteHealthStatus` on any fixture under
    `tests/fixtures/site_health/{mantenimiento,waf_challenge,rate_limited}/`
    and `None` on every `ok/` fixture (enforced in Phase 3).
  - Gate: Phase 3 unit tests.

- Step 2.2 - Build the fixture corpus
  - Files:
    - `tests/fixtures/site_health/README.md` (new)
    - `tests/fixtures/site_health/mantenimiento/*.html` (5+ files:
      `interstitial.html`, `novedades_announcement.html`,
      `sede_banner.html`, `title_only.html`, `disculpe_only.html`)
    - `tests/fixtures/site_health/waf_challenge/*.html` (5+ files:
      `request_blocked.html`, `reference_id.html`, `generic_waf.html`,
      `bare_403_support_id.html`, `blocked_minimal.html`)
    - `tests/fixtures/site_health/rate_limited/*.html` (5+ files:
      `429_retry_after.html`, `429_no_header.html`,
      `503_retry_after.html`, `503_no_header.html`,
      `503_not_mantenimiento.html`; each accompanied by a sibling
      `.headers.json` describing status + headers)
    - `tests/fixtures/site_health/ok/*.html` (5+ healthy AEAT-shaped
      pages as negative controls)
  - The README documents provenance (synthesised) and the marker each
    fixture asserts, following the scrub procedure in
    `tests/fixtures/aeat-pages/README.md`.
  - Acceptance: `ls tests/fixtures/site_health` lists the four
    subfolders, each with at least five HTML files, plus a README.
  - Gate: Phase 3 parameterised tests consume every fixture.

### Phase 3 - Parser and model unit tests

- Step 3.1 - Colocated unit tests
  - Files: `src/aeat/status/test_site_health.py` (new)
  - Contents:
    - `@pytest.mark.unit` on every test.
    - A parser loader fixture that reads every HTML under
      `tests/fixtures/site_health/` and yields
      `(state_dir, path, headers_dict, body)` tuples from an adjacent
      `.headers.json` if present (or `{}`).
    - Parameterised tests asserting:
      - Every file under `mantenimiento/` yields
        `SiteHealthState.MANTENIMIENTO`.
      - Every file under `waf_challenge/` yields
        `SiteHealthState.WAF_CHALLENGE`.
      - Every file under `rate_limited/` yields
        `SiteHealthState.RATE_LIMITED` with
        `retry_after_seconds` set.
      - Every file under `ok/` yields `None` from
        `evaluate_response`.
    - Model-shape tests: `SiteHealthStatus`, `SiteHealthEvidence`,
      `SiteHealthAlert` accept valid kwargs, reject unknown keys, and
      reject out-of-bounds `http_status`, `html_fragment` over 4096,
      and empty markers.
    - Zero `unittest.mock`, `monkeypatch.setattr` on internals, or any
      stub/fake constructions. Tests drive plain strings loaded from
      disk.
  - Acceptance: `uv run pytest src/aeat/status/test_site_health.py -m unit -q`
    green.
  - Gate: Phase 8 `just test`.

### Phase 4 - Browser session navigation hook

- Step 4.1 - Add health-probe helper and `navigate`
  - Files:
    - `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/_site_health_probe.py` (new) - private helper
      exporting `probe_response(url, http_status, headers, html, *, rate_limit_retry_after_default) -> SiteHealthStatus | None`.
      Imports `evaluate_response` from
      `aeat.status._site_health_parsers`. Forbids importing anything
      from `aeat.adapters.outbound.aeat.auth`, `aeat.application.filing`, or `aeat.domain.financial`.
    - `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` - additive:
      - Import `SiteHealthError` from `aeat.core.errors`.
      - Import `Settings` resolution via the existing pattern.
      - Add `async def navigate(self, page, url: str) -> Response`:
        - Calls `await page.goto(url)` and captures the `Response`.
        - Collects `http_status`, `headers` (dict), and `await page.content()`.
        - Invokes `probe_response(...)`. A non-None return is raised as
          `SiteHealthError(status=result)`.
        - Wraps `DNS`/`TCP`/`TLS`/`PlaywrightTimeoutError` into
          `SiteHealthError` with state `UNREACHABLE` and an evidence
          record (`http_status=0` not allowed - use `599` as a
          sentinel within the 100..599 bound, marked via
          `detected_markers=("transport-error:<exc-type>",)`).
      - The existing `create_context` signature and return type are
        untouched.
  - Acceptance: `python -c "from aeat.adapters.outbound.aeat.browser.session import BrowserSession; assert hasattr(BrowserSession, 'navigate')"`
    succeeds; direct `page.goto` is still callable.
  - Gate: Phase 8 `just typecheck`.

- Step 4.2 - Session unit tests (no live)
  - Files: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py` (extend existing or
    create if absent)
  - Contents:
    - `@pytest.mark.unit` tests that exercise `navigate`'s
      classification branch by calling `probe_response` directly with
      fixture HTML from `tests/fixtures/site_health/` and asserting it
      raises the correct `SiteHealthError` when surfaced through a
      thin test harness that composes the real helper (no Playwright
      required, no mocks).
    - Negative control: an `ok/` fixture returns `None` and does NOT
      raise.
  - Acceptance: `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py -m unit -q`
    green.
  - Gate: Phase 8 `just test`.

### Phase 5 - Workflow pause-and-alert

- Step 5.1 - Extend the abort enum
  - Files: `src/aeat/application/workflow/_models.py`
  - Add `SITE_UNAVAILABLE = "site_unavailable"` to
    `WorkflowAbortReason`.
  - Add a new field on `WorkflowStep`:
    `site_health_alert: SiteHealthAlert | None = None`, preserving
    strict/frozen/extra=forbid. Import `SiteHealthAlert` from
    `aeat.status`.
  - Acceptance: An existing persisted `WorkflowStep` deserialises
    unchanged (missing optional field); setting a new
    `site_health_alert` is accepted.
  - Gate: Phase 5.3 tests.

- Step 5.2 - Typed catch arm in the engine
  - Files: `src/aeat/application/workflow/_engine.py`
  - Import `SiteHealthError` from `aeat.core.errors`.
  - In each stage method that currently wraps a component call with
    `_record_unhandled`, insert, strictly BEFORE the generic
    `except Exception`, a new arm:
    `except SiteHealthError as exc: self._record_site_unavailable(stage, started, exc, steps)`.
  - Implement `_record_site_unavailable(self, stage, started, exc, steps)`:
    - Builds a `SiteHealthAlert` composing `stage`, `exc.status`, and
      the current `run_id`.
    - Appends a failed `WorkflowStep` carrying
      `site_health_alert=alert` and the `status_reader`-style details.
    - Raises `_AbortError(reason=WorkflowAbortReason.SITE_UNAVAILABLE, steps=tuple(steps))`.
  - Acceptance: A simulated `SiteHealthError` raised by a stage
    component terminates the run with
    `WorkflowAbortReason.SITE_UNAVAILABLE` and never reaches the
    generic unhandled arm.
  - Gate: Phase 5.3 tests; Phase 8 typecheck.

- Step 5.3 - Engine unit test scenario
  - Files: `src/aeat/application/workflow/test_engine.py` (extend)
  - Contents:
    - `@pytest.mark.unit` test that instantiates the real
      `WorkflowEngine` with a real component implementing the stage
      Protocol that, on call, raises a real
      `SiteHealthError(status=real_SiteHealthStatus)` built from a
      real `tests/fixtures/site_health/mantenimiento/*.html` fixture
      through `evaluate_response`. No mocks; the component is a plain
      class implementing the protocol.
    - Asserts: the returned `WorkflowResult.abort_reason` equals
      `WorkflowAbortReason.SITE_UNAVAILABLE`, the last step carries a
      `SiteHealthAlert`, and the generic unhandled arm is not
      triggered.
  - Acceptance: `uv run pytest src/aeat/application/workflow/test_engine.py -m unit -q`
    green.
  - Gate: Phase 8 `just test`.

### Phase 6 - CLI sub-app

- Step 6.1 - Directory-backed `aeat browser` sub-app
  - Files:
    - `src/aeat/entrypoints/cli/browser/__init__.py` (new):
      - Defines `app = typer.Typer(name="browser", help="Playwright browser session health probes")`.
      - Imports the `health` command from `health.py`.
    - `src/aeat/entrypoints/cli/browser/health.py` (new):
      - `@app.command("health") def health_cmd(json_output: bool = typer.Option(False, "--json"))`.
      - Instantiates `Settings()` and opens a real `BrowserSession`.
      - Calls `session.navigate(page, settings.site_health_probe_url)`.
      - On success prints a human summary or
        `SiteHealthStatus(state=OK, ...).model_dump(mode="json")` when
        `--json`; exits with 0.
      - On `SiteHealthError` catches the status, prints summary/JSON,
        and exits with the ADR-locked code:
        - `0` -> `OK`
        - `2` -> `MANTENIMIENTO`
        - `3` -> `WAF_CHALLENGE`
        - `4` -> `RATE_LIMITED`
        - `5` -> `UNREACHABLE`
        - `6` -> `UNKNOWN_ERROR`
      - Exit code `1` reserved for Typer usage errors (unchanged).
    - `src/aeat/entrypoints/cli/__init__.py`:
      - `from aeat.entrypoints.cli import browser as browser_module`
      - `app.add_typer(browser_module.app, name="browser", help="...")`
  - Acceptance: `uv run aeat browser health --help` lists `--json`;
    `uv run aeat --help` lists the `browser` sub-app.
  - Gate: Phase 6.2 tests; Phase 8 `just lint`.

- Step 6.2 - CLI unit tests
  - Files: `src/aeat/entrypoints/cli/browser/test_health.py` (new)
  - Contents:
    - `@pytest.mark.unit` tests using Typer's `CliRunner`.
    - A real test double class implementing the minimal navigate
      protocol (concrete class, NOT `unittest.mock`), constructed and
      injected via a dependency-injection hook the command exposes
      (`--session-factory` private param, or a module-level
      `SESSION_FACTORY` callable the test replaces with a real
      concrete class). The double raises a real `SiteHealthError`
      built from a real fixture.
    - Assertions: human output contains the state value; `--json`
      output parses as JSON; exit codes match the ADR table for each
      state (parametrised).
  - Acceptance: `uv run pytest src/aeat/entrypoints/cli/browser/test_health.py -m unit -q`
    green.
  - Gate: Phase 8 `just test`.

### Phase 7 - Settings

- Step 7.1 - Extend `Settings`
  - Files: `src/aeat/config.py`
  - Add:
    - `site_health_probe_url: str = Field(default="https://sede.agenciatributaria.gob.es/", description="AEAT site-health probe URL")`.
    - `site_health_rate_limit_retry_after_default: int = Field(default=300, ge=1, description="Fallback Retry-After seconds")`.
  - Acceptance: `Settings()` instantiates with the defaults;
    env overrides work for both keys.
  - Gate: Phase 7.2.

- Step 7.2 - `.env.example` and config tests
  - Files:
    - `env/.env.example` - add two lines with documenting comments,
      following the surrounding format.
    - `tests/test_config.py` - extend the alignment assertion set so
      both new keys are present in both sources (the test enforces
      alignment automatically; add explicit presence assertions if
      the pattern there uses them).
  - Acceptance: `uv run pytest tests/test_config.py -m unit -q` green.
  - Gate: Phase 8 `just test`.

### Phase 8 - Quality gates

- Step 8.1 - Lint, typecheck, tests, hooks
  - Commands, in order, on Windows bash:
    - `just lint`
    - `just typecheck`
    - `just test`
    - `just hooks`
  - Acceptance: all four commands exit 0. `just test` runs unit tests
    only; live tests remain skipped because
    `AEAT_LIVE_TESTS_ENABLED` is unset.
  - Gate: this phase IS the final gate.

## Parallelization

Phases 1 and 2.2 (fixture authoring) can run in parallel with Phase
1.2/1.3 once Step 1.1 (error hoist) lands. Phase 3 depends on Phase 1
and Phase 2. Phases 4, 5, 6, 7 all depend on Phases 1-3 and are
internally independent; they can be delegated to three parallel
executors. Phase 8 is a sequential final gate.

## Verification

- `just lint && just typecheck && just test && just hooks` all green.
- Unit-test assertions guarantee at least five positive fixtures per
  non-OK state classify correctly and at least five OK fixtures do
  NOT over-trigger.
- The workflow engine unit test proves the typed arm fires BEFORE the
  generic `except Exception`, eliminating the
  `UNHANDLED_EXCEPTION` collapse documented in the research.
- CLI tests exhaustively parametrise the ADR-locked exit-code table.
- Config test enforces `.env.example` alignment for the two new keys.
- Visual / operator validation is not required for merge; a follow-up
  operator smoke test (`aeat browser health` against the real probe
  URL under `AEAT_LIVE_TESTS_ENABLED=1`) is recommended but optional
  and explicitly out of scope for this plan.

## Explicit Plan Review

- [x] ADR decisions mirrored faithfully (module placement, error
  hoist, navigation hook shape, workflow pause-and-alert with typed
  arm BEFORE generic `except Exception`, CLI exit-code table, two
  settings additions, fixture layout, pydantic conventions).
- [x] No edits to `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/**`, `src/aeat/application/filing/**`, or
  `src/aeat/domain/financial/**` - every listed file path is outside those
  trees.
- [x] Pydantic v2 `strict=True, frozen=True, extra="forbid"` enforced
  on every new record via the private `_SiteHealthRecord` base;
  `SiteHealthState` is a `StrEnum`.
- [x] Live tests gated under `AEAT_LIVE_TESTS_ENABLED=1` only; this
  plan introduces zero live tests and zero skip markers.
- [x] No GitHub Actions workflow files added; `.github/workflows/`
  remains untouched.
- [x] No mocks, patches, fakes, shadows, or stubs - tests drive real
  strings from disk and real concrete protocol implementations.

Approved by orchestrator on 2026-04-13
