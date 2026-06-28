---
tags:
  - "#exec"
  - "#cert-auth"
date: 2026-04-12
modified: '2026-04-12'
title: "cert-auth phase1 step2 — loader + backend dispatch"
related:
  - "[[2026-04-12-cert-auth-plan]]"
---

# cert-auth phase1 step2: loader + backend dispatch

## Scope
- `load_certificate(bundle)` — reads the passphrase from the env var
  *name* stored in the bundle, reads the PKCS#12 bytes from disk,
  parses via `cryptography.hazmat.primitives.serialization.pkcs12
  .load_pkcs12`, populates public metadata, stows secrets in
  `PrivateAttr`, and raises `CertificateExpiredError` if the cert is
  already past its `not_after`.
- `_select_backend()` — enum-dispatched factory with lazy imports so
  the cryptography + playwright dependency cost is paid only for
  backends that are actually requested.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/` — private package with
  `_base._CertBackend` ABC and two stub backends
  (`_user_data_dir.UserDataDirBackend`,
  `_mtls_proxy.MtlsProxyBackend`) that raise `NotImplementedError`
  from both `preload` and `verify`.

## Design notes
- `cryptography` raises `ValueError` on both bad password and
  malformed bytes; the loader inspects the error message for the
  canonical "invalid password / mac verify" substrings and maps the
  match onto `CertificatePasswordError`, everything else onto
  `CertificateLoadError`.
- `not_valid_before_utc` / `not_valid_after_utc` on modern
  `cryptography` are already UTC-aware, but we `_ensure_utc()` on them
  defensively so the module does not drift when the project upgrades.
