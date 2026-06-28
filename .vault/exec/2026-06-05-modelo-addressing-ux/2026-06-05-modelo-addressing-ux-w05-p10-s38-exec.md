---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S38'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W05.P10.S38 Follow-Up ADR Queue

Scope: update the ADR queue for unresolved architecture questions.

## Description

- Persist a follow-up ADR queue under `.vault/adr`.
- Confirm no new ADR is needed for natural-key modelo work addressing because the accepted modelo-addressing UX ADR already covers it.
- Mark persistent hidden selection state such as a future `work use` command as ADR-required before implementation.
- Mark any future departure from singleton active work unit per filing target as ADR-required before implementation.
- Mark broad CLI decomposition as execution-plan debt unless it proposes a new operator-facing contract or hidden state model.

## Outcome

Future architecture questions are bounded by the VaultSpec ADR pipeline, while implementation-only extraction debt remains tracked through Vault Plans.

## Notes

No hidden persistent command state was introduced in this execution.
