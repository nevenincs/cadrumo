---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:46ef99524ee7d95c3bebb8645b9acbb0b516c38bdb7f9cc76a54f136ac8ff1ce'
step_id: 'S15'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Ground the chain on an AEAT worked example carrying retencion, asserting against the published figure and never against the formula under test

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Add `src/cadrumo/domain/calculations/registry/tests/test_ledger_income_chain_oracle_rated.py` driving one rated professional invoice through all three links of the income chain.
- Build the row as a real `Transaction` and run the production classifier rather than hand-building an observation, so the grounding marker and the withholding derivation are set where production sets them.
- Read the resolved value of the three committed Modelo 130 income bindings, which no prior test did for a row that started as an invoice.
- Ground casilla 01 on the invoice's own base imponible, the measure the bundled AEAT Modelo 130 instructions call the ingresos integros fiscalmente computables.
- Ground the retencion on the RIRPF art. 95.1 general rate read from the registry parameter catalogue, applied to the base that article names, never on the engine's own gross-minus-cash route.
- State the two invoice identities as their own gate so a later edit to one figure reddens at the source instead of silently re-grounding the module.
- Exclude the two wrong retencion bases explicitly: the IVA-inclusive total, and a rate inverted off the cash.
- Pin the base-absent branch as the rated case's error direction, which runs opposite to the exempt one.

## Outcome

Landed as commit `e5a88bb5e8` (1 file, +308, 0 deletions).

Raw counts, serial runs (`-n 0`): the module alone 7 passed, 0 failed, 0 skipped; with its exempt sibling 14 passed, 0 failed, 0 skipped.

The independent cross-check is the substance of the step. The engine derives a withholding one way only, as declared invoice gross minus cash received, and never applies a rate; the expectation arrives from the statutory rate on the statutory base. Two unrelated routes landing on the same 150 is what makes the figure grounded rather than self-confirming. Had the module recomputed 1210 minus 1060 it would have agreed with the engine by construction whatever the engine did.

The base-absent half records a direction nothing previously watched. With the substrate unrecorded, casilla 01 receives the banked 1060 rather than the 1000 ingresos integros, because the IVA collected on Hacienda's behalf outweighs the retencion withheld. The taxpayer therefore over-declares income by 60 while the 150 credit disappears, roughly 210 worse off on one invoice, and both movements are visible only because the ungrounded screen fires.

## Notes

The bundled manual-oracle corpus could NOT be used for this step, and the reason is structural rather than a matter of effort. The grounding honesty gate requires every casilla carrying an `expected_by_casilla_id` figure to be `input_kind = "computed"` and enrolled in a verification contract; Modelo 130 casilla 01 is `input_kind = "bound"`, so bundling a payload naming it would raise an `oracle_casilla_not_computed` finding and redden that gate. The corpus mechanism is scoped to computed casillas by construction and cannot express a grounding claim about a bound one. Reported to the coordinator as a finding rather than worked around: the alternatives are to make casilla 01 computed, or to widen the gate, and both are registry decisions well outside a test step.

What replaced it is the same discipline through a different authority. The published figure is the invoice's own base imponible, whose status as the casilla 01 measure is stated in the bundled AEAT Modelo 130 instructions corpus, and the statutory rate is the registry parameter carrying its own BOE citation and review stamp. Neither is engine output, which is the property the step's no-tautology mandate actually asks for.

### Mutation proofs

Run in process by rebinding the registry fact aggregator, so no broken state ever existed in the working tree. Three regressions, each reddening the value gates rather than passing vacuously:

- Sum the gross amount unconditionally: 3 of 7 gates red.
- Sum only the declared base, dropping the cash fallback: 2 of 7 red.
- Apply the retencion rate to the IVA-inclusive total instead of the base: 2 of 7 red.

The four gates that stay green under all three are the arithmetic identity, the statutory-rate premise, and the two advisory-screen assertions, none of which reads a resolved binding value. That is the expected partition rather than a coverage gap.
