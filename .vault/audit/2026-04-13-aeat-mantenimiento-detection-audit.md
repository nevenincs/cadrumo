---
name: aeat-mantenimiento-detection-audit
description: Final code-review audit for wgergely/aeat#95 (commit 399daf3) — site-health detection + pause-and-alert
tags:
  - "#audit"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
  - "[[2026-04-13-aeat-mantenimiento-detection-adr]]"
  - "[[2026-04-13-aeat-mantenimiento-detection-research]]"
---

# aeat-mantenimiento-detection audit

Commit under review: `399daf3 feat(status): detect AEAT mantenimiento / WAF / rate-limit states (#95)`
Branch: `feature/95-aeat-mantenimiento-detection`
Reviewer: vaultspec-code-reviewer (orchestrator-driven, no human-in-the-loop)

## non-negotiable checks

| # | check | result | notes |
|---|---|---|---|
| 1 | pydantic v2 strict/frozen/forbid; StrEnum; tuple | PASS | `_SiteHealthRecord` base carries `ConfigDict(strict=True, frozen=True, extra="forbid")`; `SiteHealthState` is `StrEnum`; `detected_markers` is `tuple[str, ...]`; no new bare dict on boundaries. |
| 2 | `SiteHealthError(AeatError)` + typed raise sites | PASS | `src/aeat/errors.py:44-68`; raised from `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:151,153,167`; caught in `_engine.py`. |
| 3 | no edits under `auth/**`, `filing/**`, `financial/**`, `.github/workflows/**` | PASS | `git diff --stat` against those paths empty. |
| 4 | typed `except SiteHealthError` strictly before `except Exception` in every engine stage | PASS | lines 409/416, 457/464, 564/571, 629/636, 671/678, 693/700, 817/824/840, 900/907. |
| 5 | `SiteHealthAlert` persisted onto the workflow step record | PASS | `_record_site_unavailable` appends `WorkflowStep(... site_health_alert=alert)` then raises `_AbortError(SITE_UNAVAILABLE)`. |
| 6 | `aeat browser health --json` + ADR exit-code table | PASS | `_EXIT_CODES` at `health.py:41-48` mirrors 0/2/3/4/5/6; parametrised CLI tests lock the table. |
| 7 | settings + env mirror + config test green | PASS | `config.py:249-255`; `env/.env.example:224-229`; alignment test passes. |
| 8 | ≥5 positives per non-ok state + negatives | PASS | mantenimiento: 5, waf_challenge: 5, rate_limited: 5 (+ sibling `.headers.json`), ok: 5. |
| 9 | markers, no mocks in tests; concrete `_RaisingProbe` | PASS | `_RaisingProbe` is a plain class; `monkeypatch.setattr(..., "PROBE_FACTORY", ...)` is a DI seam, not `mock.Mock`. All tests marked `@pytest.mark.unit`. |
| 10 | google-style docstrings + full type hints on new public symbols | PASS | every new public class/function documented. |
| 11 | `aeat.core.logging.get_logger(__name__)` for new logging | PASS | `session.py`, `_engine.py`, `health.py` all use the factory. |
| 12 | conventional commit + `#95` reference | PASS | `feat(status): ... (#95)` with `Refs #95` trailer. |
| 13 | no new `.github/workflows/**` | PASS | empty diff. |
| 14 | `just lint` / `just typecheck` / `just test` / `just hooks` | PASS | lint clean, typecheck clean, 744 passed / 1 skipped / 23 deselected, hooks clean. |
| 15 | forward-ref rebuild resolves `SiteHealthAlert.stage` | PASS | `SiteHealthAlert.model_fields['stage'].annotation` resolves to `<enum 'WorkflowStage'>` after importing `aeat.application.workflow`. |

## minor observations (non-blocking)

- Hidden `_reserved` Typer command in `src/aeat/entrypoints/cli/browser/__init__.py` is a pragmatic workaround for Typer single-command collapsing; remove when a second real subcommand lands.
- `parse_mantenimiento_banner` / `parse_waf_challenge` accept an unused `rate_limit_retry_after_default` to keep a uniform parser signature; documented in their docstrings.
- `BrowserSession.navigate` wraps generic transport exceptions into `SiteHealthError(UNREACHABLE)` — intentional per ADR Decision 3.
- `WorkflowEngine._current_run_id` is instance-mutable; engine is documented as single-run, but worth revisiting if concurrent drives are ever introduced.
- `tests/test_config.py` relies on the generic key-alignment test; no bespoke assertion for the two new keys was added (plan allowed either).

## verdict

**APPROVED** — 15/15 non-negotiable gates passed. No CRITICAL or HIGH findings. Safe to merge.
