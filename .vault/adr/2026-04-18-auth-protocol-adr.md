---
tags:
  - "#adr"
  - "#auth-protocol"
date: "2026-04-18"
modified: '2026-04-18'
related:
  - "[[2026-04-18-auth-protocol-research]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-17-export-first-adr]]"
---

# `auth-protocol` adr: `issue-281 auth-provider protocol and session-shape split` | (**status:** `accepted`)

## Problem Statement

Issue `#281` is the prerequisite refactor for EPIC `#279`. The current AEAT auth surface is centered on a certificate session shape rather than on a provider contract. `AeatAuthenticator`, `AeatSession`, `AeatLoginAssertion`, and `BrowserSessionLike.create_context(cert=...)` all assume that AEAT authentication means “load a certificate, verify the handshake, then build a browser context.” That assumption blocks any future provider whose login flow happens after context creation and forces downstream consumers to depend on certificate-specific stubs.

## Considerations

- Existing certificate behavior must remain intact because it is already used by live-read and submission-adjacent surfaces.
- The export-first charter keeps live-write policy separate from authentication choice. Provider selection must not weaken or replace the existing live-write gate.
- `storage_state_path` and the session idle TTL are already provider-agnostic concepts and should remain part of the shared session core.
- Submission, workflow, and status modules still compile against in-flight protocol stubs, so the refactor must provide a rebase-safe migration path.
- The issue acceptance criteria require a protocol conformance test and per-variant session JSON round-trips.

## Constraints

- This issue does not implement Cl@ve or any other new provider. It defines the abstraction and migrates the core engine away from cert-only shapes.
- The modernized path must not introduce a new default-enabled live-write flow or change the existing charter-backed submission refusal semantics.
- The change must remain incremental enough that downstream callers can continue to operate with the existing certificate implementation while the provider epic lands in follow-up issues.

## Implementation

- Introduce `AuthProviderKind`, `AuthProvider`, and provider-description/detail models in `src/aeat/auth`.
- Reframe the current certificate implementation as the concrete certificate provider behind that protocol.
- Split `AeatSession` into provider-agnostic fields plus a discriminated `provider_detail` payload. The core fields are `provider_kind`, `identity_nif`, `authenticated_at`, `idle_deadline`, and `storage_state_path`.
- Split `AeatLoginAssertion` the same way: provider-agnostic validity and timing fields plus a discriminated assertion-detail payload. Certificate-specific handshake and subject material move into the certificate detail record instead of staying at the top level.
- Replace `BrowserSessionLike.create_context(cert=...)` with a provisioner-based seam. The browser layer will accept an optional provisioner that can contribute `new_context()` kwargs and context markers. The certificate provider will supply the current `client_certificates` behavior through that seam.
- Rebase-swap downstream protocol stubs in `submission`, `workflow`, and related helpers away from `LoadedCertificate` so they depend on provider-agnostic contracts.
- Keep `AeatAccessGate` as the env-policy layer and continue using it for audit snapshots and doctor output. The gate remains orthogonal to provider selection.

## Rationale

This is the smallest architectural change that unlocks pluggable auth providers without destabilizing current certificate behavior. It moves provider-specific material behind explicit detail records, keeps the browser seam focused on context construction, and prevents submission/workflow/status code from hard-coding certificate-shaped dependencies. The result is a stable core auth contract that future providers can implement without rewriting shared engine code.

## Consequences

- `src/aeat/auth`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py`, `src/aeat/adapters/outbound/aeat/export/_protocols.py`, `src/aeat/application/workflow/_protocols.py`, and their tests will all need coordinated edits.
- The certificate provider becomes the first concrete implementation of the new protocol, so some current names and exports will shift even though the observable behavior should remain unchanged.
- Transitional translation code may exist briefly while downstream modules move from `LoadedCertificate`-based seams to provider-agnostic contracts.
- The issue will leave follow-on work for the concrete Cl@ve providers, doctor/provider UX, and any status/sync surfaces that still assume certificate preloading as the only authenticated path.
