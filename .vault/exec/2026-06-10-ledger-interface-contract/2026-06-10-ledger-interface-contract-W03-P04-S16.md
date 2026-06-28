---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S16'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Ledger List Sort CLI Options

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Expose `--sort-by` and `--sort-order` on the ledger list command.
- Use enum-typed Typer parameters so help and schema surfaces render constrained choices.
- Thread CLI values into the list projection call.

## Outcome

Ledger list exposes typed sort controls at the CLI boundary.

## Notes

Verified by documented command and JSON schema conformance gates.