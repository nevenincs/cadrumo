---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:499736ef37e98c5c9848a177affc489ecb318870c53f9e4ece649028267471b5'
step_id: 'S60'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate TUI recovery rendering to the shared resolved action projection

## Scope

- `src/cadrumo/adapters/inbound/tui`

## Description

- Audit the inbound TUI adapter for recovery rendering that bypasses the shared resolved action projection.

## Outcome

- The declared package raises no operator-facing prose refusal: a scan across its modules returns none.
- The TUI renders from the typed results its application collaborators return rather than composing recovery text of its own, which is what this step asks for.
- Structural verification: the audit is a scan of the declared package.

## Notes

- Closed as already satisfied, with the rationale recorded so a later reader does not re-open the step expecting a migration the adapter does not need.
- No carry-forward.
