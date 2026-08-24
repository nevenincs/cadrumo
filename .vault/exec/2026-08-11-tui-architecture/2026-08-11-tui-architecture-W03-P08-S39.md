---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:cf73ee1b193f15d1454105e2893929a9a499d5fb8be7f85728f05095459ebba2'
step_id: 'S39'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-24-tui-architecture-pre-custody-login-secret-submission-research]]'
  - '[[2026-08-24-tui-architecture-pre-custody-login-secret-submission-reference]]'
---
# Register login, provider configuration, credential acquisition, passphrase rotation, and auth teardown as application-owned operations

## Scope

- `src/cadrumo/application/auth/_operation_definitions.py`
- `src/cadrumo/application/auth/tests/test_operation_definitions.py`
- `src/cadrumo/application/user_profile/_custody_ports.py`

## Description

- Composed six canonical operation definitions for S39's five auth families, keeping logout and reset as distinct authorities.
- Bound profile login and passphrase rotation to S114's exact requirement-bound one-shot secret broker.
- Bound active-profile auth authorities to an exact canonical `profile:<uuid>` operation subject.
- Verified real filesystem-backed login, secret mismatch, pre-entry cancellation, restart interruption, and passphrase rotation through the operation supervisor.
- Verified real active-profile custody execution for provider configuration, AEAT acquisition refusal before outbound access, logout, and reset; observed logout preservation and reset removal of configuration.
- Re-audited the pre-existing passphrase rotation custody ports and normalized their public export ordering only.
- Completed independent review and resolved its medium coverage finding with custody-backed supervisor proofs.

## Outcome

The implementation and independent audit are complete. `auth/_operation_definitions.py` is the single application owner for registered auth orchestration; it composes existing public user-profile and auth authorities without new facades, forwarding wrappers, frontend callback identity, or persisted secret fields. Login and rotation use credential-free recorded requests, `INTERRUPT` reconciliation, unsupported cancellation after entry, no deadline, and the exact S114 ephemeral-secret requirement. Provider configuration, session acquisition, logout, and reset remain non-secret credential-free operations; logout preserves configuration whereas reset clears it.

## Notes

Verification passed: targeted Ruff on the S39 Python surface; `pytest -q -m integration src/cadrumo/application/auth/tests/test_operation_definitions.py` (5 passed); and `vault check all --feature tui-architecture` after regenerating the feature index. No plan checkbox was changed. The originally reported direct rotation custody fragmentation had already been consolidated in shared HEAD into purpose-specific `_custody_ports` functions by the time implementation resumed; the only local edit there is `__all__` ordering. The adjacent `user_profile/_recovery_custody.py` adapter-warning bridge does not intersect S39's auth/credential/rotation authority and remains out of scope.
