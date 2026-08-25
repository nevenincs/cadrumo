---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:725be2cb4783be881e7e76a20bfcdf5eceff43c2c56bbd98b9e871e2d2e21a09'
step_id: 'S42'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---




# Generate the leaf-condition-scenario matrix from live surface and production verdict declarations

## Scope

- `dev/agent_eval/_action_coverage.py [new]`
- `src/cadrumo/application/operator_surface/_manifest.py`
- `src/cadrumo/application/operator_surface/_models.py`
- `src/cadrumo/application/operator_actions`

## Description

- Generate the evaluator matrix from the live operator-surface reconciliation and production precondition profiles.
- Retain the resolved production profile without copying catalogue, schema, or expected-action authority.
- Reject duplicate and unknown identities and require both actionable and explicit no-recovery categories.

## Outcome

Commit `4ef48073bd` adds a 121-row matrix covering eight live leaves: seven actionable rows and 114 explicit no-recovery rows. The matrix is sorted, unique, non-vacuous, and delegates all resolution to the canonical production authorities.

VaultSpec RAG and independent review found no parallel catalogue, schema, or scenario expectation authority. Four focused tests pass; Ruff and diff checks pass.

## Notes

- Existing operator-surface and operator-action production sources required no change because they already expose the necessary resolved declarations.
