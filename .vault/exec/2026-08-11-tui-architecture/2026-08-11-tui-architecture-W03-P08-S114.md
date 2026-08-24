---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:27ed9cc7f61e7182f91e29649e6693c2bee417e1466b2d7acdf5e0f73d51d052'
step_id: 'S114'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement credential-free non-secret operation requests and one-shot supervisor-owned ephemeral secret submission with exact binding, expiry, zeroisation, restart interruption, and no durable secret derivatives before registering login or passphrase operations

## Scope

- `src/cadrumo/application/operations`
- `src/cadrumo/adapters/persistence/operations`
- `and focused real persistence and lifecycle tests`

## Description

- Add registry-owned request storage policy validation for secure references and strict credential-free request models.
- Persist credential-free request JSON with its safe content digest while refusing secret-capable fields and serialization shapes.
- Add the supervisor-owned one-shot `EphemeralSecretSubmission` port with exact durable requirement binding and mutable-buffer transfer.
- Serialize secret submission with cancellation and terminal settlement under the operation boundary.
- Permanently close runtime custody on shutdown and zeroize pending and actively consumed buffers.
- Classify restart before executor entry as `INTERRUPTED/NONE` and retain ordinary `UNKNOWN` reconciliation after entry.
- Consolidate the public contracts in `application.operations` and durable validation in persistence operations without login-specific policy or active-profile inference.
- Prove the lifecycle on real filesystem repositories, including restart, mismatch, expiry, duplicate, race, byte-scan, and non-retention cases.

## Outcome

Implemented the generic credential-free request journal and one-shot ephemeral
secret substrate required before any login or passphrase operation can be
registered. Durable state contains only registry-approved request values and
credential-free secret requirement identity; submitted secret bytes, callbacks,
and reversible derivatives remain absent from persistence and diagnostics.

Verification passed:

- Ruff: all checks passed on the S114 Python surface.
- basedpyright: 0 errors, 0 warnings, 0 notes.
- Application operation unit tests: 167 passed.
- Focused real persistence tests: 11 passed, including 7 ephemeral-secret lifecycle tests.
- Import migration identity proof: 1 passed.
- Independent code review: the reported cleanup-serialization finding was remediated and closed after deterministic cancellation, settlement, shutdown, and active-consumption proofs; no S114 blocker remains.

## Notes

The initial independent review reproduced stale insertion after cancellation and
submission after shutdown. The supervisor and broker synchronization was amended,
and the reviewer independently verified the corrected behavior. No compatibility
shim, forwarding wrapper, mock, fake, patch, or skipped test was introduced.
