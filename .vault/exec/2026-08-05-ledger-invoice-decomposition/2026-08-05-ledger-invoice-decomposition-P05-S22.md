---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:257ee663510f83808d3e69b0a6c7298051e041496173c1454d34c1e5a862297a'
step_id: 'S22'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Prove one well-formed ledger invoice surfaces consistently in renta income, retenciones and IVA together in a single scenario, with the three figures reconciling to the same decomposition

## Scope

- `src/cadrumo/application/aggregation/tests`

## Description

- Drive the grounded invoice through renta income, retenciones and IVA in one scenario and assert the three legs reconcile to a single decomposition.
- Resolve the committed Modelo 130 bindings through the production registry authority and assert the filed figures against the invoice arithmetic.
- Guard the income assertion against the two figures a mis-wired resolver would most plausibly produce.

## Outcome

Landed across two commits: the observation-level reconciliation in `c8bec3fff9` (written alongside S23, since both drive the same invoice) and the binding-level reconciliation in `86ccfe97ce`.

The two layers are different claims and both were needed. Observation-level proves the three pipelines agree about the invoice. Binding-level proves the registry then routes those figures to the casillas a taxpayer actually files - a correct observation consumed by the wrong binding, or by none, is still a wrong return.

At the filed layer: ingresos takes the IVA-exclusive base (casilla 01 is the ingresos integros fiscalmente computables; IVA repercutido is collected for Hacienda rather than earned), retenciones takes the 150 recovered by inference, which is the credit RIRPF art. 110.3.a deducts from the pago fraccionado. Both are asserted against the invoice figures rather than against each other, so a resolver routing the same wrong number to both casillas would still fail.

The revision is resolved through the production registry authority rather than a test-side snapshot builder, so the bindings asserted are the ones a real calculate loads. A hand-built snapshot could agree with the test and disagree with the filing.

Test evidence: the module 11 passed, 0 failed. Aggregation suite 610 passed, 0 failed.

Mutation proof: making the ingresos fact route bank cash to casilla 01 instead of the declared base reddens the module (2 failed, 9 passed). Restored byte-exact and confirmed by git status afterwards rather than trusting the restore.

## Notes

The expected figures came from the campaign's measured invoice arithmetic and the two cited rates, never from aggregator output. Nothing disagreed with them, so there is no finding to report on that axis - but the direction was the point: had a domain disagreed, the domain would have been the defect rather than the expectation.

Two discriminating guards carry the income assertion: casilla 01 must receive neither the credited cash (1060) nor the IVA-inclusive total (1210). Without them a resolver reading the wrong field could still satisfy an equality against a coincidentally-correct number, and those two are exactly the figures such a resolver would produce.

The retenciones leg here is the ISSUED side - the taxpayer's credit, suffered on income they invoiced. It is deliberately not the per-perceptor store that the received-side routing Step feeds: that store holds the taxpayer's LIABILITY as retenedor, which is the opposite role on the opposite kind of invoice. Reading one for the other would invert a credit into a debt, which is the distinction the component table's retencion role now declares.

The order-dependent failure recorded against a peer module in the S23 and S24 records no longer reproduces; the aggregation suite is fully green at 610.
