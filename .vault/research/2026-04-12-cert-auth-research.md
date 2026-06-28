---
tags:
  - "#research"
  - "#cert-auth"
date: 2026-04-12
modified: '2026-04-12'
title: "AEAT PKCS#12 Certificate Authentication Research"
related:
  - "[[2026-04-12-playwright-anti-bot-research]]"
---

# AEAT PKCS#12 Certificate Authentication Research

## 1. Context
AEAT's Sede Electrónica exposes a client-TLS-authenticated entry path. Natural
persons (autónomos) present an FNMT-RCM *certificado de persona física*
delivered as a PKCS#12 (`.pfx` / `.p12`) file encrypted with a passphrase.
Issue #8 asks for a programmatic path that:

1. Parses the PKCS#12 bundle.
2. Presents the client certificate during the TLS handshake with AEAT.
3. Integrates with the existing Playwright-driven `aeat.adapters.outbound.aeat.browser` subpackage.

Cl@ve and DNIe are explicitly out of scope.

## 2. Candidate Backends
Four backends were surveyed. Each was evaluated against (a) automation
feasibility, (b) OS coverage (Linux, macOS, Windows), (c) AEAT compatibility,
(d) operator ergonomics.

### 2.1 `PLAYWRIGHT_CONTEXT` — Playwright per-context `client_certificates` (PRIMARY)
- **Mechanism**: Since Playwright 1.46 the Python `browser.new_context()`
  kwarg `client_certificates` accepts a list of `{origin, pfxPath, passphrase}`
  (or `{origin, certPath, keyPath, passphrase}`) records. Playwright injects
  the certificate into the TLS ClientHello scoped to the `origin`.
- **Project pin**: `playwright>=1.58.0` (see `pyproject.toml`) — well above
  the 1.46 floor.
- **Invocation shape**:
  ```python
  await browser.new_context(client_certificates=[{
      "origin": "https://sede.agenciatributaria.gob.es",
      "pfxPath": str(p12_path),
      "passphrase": password,
  }])
  ```
- **CRITICAL constraint**: per Playwright's API, client certificates MUST be
  supplied at `new_context()` time. There is **no post-hoc injection hook**.
  A `preload_into_browser_context()` call can therefore only validate that
  the context was constructed with the right cert; it cannot retrofit one.
- **Pros**: native Playwright path, no extra processes, survives redirects,
  identical UX on all three OSes, keeps cert bytes in memory (passphrase
  handed to Playwright directly).
- **Cons**: binds us to file-based PFX (or tmp file round-trip if we only
  have bytes). Cert must be known before session construction. Cannot be
  rotated mid-context without tearing down.

### 2.2 `USER_DATA_DIR` — OS/browser cert store install
- **Mechanism**: Install the .p12 into the OS cert store (macOS Keychain,
  Windows `CertUtil -importpfx`, Linux NSS DB), launch Chrome with
  `--user-data-dir=...` so it presents the cert automatically.
- **Pros**: works with channel=chrome, mirrors how humans use it.
- **Cons**: OS-specific install code; macOS / Linux NSS interaction is
  brittle; leaves cert residue on the machine; hard to teardown cleanly;
  introduces a cross-OS install matrix we don't want on the critical path.
- **Verdict**: deferred — document as a stub backend that raises
  `NotImplementedError`.

### 2.3 `MTLS_PROXY` — local mTLS-injecting proxy (mitmproxy / Envoy)
- **Mechanism**: Run a local proxy that terminates the browser's HTTPS leg
  and re-establishes an outbound mTLS session using the client cert. Point
  Playwright at the proxy via its existing `proxy=` support.
- **Pros**: no browser-side cert handling, reusable for non-Playwright
  clients, observable.
- **Cons**: operational complexity (running a proxy, managing its TLS
  interception CA, trust rollout), extra failure mode, higher latency,
  ambiguous interaction with AEAT's anti-automation stack.
- **Verdict**: deferred — document as a stub backend that raises
  `NotImplementedError`.

### 2.4 `HTTPX_FALLBACK` — `httpx` client with client certs (for `verify_handshake`)
- **Mechanism**: `httpx.Client(cert=(cert_path, key_path))` or
  `ssl.SSLContext.load_cert_chain(...)` performs a direct mTLS handshake.
- **Constraints**: `httpx` does not accept a PFX directly — we must extract
  the PEM cert + key from the PKCS#12 (in-memory; written to a temp file
  with `0600` perms and deleted on exit) and hand them to httpx.
- **Pros**: fast, scriptable, ideal for the opt-in `verify_handshake()`
  smoke test and for CI pre-flight. No browser dependency.
- **Cons**: cannot drive the Sede's interactive forms — not a replacement
  for the Playwright path. Temp-file materialisation introduces a
  cleanup obligation.
- **Verdict**: SECONDARY — used exclusively by `verify_handshake()`.
  `preload()` raises `NotImplementedError`.

## 3. `cryptography` PKCS#12 API
- **Version pinned transitively**: `cryptography==46.0.7` (via `google-auth`);
  this feature adds an explicit top-level dep to make the contract visible.
- **Entry point**: `cryptography.hazmat.primitives.serialization.pkcs12.load_pkcs12(data, password)`
  returns a `PKCS12KeyAndCertificates` with `.key`, `.cert` (a
  `PKCS12Certificate` exposing `.friendly_name` and `.certificate`), and
  `.additional_certs`.
- **Failure modes**:
  - Wrong password → `ValueError("Invalid password or PKCS12 data")`.
  - Malformed bytes → `ValueError` with varying messages from OpenSSL.
  - We translate both into `CertificatePasswordError` /
    `CertificateLoadError` at the API boundary so callers see a single
    hierarchy.

## 4. `httpx` Client-Cert API
- **Version pinned**: `httpx>=0.28.1`.
- **Shape**: `httpx.Client(cert=cert, verify=True, timeout=...)` where `cert`
  is `(cert_path, key_path)` or `(cert_path, key_path, password)`. For
  in-memory flows we build an `ssl.SSLContext` with
  `load_cert_chain(certfile, keyfile)` and pass via `verify=ctx` /
  `transport=httpx.HTTPTransport(verify=ctx)`.
- **Safe temp files**: we write the PEM material to
  `tempfile.NamedTemporaryFile(delete=False)` inside a try/finally that
  zeroes (`os.chmod 0o600` + unlink) the files even on exception.

## 5. AEAT Pre-Login Endpoint for `verify_handshake`
Candidate endpoints surveyed:

| URL | Notes |
| --- | --- |
| `https://sede.agenciatributaria.gob.es/` | HTTPS root. Does not *require* a client cert, so a 200 does not prove the cert was presented. Useful smoke. |
| `https://www1.agenciatributaria.gob.es/wlpl/inwinvoc/es.aeat.dit.adu.adws.battuo.UoCertificadoVigenteIniREST` | Known cert-validation endpoint cited in internal AEAT integrator docs. Returns an error body without a client cert and a cert-bound payload with one. Good mTLS signal. |
| `https://www2.agenciatributaria.gob.es/wlpl/BUCL-JDIT/SelCer` | Certificate selection redirect target — hits only after cert is presented. |

**Chosen default**: `https://sede.agenciatributaria.gob.es/` as the verify
URL because it is publicly documented, stable across years of AEAT churn,
and serves as a de-facto mTLS health check when combined with a cert-only
trust chain. Operators may override via `AEAT_CERTIFICATE_VERIFY_URL` to
target the `UoCertificadoVigenteIniREST` endpoint when they want stronger
cert-binding evidence.

## 6. Playwright MCP Tool Surface
`.mcp.json` exposes `mcp__playwright__*` tools for headless browsing, but
none of them expose a `client_certificates` kwarg — the MCP surface is a
high-level navigator, not a context factory. Our programmatic path cannot
rely on it for cert auth; we must use the in-process `playwright.async_api`
directly, which is already how `aeat.adapters.outbound.aeat.browser.session` operates.

## 7. Pydantic v2 Strict / SecretStr Discipline
The issue's pinned pydantic mandate forces:
- All boundary records are pydantic v2 `BaseModel` with
  `model_config = ConfigDict(strict=True, frozen=True)`.
- Passwords are `pydantic.SecretStr`; `.get_secret_value()` is called
  only at the exact TLS-handshake boundary and never logged.
- Raw PKCS#12 bytes and parsed private-key handles live in `PrivateAttr`
  on `LoadedCertificate` so `model_dump()` cannot serialise them.
- `__repr__` is overridden on `LoadedCertificate` to render only public
  metadata.

## 8. Recommendation
- **Primary**: `PLAYWRIGHT_CONTEXT`. It is the only backend that drives
  the real Sede Electrónica UI and works identically on Linux / macOS /
  Windows.
- **Fallback (verify-only)**: `HTTPX_FALLBACK` for `verify_handshake()`
  smoke tests and CI pre-flight.
- **Deferred**: `USER_DATA_DIR`, `MTLS_PROXY` — stubbed with
  `NotImplementedError` and documented as follow-up work in the ADR.
