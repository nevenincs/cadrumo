---
tags:
  - "#research"
  - "#live-cert-auth"
date: 2026-04-16
modified: '2026-04-16'
related:
  - "[[2026-04-12-cert-auth-research]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-16-live-cert-auth-adr]]"
  - "[[2026-04-21-live-cert-auth-supersession-adr]]"
---

> **PRESERVATION NOTE (apex-PM sweep, 2026-04-27):** This research was
> originally drafted in worktree `feature-117-live-cert` on 2026-04-16
> as the companion to `[[2026-04-16-live-cert-auth-adr]]` (PR #148,
> CLOSED unmerged 2026-04-21). The cert-auth design these documents
> describe was superseded by the AuthProvider abstraction landed via
> PRs #295 / #297 — see `[[2026-04-21-live-cert-auth-supersession-adr]]`.
> **Preserved here for design-rationale provenance** alongside the
> companion ADR. Do NOT implement against this research.

# live-cert-auth research: issue-141 live certificate auth setup and verification

This note narrows issue #141 to the concrete gap between PKCS#12 parsing
and a real Playwright-authenticated AEAT session, then separates that from
the safe read-only verification path and the CLI/operator workflow that can
follow once the certificate material is actually present.

## Findings

- Existing PKCS#12 handling is real and already verified by tests. `aeat.adapters.outbound.aeat.auth.load_certificate()` parses the bundle into a frozen `LoadedCertificate`, `verify_handshake()` performs an opt-in mTLS GET, and the `HTTPX_FALLBACK` backend writes only temporary PEM material that it deletes on exit. That confirms the bundle can be loaded and used for a TLS handshake, but it does not prove the browser session can present the same cert to AEAT.
- The browser/session gap is in wiring, not in parsing. `aeat.adapters.outbound.aeat.browser.session.BrowserSession.create_context()` launches Playwright and builds a context, but its `auth_backend` branch is still a stub, it never passes `client_certificates` to `browser.new_context()`, and it never sets the thumbprint marker that `PlaywrightContextBackend.preload()` expects. The existing `build_client_certificates_kwarg()` helper is therefore necessary but still unused.
- `aeat.status.StatusReader` already expresses the intended contract for live AEAT reads. It accepts a `CertificateBackend` Protocol, calls `preload_into_browser_context()` before the first navigation, and `fetch_expedientes()` is the only fully wired live surface. The other `fetch_*` methods still raise `StatusReaderError`, so exposing them in the CLI before their parsers exist would create dead-end commands.
- The current `aeat status` CLI is hidden wholesale. `src/aeat/entrypoints/cli/status/__init__.py` marks every command `hidden=True` and exits with code 2 via `_bail_cert_missing()`. Given the reader state, the sensible unhide target is `expedientes` only once the Playwright cert path is real; the other status commands should stay hidden until their reader methods stop being stubs.
- Safe live verification can stay read-only at two layers. First, run `verify_handshake()` against `AEAT_CERTIFICATE_VERIFY_URL` to confirm AEAT accepts the client cert at TLS time. Second, run one `StatusReader.fetch_expedientes()` pass in a live session and compare only the returned filing list. No AEAT write path is required for this blocker, and the anti-bot runbook still applies: do not bypass challenges, do not rotate proxies aggressively, and honor rate limiting.
- The issue thread constrains the operator workflow. The issue body explicitly asks for investigation, fix, and verification only, and the latest audit comment says the current environment has no `AEAT_CERTIFICATE_PATH` and no `AEAT_CERTIFICATE_PASSWORD_SECRET`, so a sanctioned client-certificate session cannot be established yet. That comment also defines the next safe sequence: provide the real `.p12` and passphrase, run certificate handshake verification, then run one read-only `StatusReader.fetch_expedientes()` pass.
- `aeat.entrypoints.cli.doctor` already has a certificate health row, which is useful as a preflight check for path, password, and expiry, but it is not a live AEAT acceptance test. The live test modules reinforce the same split: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate_live.py` is a gated handshake smoke test, while `src/aeat/status/test_live.py` is still an intentional skip placeholder until the cert-backed reader path lands.

## Recommendation

- Treat issue #141 as a browser-integration and operator-verification problem, not a PKCS#12 parsing problem.
- Unhide and wire the status CLI for `expedientes` only once the Playwright context can actually receive the certificate.
- Keep verification read-only: handshake probe first, then `fetch_expedientes()`, then stop unless the live result disagrees with expectations.
