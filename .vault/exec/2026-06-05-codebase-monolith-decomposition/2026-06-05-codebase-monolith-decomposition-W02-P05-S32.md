---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:c284666a7ecd8026b88d960d3be7dc6c40bdbcc94190e9bbe61df458e9cc57ba'
step_id: 'S32'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# `codebase-monolith-decomposition` `W02.P05.S32`

## Scope

Ledger root closure selection.

## Description

- Measured `_ledger.py` at 2890 lines before the slice.
- Ran exact discovery over ledger command decorators and existing ledger registrar modules.
- Ran semantic RAG search for ledger CLI command group extraction.
- Selected the `rule` nested command group because it was already a coherent sub-app with local add, apply, list, and helper functions.

## Outcome

The selected closure group was `aeat app ledger rule`, targeting extraction into `_ledger_rules_cli.py`.

## Notes

No data loss. Work was performed in a dirty shared workspace; unrelated concurrent edits were left intact.
