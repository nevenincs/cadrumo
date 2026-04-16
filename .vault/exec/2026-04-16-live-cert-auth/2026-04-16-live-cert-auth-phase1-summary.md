---
tags:
  - "#exec"
  - "#live-cert-auth"
date: 2026-04-16
related:
  - "[[2026-04-16-live-cert-auth-plan]]"
  - "[[2026-04-16-live-cert-auth-phase1-step1]]"
---

# `live-cert-auth` `phase1` summary

Phase 1 closed the browser-side gap left after the original cert-auth work:
the codebase can now attach the configured PKCS#12 bundle to a real Playwright
context, validate that context through the existing auth backend, and run a
single sanctioned read-only AEAT verification flow without touching any live
write surface.

- Modified: `src/aeat/auth/certificate.py`
- Modified: `src/aeat/browser/session.py`
- Created: `src/aeat/cli/browser/verify_cert.py`
- Modified: `src/aeat/status/test_live.py`

## Description

The implementation keeps concrete certificate behavior in `aeat.auth`,
connects it to the browser factory in `aeat.browser`, and reuses the existing
status-reader read path for verification rather than expanding unfinished
status surfaces. The new verification command gives operators and automation a
clear two-stage signal: certificate accepted at handshake time, then one
authenticated `fetch_expedientes()` pass. The live environment still lacks the
operator certificate material on 2026-04-16, so the final live-green proof
remains an honest gated step instead of a fabricated pass.

## Tests

- Targeted browser, CLI, status, and auth unit tests passed.
- Targeted `ruff` and `ty` checks for the touched packages passed.
- The live status smoke test is now real and gated on
  `AEAT_LIVE_TESTS_ENABLED` plus configured certificate settings.
