---
tags:
  - '#adr'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-research]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-research]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-adr]]'
  - '[[2026-04-17-aeat-access-gate-adr]]'
  - '[[2026-04-17-session-persistence-adr]]'
  - '[[2026-04-16-live-cert-auth-adr]]'
---



# `live-iva-compensation-wallet` adr: `read-only live auth diagnostics and acquisition boundary` | (**status:** `accepted`)

## Problem Statement

The live IVA compensation feature depends on authenticated AEAT read access, but
the current operator experience can leave auth failures ambiguous. Missing
Cl@ve prompts, QR fallback, certificate gates, 403 pages, wrong profile
configuration, timeouts, and browser DOM drift can all look like generic
unavailability. That is not acceptable for a calculation chain that treats
AEAT state as binding external evidence.

The architecture also needs to prevent a CLI-first implementation from owning
the live behavior. CLI commands may launch acquisition, but the authoritative
read-only workflow must live in application services and outbound AEAT
adapters so tests, workflows, and later operator surfaces share one result
contract.

## Considerations

The existing live IVA and profile/bucket/repository research establishes that
AEAT wallet evidence, filed-history evidence, local recurrence, and taxpayer
override are separate source observations. It also establishes that a persisted
non-blocking reconciliation decision is the only remote-state value that may
affect Modelo 303.

The no-synthetic Sede research and ADR establish a hard input boundary: no
synthetic taxpayer, declaration, profile, counterparty, or form data may be sent
to AEAT-hosted surfaces. Live acquisition can only authenticate and retrieve
operator-owned read-only data.

The access-gate and session-persistence ADR trail already treats live AEAT
auth as a guarded browser/session concern. This ADR narrows that general
boundary for IVA wallet and filed-history acquisition.

## Constraints

No live filing, payment, represented-taxpayer selection, form confirmation, or
submission action is authorized.

No implementation may infer that the operator approved a Cl@ve request unless
the driver observes an authenticated read surface or another explicit success
signal.

Diagnostics must redact taxpayer identifiers, support-number values, profile
UUIDs, filing identifiers, expediente identifiers, token material, passphrases,
wallet amounts, and filed monetary values.

Tests must not hardcode the operator's private tax history as expected values.
Live tests may require operator approval, but they may persist only redacted
diagnostics and aggregate evidence shape.

## Implementation

Create a backend live acquisition service that owns the read-only flow:

1. Resolve the active profile and configured auth provider.
2. Produce a redacted preflight diagnostic for configured identity shape,
   support-number presence, certificate availability, Cl@ve preference, timeout,
   and active profile readiness.
3. Authenticate through the configured provider.
4. Classify the observed auth route as push, QR, non-QR fallback, certificate,
   already-authenticated, or unknown.
5. Fetch filed-history evidence for the requested models and years.
6. Attempt wallet/cartera acquisition when requested.
7. Return a typed result containing successful evidence and typed failures.
8. Persist redacted acquisition diagnostics through the active profile runtime
   when storage is available.

Introduce typed acquisition outcomes for authenticated, no prompt,
operator-timeout, QR required, certificate required, wrong identity, AEAT 403,
DOM drift, and unknown failure. Wallet failure must not erase filed-history
success.

Keep CLI output as a rendering of the backend result. CLI code must not own
separate auth, retry, wallet, or filed-history decision logic.

## Rationale

Separating acquisition from CLI rendering gives the codebase a single live-read
contract. It also makes failures testable without turning private AEAT data into
fixtures. The typed outcome taxonomy prevents the previous class of failures
where missing prompts, 403 pages, and unreadable wallet paths were collapsed
into vague unavailability.

The redacted preflight diagnostic is necessary because the operator is the only
person who can confirm a Cl@ve push. The system must therefore show enough
configuration shape for the operator to detect wrong-profile or missing-credential
setup before waiting.

## Consequences

Live acquisition becomes stricter and more verbose. Some previously tolerated
flows will now fail closed with typed outcomes.

The backend service must be usable by CLI, workflow, and tests. That may require
moving logic out of existing CLI modules.

Live tests become evidence-shape tests rather than private-value tests. This
reduces oracle strength for exact values, but prevents privacy leaks and
tautological tests built from the operator's own tax history.
