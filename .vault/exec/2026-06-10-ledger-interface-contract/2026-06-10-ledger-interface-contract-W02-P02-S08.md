---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:ac0ea551319906427e6efededfae2726cd36652a8b8ffac1aa44ff501227aef5'
step_id: 'S08'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Review And Classify ID Convention

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Confirm classify and review use optional positional id arguments where applicable.
- Remove the legacy `--id` spelling from converted review/classify paths.
- Keep command conformance as the contract gate for id input shape.

## Outcome

Review and classify surfaces use the unified positional id convention.

## Notes

This records prior landed implementation that was already checked in the plan without an exec record.
