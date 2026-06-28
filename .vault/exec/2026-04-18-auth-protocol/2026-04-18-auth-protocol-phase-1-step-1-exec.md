---
tags:
  - '#exec'
  - '#auth-protocol'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-auth-protocol-plan]]'
---

# `auth-protocol` `phase-1` `step-1`

Defined the provider-facing auth contracts and generalized the session/assertion records.

- Modified: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py`
- Modified: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`
- Created: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers.py`

## Description

Added `AuthProviderKind`, `AuthProviderDescription`, provider-detail models, and the `AuthProvider` / `BrowserContextProvisioner` protocols. Refactored `AeatSession` and `AeatLoginAssertion` into provider-agnostic cores with discriminated certificate detail payloads, while preserving compatibility accessors and legacy constructor shims for the existing certificate-backed tests and call sites.

## Tests

Validated the contract and compatibility behavior with `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py -q`. The suite now covers the provider-conformance path through a `NullAuthProvider` test and keeps the prior certificate-backed session/assertion scenarios green.
