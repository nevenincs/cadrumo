---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:64587281e3a806e938ee8720152ab8a3858ada1ea803889bf9d291beabc26388'
step_id: 'S112'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Reconcile the accepted availability decision with the still-open dedicated-entrypoint migration and complete a fresh honesty review

## Scope

- `.vault/adr/2026-08-11-tui-architecture-adr.md`
- `.vault/adr/2026-08-11-tui-interface-adr.md`
- `.vault/audit`

## Description

- Amend both accepted TUI ADRs after explicit user approval.
- Define callable availability independently from dedicated migration completion.
- Preserve the global-only flag, typed refusal, and no-line-fallback contracts.
- Record a fresh honesty review.

## Outcome

Completed. Current interfaces may be declared truthfully without claiming the
future sibling-entrypoint migration is finished.

## Notes

The bounded CLI-to-inbound-TUI imports remain explicit migration debt.
