---
tags:
  - "#adr"
  - "#live-cert-auth"
date: 2026-04-16
modified: '2026-04-16'
related:
  - "[[2026-04-16-live-cert-auth-research]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-12-status-reader-adr]]"
  - "[[2026-04-21-live-cert-auth-supersession-adr]]"
---

> **PRESERVATION NOTE (apex-PM sweep, 2026-04-27):** This ADR was
> originally authored in worktree `feature-117-live-cert` on 2026-04-16
> for PR #148 (CLOSED unmerged 2026-04-21). The cert-auth design
> described here was superseded by the AuthProvider abstraction landed
> via PRs #295 / #297 — see the supersession ADR
> `[[2026-04-21-live-cert-auth-supersession-adr]]` for the canonical
> follow-on design that main now carries. **Preserved here for
> design-rationale provenance** — main's supersession ADR summarizes
> WHY this approach was abandoned but does not reproduce the original
> design in full. Do NOT implement against this ADR.

# `live-cert-auth` adr: `issue-141 live certificate auth stabilization and verification` | (**status:** `superseded` *(originally `accepted`; superseded 2026-04-21 by AuthProvider abstraction)*)

## Problem Statement

Issue #141 is not blocked by PKCS#12 parsing anymore. The current blocker is
that the existing certificate code can prove a bundle loads and can complete
an mTLS handshake, but the Playwright browser layer still does not attach that
certificate to a real AEAT session, and the only honest read-only live
verification path remains partly hidden behind placeholder CLI and live-test
surfaces.

## Considerations

- `aeat.adapters.outbound.aeat.auth.load_certificate()` and `verify_handshake()` already provide real
  PKCS#12 and mTLS behavior, so replacing that layer would be unnecessary
  churn.
- `aeat.adapters.outbound.aeat.browser.session.BrowserSession.create_context()` already owns the
  `browser.new_context(...)` call site, which is the only place Playwright can
  accept `client_certificates`.
- `aeat.status.StatusReader.fetch_expedientes()` is the only fully wired
  authenticated read surface today. The other status-reader methods still
  raise intentional stubs.
- The environment on 2026-04-16 still resolves no configured
  `AEAT_CERTIFICATE_PATH` and no `AEAT_CERTIFICATE_PASSWORD_SECRET`, so the
  final live proof cannot be fabricated locally and must degrade honestly until
  the operator material exists.
- The safety charter forbids live AEAT writes for this blocker. Verification
  must stop after read-only handshake and filing-history reads.

## Constraints

- The change must remain additive inside the existing `aeat.adapters.outbound.aeat.auth`,
  `aeat.adapters.outbound.aeat.browser`, `aeat.status`, and CLI package boundaries.
- No new write path to AEAT may be introduced.
- Only the `expedientes` status surface may be exposed as live-ready in this
  slice; the other status surfaces must stay hidden or stubbed until their
  parsers land.
- Tests must remain real-behavior tests. No mocks, patches, or fake network
  calls as a shortcut for the live/browser path.

## Implementation

- `BrowserSession` will accept a loaded certificate object and, when present,
  translate `aeat_base_url` into a Playwright `origin`, pass
  `client_certificates=[...]` into `browser.new_context(...)`, and tag the
  resulting context with the expected thumbprint marker so later validation
  stays explicit.
- The concrete certificate behavior will stay in `aeat.adapters.outbound.aeat.auth`, not move into
  `aeat.status`. The loaded certificate object will expose the
  `preload_into_browser_context(...)` behavior the status-reader seam already
  expects, so the existing reader Protocol can consume the real auth object
  without introducing a second package-local backend.
- The explicit user-facing verification entry point will be a browser-layer
  diagnostic command that runs the two safe checks in sequence: first the
  existing handshake probe, then one read-only `fetch_expedientes()` pass
  through a real Playwright session. Failures in the handshake and read phases
  will stay distinguishable.
- The live verification gate will remain the existing
  `@pytest.mark.live` plus `AEAT_LIVE_TESTS_ENABLED=1` contract. The current
  status live placeholder will be replaced with a real gated
  `fetch_expedientes()` smoke test that uses the same certificate-backed
  browser path and skips honestly when operator certificate material is absent.

## Rationale

This option reuses the strongest parts of the current architecture instead of
reopening already-solved areas. The existing auth code already owns PKCS#12
loading, secret discipline, handshake probing, and the concrete Playwright
backend; the browser session already owns Playwright context construction; and
the status reader already owns the read-only AEAT filing-history workflow.
Wiring those three layers together is the shortest path that satisfies issue
#141 without expanding into unrelated status-surface or submission work.

## Consequences

- The browser package becomes the single sanctioned place where Playwright
  client certificates are attached, which reduces the risk of duplicate
  one-off context factories elsewhere.
- `fetch_expedientes()` becomes the canonical read-only live verification
  target for certificate-backed AEAT sessions.
- The final live proof remains operationally blocked until real certificate
  material is configured, but the codebase will stop pretending that the
  browser path is unwired.
- The rest of the status CLI remains intentionally deferred; this ADR does not
  widen scope to unfinished status-reader surfaces.
