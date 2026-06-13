---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S59'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W05.P16.S59 - review fail-closed HTTPX fallback naming and registration

Scope: Wave `W05`; Phase `W05.P16`; Step `S59`.

## Description

- Retargeted the shifted HTTPX fallback path from the removed browser location to the certificate-backend location.
- Reviewed backend registration through `CertificateBackend.HTTPX_FALLBACK`.
- Verified preload fails closed for browser contexts and verify returns a closed failure without materialising PEM/key temporary files.

## Outcome

No code change was required. The HTTPX fallback remains explicitly registered as a verify-only, fail-closed certificate backend, and the Playwright backend delegates handshake verification to the same closed fallback path rather than writing decrypted certificate material to disk.

## Notes

Verification:

- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py src/aeat/adapters/outbound/aeat/auth/certificate.py src/aeat/adapters/outbound/aeat/auth/test_certificate.py`
- `uv run --no-sync pytest src/aeat/adapters/outbound/aeat/auth/test_certificate.py -q`
