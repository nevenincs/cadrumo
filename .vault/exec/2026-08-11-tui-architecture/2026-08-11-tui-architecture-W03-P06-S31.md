---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:12f88997923d67f552d7f26478c4d5e8ce3488087ab720c1e7688b63b6b1ea8b'
step_id: 'S31'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Apply only the approved censal proposal through the existing cotejo authority and refuse stale baselines without effect

## Scope

- `src/cadrumo/application/user_profile/_cotejo_apply.py`
- `src/cadrumo/application/user_profile/tests/test_censal_reviewed_apply.py`

## Description

- Extend the sole cotejo mutation authority with an explicit reviewed-proposal mode while retaining the distinct certificate reconciliation mode.
- Strictly rehydrate the approved operand so proposed-effect digest tampering refuses before mutation.
- Compare profile identity, revision, and content digest against the exact reviewed baseline before deriving or publishing effects.
- Derive adopted facts and preserved-value divergences only from the frozen observation and complete typed field intents.
- Publish the exact replacement and one CENSO_APPLIED event through the existing repository CAS command.

## Outcome

- Approved proposals apply without re-reading or rebuilding remote evidence.
- Stale revision, stale content digest, foreign profile identity, tampered intents, mixed reviewed/direct mode, and incomplete direct mode leave both record and authenticated event history unchanged.
- Exact adopted/divergence counts and one-event publication are proven with the real encrypted profile repository.

## Notes

- The caller/supervisor remains responsible for entering the irreversible section around this synchronous atomic apply call.
- No supervisor, TUI, CLI, acquisition, or alternate persistence logic was added.
- The shared plan checkbox remains untouched for the coordinating session.
