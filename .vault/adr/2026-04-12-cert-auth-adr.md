---
tags:
  - "#adr"
  - "#cert-auth"
date: 2026-04-12
modified: '2026-04-12'
title: "AEAT PKCS#12 Certificate Authentication"
related:
  - "[[2026-04-12-cert-auth-research]]"
  - "[[2026-04-12-playwright-anti-bot-adr]]"
---

# ADR: PKCS#12 Certificate Authentication for AEAT Sede Electrónica

## Status
Accepted — 2026-04-12.

## Context
AEAT's Sede Electrónica gates most autónomo-facing endpoints behind a
client-TLS handshake using an FNMT-RCM PKCS#12 *certificado de persona
física*. Issue #8 requires a programmatic auth path for the
Playwright-driven `aeat.adapters.outbound.aeat.browser` subpackage. Cl@ve and DNIe are explicit
non-goals. See `[[2026-04-12-cert-auth-research]]` for the survey.

## Decision

### Primary backend: `PLAYWRIGHT_CONTEXT`
Supply the PKCS#12 bundle to Playwright via `browser.new_context(
client_certificates=[...])`. This is the only backend that drives the
real Sede Electrónica UI and is supported on all three target OSes. The
project already pins `playwright>=1.58.0`, which exceeds the 1.46 floor
for the `client_certificates` kwarg.

### Fallback backend: `HTTPX_FALLBACK`
Used exclusively by `verify_handshake()`. Extracts PEM cert + key from
the PKCS#12 (in-memory; written to securely-permissioned temp files
that are deleted on exit) and performs a direct mTLS handshake via
`httpx`. Not capable of driving the Sede UI. `preload_into_browser_context`
on this backend raises `NotImplementedError`.

### Deferred backends: `USER_DATA_DIR`, `MTLS_PROXY`
Stub-implemented with `NotImplementedError` and a docstring explaining
when they would apply. They remain in the `CertificateBackend` enum so
operators can see the decision space, but the implementation cost is
not justified by the primary use case today.

### Pydantic + SecretStr discipline
- `CertificateBundle`, `LoadedCertificate`, `HandshakeResult` are pydantic
  v2 `BaseModel`s with `model_config = ConfigDict(strict=True, frozen=True)`.
- Cert passwords are `pydantic.SecretStr` only. `.get_secret_value()` is
  called exactly at the TLS handshake boundary and never otherwise.
- Raw PKCS#12 bytes and the parsed private-key handle live in
  `PrivateAttr` fields on `LoadedCertificate` and are therefore
  **NEVER** serialised by `model_dump()` and **NEVER** exposed by `repr()`.
- The public API lives in `aeat.adapters.outbound.aeat.auth.certificate`; backends live in
  `aeat.adapters.outbound.aeat.auth._certificate_backends/` as private modules. Callers import
  exclusively from `aeat.adapters.outbound.aeat.auth`.

### Error hierarchy
All domain errors inherit from `aeat.core.errors.AeatError` via a single
`CertificateError` base:

- `CertificateError` — base.
- `CertificateLoadError` — malformed PKCS#12 bytes.
- `CertificatePasswordError` — missing env var or wrong passphrase.
- `CertificateExpiredError` — cert loaded OK but `not_valid_after` is in
  the past.
- `CertificateHandshakeError` — malformed handshake input (not a TLS
  failure during verify; TLS failures are returned as
  `HandshakeResult(success=False)`).

### Settings surface
Five additive fields on the existing `Settings` model, all documented in
`env/.env.example`:

| Field | Env var | Purpose |
| --- | --- | --- |
| `aeat_certificate_path` | `AEAT_CERTIFICATE_PATH` | Path to the .p12 bundle |
| `aeat_certificate_password_secret` | `AEAT_CERTIFICATE_PASSWORD_SECRET` | Passphrase (SecretStr, never logged) |
| `aeat_certificate_friendly_name` | `AEAT_CERTIFICATE_FRIENDLY_NAME` | Optional label |
| `aeat_certificate_backend` | `AEAT_CERTIFICATE_BACKEND` | `PLAYWRIGHT_CONTEXT` (default) / `HTTPX_FALLBACK` / stubs |
| `aeat_certificate_verify_url` | `AEAT_CERTIFICATE_VERIFY_URL` | Target URL for `verify_handshake()` |

## Non-goals
- **Cl@ve** (user + PIN) authentication.
- **DNIe** (Spanish national ID card) authentication.
- Installing the cert into OS cert stores (`USER_DATA_DIR` stub).
- Running a local mTLS proxy (`MTLS_PROXY` stub).
- Renewal / revocation tooling — FNMT issues + AEAT ownership remain
  with the operator.
- Any code path that logs, persists, or otherwise surfaces the cert
  passphrase.

## Operator runbook

### When `verify_handshake` reports failure
1. Re-run `aeat doctor` (once the doctor gains cert checks) or call
   `verify_handshake()` directly.
2. Confirm `AEAT_CERTIFICATE_PATH` points at an existing readable file.
3. Confirm `AEAT_CERTIFICATE_PASSWORD_SECRET` is set and non-empty; the
   value never appears in logs — re-enter it if unsure.
4. Confirm the cert is not expired: the error will include
   `subject` and `not_after`; never bytes or passphrase.

### When the cert is near-expiry
1. Download a fresh .p12 from FNMT-RCM (or re-issue via AEAT's
   certificate renewal page). Save it to a new path so you can roll
   back if needed.
2. Update `AEAT_CERTIFICATE_PATH` to point at the new file.
3. Update `AEAT_CERTIFICATE_PASSWORD_SECRET` if the passphrase changed.
4. Re-run `verify_handshake()` and confirm `success=True`.
5. Delete the superseded .p12 from disk.

### When the cert is revoked
1. Do not attempt to reuse it. Generate a fresh cert as above.
2. Audit any cached Playwright `storage_state` files tied to the old
   cert — they may still contain stale session tokens.

## Consequences
- New code lives under `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` and
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/`. Existing Google auth symbols
  in `aeat/adapters/outbound/aeat/auth/__init__.py` are untouched; cert symbols are re-exported
  additively.
- `aeat.adapters.outbound.aeat.browser.session.BrowserSession` must eventually learn to accept
  a `CertificateBundle` and propagate it to
  `browser.new_context(client_certificates=[...])`. That wiring is
  **out of scope for this issue** but is explicitly enabled by the
  `preload_into_browser_context()` Protocol surface shipped here.
- The `HTTPX_FALLBACK` backend introduces a temp-file round-trip; the
  implementation zeroes perms to `0o600` and unlinks on exit.
