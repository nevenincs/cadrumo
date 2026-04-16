---
tags:
  - "#exec"
  - "#live-cert-auth"
date: 2026-04-16
related:
  - "[[2026-04-16-live-cert-auth-plan]]"
  - "[[2026-04-16-live-cert-auth-adr]]"
  - "[[2026-04-16-live-cert-auth-research]]"
---

# `live-cert-auth` `phase1` `step1`

Connected the existing certificate-auth code to real Playwright browser
contexts and added a read-only verification command plus live/test coverage for
the authenticated `fetch_expedientes()` path.

- Modified: `src/aeat/auth/certificate.py`
- Modified: `src/aeat/auth/__init__.py`
- Modified: `src/aeat/auth/_certificate_backends/_playwright_context.py`
- Modified: `src/aeat/browser/session.py`
- Modified: `src/aeat/browser/test_session.py`
- Modified: `src/aeat/cli/browser/__init__.py`
- Created: `src/aeat/cli/browser/verify_cert.py`
- Created: `src/aeat/cli/browser/test_verify_cert.py`
- Modified: `src/aeat/status/_protocols.py`
- Modified: `src/aeat/status/_reader.py`
- Modified: `src/aeat/status/test_live.py`
- Modified: `src/aeat/status/test_reader.py`

## Description

The step reuses the existing PKCS#12 and Playwright backend work instead of
reimplementing certificate behavior in a second package. The loaded
certificate object now exposes the browser-preload surface the status reader
expects, `BrowserSession` now passes Playwright `client_certificates` at
context-construction time and tags the context for later validation, and the
new `aeat browser verify-cert` command performs the sanctioned read-only
verification flow: handshake first, then one authenticated
`fetch_expedientes()` pass. The old status live placeholder was replaced with
the real gated browser-backed read test.

## Tests

- `uv run pytest src/aeat/browser/test_session.py src/aeat/cli/browser/test_health.py src/aeat/cli/browser/test_verify_cert.py src/aeat/status/test_reader.py -m "not live"` — passed.
- `uv run pytest src/aeat/auth/test_certificate.py -m "not live"` — passed.
- `uv run ruff check src/aeat/auth src/aeat/browser src/aeat/cli/browser src/aeat/status` — passed.
- `uv run ty check src/aeat/auth src/aeat/browser src/aeat/cli/browser src/aeat/status` — passed.
