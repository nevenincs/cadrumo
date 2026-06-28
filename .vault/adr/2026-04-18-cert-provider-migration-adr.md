---
tags:
  - "#adr"
  - "#cert-provider"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-18-cert-provider-migration-research]]"
  - "[[2026-04-18-auth-provider-ecosystem-research]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
---

# cert-provider-migration-adr

## status
Accepted — 2026-04-18. This acts as the execution-level ADR for the Certificate Provider Migration sub-task.

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
