---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:f7dadc7276f79179e722decbc8ed5709b4a7e06d29296370e8485fba42ed571f'
step_id: 'S151'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# emit IVA wallet decisions as immutable event-key primaries and parent their authority-source contributors to the decision provenance node

## Scope

- `src/cadrumo/application/calculations`
- `src/cadrumo/application/aggregation`

## Description

- Use `iva_wallet_decision_event_key` as the durable decision primary reference.
- Fingerprint the canonical decision payload on that primary.
- Parent wallet and local-recurrence authority contributors to the decision node.
- Verify exactly one primary and explicit contributor edges.

## Outcome

IVA wallet provenance distinguishes the resolver-owned reconciliation decision from the evidence that informed it.

## Notes

Implemented in shared-worktree commit `31e504c55b`. Contributors do not borrow the decision fingerprint when no canonical contributor-content digest exists.
