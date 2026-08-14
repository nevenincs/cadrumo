---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ae4d31e54abae49eea87ce391c54a7739b791bb754c9e804ea721679e40a46a3'
step_id: 'S10'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-14-profile-password-custody-s10-login-review-audit]]"
---

# Have Terra XHigh authenticate profile B in a transaction-owned candidate namespace, clean it before swap on failure, and leave active A byte-for-byte intact

## Scope

- `src/cadrumo/application/user_profile/_login_session.py`

## Description

- Authenticate B through its current password envelope and sentinel only after
  target resolution and throttle evaluation.
- Promote B through an unbound candidate, exact pointer CAS, session binding,
  optional acceleration, durable activation, and A retirement.
- Recover every boundary through one bounded canonical journal and anchored
  same-or-predecessor custody operation.
- Preserve A exactly and clean B on authentication or promotion failure.
- Exercise filesystem hostility, idempotence, rollback, and five process-death
  boundaries through real integrations.

## Outcome

S10 passed independent Sol review with no attributable CRITICAL or HIGH finding.
Activation is inside the rollback window before A retirement. Unavailable
acceleration leaves B process-scoped without weakening authentication.

The 4 KiB journal is exact-canonical and no-follow. Its atomic
same-or-predecessor operation accepts an already-current receipt without target
mutation, permits only absence or the exact predecessor transition, preserves
mismatches, and converges after interrupted verified-sidecar cleanup.

The complete real selector passed 26 tests in 538.75 seconds: 14 journal cases,
seven non-journal cases, and all five crash phases. Scoped Ruff, Ty, and
BasedPyright gates were clean.

## Notes

Known MCP schema-registration and Modelo 303 review failures are outside S10.
No production data, remote service, or S11 work was touched.
