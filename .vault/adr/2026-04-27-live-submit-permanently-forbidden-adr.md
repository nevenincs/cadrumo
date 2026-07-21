---
tags:
  - '#adr'
  - '#live-submit-permanently-forbidden'
date: '2026-04-27'
modified: '2026-07-17'
related:
  - '[[2026-04-27-live-submit-permanently-forbidden-research]]'
  - '[[2026-04-27-security-storage-audit-audit]]'
  - '[[2026-04-18-auth-provider-abstraction-adr]]'
---

# Live AEAT submission is permanently forbidden | (**status:** `accepted`)

## Decision

Cadrumo never performs a live AEAT write or submission. The supported product
flow is produce, verify, export, then let the operator upload through the
official portal.

`cadrumo.core.access_gate.AeatAccessGate.require_live_write()` is the canonical
unconditional safety guard. It always raises `LiveSubmitForbiddenError`. The
method is active policy, not a compatibility shim, deprecation surface, feature
flag, or future extension point.

## Constraints

- No environment variable, setting, CLI option, test marker, confirmation, or
  authentication state can enable a live write.
- Any path that could attempt an AEAT-side mutation must call the guard and
  receive the typed refusal, or remove the mutation path entirely.
- Live-read authentication and read-only portal navigation remain supported and
  are governed separately by `require_live_read()` and the authentication
  boundaries.
- Local calculation, preflight, verification, draft generation, export, and
  sealed review-package creation remain supported. Their existence does not
  imply a remote transport.
- Tests must exercise the production guard and public write-attempt surfaces;
  source introspection or a duplicated refusal implementation is not sufficient
  evidence.

## Rationale

AEAT has no harmless submission sandbox: a successful write can be legally
binding. An unconditional policy boundary is therefore safer and clearer than
a dormant transport hidden behind multiple gates. Keeping the guard provides a
single typed, auditable failure wherever a caller attempts a prohibited action;
deleting it would weaken the architecture.

## Consequences

Live-write compatibility code, opt-in settings, dual-mode transports, and
planned reintroduction dates are prohibited. Authentication work serves
read-only operations and is never a stepping stone to submission. Product and
operator surfaces describe export and manual upload only.
