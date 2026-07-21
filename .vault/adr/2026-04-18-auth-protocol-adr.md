---
tags:
  - "#adr"
  - "#auth-protocol"
date: "2026-04-18"
modified: '2026-07-17'
related:
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-17-export-first-adr]]"
  - '[[2026-07-16-protected-browser-certificate-auth-adr]]'
  - '[[2026-07-16-protected-browser-certificate-auth-research]]'
---

# `auth-protocol` adr: `issue-281 auth-provider protocol and session-shape split` | (**status:** `accepted`)

## Problem Statement

Certificate and Cl@ve authentication share session acquisition, verification,
persistence, and ownership semantics, but their proof details differ. The
shared application boundary must remain provider-agnostic without duplicating
provider kind, certificate fields, browser construction, or cleanup policy in
downstream consumers.

## Decision

The layer-neutral `AuthProviderKind` and `AuthProviderDescription` records live
in `src/cadrumo/core/_auth_provider.py`. The sole application provider protocol
lives in `src/cadrumo/application/auth/__init__.py`:

```python
class AuthProvider(Protocol):
    kind: AuthProviderKind

    async def authenticate(self) -> AeatSession: ...
    async def verify(self, session: AeatSession) -> AeatLoginAssertion: ...
    def describe(self) -> AuthProviderDescription: ...
    async def close(self) -> None: ...
```

`close()` is mandatory. Every concrete provider owns the browser resources it
creates, bars new work once close intent exists, drains admitted work, and
releases its context and browser deterministically. Application orchestration
closes providers on success and failure and performs one bounded retry while a
provider retains failed cleanup handles.

`AeatSession` and `AeatLoginAssertion` live in
`src/cadrumo/adapters/outbound/aeat/auth/_authenticator_types.py`. Their common
fields are provider-neutral. Each carries a discriminated provider-detail
union whose `kind` field is the sole stored provider-kind authority;
`provider_kind` is only a projection. Certificate proof, Cl@ve landing data,
and other provider-specific evidence remain inside those detail records.

`BrowserSessionLike.create_context()` and the concrete `BrowserSession` accept
only keyword arguments for an optional `BrowserContextProvisioner` and an
optional in-memory `storage_state` mapping. A certificate provisioner
contributes Playwright `client_certificates` at construction time. Cl@ve
providers authenticate after construction. No auth contract accepts a
certificate object, auth backend, context marker, or storage-state filesystem
path.

The certificate implementation is `AeatAuthenticator`; no parallel
`CertificateAuthProvider` alias or extraction exists. Certificate validity is
the exact protected-resource browser proof governed by the related
protected-browser decision. Cl@ve Móvil and Cl@ve Permanente implement the same
application protocol with their own proof details.

Application `select_provider()` is the provider-construction choke point. It
passes already resolved `ActiveCertificateCredentials` to the outbound
certificate factory, preserving explicit absent secrets and preventing an
adapter from resolving a second credential source.

## Rationale

The split gives downstream code one lifecycle and session contract while
keeping provider-specific mechanics in the outbound adapter. A discriminated
detail union prevents parallel kind fields from drifting. A construction-only
browser provisioner keeps certificate material out of the generic browser and
lets every resume path use the same validated in-memory storage-state boundary.

## Consequences

- Application and live-read consumers depend on `AuthProvider`, not local
  protocol mirrors or certificate backends.
- Provider selection, typed credential resolution, browser ownership, and
  encrypted session persistence each have one authority.
- There are no compatibility aliases, rebase stubs, or transitional protocol
  shapes in this pre-release contract.
- Authentication never enables an AEAT write path; the independent access gate
  permanently refuses live writes.
