---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S20'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Add local delivered-to-payer and completed communication state transitions

## Scope

- `src/aeat/application/modelo`

## Description

- Add local `delivered_to_payer` and `locally_completed` states to the Modelo 145 communication record.
- Persist delivery and completion timestamps with model-level ordering invariants.
- Add idempotent backend transitions for delivery retries, completion retries, and delivery calls after completion.
- Refuse local completion until delivery has occurred, and refuse delivery for records that do not pass registry-backed validation.
- Cover the transition path with real secure-runtime tests.

## Outcome

- Focused ruff gate passed for the Modelo 145 communication implementation, facade, and service tests.
- Focused pytest gate passed for the Modelo 145 communication create, validate, export, transition, and service-contract tests: 23 passed.
- Required review found no `P04.S20` issues and was recorded in the feature audit.
- Plan status now reports 20 completed steps, next open step `P04.S21`, and no missing exec records.
- Plan check and feature check both passed cleanly after the feature index rebuild.

## Notes

- Bucket-event emission remains deliberately untouched for `P04.S21`.
