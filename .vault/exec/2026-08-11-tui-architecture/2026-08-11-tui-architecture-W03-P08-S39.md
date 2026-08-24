---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:f3d4c03a1ce05b54c317971ec27a056dae8d104044e810113e64d8948c5a9b24'
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

## Description

- Grounded every S39 auth, custody, CLI, TUI, operation, and persistence path through RAG and exact-symbol inspection.
- Produced focused pre-custody-login research and code reference records.
- Amended the accepted operation ADR with the generic credential-free request and supervisor-owned ephemeral-secret prerequisite.
- Classified custody-port and auth-operation scatter, preserving existing canonical authorities.
- Stopped S39 implementation when the coordinator inserted predecessor S114.

## Outcome

S39 remains open. No production or test source was changed. Profile login and passphrase rotation may not be registered until S114 provides the generic `EphemeralSecretSubmission` substrate. Provider configuration, AEAT credential acquisition, and distinct logout/reset remain scoped S39 compositions after that prerequisite lands; their existing authorities remain unchanged.

## Notes

The plan now names S114 ahead of S39. A registered pre-custody login cannot use the active-profile operand store, persist a passphrase, carry a frontend callback identity, or be misdeclared as an effect-free ephemeral operation. `user_profile/_passphrase_rotation.py` still contains direct custody-adapter bypasses and its monkeypatch-based test remains in-scope cleanup for the later secret-bearing S39 implementation. No plan checkbox was changed.
