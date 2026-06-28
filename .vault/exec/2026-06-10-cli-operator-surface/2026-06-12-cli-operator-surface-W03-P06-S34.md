---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S34'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W03.P06.S34 Switch Documentation Sweep Reconciliation

Scope: verify operator how-to and generated CLI docs no longer teach the retired `unlock` command.

## Description

- Searched `docs/how-to` and `docs/cli` for `aeat config unlock`, `config unlock`, `unlock NAME`, and `switch by unlocking`.
- Verified matches are absent from operator docs and generated CLI reference.
- Verified live help describes `aeat config switch NAME` as the profile activation command.

## Outcome

S34 is closed. Operator docs teach `switch`, not `unlock`, and the switch-by-unlocking gloss is absent from user-facing how-to/CLI docs.

## Notes

- Remaining `unlock` text is limited to ADR/history/test comments or non-command prose about credential/session mechanics.
