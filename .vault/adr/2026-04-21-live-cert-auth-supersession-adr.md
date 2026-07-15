---
tags:
  - "#adr"
  - "#live-cert-auth"
date: '2026-04-21'
related:
  - '[[2026-04-18-auth-protocol-adr]]'
  - '[[2026-04-18-auth-provider-abstraction-adr]]'
  - '[[2026-04-27-live-cert-auth-research]]'
supersedes:
  - '2026-04-16-live-cert-auth-adr'
modified: '2026-07-15'
---
# `live-cert-auth` adr: `issue-141 pr-148 superseded by the landed AuthProvider implementation` | (**status:** `accepted`)

## Problem Statement

Issue #141 ("P1-Blk: Live AEAT Certificate Auth Setup and Verification") tracked a
blocker: the operator certificate could load and complete an mTLS handshake, but
the Playwright browser layer did not attach that certificate to a real AEAT
session, and no honest read-only live verification path existed end-to-end.

PR #148 (`feature/117-live-cert`) proposed a concrete fix: wire the loaded
PKCS#12 bundle into `BrowserSession.create_context`, add an `aeat browser
verify-cert` CLI that runs handshake + a read-only `fetch_expedientes()` pass,
and promote the placeholder live status-reader test to a real gated smoke test.

Between PR #148's review cycle and now, `main` advanced with two merged PRs
that replaced the authenticator layer wholesale:

- PR #295 — `refactor(auth): decouple AEAT auth provider protocol` (merged
  2026-04-18). Introduced the `AuthProvider` protocol in
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_protocols.py`, the `AeatLoginAssertion` +
  `CertificateSessionDetail` pydantic records, and the
  `AEAT_CERTIFICATE_THUMBPRINT_MARKER` context tag.
- PR #297 — `feat(auth): refactor cert auth into AuthProvider protocol (#282)`
  (merged 2026-04-18). Landed `CertificateAuthProvider` at
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers/_certificate/provider.py` with full
  `authenticate / resume / verify` implementations, a real handshake worker
  executed via `asyncio.to_thread`, Playwright `client_certificates` wiring
  through `build_client_certificates_kwarg`, and a navigation-based login
  assertion returning `AeatLoginAssertion`.

Additionally, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator_live.py` (merged under #167 / PR
#181, still present on `main`) already runs the full end-to-end live flow
gated on `AEAT_LIVE_TESTS_ENABLED=1`:

1. Health severity gate (OK or WARN).
2. Real mTLS handshake via `AeatAuthenticator.verify_handshake()`.
3. Cert load + NIF extraction from the FNMT subject.
4. A full async `authenticate()` + `verify()` pass driven by real
   `async_playwright` — no mocks, patches, or monkey-patched attributes.

The gated live cert smoke test at `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate_live.py` covers
the lower-level handshake path.

## Considerations

- The whole-of-scope of issue #141 — "investigate current certificate setup,
  fix bugs, implement a robust verification step, ensure no writes" — is
  already delivered on `main` by PR #295 + PR #297 + the live test surface
  from PR #181.
- PR #148 was authored against the pre-#295 authenticator. Its primary
  artifacts — wiring `client_certificates` into `BrowserSession`, tagging the
  context with the cert thumbprint, running handshake + navigation
  verification — are exactly what `CertificateAuthProvider.authenticate` and
  `CertificateAuthProvider.verify` now do. Landing PR #148 would duplicate
  that logic against a now-nonexistent facade (`AeatAuthenticator` was rewired
  around `AuthProvider`).
- PR #148 also carried a `load_certificate_from_settings` helper that mutated
  `os.environ` globally inside a `try/finally` — a thread-safety smell that
  Gemini's review flagged. The equivalent bridge on `main` does not need that
  helper: `CertificateBundle` is constructed directly from `Settings` inside
  `AeatAuthenticator._require_bundle`, and `pydantic-settings` handles
  env loading once at startup. The obsolete helper is not worth porting.
- PR #148's `aeat browser verify-cert` CLI command is the only sliver of the
  diff that has no analogue on `main`. That command wraps
  `load_certificate + verify_handshake + one read-only StatusReader pass` into
  an on-demand CLI. Its value is ergonomic only: the same verification already
  runs via the gated live tests and via `AeatAuthenticator.authenticate`
  during any real authenticator invocation. Any future CLI convenience should
  be scoped as a small follow-up issue against `AeatAuthenticator` —
  not resurrected from PR #148's pre-protocol diff.
- PR #148's branch has diverged from `main` by dozens of file deletions (the
  now-retired `_authenticator.py`, `_gate.py`, `_models.py`, `_protocols.py`
  rewrites) and three PR reviewers have not re-engaged. Attempting a rebase
  would produce a near-total rewrite with no residual value beyond the CLI
  command noted above.

## Decision

- **Close PR #148 without merging.** Its scope is fully superseded by merged
  PRs #295 and #297. No code from PR #148 is ported forward; no rebase is
  attempted.
- **Close issue #141 as resolved-by-#297.** The live-verification
  requirement is satisfied in `main` by `CertificateAuthProvider.authenticate`
  + `CertificateAuthProvider.verify` + the gated
  `test_authenticator_live.py` / `test_certificate_live.py` tests.
- **Do not port the `aeat browser verify-cert` CLI** in this ADR's scope.
  If an on-demand CLI verifier is still desired, file a new issue scoped as a
  thin wrapper around `AeatAuthenticator.authenticate` and
  `AeatAuthenticator.verify`; it must not reintroduce the
  `load_certificate_from_settings` helper or its environment-mutation
  pattern.
- **No other code changes are proposed by this ADR.** The Gemini-flagged
  `setattr` concern against Playwright `BrowserContext` carries over to
  `main`'s use of `AEAT_CERTIFICATE_THUMBPRINT_MARKER`, but addressing it is
  out of scope here — track as a separate hardening issue if warranted.

## Consequences

- **Positive:** Avoids merging 961 lines of duplicated / superseded logic and
  sidesteps the thread-safety smell flagged in PR #148 review.
- **Positive:** Issue #141 is closed with a clear provenance trail
  (this ADR → #297 → `CertificateAuthProvider.verify`).
- **Negative:** Operators lose the proposed ergonomic `aeat browser
  verify-cert` command. Mitigation: the gated live tests and any invocation
  of `AeatAuthenticator.authenticate` already perform the same verification.
- **Neutral:** The `feature/117-live-cert` worktree and branch become
  abandoned; history remains available via the closed PR.

## Reconciliation (issue #353, 2026-07-01)

The certificate-provider extraction described above and in
`2026-04-18-cert-provider-migration-adr` did not land as a standalone
`CertificateAuthProvider` symbol. The review audit
`2026-04-18-cert-provider-migration-review-audit` (findings AUTH-001 and
AUTH-002) recorded the extracted provider as a hollow shell whose
`authenticate()` and `verify()` raised `NotImplementedError`, and
`AeatAuthenticator` was never decoupled from the certificate path. That shell
was subsequently removed. At HEAD there are zero source references to
`CertificateAuthProvider`.

The live certificate `AuthProvider` implementation is `AeatAuthenticator`
(`src/aeat/adapters/outbound/aeat/auth/_authenticator.py`, with
`kind = AuthProviderKind.CERTIFICATE`). Read every `CertificateAuthProvider`
mention above against the real surface: `CertificateAuthProvider.authenticate`
is `AeatAuthenticator.authenticate`, and historical
`CertificateAuthProvider.verify` references map solely to
`AeatAuthenticator.verify`. `AeatAuthenticator.verify_handshake` remains a
separate lower-level certificate helper, not a provider-verification alias. The
decisions this ADR records — close PR #148, close issue #141 — are unaffected by
the naming reconciliation.
