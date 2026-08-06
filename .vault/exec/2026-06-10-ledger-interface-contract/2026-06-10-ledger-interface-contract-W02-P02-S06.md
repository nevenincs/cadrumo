---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:e6fb94b2c0ec2e1431f04673f6d33230d169e94e2573241cee351fc6bb99d64c'
step_id: 'S06'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Primary Mutation Positional ID

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Confirm update, classify, allocate, attach, and doclink no longer expose `--id`.
- Use positional transaction identifiers for single-subject mutation verbs.
- Verify the ledger CLI modules contain no `--id` option token.

## Outcome

Primary mutation verbs use positional transaction ids with no legacy `--id` option surface.

## Notes

The explicit `--id` scan returned no matches in `_ledger*.py`.
