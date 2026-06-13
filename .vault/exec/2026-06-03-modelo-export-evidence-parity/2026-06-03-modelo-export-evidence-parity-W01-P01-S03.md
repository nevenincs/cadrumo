---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S03'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W01.P01.S03` step record

Scope: `W01.P01.S03` - Peg evidence onto CalculationRevision and wire capture into verify_modelo_revision.

## Description

- Add `ledger_filing_evidence` to `CalculationRevision` without changing the content-addressed revision id.
- Exercise the real `verify_modelo_revision` path and assert the persisted verified revision carries evidence pegged to the snapshot fingerprint.
- Confirm operator casilla inputs become manual evidence entries.

## Outcome

Verified-complete revisions can now persist the bundled evidence record alongside the immutable ledger filing snapshot. The verify-time `_actions.py` wiring was already present in `HEAD` via the shared-worktree commit `b7b6fc46b`; this step lands the remaining domain field, regression coverage, plan closure, and execution record.

## Notes

The no-silent-omission guard remains tracked in S05. The encrypted roundtrip / anti-tautology evidence persistence test remains tracked in S04.
