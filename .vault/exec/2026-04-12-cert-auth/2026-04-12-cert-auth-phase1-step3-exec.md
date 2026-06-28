---
tags:
  - "#exec"
  - "#cert-auth"
date: 2026-04-12
modified: '2026-04-12'
title: "cert-auth phase1 step3 — Playwright + httpx backends"
related:
  - "[[2026-04-12-cert-auth-plan]]"
---

# cert-auth phase1 step3: Playwright + httpx backends

## Scope
- `_playwright_context.PlaywrightContextBackend` — primary backend.
  Documents the hard constraint that per-context client certs MUST be
  supplied at `browser.new_context(client_certificates=[...])` time
  (there is no post-hoc injection hook). `preload()` validates that
  the caller tagged the constructed context with
  `_aeat_certificate_thumbprint`; `verify()` delegates to the httpx
  backend so we do not spin up a browser for a TLS probe.
- `_playwright_context.build_client_certificates_kwarg(cert, origin)`
  — helper that the browser session factory (follow-up issue) will
  call to build the exact kwarg shape Playwright expects. The
  passphrase is materialised from `SecretStr` at this single call
  site and nowhere else.
- `_httpx_fallback.HttpxFallbackBackend` — verify-only backend.
  Re-parses the in-memory PKCS#12, exports PEM cert+key, writes them
  to `tempfile.mkstemp`-backed temp files chmod'd to `0o600`, runs
  `httpx.Client(verify=ssl_ctx).get(url)` where `ssl_ctx` has
  `load_cert_chain`'d the temp files. Unconditionally unlinks the
  temp files in a `finally`. Returns a `HandshakeResult` with
  `success=False` on any TLS/network error (never raises for normal
  failures).
- `pyproject.toml` — explicit `cryptography>=46.0.7` dep so the
  contract is visible even though the library is already pulled in
  transitively by `google-auth`.
