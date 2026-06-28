---
tags:
  - "#plan"
  - "#playwright-anti-bot"
date: 2026-04-12
modified: '2026-04-12'
title: Implementation Plan for Playwright Anti-Bot Evasion
related:
  - "[[2026-04-12-playwright-anti-bot-adr]]"
  - "[[2026-04-12-playwright-anti-bot-research]]"
---
# Implementation Plan: Playwright Anti-Bot Evasion

## 1. Scaffolding Phase (src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/)
- **Task 1.1**: Define `Profile` dataclass/pydantic model for persistent fingerprints and `storage_state` paths.
- **Task 1.2**: Define a pluggable evasion strategy interface (e.g., `EvasionStrategy` Protocol).
- **Task 1.3**: Implement the chosen evasion strategy (`PlaywrightStealthEvasion`) using `playwright-stealth`.
- **Task 1.4**: Build the `BrowserSession` factory that takes a `Profile`, auth backend, and proxy config, returning a configured Playwright `BrowserContext` with evasion patches applied.
- **Task 1.5**: Implement `BrowserHealthCheck` callable that verifies the Playwright installation, browser binary, and performs a smoke test.
- **Task 1.6**: Ensure all public symbols have Google-style docstrings, type hints, use `aeat.core.errors.AeatError` derived exceptions, and use the project logger factory. Add minimal usage example in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/__init__.py`.

## 2. Wiring Phase
- **Task 2.1**: Update `pyproject.toml` to add `playwright` and `playwright-stealth` under the `dependency-groups.dev` group.
- **Task 2.2**: Update `justfile` to add a `playwright-doctor` recipe (supporting both Windows powershell and Unix bash).
- **Task 2.3**: Update `src/aeat/config.py` to add new additive pydantic-settings: `browser_channel`, `headless`, `default_profile_name`, `proxy_url`, `proxy_username`, `proxy_password_secret`, `proxy_bypass`, `rate_limit_delay_seconds`.
- **Task 2.4**: Document the new configuration keys in `env/.env.example`.
- **Task 2.5**: Update `tests/test_config.py` to cover the new environment variable validations.

## 3. Testing Phase
- **Task 3.1**: Add `@pytest.mark.unit` tests colocated in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/` (e.g., `test_profile.py`, `test_session.py`, `test_health.py`) for the factory composition, profile loader, proxy wiring, and health check. These tests will use Playwright mocks or local-only checks.
- **Task 3.2**: Add one `@pytest.mark.live` test in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py` that is opt-in (`AEAT_LIVE_TESTS=1`), hits a real public bot-detection probe (e.g., `https://bot.sannysoft.com/`), and asserts a successful non-automated score without using mocks.

## 4. Documentation Phase
- **Task 4.1**: Create an operational runbook for detection events in `.vault/reference/2026-04-12-playwright-anti-bot-runbook.md` (e.g., handling CAPTCHAs, IP blocks, pausing execution, alerting).

## Explicit Plan Review
- **Scope Alignment**: The plan precisely matches the required deliverables from the issue description (#16).
- **Vaultspec Rules**: Files are correctly routed to `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/` with strict adherence to `tags` format and wiki-links.
- **Sibling Branch Boundaries**: We are strictly appending to `pyproject.toml` dependencies, adding additive fields to `src/aeat/config.py` and `tests/test_config.py`, and avoiding `conftest.py` modifications. Tests will be properly tagged with `@pytest.mark.unit` and `@pytest.mark.live` as specified by project conventions.
- **Review Outcome**: PASSED. Ready for execution.
