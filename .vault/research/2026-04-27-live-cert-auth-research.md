---
tags:
  - '#research'
  - '#live-cert-auth'
date: '2026-04-27'
modified: '2026-07-15'
related:
  - '[[2026-04-12-cert-auth-research]]'
  - '[[2026-04-18-auth-protocol-research]]'
  - '[[2026-04-21-live-cert-auth-supersession-adr]]'
---

# `live-cert-auth` research: supersession of issue-141 pr-148 by merged auth protocol work

Issue #141 tracked a live-cert-auth blocker: the operator PKCS#12 certificate could
complete an mTLS handshake but the Playwright browser layer did not attach it to a real
AEAT session, and no honest end-to-end read-only verification path existed. PR #148 was
filed to fix this. This research consolidates the evidence that led to declaring PR #148
superseded rather than merging it.

## Evidence base

The following documents form the evidence base consolidated here:

- `2026-04-12-cert-auth-research` — initial investigation into PKCS#12 certificate
  loading, mTLS handshake mechanics via the FNMT authority, and the original
  `AeatAuthenticator` facade. Established the requirement that the certificate must be
  wired into the Playwright `BrowserContext` via `client_certificates` and that NIF
  extraction from the FNMT subject is the correct identity assertion.

- `2026-04-18-auth-protocol-research` — documented the `AuthProvider` protocol
  design introduced by PR #295, including the `AeatLoginAssertion` and
  `CertificateSessionDetail` Pydantic records and the `AEAT_CERTIFICATE_THUMBPRINT_MARKER`
  context tag. This research made clear that the pre-protocol approach in PR #148 was
  targeting a facade that no longer existed on `main`.

- `2026-04-18-cert-provider-migration-research` — documented a proposed
  `CertificateAuthProvider` extraction target, not a completed migration. The
  standalone class was a rejected proposal and never decoupled certificate
  authentication from `AeatAuthenticator`.

- `2026-04-18-cert-provider-migration-review-audit` — findings `AUTH-001` and
  `AUTH-002` established that `CertificateAuthProvider.authenticate()` and
  `CertificateAuthProvider.verify()` remained a hollow shell of
  `NotImplementedError` methods. The class was removed. The current certificate
  `AuthProvider` implementation is `AeatAuthenticator`, exposing the canonical
  `authenticate()`, `verify()`, and `describe()` operations. `AuthProvider` has
  no `resume()` operation; `verify_handshake()` is a separate lower-level mTLS
  probe, not a provider verification alias.

- `2026-04-18-auth-provider-pending-items-audit` — records deferred follow-up
  work after the protocol change. It is not evidence that the certificate
  marker concern remained in the delivered implementation.

- `2026-04-21-live-cert-auth-supersession-adr` and the current source establish
  the execution comparison: the environment-mutating helper proposed by PR
  #148 was not retained, while PRs #295 and #297 delivered the protocol,
  Playwright certificate wiring, authentication flow, and gated live-test
  surface through `AeatAuthenticator`. PR #148 was therefore closed without
  porting the rejected standalone provider extraction.

## Consolidated finding

The research established that by the time PR #148 was ready for final review, PRs #295
and #297 had delivered the same scope — Playwright `client_certificates` wiring,
handshake worker, navigation-based login assertion, and gated live tests — against the
new `AuthProvider` protocol abstraction. PR #148's branch had diverged by dozens of
file deletions (the retired pre-protocol authenticator modules) and the only unique
artifact it carried was an ergonomic `aeat browser verify-cert` CLI command, whose
verification value was already covered by the gated live tests and any real
`AeatAuthenticator.authenticate()` invocation. The ADR closed PR #148 without merging
and resolved issue #141 via PR #297.
