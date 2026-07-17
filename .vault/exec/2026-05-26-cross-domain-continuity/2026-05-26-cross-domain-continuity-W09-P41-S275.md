---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S275'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# FU-S274-A centralise counterparty-None coercion into display_counterparty property on TransactionRaw domain model

## Scope

- `retire two identical call-site counterparty or empty-string coercions in ledger actions`
- `src/aeat/application/ledger/_actions.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `a3a1ad3da3` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
