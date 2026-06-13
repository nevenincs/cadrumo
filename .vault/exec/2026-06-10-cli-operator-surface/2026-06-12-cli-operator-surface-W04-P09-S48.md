---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S48'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W04.P09.S48 M036 Guide Reconciliation

Scope: verify the Modelo 036 guide no longer carries the old no-read-back limitation.

## Description

- Searched `docs/how-to/modelo-036.md` for stale no-command and no-read-back wording.
- Verified the guide teaches `aeat app modelo m036 list` and `aeat app modelo m036 view <declaration-id>`.

## Outcome

S48 is closed. The guide reflects the shipped M036 read-back verbs.

## Notes

- Checks run: documentation text sweep and documented-command conformance.
