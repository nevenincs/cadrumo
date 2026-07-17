---
tags:
  - '#adr'
  - '#aeat-auth-providers'
date: '2026-04-18'
modified: '2026-07-17'
related:
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-17-export-first-adr]]"
  - '[[2026-07-16-protected-browser-certificate-auth-adr]]'
  - '[[2026-07-16-protected-browser-certificate-auth-research]]'
---

# auth-provider-abstraction-adr | (**status:** `accepted`)

## Problem Statement

AEAT Sede users may authenticate with a PKCS#12 certificate or a Cl@ve
credential. The application needs one session-acquisition contract without
making certificate loading, form-driven login, or phone approval part of every
consumer. Provider generalisation must not create parallel credential,
persistence, browser, or write-policy paths.

## Decision

AEAT authentication uses the application-owned `AuthProvider` protocol. The
implemented and reserved inventory is:

| Provider | Runtime state | Automation envelope |
| --- | --- | --- |
| `AeatAuthenticator` (`certificate`) | Implemented | Headless protected-browser proof |
| `ClavePermanenteAuthProvider` | Implemented | Headless read-path login |
| `ClaveMovilAuthProvider` | Implemented | Browser drive plus per-session phone approval |
| `clave_pin` | Reserved catalogue entry | No runtime provider |

Reserved catalogue entries describe operator-visible availability; they are
not provider implementations or engineering commitments. DNI electrónico and
eIDAS require separate accepted decisions before they can join the catalogue.

Every implemented provider has the same mandatory surface:

```python
class AuthProvider(Protocol):
    kind: AuthProviderKind

    async def authenticate(self) -> AeatSession: ...
    async def verify(self, session: AeatSession) -> AeatLoginAssertion: ...
    def describe(self) -> AuthProviderDescription: ...
    async def close(self) -> None: ...
```

`AeatSession` contains provider-neutral timestamps, identity, and encrypted
session object identity plus a discriminated provider detail. The detail's
`kind` is the sole stored provider-kind authority. Certificate thumbprint,
subject, and protected-resource evidence remain certificate detail; Cl@ve data
remains in its corresponding detail. Session records carry no password,
private key, QR payload, or browser cookie payload.

The application layer owns provider selection. It resolves one active bucket,
workflow state, and typed `ActiveCertificateCredentials` snapshot before
constructing the certificate provider. The outbound factory requires those
credentials explicitly and never resolves another named secret or inherited
global password.

Browser creation remains auth-agnostic. A provider receives a
`BrowserSessionFactory`; `BrowserSession.create_context()` accepts an optional
construction-only provisioner and optional validated in-memory storage state.
Certificate auth supplies a provisioner for Playwright
`client_certificates`; Cl@ve authenticates after context creation. Every
provider owns and closes the context and browser it creates.

For Cl@ve, selector-page reachability is not authentication proof. A successful
real browser flow records the concrete authenticated application landing URL;
host rotation must be observed from that flow rather than replaced with a
static host assumption. Cl@ve Móvil additionally requires fresh phone approval
for each new session.

Session persistence is provider-independent at the repository boundary. Each
provider has a distinct logical key under the active bucket, but all use the
same encrypted `PersistedBrowserSession` envelope and
`SecureObjectRepository` namespace. Switching providers requires a new login;
sessions are never merged.

## Policy boundary

`AeatAccessGate` remains independent of provider selection. Under pytest, live
reads require the `aeat_live` marker and the exact
`CADRUMO_LIVE_TESTS_ENABLED=1` opt-in. Operator reads proceed through profile,
credential, identity, authentication, and read-only workflow guards. Live AEAT
writes are permanently forbidden for every provider.

Protocol-shaped local choreography tests, including tests driven by a
handwritten browser substitute, are not live authentication proof. Only the
concrete provider running through the production browser boundary under the
gated live-test contract can establish live AEAT/Cl@ve authentication; required
operator or phone approval remains part of that boundary.

## Operator surface

Provider configuration is exposed through the current `config auth` command
family. The CLI grammar is governed by the later CLI workflow decision, not by
this provider architecture record.

## Rationale

One provider protocol lets application workflows acquire and verify sessions
without knowing how the identity was proved. Typed provider details preserve
provider-specific evidence without widening the common contract. Central
selection, encrypted persistence, and mandatory cleanup prevent provider
plugins from becoming alternate authorities for credentials or browser state.

## Consequences

- Certificate, Cl@ve Permanente, and Cl@ve Móvil share application orchestration
  but retain distinct outbound authentication mechanics.
- Adding a provider requires a catalogue decision, a protocol implementation,
  encrypted persistence metadata, deterministic cleanup, and real-behavior plus
  gated-live proof.
- Cl@ve passwords remain `SecretStr` inputs and never enter session records or
  logs.
- No provider implies or preserves a future live-submit capability.
