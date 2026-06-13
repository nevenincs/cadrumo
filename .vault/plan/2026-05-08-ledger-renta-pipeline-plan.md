---
tags:
  - '#plan'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-audit]]"
  - "[[2026-05-08-ledger-renta-pipeline-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-research]]"
---



# `ledger-renta-pipeline` `ledger-to-renta-rollout` plan

Plan for creating the real ledger-to-modeller/Renta pipeline. The
feature starts from the live ledger backend and ends at verifiable
registry calculation inputs, with legal/category/proportionality
grounding and traceable execution records.

## Proposed Changes

Create a pre-calculation aggregation layer that converts persisted
ledger, invoice, category, and usage-ratio facts into typed Renta
observations and binding values.

Keep the registry calculation runtime pure. Repository loading,
period filtering, invoice/transaction reconciliation, category
validation, proportionality evaluation, and legal provenance capture
happen before `calculate_registry_snapshot`.

Add Renta-specific observation, deductibility, binding, and filing
input aggregation behavior in staged slices. The first implementation
slice covers a narrow Modelo 100 direct-estimation expense path, then
subsequent slices broaden the model inventory, legal grounding, and
edge-case coverage.

## Tasks


- Phase 0: Pipeline normalization

  Status: completed on 2026-05-08. Execution recorded in
  `2026-05-08-ledger-renta-pipeline-phase0-step1`.

  1. Create the formal ADR and plan from the existing research.
  1. Remove temporary kickoff files once their useful content is in
     pipeline artifacts.
  1. Run VaultSpec feature checks and record the execution result.

- Phase 1: Modeller input inventory

  Status: completed on 2026-05-08. Execution recorded in
  `2026-05-08-ledger-renta-pipeline-phase1-step1`. Inventory recorded
  in `2026-05-08-ledger-renta-pipeline-reference`.

  1. Inventory Modelo 100 direct-estimation income and deductible
     expense inputs that can be ledger-derived.
  1. Inventory Modelo 130 direct-estimation income and expense inputs.
  1. Confirm existing IVA and OSS/IOSS ledger aggregation coverage and
     identify where declaration aggregation should call it.
  1. Identify retention and prior-filing relation values that should
     stay relation-driven rather than direct ledger inputs.

- Phase 2: Contract decisions

  Status: completed on 2026-05-08. Decisions recorded in
  `2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr`.

  1. Decide the Renta binding source kind.
  1. Define the Renta ledger observation schema.
  1. Define canonical reconciliation from CLI review state to
     transaction catalogue state.
  1. Define invoice-versus-transaction precedence and duplicate
     prevention rules.
  1. Define period, sign, refund, reversal, partial-payment, and
     date-axis rules for the first supported slice.

- Phase 3: Deductibility model and evaluator

  Status: completed on 2026-05-08. Execution recorded in
  `2026-05-08-ledger-renta-pipeline-phase3-step1`. Review recorded in
  `2026-05-08-ledger-renta-pipeline-audit`.

  1. Add strict models for Renta ledger observations and
     deductibility evaluation results.
  1. Normalize persisted category identifiers to closed
     `SpendingCategory` members before calculation.
  1. Evaluate full, fixed-percentage, usage-ratio, home-area,
     statutory-cap, non-deductible, and exclusive-use proportionality
     rules.
  1. Preserve gross, business-use, deductible, non-deductible,
     category, proportionality, and legal provenance fields.

- Phase 4: Repository-backed aggregation

  Status: completed on 2026-05-08. Execution recorded in
  `2026-05-08-ledger-renta-pipeline-phase4-step1`.

  1. Load real transaction and invoice catalogues for the filing
     period.
  1. Apply date and period filters.
  1. Reconcile linked invoice and transaction facts without duplicate
     counting.
  1. Resolve category profiles and usage ratios.
  1. Emit binding values and filing inputs for the covered Renta
     slice.

- Phase 5: Registry binding and calculation integration
  1. Add registry binding definitions for the covered Modelo 100
     direct-estimation expense slice.
  1. Add the resolver path that converts Renta observations into
     binding values.
  1. Route the covered slice through `_aggregate_filing_inputs`.
  1. Run `calculate_registry_snapshot` with explicit inputs, binding
     values, and relation values.
  1. Keep existing manual, invoice, IVA, and OSS/IOSS calculation
     behavior intact.

- Phase 6: Legal refresh and hardening
  1. Refresh deductible category grounding against official AEAT and
     BOE sources before claiming a legally current category list.
  1. Bind deductible categories to strongly typed models with legal
     references and source references.
  1. Add period boundary, duplicate prevention, refund/sign,
     proportionality, and provenance tests.
  1. Add an execution summary and code review record before marking
     the feature complete.

## Parallelization

Phase 1 inventory can run in parallel across Modelo 100, Modelo 130,
IVA/OSS, and retention relation surfaces. Phase 2 decisions should be
centralized because source-kind naming, observation shape, duplicate
prevention, and period semantics affect every later slice.

After Phase 2, model implementation and registry binding work can be
split if write scopes are kept disjoint. Deductibility models,
repository aggregation, and registry binding definitions should not be
implemented independently without a shared contract.

## Verification

VaultSpec validation:

- Run `uv run vaultspec-core vault check features --feature ledger-renta-pipeline`.
- Run frontmatter, schema, link, body-link, and structure checks for
  the feature artifacts before execution records are finalized.

Code verification for implementation phases:

- Use real registry data when registry behavior is under test.
- Use real transaction and invoice domain objects for aggregation
  behavior.
- Assert observation fields, binding values, and provenance before
  final formula totals.
- Assert source transaction IDs and invoice IDs survive aggregation.
- Assert legal citation presence when category proportionality drives
  deductible results.
- Assert duplicate prevention for linked invoice/transaction facts.
- Assert period/date inclusion and exclusion.
- Assert sign/refund behavior in observations and final binding
  values.
- Avoid fakes, mocks, stubs, monkeypatches, skips, and xfails as
  shortcuts.

The first implementation slice is successful when a persisted
classified outgoing ledger transaction with a valid category can be
converted into a Renta observation, resolved into a Modelo 100 binding
value, routed through declaration aggregation, and consumed by the
calculation registry without repository access inside the formula
runtime.
