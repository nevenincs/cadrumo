---
tags:
  - "#exec"
  - "#cert-auth"
date: 2026-04-12
modified: '2026-04-12'
title: "cert-auth phase1 step4 — settings + env example"
related:
  - "[[2026-04-12-cert-auth-plan]]"
---

# cert-auth phase1 step4: settings + env example

## Scope
- `src/aeat/config.py` — five additive fields on the existing
  `Settings` model:
  `aeat_certificate_path`, `aeat_certificate_password_secret`
  (SecretStr, never logged), `aeat_certificate_friendly_name`,
  `aeat_certificate_backend` (defaults to `PLAYWRIGHT_CONTEXT`),
  `aeat_certificate_verify_url` (defaults to the Sede root).
- `env/.env.example` — five new documented lines under a new
  `AEAT certificate authentication (#8)` section.
- The alignment test in `tests/test_config.py` continues to pass
  because both sides gain the same five entries.

## Import-cycle note
`aeat.core.config` imports `CertificateBackend` from
`aeat.adapters.outbound.aeat.auth.certificate`. To keep that import safe, the existing
`from aeat.core.config import Settings` line at the top of
`aeat.adapters.outbound.aeat.auth.__init__` was moved under `TYPE_CHECKING` (it is used only
in annotations — runtime consumers already re-import inside their
functions). No behavioural change.
