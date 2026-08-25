---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:c8d713eb3ed79c39337de619bddaf7e99782357aca483d58dd788a81a9640984'
step_id: 'S74'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate evidence-service recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/evidence`

## Description

- Audit the evidence service for refusal producers carrying prose or an unresolved recovery.

## Outcome

- Every refusal in the module already renders from a locale key and carries its subject as machine facts: the bundle and bucket identifiers for an absent bundle, the candidate set for an ambiguous one, and the bundle identity beside its verification state for a failed verification.
- The not-found and ambiguous cases hold distinct keys rather than one shared lookup key, so a consumer can tell a missing bundle from an under-specified reference without parsing text.
- No producer carries an operator-facing sentence, an embedded command, or a flattened cause, so the step's contract is already satisfied and no change was made.
- Structural verification: the audit is a scan of the declared package and each producer was read in full.

## Notes

- Closed as already satisfied, with the rationale recorded so a later reader does not re-open the step expecting a migration the package does not need.
- No carry-forward.
