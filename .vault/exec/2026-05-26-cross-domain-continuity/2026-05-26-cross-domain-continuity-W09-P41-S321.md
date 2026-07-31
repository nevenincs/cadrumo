---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:da336812439ba28ec7643e34b354dce37fdf216cc619542c84f48f3debf147dc'
step_id: 'S321'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# FU-W05-E wire effective_eur_amount into amount projection when taxable_base is absent on non-EUR import

## Scope

- `currently exported but unused`
- `non-blocking follow-up from W05.P23 review #122`
- `src/aeat/domain/transactions/_raw_transaction.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `38526f2984` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
