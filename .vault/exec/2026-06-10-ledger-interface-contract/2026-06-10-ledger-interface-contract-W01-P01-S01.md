---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S01'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Transaction Lifecycle Timestamps

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Add mandatory UTC-aware `created_at` and `modified_at` fields to `Transaction`.
- Stamp missing in-memory construction through `now` while validating timestamp awareness.
- Remove nullable timestamp storage semantics from the domain model comments.

## Outcome

`Transaction` now has non-null lifecycle timestamps on construction, and timestamp validators require UTC-aware values.

## Notes

The repository load boundary separately rejects persisted rows that omit the fields, so model defaults cannot silently repair stored drift.