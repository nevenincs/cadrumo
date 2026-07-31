---
tags:
  - "#adr"
  - "#cert-provider"
date: '2026-04-18'
modified: '2026-07-15'
body_hash: 'sha256:0a6d386e217205f0adf919f5f1068818ef86e83c377bf19a2ddd64d4bba8d25e'
related:
  - "[[2026-04-18-cert-provider-migration-research]]"
  - "[[2026-04-18-auth-provider-ecosystem-research]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
---

# cert-provider-migration-adr | (**status:** `rejected`)

## Rejected proposal provenance

This 2026-04-18 proposal was rejected. Its extraction design is retained only
to explain the rejected path and has no architectural force; the reconciliation
below names the implementation that actually landed. No consumer may resume or
recreate `CertificateAuthProvider` from this section.

## context
Following the `2026-04-18-auth-provider-abstraction-adr.md`, the AEAT authentication must be generalized to support multiple `AuthProvider` implementations, starting with `CertificateAuthProvider`. The existing certificate-specific implementation resides directly in `AeatAuthenticator` and `AeatSession`. We need to extract the certificate logic into its own provider and generalize the core session structures.

## decision

1. **Protocol Definition**: We will define the `AuthProvider` protocol and `AuthProviderKind` enum in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/provider.py`.
2. **Session Refactoring**: `AeatSession` will be updated to hold a `provider_detail` discriminated union. We will define `CertificateSessionDetail` with kind `AuthProviderKind.CERTIFICATE`. `identity_nif` will replace `certificate_nif` on the root of `AeatSession`.
3. **Module Restructuring**:
   - Move `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` to `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers/_certificate/certificate.py`.
   - Move `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/` to `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers/_certificate/_certificate_backends/`.
   - Implement `CertificateAuthProvider` in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers/_certificate/provider.py`.
4. **Facade Updates**: `AeatAuthenticator` will be refactored or kept as a thin facade/session manager that operates on an injected `AuthProvider` instead of hardcoding certificate loading. Or, if `AeatAuthenticator` is no longer the intended facade, we replace its functionality with the direct use of `AuthProvider`. Given the requirement to keep tests passing identically, we'll keep `AeatAuthenticator` backward-compatible if possible, or update tests to test `CertificateAuthProvider` directly.
5. **No Behavior Change**: The actual PKCS#12 parsing and Playwright integration will remain identical.

## consequences
- **Positive**: Certificate authentication will be completely decoupled from the core session management, fulfilling the prerequisite for adding Cl@ve providers.
- **Negative**: A large structural diff impacting imports and test paths.
- **Neutral**: The execution purely reorganizes existing logic without changing external behavior.

## Status

**Reverted — 2026-07-01 (issue #353).** This ADR's decision never landed as
described. The code review `2026-04-18-cert-provider-migration-review-audit`
(findings AUTH-001, AUTH-002) recorded that the extracted
`CertificateAuthProvider` shipped as a hollow shell — `authenticate()` and
`verify()` both raised `NotImplementedError` — and `AeatAuthenticator` was
never decoupled from the certificate path as Step 4 required. That hollow
shell was subsequently removed; at HEAD there are zero source references to
`CertificateAuthProvider` anywhere under `src/`.

The certificate `AuthProvider` implementation that actually shipped and lives
at HEAD is `AeatAuthenticator`
(`src/aeat/adapters/outbound/aeat/auth/_authenticator.py`, with
`kind = AuthProviderKind.CERTIFICATE`), landed via PR #295
(`refactor(auth): decouple AEAT auth provider protocol`) and PR #297
(`feat(auth): refactor cert auth into AuthProvider protocol (#282)`) — not via
this ADR's proposed `CertificateAuthProvider` extraction. The reconciliation
was first recorded on the sibling
`2026-04-21-live-cert-auth-supersession-adr` (Reconciliation section, issue
#353, commit `66b593290a`); this Status section extends the same
reconciliation to this ADR, the decision record the reverted extraction
actually originates from. Read every `CertificateAuthProvider` mention above
against `AeatAuthenticator`: no consumer should attempt to complete, resume,
or re-propose this extraction under the `CertificateAuthProvider` name.
