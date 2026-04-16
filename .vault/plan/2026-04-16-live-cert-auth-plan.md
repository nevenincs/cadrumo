---
tags:
  - "#plan"
  - "#live-cert-auth"
date: 2026-04-16
related:
  - "[[2026-04-16-live-cert-auth-adr]]"
  - "[[2026-04-16-live-cert-auth-research]]"
  - "[[2026-04-12-cert-auth-plan]]"
  - "[[2026-04-12-status-reader-plan]]"
---

# `live-cert-auth` `phase1` plan

Stabilize the live AEAT certificate path by connecting the existing PKCS#12
auth layer to real Playwright contexts, then expose one honest read-only
verification flow that proves AEAT accepts the certificate and that one real
authenticated read surface works without performing any writes.

## Proposed Changes

- Wire the existing certificate model into the browser session so
  `browser.new_context(...)` can receive the Playwright
  `client_certificates` kwarg and the resulting context can be validated by
  the existing thumbprint-based auth contract.
- Align the existing status-reader certificate seam with the real auth object
  so `StatusReader` can consume the loaded certificate directly rather than
  relying on a package-local placeholder backend.
- Add one verification surface that runs the low-level handshake probe and one
  read-only `fetch_expedientes()` pass through a real Playwright session, with
  clear phase-specific failures.
- Replace the live status placeholder with a real gated live read test and add
  the missing browser-session regression coverage for certificate-aware context
  creation.

## Tasks

- `Phase 1 — Browser context wiring`
  1. Update the browser session so a loaded certificate is translated into the
     Playwright `client_certificates` context option.
  1. Tag the created context with the expected certificate thumbprint so the
     existing validation hook can confirm the session was created correctly.
  1. Add browser-session tests covering certificate-aware context creation.
- `Phase 2 — Status-reader integration`
  1. Align the reader-side certificate Protocol with the real loaded
     certificate surface exposed by `aeat.auth`.
  1. Reuse that real auth object from the read-only verification path.
  1. Keep the unfinished status-reader surfaces hidden or stubbed.
- `Phase 3 — Verification surface`
  1. Add one user-facing verification command that runs the handshake probe
     first and the read-only `fetch_expedientes()` pass second.
  1. Surface clear exit behavior and machine-readable output so operators can
     tell whether failure happened at certificate loading, mTLS handshake, or
     authenticated read.
  1. Keep the verification strictly read-only and stop before any submission or
     inbox mutation path.
- `Phase 4 — Live and unit verification`
  1. Replace the status live-test placeholder with a real gated live
     `fetch_expedientes()` smoke test that skips honestly when cert material is
     absent.
  1. Run targeted unit tests for browser, status, and CLI verification paths.
  1. Run the relevant lint and type-check gates on the changed files.
- `Phase 5 — Vaultspec execution and review`
  1. Persist execution step records and the phase summary for this slice.
  1. Run the mandatory code-review pass and address any material findings.
  1. Update branch/PR metadata with the new artifact links and the current live
     verification constraint if certificate material is still absent.

## Parallelization

The browser-session change and the verification CLI can proceed in parallel
once the certificate-adapter shape is fixed, but the live test should wait
until the browser wiring and verification surface are both in place. The audit
and review work can run in parallel with final test execution.

## Verification

- Browser-session unit coverage proves the Playwright context receives the
  certificate data and the context marker.
- The verification command reports success only when the handshake probe
  succeeds and the read-only `fetch_expedientes()` pass completes without
  auth or parse errors.
- The live status smoke test is real and read-only. It must skip clearly when
  the operator certificate material is absent, and otherwise exercise the real
  cert-backed browser path.
- Targeted `pytest`, lint, and type-check runs pass for the touched modules.
- If the environment still lacks `AEAT_CERTIFICATE_PATH` or
  `AEAT_CERTIFICATE_PASSWORD_SECRET`, the code and tests must state that
  honestly rather than fabricating a final live-green result.
