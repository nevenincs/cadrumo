---
tags:
  - "#exec"
  - "#cert-auth"
date: 2026-04-12
modified: '2026-04-12'
title: "cert-auth phase1 step1 — schema + error hierarchy"
related:
  - "[[2026-04-12-cert-auth-plan]]"
  - "[[2026-04-12-cert-auth-adr]]"
---

# cert-auth phase1 step1: schema + error hierarchy

## Scope
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` — new module containing
  `CertificateBackend` StrEnum, `CertificateBundle`, `LoadedCertificate`
  (with `PrivateAttr` fields for the PKCS#12 bytes, passphrase
  `SecretStr`, and parsed private key handle), `HandshakeResult`, and
  the full `CertificateError` hierarchy (`CertificateLoadError`,
  `CertificatePasswordError`, `CertificateExpiredError`,
  `CertificateHandshakeError`).
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py` — additive re-exports. No changes to the
  existing Google-auth public API.

## Design notes
- All boundary records use `model_config = ConfigDict(strict=True,
  frozen=True, extra="forbid")` per the pydantic mandate.
- `LoadedCertificate.__repr__` is overridden to render only public
  metadata. Private bytes/key/password live in `PrivateAttr` and are
  therefore invisible to `model_dump`, `model_dump_json`, and `repr`.
- `is_expired()` accepts an optional `now` argument for deterministic
  unit tests; defaults to `datetime.now(UTC)`.
