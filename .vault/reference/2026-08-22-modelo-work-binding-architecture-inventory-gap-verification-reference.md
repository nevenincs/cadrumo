---
tags:
  - '#reference'
  - '#modelo-work-binding-architecture'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:08e7258eefb1be89b26f0152099db9dfcce80bb1760eb595a25db9e1d5d4d020'
related:
  - "[[2026-08-22-modelo-work-binding-architecture-reference]]"
  - "[[2026-06-14-bindings-interface-hardening-adr]]"
---
# `modelo-work-binding-architecture` reference: `inventory gap verification`

This reference falsifies or verifies the claim that the completed casilla-schema work does not integrate the secure stock-inventory register into modelo calculations. It distinguishes schema/read-model completion, inventory-domain completeness, foreign-asset row integration, and the missing stock-inventory handoff.

## Summary

**Verdict: verified, with a correction.** Inventory-related M100 casillas already exist, and secure inventory storage plus FIFO/PMP valuation already exist. What is absent is the governed source bridge that resolves an `InventoryLedger` into those casillas and freezes its provenance in a `CalculationRevision`. Modelo 720 foreign-asset rows are already integrated through a different typed resolver and must not be conflated with stock inventory.

The casilla-schema campaign was read-side and canonical-derivation work. Its plan describes a registry read side and one assembled review record at `.vault/plan/2026-08-10-casilla-schema-plan.md:21`, `:25`, and `:100`. The accepted read-model ADR requires `ModeloWorkReview` to remain a pure read model at `.vault/adr/2026-08-10-casilla-schema-read-model-adr.md:45-57`. `CasillaDefinition` in `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:199-275` describes an official filing box and its type, input kind, formula or binding, constraints, export references, and grounding. `RegistrySnapshot` in `src/cadrumo/domain/calculations/registry/_schema.py:1448-1468` pins the legal modelo/revision/filing coordinate. Neither owns taxpayer inventory movements.

Stock inventory is a separate business aggregate. `InventoryLedger` in `src/cadrumo/domain/contribuyente/inventory/__init__.py:202-243` is keyed by activity and year and carries valuation method, opening and closing stock, stock layers, and typed movement rows. `InventoryService` persists it through the bucket-local repository, and `src/cadrumo/adapters/persistence/profile/inventory.py:108-185` stores the document as encrypted FINANCIAL secure-object state. `compute_inventory_variation` and `compute_anexo_d_inventory_variation` at `src/cadrumo/domain/contribuyente/inventory/__init__.py:322-386` already calculate signed closing-minus-opening variation, but exact consumer search found no production calculation consumer.

The absent bridge is proven at all enrollment points. `DataBindingDefinition.source` must be the closed `BindingSourceKind` at `src/cadrumo/domain/calculations/registry/_schema.py:656-665`; the enum at `src/cadrumo/core/aggregation.py:223-369` has no inventory member. Live source policy at `src/cadrumo/application/modelo/_calculation_source_policy.py:43-68` has no inventory disposition. Calculation explicitly instantiates its resolver set at `src/cadrumo/application/modelo/_calculation_actions.py:775-873` and never imports or reads `InventoryLedgerRepository`. Novel source kinds are refused at `src/cadrumo/application/modelo/_calculation_actions.py:1664-1702`. Consequently registry TOML cannot declare `source = "inventory"`, and calculation has no route by which secure inventory movements can produce binding or casilla values.

The project states the gap directly. `src/cadrumo/application/inventory/_source_readiness.py:1-51` says the readiness record does not resolve values, enroll a source, participate in the source mesh, or emit diagnostics; it returns `ready=False` because movements and valuations do not cross the canonical calculation-revision boundary. This is executable production behavior, not an inference from missing names.

Current M100 schema proves the distinction between absent casillas and absent automation. In revision 2025, casilla `0177` is inventory increase and `0182` is inventory decrease; neither declares a binding, so the `CasillaDefinition` default makes it manual. Purchases are represented separately by `0181`. These feed downstream income and expense formulas. The application can therefore calculate correctly when an operator supplies the numbers, but it cannot demonstrate that those numbers came from the stored inventory ledger, reject a conflicting caller replacement, or replay the inventory source from its fingerprint.

A critical semantic hazard blocks a mechanical wire-up. The dormant helper calls its signed result “Anexo D casilla 0155,” but current M100 casilla `0155` is the computed real-estate-income sum, while current inventory effects are split across `0177`, `0181`, and `0182`. A signed closing-minus-opening value also does not directly decide the separate increase/decrease/purchases presentation. Official tax adjudication must determine the target semantic roles per modelo, revision, activity, and legal context before implementation.

Integrated analogues show why the bridge matters. Ledger, invoice, previous-filing, relation, and foreign-asset adapters implement `ModeloSourceResolver` and return `CalculationSourceResolution` with typed values, source ids, diagnostics, and provenance. Merge code detects ownership collisions; enrollment checks prevent silent unknown sources; `CalculationRevision` freezes resolved values and source provenance. Without the inventory bridge, inventory changes do not alter the calculation revision identity, missing or unreadable inventory does not surface as a calculation diagnostic, source-owned override protection does not apply, and registry legal/source grounding cannot be attached to inventory-derived observations.

The verified implementation boundary is therefore:

`InventoryLedger` -> officially adjudicated selector and target semantics -> `BindingSourceKind` member -> typed selector validator -> enrolled `ModeloSourceResolver` -> `CalculationSourceResolution` values, diagnostics, source ids and provenance -> registry binding declarations -> bound casillas -> immutable `CalculationRevision` round trip.

This investigation did not decide whether the proper output is one signed source fact, three separate M100 facts, or another activity-grained structure. That is a tax-schema decision requiring official evidence, not a conclusion licensed by the current helper.

Verification run: the focused source-enrollment, source-mesh missing-source, inventory-domain, and encrypted inventory round-trip selection passed 33 tests. A broader exploratory selection passed 35 tests and exposed one current unrelated failure in `test_modelo_349_refuses_intracom_ledger_rows_without_operator_rows`: the exception rendered translation key `errors.error.error_modelo_aggregation_binding` rather than the asserted diagnostic prose. Separate agent sweeps reported 12 relevant gates passing and another 52 passing with two unrelated current runtime/registry failures. These failures do not create an inventory bridge, but they remain confidence caveats for the surrounding tree.
