---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-adr]]"
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
  - "[[2026-04-13-aeat-mantenimiento-detection-phase8-summary-exec]]"
---

# aeat-mantenimiento-detection phase9 review-followup

PR wgergely/aeat#131 received five actionable review findings from
gemini-code-assist. All five are addressed in a single follow-up commit
on top of the existing feature branch; no history was amended.

## Fixes

### 1. mantenimiento classifier — title-only guard

`src/aeat/status/_site_health_parsers.py::parse_mantenimiento_banner`
now requires at least one *body* marker hit before classifying a
response as MANTENIMIENTO. Previously the guard
`body_hit_count < 2 and title_hit_count == 0` allowed a title-only
match (with zero body hits) to classify. This contradicted ADR Decision
2.1 which mandates "two or more curated body markers OR one body
marker alongside a matching title".

New guard, explicit and ADR-aligned:

- `body_hit_count == 0` → always `None`
- `body_hit_count < 2 and title_hit_count == 0` → `None`
- otherwise → classify

Docstring updated to cite the ADR decision. Negative unit test
`TestMantenimientoTitleOnlyGuard.test_title_only_is_not_classified_as_mantenimiento`
drives a concrete HTML fixture whose title carries `interrupcion`
(title-only marker) with a body free of any body marker and asserts
both `parse_mantenimiento_banner` and `evaluate_response` return
`None`. Positive companion
`test_one_body_marker_plus_title_classifies` guards the
one-body-plus-title branch so the new guard does not over-correct.

### 2. `Retry-After` HTTP-date support

`parse_rate_limit_response` now accepts RFC 9110 §10.2.3 HTTP-date
values in addition to integer delta-seconds. The parser first tries
`int()`, then delegates to a new `_parse_http_date_retry_after` helper
that uses `email.utils.parsedate_to_datetime` and computes the delta
against an injected `now: datetime | None = None` reference (default
`datetime.now(UTC)`). Negative deltas clamp to zero, which falls back
to `rate_limit_retry_after_default`. If both parses fail, the
fallback default is used and a `retry-after:invalid:*` marker is
recorded.

The injected-now seam keeps tests deterministic without freezegun or
mocks. Three new unit tests in `TestRateLimitRetryAfter`:

- `test_http_date_retry_after_computes_delta` — HTTP-date 180 s in the
  future yields `retry_after_seconds == 180` and a `http-date` marker.
- `test_http_date_retry_after_in_past_falls_back_to_default` — past
  HTTP-date clamps to zero and falls back to the default.
- `test_invalid_retry_after_falls_back_to_default` — garbage value
  (neither int nor date) falls back to the default.

### 3. `evaluate_response` single lowercase pass

`evaluate_response` now lowercases the HTML body once and forwards the
pre-lowered view to each parser via a private `_lowered` keyword
argument. The three parsers retain their public signatures and still
lowercase internally when called standalone, so existing callers
(including the test suite) keep working unchanged. `_extract_title`
also accepts the pre-lowered view to avoid a second pass. Existing
parser fixture tests cover the new path end-to-end.

### 4. workflow engine provisional `run_id` mismatch

`src/aeat/application/workflow/_engine.py::WorkflowEngine` previously stored a
provisional `run_id` containing `-` placeholders on `_current_run_id`
and attached that to any `SiteHealthAlert`. When a site-health error
fired *after* `_stage_computing_deadlines` resolved an obligation,
the final `WorkflowResult.run_id` recomputed from the resolved
obligation — producing a different hash than the alert's stored run_id.

Fix: the engine now tracks the run context
(`_run_tax_id`, `_run_started_at`, `_run_target_modelo`,
`_run_target_period`, `_run_obligation`) on `self` and
`_record_site_unavailable` recomputes the run_id lazily via the new
`_compute_current_run_id` helper, preferring the resolved obligation's
`modelo`/`period` when available. This matches the exact logic used to
build the final `WorkflowResult.run_id`. When no obligation is known
(e.g. error from `_stage_syncing_catalogues`) the `-`/`-` placeholders
still appear and still match the final result's placeholder hash —
documented as the contract in the helper docstring.

New unit test
`TestSiteUnavailableArm.test_site_unavailable_after_obligation_resolved_matches_run_id`
routes a `SiteHealthError` through `_FakeInputsProvider.raise_exc`
(triggered inside `_stage_building_draft` after the obligation has
been resolved) and asserts:

- `last.site_health_alert.run_id == result.run_id`
- the alert's run_id differs from the `-`/`-` placeholder hash for the
  same `tax_id` + `started_at`

### 5. `_RealProbe` Playwright leak

`src/aeat/entrypoints/cli/browser/health.py::_default_probe_factory` previously
defined `_RealProbe` inline where the `try/finally` began *after*
`create_context()` and `new_page()` had already been awaited. If
either raised, `playwright.stop()` was never called and the Playwright
driver leaked.

Fix: `_RealProbe` is now a module-scoped class taking explicit
`session` and `playwright` collaborators. The `try` block wraps the
entire context/page setup, the `finally` block always runs
`playwright.stop()`, and closes the context on a best-effort basis
when one was successfully created. Two new unit tests in
`TestRealProbeCleanup`:

- `test_playwright_stop_runs_when_create_context_raises` — concrete
  `_RaisingCreateContextSession` + `_StubPlaywright` prove
  `playwright.stop()` ran (counter == 1).
- `test_playwright_stop_and_context_close_run_when_new_page_raises` —
  concrete `_RaisingNewPageSession` + `_RaisingNewPageContext` prove
  both `context.close()` and `playwright.stop()` ran when `new_page`
  raises after `create_context` succeeded.

All test doubles are concrete classes recording real method calls; no
`unittest.mock`, patches, or stubs.

## Gates

- `just lint` — passed (ruff check + format)
- `just typecheck` — passed (ty check)
- `just test` — passed (752 unit tests, 1 skipped, 23 deselected)
- `just hooks` — passed (prek run --all-files)

## Files touched

- `src/aeat/status/_site_health_parsers.py`
- `src/aeat/status/test_site_health.py`
- `src/aeat/application/workflow/_engine.py`
- `src/aeat/application/workflow/test_engine.py`
- `src/aeat/entrypoints/cli/browser/health.py`
- `src/aeat/entrypoints/cli/browser/test_health.py`
- `.vault/exec/2026-04-13-aeat-mantenimiento-detection/2026-04-13-aeat-mantenimiento-detection-phase9-review-followup.md`
