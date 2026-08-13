---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:4a1a8a64dfe33cf3e5e7859f72ebfc279e5e85a9725026fdacae39d137820963'
step_id: 'S80'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate integrity-repair continuation producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/repair_integrity.py`

## Description

- Audit the integrity-repair module for continuation producers carrying prose or an unresolved recovery.

## Outcome

- Every refusal in the module already renders from its own distinct locale key and carries its subject as machine facts: the conflicting filter pair, the mismatched decision identity, and the absent decision identifier.
- Distinct keys per condition rather than one shared key means a consumer can tell the refusals apart without parsing text.
- No producer carries an operator-facing sentence, an embedded command, or a flattened cause, so the step's contract is already satisfied and no change was made.
- Structural verification: the audit is a scan of the declared module and each producer was read in full.

## Notes

- Closed as already satisfied, with the rationale recorded so a later reader does not re-open the step expecting a migration the module does not need.
- No carry-forward.
