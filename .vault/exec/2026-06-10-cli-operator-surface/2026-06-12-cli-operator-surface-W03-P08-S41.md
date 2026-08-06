---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:4f6211e15e2de344363055e9ac2ea33715c866eb3173777a001324b4d4230f92'
step_id: 'S41'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W03.P08.S41 Period Refusal Message Reconciliation

Scope: verify period refusal guidance follows the strict-token grammar.

## Description

- Verified period tests cover malformed token, calendar shape, missing year, and year-qualified hybrid refusals.
- Verified troubleshooting text tells operators to use AEAT tokens with `--year`.
- Verified generated help and docs do not promise conversion from calendar shapes.

## Outcome

S41 is closed. Refusal guidance points operators to the AEAT-token plus year grammar.

## Notes

- Checks run: ledger period grammar pytest and documented-command conformance.
