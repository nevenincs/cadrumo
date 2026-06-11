---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
step_id: 'S04'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Timestamp Roundtrip Drift Proof

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Keep the encrypted save-load equality test for distinct non-default lifecycle timestamps.
- Replace the missing-key grandfather proof with a stored-drift rejection proof.
- Validate persisted rows for required timestamp keys before catalogue model deserialisation can apply defaults.

## Outcome

Repository roundtrip coverage proves timestamps survive encrypted storage and missing `created_at` fails as stored-data validation drift.

## Notes

Focused repository tests passed with the strict timestamp proof.