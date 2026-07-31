---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:00a92f3c07ae878f5ebc470f727b3dd3f861e493263a70f4636c75ac344b2907'
step_id: 'S12'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Wire every new refusal and advisory through the typed error registry and Notice channel (expired-session, not-logged-in, throttle-wait, no-keychain persistence warning, cross-profile handover, idempotent no-op) and land all locale keys through the locales CLI in every catalogue, verified by the locale parity and translation-honesty gates plus the notice-conformance gate

## Scope

- `src/cadrumo/entrypoints/cli`
- `src/cadrumo/locales (via python -m cadrumo.locales)`

## Description

- Route the three non-blocking login conditions through the typed notice channel: the idempotent resume no-op, the cross-profile handover close, and the warning-severity degraded host that cannot custody a session key.
- Route the logout idempotent no-op through the same channel.
- Confirm the blocking refusals already reach the typed error registry with a concrete next verb: the throttle wait carries its remaining seconds, and the absent and expired session refusals each name the login verb.
- Land every new key in all four catalogues through the locales CLI.

## Outcome

All six conditions the Step names are covered. No bespoke advisory, next, or suggestion field was added to any registered output schema, so the notice-conformance gate stays green. Locale parity and translation honesty pass in all four catalogues.

## Notes

The error-registry half of this Step was already satisfied by the login orchestration and root-resume Steps that preceded it; only the notice projections and locale coverage were outstanding. Recorded rather than re-implemented.
