---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:9cced6d8191ed668ab74b91fdbc94d91ad2baaa40bbb6b907a531822c7f616a9'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
---
## Scope

Read-only review of S20 against the accepted M303 carry-reconciliation ADR amendment and S20 plan row. The review examined positive-result election resolution, C/D versus U/G carry separation, charge-account handling, export receipt and event provenance, all four CLI/wrapper routes, removed legacy option exposure, localisation, and focused public export coverage.

## Findings

### zero-refund-election-silently-ignored | medium | A refund election on a zero result did not fail closed

The initial review found that the shared resolver rejected a non-default payment election when the computed disposition was `N`, but routed a non-default `RefundElection.DEVOLVER` through the negative-result helper unchanged because only `C` consumed that election. A Modelo 303 zero result therefore resolved to `N` without a refusal or election provenance. The ADR amendment requires every non-default election incompatible with the computed sign to refuse rather than be ignored.

Resolution verified during review: the resolver now rejects `DEVOLVER` unless the base disposition is `C`, and the targeted zero-result regression expects `ModeloRefundElectionNotEligibleError`. The direct current-runtime reproduction now raises that refusal, and the focused S20 suite passed 29 tests.

## Recommendations

- Preserve the zero-result refusal regression with the positive and negative election cases; no open S20 payment-election finding remains from this review.
- Resolution status: the recorded MEDIUM zero-`DEVOLVER` finding was remediated and re-reviewed clean.
