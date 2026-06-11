---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
step_id: 'S09'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Documented ID Conformance

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Assert single-transaction verbs accept positional ids.
- Assert the documented command surface has no `--id` option for converted verbs.
- Run the integration-marked documented-command-conformance gate.

## Outcome

Documented command conformance passed and pins the positional id contract.

## Notes

This records prior landed implementation that was already checked in the plan without an exec record.