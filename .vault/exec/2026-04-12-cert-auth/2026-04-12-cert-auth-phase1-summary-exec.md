---
tags:
  - "#exec"
  - "#cert-auth"
date: 2026-04-12
modified: '2026-04-12'
title: "cert-auth phase1 summary"
related:
  - "[[2026-04-12-cert-auth-plan]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-12-cert-auth-research]]"
  - "[[2026-04-12-cert-auth-phase1-step1-exec]]"
  - "[[2026-04-12-cert-auth-phase1-step2-exec]]"
  - "[[2026-04-12-cert-auth-phase1-step3-exec]]"
  - "[[2026-04-12-cert-auth-phase1-step4-exec]]"
  - "[[2026-04-12-cert-auth-phase1-step5-exec]]"
  - "[[2026-04-12-cert-auth-code-review-exec]]"
---

# cert-auth phase1 summary

Issue #8 — PKCS#12 client-certificate authentication for AEAT Sede
Electrónica.

## Artefacts produced
- Research: `.vault/research/2026-04-12-cert-auth-research.md`
- ADR: `.vault/adr/2026-04-12-cert-auth-adr.md`
- Plan: `.vault/plan/2026-04-12-cert-auth-plan.md`
- Exec steps: this folder (step1 → step5, summary, code-review).

## Code produced
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` — public surface
  (`CertificateBackend`, `CertificateBundle`, `LoadedCertificate`,
  `HandshakeResult`, error hierarchy, `load_certificate`,
  `preload_into_browser_context`, `verify_handshake`).
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/` — private package with the
  ABC, Playwright primary backend, httpx verify-only backend, and
  two deferred stub backends.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py` — additive re-exports. Existing Google
  auth API untouched.
- `src/aeat/config.py` + `env/.env.example` — five additive cert
  settings fields.
- `pyproject.toml` — explicit `cryptography>=46.0.7` dep.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate.py` + `test_certificate_live.py`
  — 22 unit tests + 1 gated live test.

## Verification
- `uv run ruff check .` — passed.
- `uv run ruff format .` — applied (4 files).
- `uv run ty check src tests` — passed.
- `uv run pytest` — 404 passed, 1 skipped, 16 deselected (live
  markers).
- `uv run prek run --all-files` — all hooks passed.

## Out of scope (deferred follow-ups)
- `USER_DATA_DIR` and `MTLS_PROXY` backends remain stubs.
- Wiring a `CertificateBundle` through
  `aeat.adapters.outbound.aeat.browser.session.BrowserSession` to Playwright's
  `browser.new_context(client_certificates=[...])` — enabled by the
  `build_client_certificates_kwarg` helper shipped here, but the
  actual `BrowserSession` edit is a separate issue.
- `aeat doctor` integration to run `verify_handshake` on startup.
