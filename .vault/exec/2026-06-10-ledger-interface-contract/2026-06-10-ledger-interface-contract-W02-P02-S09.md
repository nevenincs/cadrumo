---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:9e1f7cb03c7b461768d375df887bf1d239f8c84fa56641582f4bb9c1e22e7b4b'
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
