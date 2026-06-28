---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S40'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W03.P08.S40 Ledger Period Help Reconciliation

Scope: verify ledger period help teaches one grammar.

## Description

- Verified `aeat app ledger preflight --help` leads with AEAT tokens `1T-4T`, `0A`, and `01-12`.
- Verified help requires `--year` and does not teach calendar shapes.
- Ran CLI-reference drift to ensure generated docs match the live help.

## Outcome

S40 is closed. Operators see the canonical AEAT-token grammar in help.

## Notes

- Checks run: ledger period grammar pytest and CLI-reference drift pytest.
