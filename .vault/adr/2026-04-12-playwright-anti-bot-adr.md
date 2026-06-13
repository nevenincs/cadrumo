---
tags:
  - "#adr"
  - "#playwright-anti-bot"
date: 2026-04-12
modified: '2026-04-12'
title: Playwright Anti-Bot Evasion Strategy
related:
  - "[[2026-04-12-playwright-anti-bot-research]]"
---

# Architecture Decision Record: Playwright Anti-Bot Evasion

## Context
AEAT interfaces require robust anti-bot evasion capabilities to ensure that our automated sessions are not immediately blocked or challenged during legitimate operations. We need a stable setup for browser automation using Python and `playwright`, managed within our `uv` environment. The strategy must handle fingerprint/entropy management, proxy configuration, and operational guardrails.

## Decision
We will adopt the following primary approach for browser automation:
1. **Primary Tooling**: Use `playwright` with `playwright-stealth` in Python.
2. **Execution Mode**: Execute using `channel: "chrome"` in "New Headless" mode to closely mimic legitimate user behavior.
3. **Entropy & Profile Management**: Maintain persistent `storage_state` and a stable profile entropy (UA, locale, timezone, viewport, fonts, WebGL, audio context) per AEAT identity. This ensures the client looks like a returning user.
4. **Proxy Configuration**: Default to **NO proxy** unless specifically configured via environment variables (e.g., static residential).
5. **Operational Guardrails**: Implement minimum delays between AEAT requests, honor `Retry-After` headers, and establish a detection-event runbook (if CAPTCHA / IP block / cert revocation occurs, pause, alert, and do not retry automatically).

## Fallback Plan
If system Chrome updates break the pipeline or `playwright-stealth` becomes ineffective, we will fall back to using bundled `chromium` with aggressive manual CDP (Chrome DevTools Protocol) patches.

## Explicit Exclusions (What We Are NOT Doing)
- **NO per-request proxy rotation**: Rapid IP changes correlate poorly with certificate identity and appear adversarial to AEAT.
- **NO `undetected-playwright`**: This Python package is currently unmaintained and poses a maintenance risk compared to our chosen setup.
- **NO dropping cookies between active sessions**: We must maintain a consistent `storage_state` to avoid triggering bot detection heuristics that flag fresh, stateless sessions.

## Consequences
- Requires a deliberate, manual upgrade workflow for Playwright and the system Chrome version.
- `playwright-stealth` and persistent profiles will need proper management in the `Profile` dataclass.
- A health check script (`just playwright-doctor`) is required to verify the local environment is correctly provisioned with the right browser channels and dependencies.
