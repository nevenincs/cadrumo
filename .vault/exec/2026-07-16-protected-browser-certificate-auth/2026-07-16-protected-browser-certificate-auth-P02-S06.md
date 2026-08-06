---
tags:
  - '#exec'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-17'
body_hash: 'sha256:42fc29c9b2cec8cb106680a0ca74c7f58f4bf2634fa8695effe3baa74ecaf4a2'
step_id: 'S06'
related:
  - "[[2026-07-16-protected-browser-certificate-auth-plan]]"
---
# Serialize concurrent provider closure so the drain barrier cannot tear down newly admitted work

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`
- `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py`
- `src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente.py`

## Description

- Share one counted close-intent barrier across certificate, Cl@ve Movil, and Cl@ve Permanente providers.
- Admit authentication and verification only through the barrier's work lease.
- Serialize every closer until admitted work drains, and require verification to use the provider's exact retained session identity.

## Outcome

A queued closer keeps new work barred until all registered close intents finish, and teardown cannot race a newly admitted verification on any implemented provider.

## Notes

Fresh semantic search resolved the shared `_CloseIntentBarrier` and all three provider integrations. The real provider lifecycle matrix, included in the 44-test focused run, covered exact-session refusal and close-versus-verification behavior.
