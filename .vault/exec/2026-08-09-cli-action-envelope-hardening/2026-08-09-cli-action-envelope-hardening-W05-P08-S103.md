---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:abe5d20168544269e42457d88ef06187606ca86a139c4c28d47fa759fa715418'
step_id: 'S103'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate application export exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions

## Scope

- `src/cadrumo/application/export/_tabular.py`

## Description

- Audit the declared tabular export module for exception producers carrying prose or an unresolved recovery.

## Outcome

- Both refusals in the module already render from a shared locale key constant and carry the offending export format as a machine fact.
- Neither carries an operator-facing sentence, an embedded command, nor a flattened cause, so the step's contract is already satisfied and no change was made.
- Structural verification: the audit is a scan of the declared file, and the two producers were read in full.

## Notes

- Closed as already satisfied. The rationale is recorded so a later reader does not re-open the step expecting a migration that the module does not need.
- No carry-forward.
