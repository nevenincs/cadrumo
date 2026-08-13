---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:7184f2cc41cd31ee633c3561f3dd2169595d6ff9453a37578980a050256ac08b'
step_id: 'S82'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate storage-management recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/storage_management`

## Description

- Audit the storage-management service for recovery producers carrying prose or an unresolved recovery.

## Outcome

- Every refusal in the module is raised through a structured constructor taking the storage area and its entry count as typed arguments. None accepts or carries an operator-facing sentence.
- The reclaim-refused and reclaim-unconfirmed conditions are separate error types rather than one type distinguished by text, so a consumer routes on the type and reads the area and count as data.
- The step's contract is therefore already satisfied and no change was made.
- Structural verification: the audit is a scan of the declared package and each producer was read in full.

## Notes

- Closed as already satisfied, with the rationale recorded so a later reader does not re-open the step expecting a migration the service does not need.
- No carry-forward.
