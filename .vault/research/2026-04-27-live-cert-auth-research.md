---
tags:
  - '#research'
  - '#live-cert-auth'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-12-cert-auth-research]]"
  - "[[2026-04-18-auth-protocol-research]]"
  - "[[2026-04-18-cert-provider-migration-research]]"
  - "[[2026-04-18-auth-provider-pending-items-audit]]"
  - "[[2026-04-18-cert-provider-migration-review-audit]]"
  - "[[2026-04-21-live-cert-auth-supersession-adr]]"
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

- `2026-04-18-cert-provider-migration-research` — surveyed PR #297's migration of
  certificate auth into `CertificateAuthProvider` with full `authenticate / resume /
  verify` implementations, a real async handshake worker, and Playwright
  `build_client_certificates_kwarg` wiring. Confirmed that every substantive artifact
  from PR #148's diff was already delivered on `main` by this migration.

- `2026-04-18-auth-provider-pending-items-audit` — enumerated open items after the
  cert-provider migration, including the thread-safety concern (`setattr` on Playwright
  `BrowserContext`) flagged in PR #148's review and confirmed still present on `main`
  via the `AEAT_CERTIFICATE_THUMBPRINT_MARKER` pattern.

- `2026-04-18-cert-provider-migration-review-audit` — code-review audit of PR #297,
  confirming the `os.environ`-mutation smell in PR #148's `load_certificate_from_settings`
  helper was absent from the merged implementation, validating the decision not to port
  that helper.

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
