---
tags:
  - "#exec"
  - "#cert-auth"
date: 2026-04-12
modified: '2026-04-12'
title: "cert-auth phase1 step5 — unit + live tests"
related:
  - "[[2026-04-12-cert-auth-plan]]"
---

# cert-auth phase1 step5: unit + live tests

## Scope
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate.py` — 22 unit tests, all marked
  `@pytest.mark.unit`, all colocated Rust-style. Each test that
  needs a bundle **generates a real self-signed PKCS#12 in-process**
  via `cryptography.x509` + `pkcs12.serialize_key_and_certificates`.
  No mocks, fakes, stubs, shadows or patches.
- Coverage:
  - `CertificateBundle` strict/frozen/extra-forbid + empty env-var-name rejection.
  - `load_certificate` happy path, missing env var, wrong password,
    expired cert, malformed bytes.
  - SecretStr and PrivateAttr non-leakage: scans `repr()`, `str()`,
    `model_dump()`, `model_dump_json()` for the secret bytes, and
    asserts the PrivateAttr names are absent from `model_dump()`.
  - `_select_backend()` returns the right class for every
    `CertificateBackend` member (parametrised).
  - `verify_handshake` rejects empty URL and returns
    `success=False` on TLS failure against an unroutable TEST-NET-1
    address.
  - `PlaywrightContextBackend.preload` rejects an unmarked context
    and accepts a marked one; `build_client_certificates_kwarg`
    materialises the secret into the exact Playwright kwarg shape.
  - `HttpxFallbackBackend.preload` raises `NotImplementedError` with
    the documented "no browser path" message.
  - `USER_DATA_DIR` / `MTLS_PROXY` backends raise
    `NotImplementedError` from both methods.
  - Settings integration: setting all five cert env vars produces a
    `Settings` with the expected values and `repr(settings)` does
    not leak the passphrase.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate_live.py` — one
  `@pytest.mark.live` test gated on `AEAT_LIVE_TESTS_ENABLED=1` AND
  on the cert env vars being set. Skips cleanly otherwise. Zero
  mocks. Runs a real mTLS handshake against the configured verify URL.
