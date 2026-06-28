---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S19'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P04.S19 Restore Real-Behavior Tests

Scope: verify restore roundtrip and guard tests.

## Description

- Verified real-behavior tests cover STASHED-to-ACTIVE and ARCHIVED-to-ACTIVE restore.
- Verified tests cover finalized-modelo refusal, active-row refusal, storage reload, and corruption anti-tautology.

## Outcome

S19 is closed. Restore behavior is covered by durable application-level tests.

## Checks

- `pytest src/aeat/application/ledger/tests/test_actions_lifecycle.py -m "unit or integration" -q --basetemp Y:/tmp/pytest-w02-restore-lineage`

