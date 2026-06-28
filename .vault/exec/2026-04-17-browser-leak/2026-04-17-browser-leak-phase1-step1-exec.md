---
tags:
  - "#exec"
  - "#browser-leak"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-browser-leak-plan]]"
  - "[[2026-04-17-browser-leak-adr]]"
  - "[[2026-04-17-browser-leak-review-audit]]"
---

# `browser-leak` `phase1` `step1`

## scope

Implement the BrowserSession ownership fix and the direct owner cleanup updates required to close the Chromium leak in issue `#190`.

## completed work

- Added explicit browser retention and idempotent `close()` to `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py`.
- Added lifecycle locking so concurrent or repeated `create_context()` calls cannot silently accumulate browsers on one session instance.
- Added failure-safe cleanup so post-launch errors close the retained browser before raising `BrowserError`.
- Updated `src/aeat/entrypoints/cli/browser/health.py` to close its owned session before stopping Playwright.
- Updated `src/aeat/domain/justificante/_verify.py` to close its self-owned session before stopping Playwright, using a concrete factory seam for deterministic unit coverage.
- Updated the live browser smoke test to close the session explicitly.

## verification

- `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/entrypoints/cli/browser/test_health.py src/aeat/domain/justificante/test_verify.py`
- `uv run ruff check src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/entrypoints/cli/browser/health.py src/aeat/entrypoints/cli/browser/test_health.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py src/aeat/domain/justificante/_verify.py src/aeat/domain/justificante/test_verify.py`
- `uv run ty check src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/entrypoints/cli/browser/health.py src/aeat/entrypoints/cli/browser/test_health.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py src/aeat/domain/justificante/_verify.py src/aeat/domain/justificante/test_verify.py`
- `uv run pytest -o addopts='' src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py -m live_read` (collected and skipped by live gating)
