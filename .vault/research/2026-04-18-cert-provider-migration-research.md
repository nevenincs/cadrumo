---
tags:
  - "#research"
  - "#cert-provider"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
---

# cert-provider-migration-research

## Goal
Locate and analyze the existing `AeatAuthenticator` and `certificate.py` code in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/` to prepare for its refactoring into the `AuthProvider` protocol shape.

## Findings

1. **Current Structure**:
   - `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` contains `AeatAuthenticator`, which acts as the single entry point for live AEAT access using certificates. It handles the browser session creation, certificate loading, TLS handshake verification, and login assertion.
   - `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` and the `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/` directory handle the low-level PKCS#12 certificate parsing, loading, and Playwright integration.
   - `AeatSession` and `AeatLoginAssertion` are currently defined in `_authenticator.py` and are tightly coupled to certificates (e.g., they include `certificate_thumbprint`, `certificate_subject`, `certificate_nif`, and `handshake` fields directly on the root of the models).

2. **Target Shape (from ADR 2026-04-18-auth-provider-abstraction-adr)**:
   - `AuthProvider` protocol needs to be defined, with `kind`, `authenticate`, `describe`, and `verify` methods.
   - `AeatSession` needs to be generalized: `certificate_thumbprint`, `certificate_subject`, and `handshake` will move to a new `CertificateSessionDetail` model, which will be stored under a discriminated union `provider_detail` field on `AeatSession`. `certificate_nif` becomes `identity_nif` on the root session object.
   - `BrowserSessionLike` should be adjusted so `create_context` takes a `provisioner` callable instead of explicitly taking a `cert` argument.

3. **Required Actions**:
   - Move `certificate.py` and `_certificate_backends/` into `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers/_certificate/`.
   - Define `AuthProvider`, `AuthProviderKind`, and related protocols in a new module (e.g., `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/provider.py` or `_protocols.py`).
   - Create `CertificateAuthProvider` that implements `AuthProvider` by moving the logic currently inside `AeatAuthenticator` into it.
   - Refactor `AeatSession` to use `provider_detail` and define `CertificateSessionDetail`.
   - Update `AeatAuthenticator` (or replace its usage) to delegate to the provided `AuthProvider`. Wait, `AeatAuthenticator` may be deprecated or refactored to simply take an `AuthProvider` instead of being certificate-specific.
   - Update all corresponding tests (`test_authenticator.py`, `test_certificate.py`, etc.) to point to the new paths and account for the new `AeatSession` structure.
