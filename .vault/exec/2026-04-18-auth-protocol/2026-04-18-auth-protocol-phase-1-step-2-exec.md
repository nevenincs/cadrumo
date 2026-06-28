---
tags:
  - '#exec'
  - '#auth-protocol'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-auth-protocol-plan]]'
---

# `auth-protocol` `phase-1` `step-2`

Moved browser-context construction behind a provider provisioner seam.

- Modified: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py`
- Modified: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py`
- Modified: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py`

## Description

Replaced the certificate-shaped `create_context(cert=...)` contract with `create_context(provisioner=...)`. The certificate-backed flow now supplies a `CertificateContextProvisioner` that injects Playwright client-certificate kwargs and stamps the expected context marker, keeping the browser package free of certificate-specific parameter types.

## Tests

Validated the browser seam with `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py -q`. The tests confirm the context marker remains present for certificate-backed contexts and absent when no provisioner is supplied.
