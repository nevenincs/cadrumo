---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:445d7cc4f95a86741ef3d3a4ca0d722881ef2b5c134eef5005e185c5a871ef0b'
related:
  - "[[2026-08-05-modelo-parity-rollup-s17-0613-cap-rounding-research]]"
---
# `modelo-parity-rollup` audit: `S17 fifth SOL ruling`

## Scope

Record the binding fifth SOL ruling for the S17/S32 2025 Modelo 100 casilla `0613` evidence boundary. This audit covers authoritative oracle acquisition and plan bookkeeping only. It does not authorize producer promotion, external-grounding enrollment, or changes to production source, registry, schema, formula, binding, relation, profile, persistence, application, test, corpus-enrollment, or IRP invocation-shape files.

## Findings

### s17-fifth-sol-ruling | high | S32 closes as authoritative oracle acquisition only

RULING: APPROVE S32 closure strictly as authoritative oracle acquisition. No further rows are required to close S32 numeric oracle acquisition. The closure records the complete evidence gate authorized for S32; it is not approval to promote the 2025 `0613` producer. All 2025 `0613` producer promotion is DEFERRED, and no external-grounding enrollment is authorized.

This ruling was grounded with VaultSpec-RAG request IDs `51ae4d3c659242ffb025ca2516611737` and `2e292d0a3ae2427d8a555aa75d6810b1`. The RAG service was available through the accepted vault search mode; the records therefore preserve a live service-backed discovery trace. The service reported index integrity as unverifiable because no claim was returned; this discovery result is grounding input, not proof.

### s17-fifth-sol-ruling | high | The live oracle closes the numeric S32 rows

The authoritative Renta WEB Open replay supplies the accepted live values:

- blank expense with zero selected months: blank, semantic zero;
- `100 / 2 = 100.00`;
- `2,000 / 2 = 166.67`;
- `2,000 / 6 = 500.00`;
- `2,000 / 7 = 583.33`;
- `2,000 / 8 = 666.67`;
- `2,000 / 12 = 1,000.00`;
- unequal children: `166.67 + 500.00 = 666.67`;
- post-third-birthday child with one qualifying month: `83.33 + 166.67 = 250.00`.

These observations support retaining the exact `1,000 / 12` fraction through the per-child multiplication and rounding the resulting amount to cents, then summing the per-child results. They close the S32 numeric oracle acquisition boundary without enrolling a 2025 registry producer.

### s17-fifth-sol-ruling | high | The runtime discrepancy exposes a dormant deficiency

The 2025 registry cap parameter is `None`; qualifying months are `1`; maternity months are `0`; the current helper result is `0`; and the live AEAT result is `83.33`. This is an honest runtime discrepancy and exposes a dormant deficiency. It does not authorize wiring, a fallback, or a compatibility path.

### s17-fifth-sol-ruling | high | The pre-promotion contract remains open

The minimum pre-promotion oracle remains:

1. A non-degenerate effective-spend row with parent-paid amount, public subsidy, and exempt employer contribution, with net effective spend below the cap.
2. An enabled multiple-right-holder allocation.
3. Disjoint maternity and guarderia months.
4. A partial overlap where count-minimisation differs from month-set intersection.
5. After source-contract implementation, a bundled Renta WEB Open replay plus an independent real secure-profile-to-registry-engine reproduction.

Until that minimum contract is acquired, the 2025 producer stays manual and no external-grounding enrollment occurs.

### s17-fifth-sol-ruling | medium | Plan closure is deliberately narrower than S17 adjudication

The plan transition is `29/32` after S32 is checked. S16 remains `OPEN/DEFERRED` with 0150 manual, S17 remains `OPEN/DEFERRED`, and S18 remains `OPEN/DEFERRED`. Only S32 may transition to complete in this write set. S32 completion does not close the W03.P08.S17 semantic adjudication step.

### s17-fifth-sol-ruling | high | The eventual producer must satisfy the reverse invariant

Any eventual producer must make the casilla computed, carry the identical formula ID on the casilla and formula target, declare and resolve every binding with provenance, and pass an independent real-runtime replay. None of those producer changes is authorized by this audit.

## Recommendations

- Keep the 2025 `0613` row manual and defer all producer promotion until the minimum pre-promotion oracle and source-contract replay are complete.
- Mark only S32 complete, regenerate the `modelo-parity-rollup` feature index, and run the feature-scoped VaultSpec checks.
- Preserve the concurrent IRP invocation-shape remediation as an unrelated workstream.
