---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:be78a137bd3b47ce015ef72e94e6306fe82171764c2155ff07ff75c23361bae9'
step_id: 'S11'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-14-profile-password-custody-s11-session-review-audit]]"
---

# Have Terra XHigh replace active and persisted sessions with bounded DEK sessions, atomic reference swap, B promotion, best-effort keyring, and ordered retirement

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/application/user_profile/_login_session.py`

## Description

- Bind each receipt to a random 32-byte session key and immutable profile and
  session UUID keychain account.
- Authenticate custody identity and deadline metadata after loading the current
  committed password envelope.
- Persist receipts through bounded exact-canonical anchored custody operations.
- Swap repeated mints through an exact predecessor/successor retirement record
  and retire only the displaced UUID-pair account.
- Preserve unavailable-keychain evidence and converge idempotently across both
  retirement crash boundaries.

## Outcome

S11 passed independent Sol review with no attributable CRITICAL or HIGH finding.
No provider, shared master key, backend-kind selector, global account, or
fallback secret participates in acceleration.

The non-keychain receipt and recovery selector passed 16 tests in 11.66 seconds.
The executor's receipt, handover, representative, taxonomy, precondition, and
static gates were clean.

## Notes

The real WinVault returned `WinError 1312`; this proves only typed unavailable-
path preservation and is not claimed as successful persistence. The stale MCP
schema inventory remains external. S12 was not started.
