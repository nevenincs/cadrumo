---
tags:
  - '#adr'
  - '#aeat-access-gate'
date: 2026-04-17
modified: '2026-07-17'
body_hash: 'sha256:d4b2c9aac80244e877c51087d107e5ffad35c841ea511ee3c5e7cf3b80afdb0f'
title: "Live AEAT Access Blocker & Verification Gate"
related:
  - "[[2026-04-13-cert-pre-expiry-gate-adr]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-16-submission-safety-sweep-adr]]"
  - '[[2026-07-16-protected-browser-certificate-auth-adr]]'
  - '[[2026-07-16-protected-browser-certificate-auth-research]]'
---

# ADR: Live AEAT Access Blocker & Verification Gate | (**status:** `accepted`)

## Problem Statement

Live AEAT reads require provider authentication, profile and identity
alignment, and a test-only opt-in when pytest would contact an external
service. Those concerns must not recreate the permanently forbidden live-write
surface or let a weak certificate signal stand in for access to an
authenticated AEAT resource.

## Decision

### Authentication boundary

`AeatAuthenticator` is the certificate implementation of the application
`AuthProvider` protocol. Application orchestration supplies non-credential
`Settings`, one already resolved `ActiveCertificateCredentials` value, and a
`BrowserSessionFactory`. The provider loads and validates that exact PKCS#12
snapshot, supplies its bytes to Playwright through
`CertificateContextProvisioner`, and owns the resulting context and browser.

Certificate authentication is proved only by a successful Playwright response
whose final scheme, host, and path exactly match
`https://www6.agenciatributaria.gob.es/wlpl/TEWV-CORE/ResumenVlt`. Certificate
health, subject, thumbprint, and subject-derived NIF/NIE remain identity
evidence, but a direct TLS response, configurable target, selector page,
context marker, or persisted historical result is not authentication proof.

`verify(session)` accepts only the provider's current active session and runs
the same protected-resource proof. `close()` is mandatory, bars new work,
drains admitted operations, and releases every provider-owned browser resource.

### Session and assertion records

`AeatSession` and `AeatLoginAssertion` are strict, frozen,
provider-discriminated records in the outbound auth boundary. Certificate
detail carries the certificate subject, thumbprint, and canonical protected
resource. The shared session field historically named `storage_state_path` is
the logical active-bucket object key for encrypted session state, not a
Playwright JSON file location.

Browser cookies and origin storage are never fields on either public record.
They remain inside the encrypted `PersistedBrowserSession` payload and are
passed to Playwright only as a validated in-memory mapping. Public result and
diagnostic surfaces must render explicitly selected and redacted fields; the
presence of no passphrase or private key does not make arbitrary session or
assertion model dumps safe to log.

### Read and write gate

The provider-agnostic `AeatAccessGate` lives in
`src/cadrumo/core/access_gate/__init__.py` and is re-exported from core:

```python
@dataclass(frozen=True, slots=True)
class AeatAccessGate:
    settings: Settings

    def require_live_read(
        self,
        *,
        pytest_current_test: str | None = None,
    ) -> None: ...
    def require_live_write(self) -> None: ...
    def snapshot_env(
        self,
        *,
        pytest_current_test: str | None = None,
    ) -> AeatGateEnvSnapshot: ...
```

`CADRUMO_LIVE_TESTS_ENABLED` is a pytest-only external-read opt-in, not an
operator CLI switch. A test that performs a real external read is marked
`aeat_live`, calls the shared live-test gate, and runs only when
`Settings.cadrumo_live_tests_enabled` is the exact string `"1"`. Outside
pytest, `require_live_read()` permits execution to continue to the normal
profile, credential, identity, authentication, and read-only workflow guards.

`require_live_write()` always raises `LiveSubmitForbiddenError`. There is no
write-enabling setting, marker, confirmation phrase, injectable bypass,
submission transport, audit-side environment fallback, or live-submit command.
Authentication does not weaken that permanent refusal.

`snapshot_env()` records only the validated Cadrumo live-test setting and
pytest's current-test marker. The gate reads application configuration through
`Settings`; direct `os.environ` access is limited to pytest's infrastructure
marker.

### Identity and recovery

Certificate NIF/NIE is derived from the certificate subject's `serialNumber`
and rejected when it is absent or unsupported. Downstream live-read workflows
must also enforce the active-profile identity contract before using a verified
session.

A downstream caller may perform one bounded reauthentication after expiry or a
failed proof. A second failure is surfaced as a typed session error; callers do
not loop. Persisted state is validated and loaded through the encrypted session
repository before it is passed to the browser as an in-memory mapping.

## Rationale

The fixed protected resource proves the same browser, certificate, cookies,
origin, and authenticated access that downstream readers require. Keeping the
pytest opt-in separate from operational authorization avoids making an
environment variable a production permission system. Permanent write refusal
ensures that adding or changing authentication providers cannot create a legal
submission path.

## Consequences

- Live tests use `pytest.mark.aeat_live` and
  `CADRUMO_LIVE_TESTS_ENABLED=1`; the retired generic marker and former
  AEAT-prefixed live-test setting are not authoritative.
- Certificate construction uses typed credentials and one browser factory; no
  backend selector, marker, or configurable proof target remains.
- Session persistence is encrypted and bucket-routed; no arbitrary
  storage-state filesystem input participates in authentication.
- Live AEAT writes remain unreachable and unconfigurable.
