---
tags:
  - "#plan"
  - "#auth-protocol"
date: "2026-04-18"
modified: '2026-04-18'
related:
  - "[[2026-04-18-auth-protocol-research]]"
  - "[[2026-04-18-auth-protocol-adr]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
---

# `auth-protocol` `phase-1` plan

Implementation plan for issue `#281`, the session-shape refactor and `AuthProvider` protocol prerequisite for EPIC `#279`. This plan keeps the existing certificate behavior intact while removing certificate-only contracts from the shared auth engine and its downstream consumers.

## Proposed Changes

- Add the provider protocol and provider-kind catalogue to `src/aeat/auth`.
- Generalize the session and assertion records into provider-agnostic cores plus certificate detail variants.
- Shift the browser seam from `cert=...` to a provisioner-based context-construction contract.
- Reframe the current certificate flow as the concrete certificate provider.
- Rebase-swap submission and workflow protocol stubs away from `LoadedCertificate` and certificate-named backend surfaces.
- Update tests to assert protocol conformance, session round-trips, and unchanged certificate behavior.

## Tasks

- `Phase 1 - contract definition`
  1. Add provider-kind, provider-description, provider-detail, and provider protocol types in `src/aeat/auth`.
  2. Replace the top-level `AeatSession` and `AeatLoginAssertion` certificate fields with provider-agnostic cores plus discriminated certificate detail payloads.
  3. Update package exports so the new auth contract is available from `aeat.adapters.outbound.aeat.auth`.
- `Phase 2 - browser and provider migration`
  1. Replace the `create_context(cert=...)` seam with a provisioner contract in auth and browser session layers.
  2. Move certificate-specific context wiring and marker behavior behind the concrete certificate provider path.
  3. Reframe the current authenticator implementation as the certificate provider without broadening scope into new provider flows.
- `Phase 3 - downstream consumer migration`
  1. Update submission, workflow, CLI helper, and any other modernized stubs so they depend on provider-agnostic auth contracts instead of `LoadedCertificate`.
  2. Preserve the existing live-write gate behavior and doctor reporting, using `AeatAccessGate` only as the policy layer.
  3. Remove dangling certificate-only assumptions from the shared engine paths touched by this issue.
- `Phase 4 - tests, audit trail, and cleanup`
  1. Update unit tests for the new session/assertion shapes and browser seam.
  2. Add a protocol-conformance test using a `NullAuthProvider`.
  3. Add per-variant JSON round-trip coverage for the session model and confirm no modernized path still relies on `AEAT_LIVE_SUBMIT_ENABLED` for provider selection.

## Parallelization

This issue is `parallel-risky` and should be treated as effectively serial within the workspace. The only safe parallelism is context enrichment and read-only review. Code edits across auth, browser, submission, workflow, and tests should land as one coordinated batch.

## Verification

- Run focused unit tests covering `aeat.adapters.outbound.aeat.auth`, `aeat.adapters.outbound.aeat.browser`, `aeat.adapters.outbound.aeat.export`, and `aeat.application.workflow`.
- Run linting and type checking over the touched modules.
- Confirm certificate behavior remains intact in existing unit-test scenarios.
- Confirm the new `AeatSession` shape round-trips for every supported detail variant.
- Confirm the provider protocol conformance test passes.
- Confirm no modernized path outside the live-write safety gate uses `AEAT_LIVE_SUBMIT_ENABLED` as an authentication-selection mechanism.
