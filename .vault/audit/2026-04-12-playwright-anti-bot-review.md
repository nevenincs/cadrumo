---
tags:
  - '#audit'
  - '#playwright-anti-bot'
date: '2026-04-12'
title: Playwright Anti-Bot Evasion Code Review
related:
  - '[[2026-04-12-playwright-anti-bot-plan]]'
  - '[[2026-04-12-playwright-anti-bot-adr]]'
---

# `playwright-anti-bot` Code Review

<!-- Persistent log of audit findings appended below. -->

EVASION-001 | INFO | ADR Alignment
The chosen evasion strategy (`playwright-stealth`) and fallback (`chromium` manual patches) are thoroughly justified in the ADR. Concrete tells covered, proxy rotation risks, and profile stability requirements are adequately documented.

TYPES-001 | INFO | Signature and Docstring Compliance
All modified files (`profile.py`, `evasion.py`, `session.py`, `health.py`, `__init__.py`) have fully typed public signatures and Google-style docstrings. All errors correctly inherit from `BrowserError` extending `aeat.errors.AeatError`. Logging utilizes the `get_logger` factory.

TESTS-001 | INFO | Unit Test Coverage
Appropriate unit-test coverage was achieved:
- `test_profile.py` verifies the profile loader.
- `test_session.py` verifies factory composition and proxy wiring.
The `test_smoke.py` was cleanly replaced.

TESTS-002 | INFO | Live Bot-Detection Probe
A live bot-detection probe was implemented in `test_live_evasion.py`. It correctly hits `https://bot.sannysoft.com/`, requires the opt-in `AEAT_LIVE_TESTS=1` flag, uses the `@pytest.mark.live` marker, and functions entirely without mocks.

CI-001 | INFO | Pipeline Verification
The entire verification pipeline executed successfully without warnings or failures:
- `just lint` (ruff) passes.
- `just typecheck` (ty) passes.
- `just test` (pytest) passes.
- `just hooks` (prek) passes.

DEPENDENCIES-001 | INFO | Boundaries Respected
Dependencies were successfully added to the `pyproject.toml` `dev` group. Sibling branch test configurations (`conftest.py`) were undisturbed. The `justfile` includes a cross-platform `playwright-doctor` recipe.

OVERALL STATUS | DONE | Ready for Submission
The implementation perfectly mirrors the issue requirements and vaultspec constraints. No immediate actions are pending.
