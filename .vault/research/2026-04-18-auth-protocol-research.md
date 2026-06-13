---
tags:
  - "#research"
  - "#auth-protocol"
date: "2026-04-18"
modified: '2026-04-18'
related:
  - "[[2026-04-18-aeat-auth-providers-research]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-12-cert-auth-adr]]"
---

# auth-protocol research: issue-281 prerequisite refactor

Research for issue `#281` on generalising the current certificate-only AEAT authentication surface into a provider protocol plus provider-agnostic session and assertion contracts. This note narrows the broader same-day auth-provider research down to the concrete prerequisite refactor the codebase needs before any Cl@ve provider work can land safely.

## Findings

### current auth shape is centered on a certificate session, not on a provider contract

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` is both the auth facade and the home of the boundary records. `AeatAuthenticator` loads a certificate, verifies the handshake, constructs a browser context, and returns `AeatSession`.
- `AeatSession` currently hard-codes certificate details into the public contract: `certificate_thumbprint`, `certificate_subject`, `certificate_nif`, and `handshake`.
- `AeatLoginAssertion` is similarly certificate-shaped: `handshake_success`, `certificate_recognised`, `parsed_nif`, and `parsed_subject`.
- `AeatAuthenticator.authenticate()` always calls `load_certificate()` and `verify_handshake()` before it can create a context, which means the top-level auth surface cannot represent a provider that authenticates post-context via a form flow.

### browser context creation is coupled to a certificate object

- `BrowserSessionLike.create_context()` in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` and `BrowserSession.create_context()` in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` both accept `cert: LoadedCertificate | None`.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` injects `client_certificates` directly into `browser.new_context()` and stamps `_aeat_certificate_thumbprint` on the returned context.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_playwright_context.py` validates that marker and exposes `build_client_certificates_kwarg()`, which makes the browser seam certificate-specific even though only the context-construction phase truly needs provider-specific decoration.
- The existing contract shape points toward a more general `BrowserContextProvisioner` boundary: a certificate provider would supply context kwargs and marker metadata, while non-certificate providers would supply a no-op provisioner and perform the login inside the created context.

### the live-read and live-write policy gate is already provider-agnostic

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py` only models env policy and pytest refusal. It does not depend on certificate fields.
- The only production consumers are `src/aeat/entrypoints/cli/doctor.py` and `src/aeat/adapters/outbound/aeat/export/_engine.py`, both of which use the gate for environment state reporting rather than for certificate transport.
- The issue requirement to eradicate legacy env logic applies to modernized auth paths, but the current gate itself is not the wrong abstraction. The coupling problem is that downstream code still treats certificate loading as synonymous with “AEAT auth,” while the gate should remain orthogonal to provider selection.

### downstream protocols still depend on certificate-specific stubs

- `src/aeat/adapters/outbound/aeat/export/_protocols.py` defines `LoadedCertificate` and `CertificateBackend` stubs, then uses them in `SubmissionEngine` dependencies.
- `src/aeat/application/workflow/_protocols.py` imports `LoadedCertificate` from `aeat.adapters.outbound.aeat.export` and exposes `CertificateBundleProtocol.load() -> LoadedCertificate`.
- `src/aeat/status/_protocols.py` defines a `CertificateBackend` with `preload_into_browser_context()`, and `src/aeat/status/_reader.py` assumes authenticated access is obtained by preloading a context rather than by a provider login flow.
- `src/aeat/entrypoints/cli/submission/_helpers.py` and test modules across `submission`, `workflow`, and `status` build stub certificates directly, so the stub surface needs to move to provider-agnostic session/auth constructs without breaking current certificate behavior.

### direct `AEAT_LIVE_SUBMIT_ENABLED` handling is now small but still isolated from auth abstraction

- `src/aeat/adapters/outbound/aeat/export/_engine.py` still performs the authoritative inline live-write checks against `settings.aeat_live_submit_enabled` and `PYTEST_CURRENT_TEST`.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py` snapshots `AEAT_LIVE_SUBMIT_ENABLED` for audit state and exposes a defensive `require_live_write()`.
- `src/aeat/entrypoints/cli/doctor.py` reports `AEAT_LIVE_SUBMIT_ENABLED` through the gate snapshot.
- No other modernized auth path currently reads `AEAT_LIVE_SUBMIT_ENABLED`, which means the refactor should preserve the submission safety gate while ensuring provider selection and session modeling do not depend on that env var.

### tests will need contract-level updates, not behavioral rewrites

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py` asserts directly against `AeatSession` certificate fields and `AeatLoginAssertion` certificate-shaped fields.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py` asserts `client_certificates` wiring and the certificate thumbprint marker on the context.
- `src/aeat/adapters/outbound/aeat/export/test_engine.py`, `src/aeat/adapters/outbound/aeat/export/test_preflight.py`, `src/aeat/adapters/outbound/aeat/export/test_live_submission.py`, and `src/aeat/application/workflow/test_engine.py` each construct stub `LoadedCertificate` records or certificate backend stand-ins.
- The issue acceptance criteria imply two new test obligations on top of preserving the existing certificate behavior: a provider-protocol conformance test using a `NullAuthProvider`, and JSON round-trips for the provider-detail variants on the new session shape.

### direct implications for the prerequisite refactor

- The provider abstraction belongs in `src/aeat/auth`, not in `browser` or `submission`, because the coupling starts at the auth facade and the session/assertion records.
- `AeatAuthenticator` should stop being the long-term public abstraction. It can be reframed as the concrete certificate provider implementation, while a provider-agnostic selector/factory becomes the new package-level entry point.
- The generalized session contract needs a provider-agnostic core that all downstream code can rely on: provider kind, authenticated timestamps, storage-state location, and identity NIF.
- Provider-specific material should move behind discriminated detail records so current certificate metadata remains preserved without locking the public session shape to certificates.
- The browser seam should change once, at the context-construction boundary, so downstream consumers no longer type themselves against `LoadedCertificate`.

## Decision inputs for the ADR

- Keep `AeatAccessGate` as the env-policy layer; do not fold provider selection into it.
- Introduce a first-class `AuthProvider` protocol and `AuthProviderKind` enum in `src/aeat/auth`.
- Split `AeatSession` and `AeatLoginAssertion` into provider-agnostic cores plus discriminated provider-detail payloads.
- Generalize browser context creation from `cert=...` to a provisioner-based contract.
- Rebase-swap submission and workflow protocol stubs away from `LoadedCertificate` so downstream code depends on provider-agnostic contracts.

## consequences and follow-up

- The refactor is mechanically broad because it touches auth, browser, submission, workflow, status, CLI helpers, and multiple unit-test modules.
- It is still a bounded prerequisite: certificate behavior remains the only concrete implementation in scope for this issue, and all new provider work can stay deferred once the protocol and session contracts exist.
- The existing same-day umbrella research and ADR remain useful context, but issue `#281` needs its own narrower ADR and implementation plan because it is the sequencing gate for EPIC `#279`.
