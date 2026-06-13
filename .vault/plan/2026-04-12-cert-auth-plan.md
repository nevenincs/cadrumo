---
tags:
  - "#plan"
  - "#cert-auth"
date: 2026-04-12
modified: '2026-04-12'
title: "Implementation Plan: PKCS#12 Certificate Authentication"
related:
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-12-cert-auth-research]]"
---

# Implementation Plan: PKCS#12 Certificate Authentication

## Phase 1 — Schema + error hierarchy
- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` (NEW),
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py` (additive re-exports).
- **Content**: `CertificateBackend(StrEnum)`, `CertificateBundle`,
  `LoadedCertificate` (with `PrivateAttr` for secret material),
  `HandshakeResult`, `CertificateError` hierarchy. No behaviour.
- **Commit**: `feat(auth): pydantic schema + error hierarchy for cert auth (#8)`

## Phase 2 — Loader + backend dispatch
- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` (extend),
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/__init__.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_base.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_user_data_dir.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_mtls_proxy.py`.
- **Content**: `load_certificate()` that reads the .p12, reads the
  passphrase from env, parses via `cryptography.pkcs12.load_pkcs12`,
  derives public metadata, stores secrets in `PrivateAttr`, raises
  appropriate errors. `_select_backend()` dispatcher. ABC + stub
  backends that raise `NotImplementedError` with documented messages.
- **Commit**: `feat(auth): certificate loader + backend dispatch (#8)`

## Phase 3 — Playwright + httpx backends
- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_playwright_context.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` (wire `preload_into_browser_context`
  and `verify_handshake`).
- **Content**: Playwright backend validates context construction
  (documents that client certs must be passed at `new_context()` time).
  httpx backend runs a real TLS handshake via PEM temp files with
  `0o600` perms and guaranteed cleanup. Explicit dep on `cryptography`
  added to `pyproject.toml`.
- **Commit**: `feat(auth): playwright + httpx cert backends (#8)`

## Phase 4 — Settings + env example
- **Files**: `src/aeat/config.py`, `env/.env.example`.
- **Content**: Five additive fields. `tests/test_config.py` alignment
  stays green.
- **Commit**: `feat(auth): settings + env example for cert config (#8)`

## Phase 5 — Tests
- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/test_backends.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate_live.py`.
- **Content**: Unit tests that generate real self-signed PKCS#12
  bundles in tmp dirs (no mocks), cover happy path, password errors,
  expired cert, malformed bytes, SecretStr non-leakage, `model_dump`
  non-leakage, PrivateAttr discipline, backend dispatch, stub backend
  `NotImplementedError`. One gated live test for `verify_handshake`.
- **Commit**: `test(auth): unit + live coverage for cert auth (#8)`

## Phase 6 — Docs
- **Files**: all `.vault/` artefacts (research, ADR, plan, exec steps,
  exec summary). Plus the code-review record from Phase 7.
- **Commit**: `docs(cert-auth): vault research, ADR, plan, exec records (#8)`

## Phase 7 — Mandatory code review
- **Files**: `.vault/exec/2026-04-12-cert-auth/2026-04-12-cert-auth-code-review.md`.
- **Content**: vaultspec-code-review checklist fully exercised against
  every commit. Included in Phase 6's docs commit.

## Test strategy
- All unit tests marked `@pytest.mark.unit`, colocated Rust-style next
  to production code.
- PKCS#12 bundles generated at runtime via `cryptography.hazmat.primitives.serialization.pkcs12.serialize_key_and_certificates`
  — never committed, never mocked.
- SecretStr leak tests: assert the secret value is NOT in `repr()`,
  `str()`, or `model_dump()` output for every model that holds it.
- Live test: `@pytest.mark.live`, gated on `AEAT_LIVE_TESTS_ENABLED=1`
  AND the cert env vars being set. Skips cleanly if absent. Zero mocks.
- Before each commit: `just lint && just typecheck && just test && just hooks`.

## Plan Review (self-review, no human in the loop)

### Risks considered
1. **Playwright `client_certificates` kwarg shape drift** — mitigated by
   pinning `playwright>=1.58.0` and documenting the exact call signature
   in the backend module. Also mitigated by the fact that the
   Playwright backend only constructs the kwarg dict; the actual
   `new_context()` call stays in `aeat.adapters.outbound.aeat.browser.session`.
2. **Temp-file PEM leak** — mitigated by `tempfile.mkstemp(mode=0o600)`
   on POSIX + equivalent ACL on Windows, wrapped in a try/finally that
   unlinks on exit; unit test asserts cleanup occurs even on exception.
3. **SecretStr leakage via `__repr__`** — mitigated by override +
   explicit unit test that scans `repr()` and `model_dump()` output for
   the known secret bytes.
4. **Cross-OS test flakiness on generated PKCS#12** — mitigated by
   generating in-process per-test rather than relying on a checked-in
   fixture.
5. **Public-API discipline drift** — mitigated by `__all__` export list
   in `aeat.adapters.outbound.aeat.auth` and a unit test that imports exclusively via the
   subpackage root.

### Alternatives considered and rejected
- **Use Playwright's own auth flow** (UI form-fill on the cert chooser)
  — rejected: FNMT cert chooser is OS-level and cannot be scripted
  portably.
- **Shell out to `openssl pkcs12`** — rejected: introduces a binary
  dependency and loses error fidelity.
- **Bundle `requests` as a second HTTP client** — rejected: `httpx` is
  already pinned and handles the case.
- **Pydantic dataclasses instead of BaseModel** — rejected: the pydantic
  mandate is explicit about `BaseModel` + strict + frozen.

### Plan review verdict
**Plan review verdict: APPROVED FOR EXECUTION**
