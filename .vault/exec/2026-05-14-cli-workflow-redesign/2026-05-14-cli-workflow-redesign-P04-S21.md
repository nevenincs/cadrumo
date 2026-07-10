---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S21'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Emit communication-specific bucket events without filing or filed-state terminology

## Scope

- `src/aeat/application/modelo`

## Description

- Add communication-specific Modelo 145 bucket event kinds for create, export, delivery to payer, and local completion.
- Add a `communication_record` bucket event object type for local payer communication records.
- Emit bucket events from the Modelo 145 communication service after successful create, export, delivery, and local completion operations.
- Keep idempotent create and transition retry paths quiet by returning the existing record before emitting another mutation event.
- Cover emitted event kinds, payload metadata, forbidden filing-shaped vocabulary, retry behavior, and invalid-delivery blocking with real secure-runtime tests.

## Outcome

- Focused ruff gate passed for the bucket event taxonomy, Modelo 145 communication implementation, and communication service tests.
- Focused pytest gate passed for the Modelo 145 communication event, transition, export, validation, create, and service-contract tests: 26 passed.
- Required review found no `P04.S21` issues and was recorded in the feature audit.
- Plan status reports 21 completed steps, next open step `P04.S22`, and no missing exec records.
- Plan check and feature check both passed cleanly after the feature index rebuild.

## Notes

- No blockers, skipped work, or scaffolds.
