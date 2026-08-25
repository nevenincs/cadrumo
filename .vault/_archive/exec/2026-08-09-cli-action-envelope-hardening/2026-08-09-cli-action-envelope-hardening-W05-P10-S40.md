---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c09441c183ae7f1ed1b0933767d0e6691249f1150e69ece324d5e8d6e495ebd2'
step_id: 'S40'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate the remaining live IVA timeout producers and boundary projection

## Scope

- `src/cadrumo/application/live/_errors.py`
- Live IVA timeout producers and CLI projection tests

## Description

Migrated all live IVA surface timeout refusals to the existing live-read typed verdict authority and standard terminal-error transport.

## Outcome

- The closed `LiveReadPrecondition` vocabulary owns `live.iva.surface.completed`.
- All three timeout producers inherit exact runtime facts, no action or bindings, not-applicable conditionality, and safety no-recovery through `live_read_no_recovery_verdict`.
- `LiveApplicationError` uses the core `TerminalPreconditionErrorMixin`; bespoke verdict storage was removed.
- VaultSpec RAG plus exact-symbol confirmation found no remaining raw condition literal or duplicate timeout-verdict constructor.
- Verification: focused live/CLI suites — 31 passed; ruff and diff checks — clean.
- Independent review: PASS.

## Notes

The later campaign-wide deduplication row will centralize the common fact-only record assembly across packages; this row no longer duplicates it inside the live package.
