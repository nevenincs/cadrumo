---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S22'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Add service-level errors and logs using communication vocabulary only

## Scope

- `src/aeat/application/modelo`

## Description

- Add typed Modelo 145 communication service errors for lookup, validation, export rendering, and state-transition refusals.
- Register the new service errors with stable error codes while leaving CLI suggestions unset until the thin CLI phase exists.
- Export the typed error classes through the public modelo facade.
- Add structured service logs for successful create/export/delivery/completion operations, idempotent retries, lookup failures, and validation or transition refusals.
- Cover error registration, catch compatibility, structured error context, and communication-only log messages with real secure-runtime tests.

## Outcome

- Focused ruff gate passed for the Modelo 145 communication implementation, facade, error-registry shard, and service tests.
- Focused pytest gate passed for the Modelo 145 communication error/log, event, transition, export, validation, create, and service-contract tests: 31 passed.
- Focused core error-registry pytest gate passed: 13 passed.
- Required review found no `P04.S22` issues and was recorded in the feature audit.
- Plan status reports 22 completed steps, next open step `P05.S23`, and no missing exec records.
- Plan check and feature check both passed cleanly after the feature index rebuild.

## Notes

- No blockers, skipped work, or scaffolds.
