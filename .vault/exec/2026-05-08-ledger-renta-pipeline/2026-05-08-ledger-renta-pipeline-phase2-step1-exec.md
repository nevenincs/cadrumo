---
tags:
  - '#exec'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr]]"
---



# `ledger-renta-pipeline` `phase2-step1-contract-decisions` `phase2-step1-contract-decisions`

Completed Phase 2 contract decisions for the first
ledger-to-Renta implementation slice.

- Created: `2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr`
- Modified: `2026-05-08-ledger-renta-pipeline-plan`
- Regenerated: `ledger-renta-pipeline.index`

## Description

The phase produced an accepted ADR that fixes the implementation
contract before feature code is written.

Decisions recorded:

- Renta binding source kind is `ledger_renta_expense_aggregation`.
- First-slice observation is a strict deductible expense observation
  carrying source identity, filing identity, date axes, monetary axes,
  closed category classification, proportionality result, legal
  provenance, and reconciliation status.
- Transaction catalogue state is canonical for calculation. CLI review
  overlays are not calculation facts unless persisted into canonical
  transaction state or a typed reconciliation record.
- Linked transactions are the counting unit for the first slice.
  Linked invoices enrich evidence and tax fields but do not create
  duplicate observations.
- Modelo 100 period is annual `0A`, with filing date selected from
  linked invoice issue date when available and transaction operation
  date otherwise.
- Normal outgoing expenses are positive deductible observations.
  Linked refunds/reversals may be negative only when they preserve the
  original category and target casilla.
- The first casilla set is intentionally narrow:
  `cuotas_autonomos_ss` to `0186`, `asesoria_*` to `0199`,
  `gastos_bancarios`/`gastos_financieros` to `0203`, and
  `arrendamiento_local` to `0192`.

The plan now marks Phase 2 completed. The next executable phase is
Phase 3: strict models and deductibility evaluator.

## Tests

Validation was run after regenerating the feature index.

- `uv run vaultspec-core vault check features --feature ledger-renta-pipeline`
- `uv run vaultspec-core vault check frontmatter`
- `uv run vaultspec-core vault check body-links`
- `uv run vaultspec-core vault check links`

No code tests were run because this phase produced contract ADR and
pipeline artifacts only.
