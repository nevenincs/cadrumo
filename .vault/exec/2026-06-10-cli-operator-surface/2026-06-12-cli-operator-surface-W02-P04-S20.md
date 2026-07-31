---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:cb1479fa8203d80b1ea7cb38ac2ff85836518cdc26d8d398f2176dd143f9c0c3'
step_id: 'S20'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P04.S20 Bulk-Stash Recovery Test

Scope: verify the CLI bulk-stash recovery journey.

## Description

- Verified `test_bulk_stash_recovery_restores_every_row_without_a_reset` stashes multiple rows and restores each one.
- Verified the journey asserts active rows return without a whole-ledger reset and that history records restore events.

## Outcome

S20 is closed. The CRUD recovery journey now passes end to end.

## Checks

- `pytest src/aeat/entrypoints/cli/tests/test_ledger_restore_journey.py -m "unit or integration" -q --basetemp Y:/tmp/pytest-w02-restore-lineage`
