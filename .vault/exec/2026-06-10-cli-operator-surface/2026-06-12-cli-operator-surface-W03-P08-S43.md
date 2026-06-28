---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S43'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W03.P08.S43 Troubleshooting Period Trap Reconciliation

Scope: verify troubleshooting docs teach the strict period grammar.

## Description

- Inspected the troubleshooting period-token section.
- Verified examples use AEAT tokens with `--year`.
- Verified the guide explicitly says `2026Q1`, `2026-03`, and bare `2026` are not accepted.

## Outcome

S43 is closed. The troubleshooting trap section teaches one canonical grammar and no conversion fallback.

## Notes

- Checks run: direct guide inspection plus documented-command conformance.
