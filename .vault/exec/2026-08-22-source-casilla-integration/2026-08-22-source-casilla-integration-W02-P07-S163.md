---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:11b56cf1d067d9d678d3a917b48161b087bd9e17ad4cdacee72f09b6111f0787'
step_id: 'S163'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# define validated complete inventory acquisition-cost facts including attributable costs, non-recoverable IVA, and evidence completeness

## Scope

- `src/cadrumo/domain/contribuyente/inventory`

## Description

- Define a strict complete acquisition-cost decomposition with canonical evidence references, typed review roles, and digest-bound evidence.
- Require the decomposition for purchases, refuse it for every other movement kind, and reconcile consideration, IVA recoverability, component totals, and cents.
- Make complete acquisition cost the sole purchase basis for FIFO, weighted average, closing stock, cost of goods sold, and purchase totals.
- Add a versioned, order-stable fingerprint using canonical decimal spelling and canonical JSON content hashing.
- Prove role coverage, partial IVA, rounding, malformed totals, no-legacy refusal, uneven-quantity PMP continuity, and fingerprint mutations.

## Outcome

Inventory purchases now fail closed unless consideration, directly attributable costs, non-recoverable IVA, recoverable IVA exclusion, evidence coverage, and both review decisions form one internally consistent fact. The complete total is capitalized throughout both valuation engines. The focused domain suite passed 25 tests; Ruff and ty passed. Independent formal review passed with no remaining findings after closing its completeness, PMP precision, and decimal fingerprint concerns.

## Notes

Concurrent commit `89dee57164` swept the primary domain implementation together with unrelated command-spec work before this Step could create its exact commit. The remaining corrections, focused tests, execution record, review audit, and plan closure are committed separately; no concurrent work was reverted.

The final feature-surface gate ran Ruff over the three owned Python files, ran the two focused test modules with 25 passing tests, and ran the feature-scoped complete vault check. The vault check had no errors; its three warnings were the retained scaffold annotations on this Step's two lifecycle records and the pre-existing stale feature index.
