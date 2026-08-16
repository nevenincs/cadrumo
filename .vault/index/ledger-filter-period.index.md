---
generated: true
tags:
  - '#index'
  - '#ledger-filter-period'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:b36748ef70e44bd84dc8dff04ea4cc9271198abae96fd3db744d91147e937dd2'
related:
  - '[[2026-06-10-ledger-filter-period-P01-S01]]'
  - '[[2026-06-10-ledger-filter-period-P01-S02]]'
  - '[[2026-06-10-ledger-filter-period-P02-S03]]'
  - '[[2026-06-10-ledger-filter-period-P02-S04]]'
  - '[[2026-06-10-ledger-filter-period-P02-S05]]'
  - '[[2026-06-10-ledger-filter-period-P03-S06]]'
  - '[[2026-06-10-ledger-filter-period-P03-S07]]'
  - '[[2026-06-10-ledger-filter-period-P03-S08]]'
  - '[[2026-06-10-ledger-filter-period-P03-S09]]'
  - '[[2026-06-10-ledger-filter-period-P04-S10]]'
  - '[[2026-06-10-ledger-filter-period-P04-S11]]'
  - '[[2026-06-10-ledger-filter-period-P05-S12]]'
  - '[[2026-06-10-ledger-filter-period-P05-S13]]'
  - '[[2026-06-10-ledger-filter-period-adr]]'
  - '[[2026-06-10-ledger-filter-period-plan]]'
  - '[[2026-06-10-ledger-filter-period-research]]'
---

# `ledger-filter-period` feature index

Auto-generated index of all documents tagged with `#ledger-filter-period`.

## Documents

### adr

- `2026-06-10-ledger-filter-period-adr` - `ledger-filter-period` adr: `Single shared year.period filter; delete residual notation; continuity gate` | (**status:** `accepted`)

### exec

- `2026-06-10-ledger-filter-period-P01-S01` - Write a boundary-authority pin test asserting Period.contains() is the sole filter path for both the CLI and the calc engine
- `2026-06-10-ledger-filter-period-P01-S02` - Assert that the CLI filter path and the calc-engine path both produce an identical Period object for the same (year, AEAT-token) input
- `2026-06-10-ledger-filter-period-P02-S03` - Confirm the four aggregation_period_for_modelo call sites pass canonical StandardPeriodCode tokens via CalculationSourceContext.period
- `2026-06-10-ledger-filter-period-P02-S04` - Delete the Q1-Q4, A, ANUAL, ANNUAL legacy alias branches from aggregation_period_for_modelo
- `2026-06-10-ledger-filter-period-P02-S05` - Add a test asserting aggregation_period_for_modelo raises on the deleted tokens and succeeds on every canonical StandardPeriodCode span member
- `2026-06-10-ledger-filter-period-P03-S06` - Migrate test_ledger_corpus_journeys.py and test_ledger_persona_autonoma_close.py from 2025Q1 to the canonical AEAT token form
- `2026-06-10-ledger-filter-period-P03-S07` - Migrate test_ledger_persona_yearend_m100.py from bare 2025/2026 to 2025-0A/2026-0A
- `2026-06-10-ledger-filter-period-P03-S08` - Migrate test_ledger_list_filter.py from bare YYYY to the canonical year-qualified form
- `2026-06-10-ledger-filter-period-P03-S09` - Run the full ledger-filter test suite and confirm zero failures after the six migrations
- `2026-06-10-ledger-filter-period-P04-S10` - Write the period-continuity invariant test for adjacent quarter and month pairs across 2+ years
- `2026-06-10-ledger-filter-period-P04-S11` - Assert the encrypted-storage invariant: the period filter adds no plaintext persistence surface
- `2026-06-10-ledger-filter-period-P05-S12` - Update test_no_annual_money_rollup_surface_exists to assert the ledger status period payload as the typed-Period object the W02.P08 refactor now serialises
- `2026-06-10-ledger-filter-period-P05-S13` - Pass a typed core.Period to derive_work_unit_id and WorkUnit in test_modification_refused_when_row_feeds_finalized_modelo

### plan

- `2026-06-10-ledger-filter-period-plan` - `ledger-filter-period` `Ledger shared period filter: ratify, delete residual notation, continuity gate` plan

### research

- `2026-06-10-ledger-filter-period-research` - `ledger-filter-period` research: `Ledger period filter grammar and boundary continuity`
