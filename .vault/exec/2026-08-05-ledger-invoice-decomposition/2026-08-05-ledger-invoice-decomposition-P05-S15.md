---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:fb61458b30fc4ef1fe0be113e7363e80469b9586f5c86b37b7416fb3200ad84c'
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

## Second pass: the Step was asking for a source that does not exist

The step text asked for an AEAT worked example carrying a retencion. The Notes above recorded a blocker for not using the bundled manual-oracle corpus, and that blocker was the wrong one. It said the corpus mechanism is scoped to computed casillas and cannot express a grounding claim about a bound one. True as stated, and routable around: ground the first COMPUTED casilla downstream of the bound one instead, which is exactly what the sibling exempt-services step then did without needing any gate change. The governing decision has since admitted bound casillas outright, so that blocker is retired twice over.

The real obstacle is upstream of any gate, and it was measured rather than assumed.

### The finding: AEAT publishes no worked professional retencion

No bundled AEAT surface publishes a worked retencion figure on actividad-economica income. Searched exhaustively on 2026-08-06:

- All six renta manuals, 2020 through 2025. Every "Caso practico" heading was enumerated (44 across the set) and each body scanned for a retencion figure. Every numeric retencion in the corpus is rendimientos del trabajo (Cap. 3), rendimientos del capital mobiliario or inmobiliario at 19 per cent (Cap. 5: "Retenciones (19% s/450) = 85,50", "19% s/1.502 = 285,38", "Retenciones soportadas (19% s/15.600) = 2.964"), or atribucion de rentas (Cap. 10: 570 total, itemised by the manual as 228 on intereses and 342 on dividendos). None on actividad economica or profesional.
- All six IVA manuals. The string "retenci" occurs ONCE in the entire 831.344-character 2024 normalised text, inside a facturacion-obligations sentence. No figures.
- The bundled Modelo 130 instructions. One occurrence of "ejemplo", used as "por ejemplo" in the casilla 18 prose. No worked example and no figures of any kind.
- All 48 bundled instruction documents. Only Modelo 210 carries retencion worked examples, and they are IRNR dividends and imputed real-estate income, a different chain.
- The Sociedades manual's retenciones are Impuesto sobre Sociedades and already back the Modelo 202 oracle.

So the RIRPF art. 95 professional rate ships in the bundled corpus as NORMATIVE TEXT ONLY, in the consolidated RD 439/2007 art. 95 excerpt, and never as a worked figure. This is not a defect in this codebase. It is a gap in what AEAT itself publishes as worked examples, and it withdraws an entire grounding class from the most common autonomo case this product serves.

### What the step now claims, and what it does not

The step text is amended to state the grounding this module ACTUALLY has. `test_ledger_income_chain_oracle_rated.py` grounds the withheld figure on the registry rate parameter, which carries its own BOE citation and resolves to the bundled consolidated RIRPF art. 95 text reading "15 por ciento sobre los ingresos integros satisfechos". That is NORMATIVE-TEXT grounding, and it is the strongest grounding available for this chain.

It is NOT external-oracle grounding, and the step must not read as though it were. No casilla of this chain is declared in `externally_grounded_casilla_ids`, and none may be: that field asserts a bundled oracle figure exists for the casilla, and for the professional retencion none does. Enrollment in a verification contract is not grounding, and neither is a rate citation; keeping those three tiers distinct is the whole point of the grounding discipline, and collapsing them here would put a claim on the registry that no evidence backs.

Closing the step on that amended claim rather than on the original one is the honest resolution. Re-opening it becomes possible only if AEAT publishes, or this repository bundles, a worked example that prints a professional retencion against its ingresos integros.
