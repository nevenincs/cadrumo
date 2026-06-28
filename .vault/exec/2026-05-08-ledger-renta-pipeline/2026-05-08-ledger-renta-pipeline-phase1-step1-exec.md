---
tags:
  - '#exec'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-reference]]"
---



# `ledger-renta-pipeline` `phase1-step1-modeller-input-inventory` `phase1-step1-modeller-input-inventory`

Completed Phase 1 modeller input inventory for the
ledger-to-Renta pipeline.

- Created: `2026-05-08-ledger-renta-pipeline-reference`
- Modified: `2026-05-08-ledger-renta-pipeline-plan`
- Regenerated: `ledger-renta-pipeline.index`

## Description

The inventory was formalized as a VaultSpec Reference. It records the
current registry binding source coverage, separates existing
IVA/OSS/IOSS ledger aggregation behavior from the missing Renta expense
bridge, and identifies the first safe Renta implementation slice.

Phase 1 findings:

- Modelo 100 has no direct ledger binding today. Direct-estimation
  expense linkage is new work and should target manual expense casillas
  rather than formula totals.
- Modelo 130 casillas `01` and `02` are strong quarterly
  income/expense candidates, but previous-year and computed casillas
  should remain existing binding/formula behavior.
- IVA and OSS/IOSS ledger binding definitions and resolver functions
  already exist. The missing piece is repository-backed declaration
  aggregation into those observation inputs.
- Modelo 100 retention and prior-filing values should remain
  relation-driven from Modelos 111, 115, 123, 130, 131, 180, 190, and
  193.
- Category-to-casilla mappings for Renta expenses are candidate
  projections only until Phase 2 defines source-kind naming,
  observation schema, duplicate prevention, date/sign semantics, and
  legal provenance requirements.

The plan now marks Phase 1 completed and leaves Phase 2 contract
decisions as the next executable phase.

## Tests

Validation was run after regenerating the feature index.

- `uv run vaultspec-core vault check features --feature ledger-renta-pipeline`
- `uv run vaultspec-core vault check frontmatter`
- `uv run vaultspec-core vault check body-links`
- `uv run vaultspec-core vault check links`

No code tests were run because this phase produced inventory and
pipeline artifacts only.
