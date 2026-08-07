---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e09225955f995022c7e6c77682f6ae91d66a5f762af22aceb82f73b1026124c0'
step_id: 'S03'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W01.P01.S03

## Outcome

Closed by **supersession, not by execution.** The hardcoded redirect this Step would retire is deliberately kept, and retiring it would remove the routing the M130 retención depends on.

## Why the premise inverted

The Step is conditional on `S02`: retire the override *once the registry declares the destination*. The registry does not declare it, because that approach was implemented and reverted (see `W01.P01.S02`). With its precondition gone, executing the Step alone would delete `_m130_retenciones_backend_inputs` and leave the resolved retención with nowhere to report — a silent zero on casilla 06, which is the defect class this campaign exists to close.

## What the override became instead

T-05 conformant rather than retired:

- its casilla constant moved to `domain/renta/_retenciones_routing_integrity.py`, the domain that owns the routing fact;
- a `CrossDomainSnapshotCheck` validates it against every M130 revision at snapshot build;
- the binding id that redirects onto it now lives beside it, so both halves of "this binding reports on that casilla" are one fact in one module rather than a constant here and an id there.

That last move landed during this pass (`W02.P03`), and it is what let the cross-domain check become conditional on the binding rather than asserted for every modelo-130 revision.

## Why the row is closed rather than left open

"Retire the hardcoded backend-inputs override" is an actively dangerous instruction now that the override is the sanctioned mechanism. The row text carries a SUPERSEDED marker pointing at the module that holds the remedy, so a future reader meets the decision rather than the retired plan.
