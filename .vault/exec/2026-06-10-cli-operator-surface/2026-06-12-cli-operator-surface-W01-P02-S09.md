---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S09'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W01.P02.S09 Choose-Modelo Guide Reconciliation

Scope: verify the guide no longer teaches a preflight revision-id detour.

## Description

- Inspected `docs/how-to/choose-modelo.md`.
- Verified the preflight section uses `aeat config profile preflight --modelo 303 --filing-year 2026 --period 1T`.
- Verified the guide states preflight picks the active revision automatically and `--revision-id` is only for exact replay.
- Confirmed the remaining `aeat app modelo describe 303` mention is a separate catalogue lookup aid, not a paste-back detour.

## Outcome

S09 is closed. The operator guide no longer asks readers to describe a modelo, copy a revision id, and paste it into preflight for the normal readiness question.

## Notes

- Checks run: `rg` over the guide plus documented-command and CLI-reference drift tests.
