---
tags:
  - '#plan'
  - '#income-tax-workflow'
date: '2026-09-21'
tier: L2
related:
  - '[[2026-09-17-filing-chain-reconciliation-adr]]'
  - '[[2026-09-07-tuimodelo-filing-lifecycle-adr]]'
  - '[[2026-09-07-tuimodelo-reconcile-verify-adr]]'
  - '[[2026-09-07-tuimodelo-work-creator-adr]]'
  - '[[2026-09-07-tuimodelo-export-destinations-adr]]'
modified: '2026-09-21'
body_schema: body-v2
body_hash: 'sha256:39a6110ef08513cfcfad668df011db9c81e09c9f8567fb6b94a143fe8ceb3b25'
---

# `income-tax-workflow` plan

Prove one synthetic direct-estimation taxpayer's Modelo 130 to Modelo 100 workflow through interchangeable CLI and installed TUI frontends.

## Description

Approved 2026-09-21 by the operator's instruction to read INCOME-01 and execute the campaign.

The scope is the latest completed calendar year supported by compatible Modelo 130 and Modelo 100 calculation and official export definitions as of 2026-09-21. It covers synthetic direct-estimation economic activity only, with no live filing submission. The run must expose any gap between the latest completed year and the selected supported year.

The accepted filing-chain reconciliation decision governs history state and the distinction between pending local and AEAT-confirmed filings. The accepted TUI filing-lifecycle, reconcile/verify, work-creator, and export-destination decisions govern P03. P01, P02, and P04 add development acceptance tooling and exercise existing product contracts; they make no new costly architecture decision. Any need to create a second calculation, serializer, persistence path, or frontend-owned filing state stops the affected Step for a new decision.

The versioned synthetic scenario and independent oracle are the single source for all paths. Product calculations may not generate their own expected values. Each frontend must persist through its supported user flow into an isolated secure store. Only the two continuation paths reuse a store, sequentially.

## Steps

### Phase `P01` - Resolve supported authority and export admission

Pin the latest completed year, compatible Modelo 130 and Modelo 100 revisions, authority generation, and actual export capability before building frontend journeys.

- [ ] `P01.S01` - Resolve and report the latest completed supported income-tax year, pinned authority generation, compatible revisions, and Modelo 100 Aux/VERSION export admission without filtering gaps; `dev/acceptance/income_tax/** and owning registry/export tests`.

### Phase `P02` - Define shared scenario and prove CLI

Define one year-parameterized synthetic taxpayer, invoice and transaction fixture, independent oracle, required history, and machine-readable receipt contract, then exercise the real CLI journey.

- [ ] `P02.S02` - Define the year-parameterized synthetic taxpayer, invoice and bank transactions, independent expected values, history states, scenario identities, and receipt schema once; `dev/acceptance/income_tax/** and focused shared-contract tests`.
- [ ] `P02.S03` - Drive CLI ingestion, restart persistence, quarterly and annual calculations, missing-history refusals, verification, controlled invoice mutation, and export from the shared scenario; `src/cadrumo/entrypoints/cli/** plus explicitly required shared application or persistence fixes`.

### Phase `P03` - Wire and prove installed TUI

Use the shared scenario through installed TUI ledger and declaration actions, complete in-scope bindings under accepted contracts, and prove both sequential continuation directions.

- [ ] `P03.S04` - Bind the installed TUI ledger and declaration actions needed by the shared income-tax journey through existing application contracts; `src/cadrumo/entrypoints/tui/ledger/**, declarations/**, modelo/**, aeat_sync/** and launcher composition`.
- [ ] `P03.S05` - Exercise TUI-only, CLI-to-TUI, and TUI-to-CLI journeys against isolated secure stores and compare canonical persisted and calculated meaning; `src/cadrumo/entrypoints/tui/** acceptance tests and dev/acceptance/income_tax/** drivers`.

### Phase `P04` - Validate exports and publish acceptance evidence

Run isolated CLI, TUI, and continuation scenarios, validate official artifact meaning, execute reserved gates, and emit the complete acceptance matrix and machine-readable receipts.

- [ ] `P04.S06` - Validate Modelo 130 and Modelo 100 artifacts against selected official structures, emit per-scenario receipts and the A1-A10 matrix, and run the reserved focused and aggregate gates; `dev/acceptance/income_tax/**, export validators, acceptance tests, and final evidence artifacts`.

## Parallelization

P01.S01 is a hard prerequisite for every other Step. P02.S02 pins the shared scenario and oracle before either frontend implementation begins. After P02.S02, P02.S03 and read-only P03 inventory may run concurrently. Shared application, domain, persistence, fixture, and oracle files remain owned by the income-cli session; the income-tui session owns only `src/cadrumo/entrypoints/tui/**` and its tests. Any shared fix discovered by TUI routes to income-cli and lands before affected TUI evidence is rerun. P03.S05 follows P02.S03 and P03.S04. P04.S06 follows both frontend phases and has exclusive ownership of final aggregate gates and acceptance receipts.

## Verification

- The resolver deterministically reports the latest completed year, selected supported year, pinned authority generation and both revision identities for an explicit as-of date and a directed alternate-year check.
- A1 through A10 each report proven, failed, blocked, or not exercised in machine-readable receipts keyed by brief revision, scenario, frontend path, year, authority, revisions, source state, and acceptance ID.
- CLI-only, TUI-only, CLI-to-TUI, and TUI-to-CLI paths use real supported user flows, isolated encrypted persistence, fresh-process reopening, and one shared versioned scenario and independent oracle.
- Tests prove invoice and bank-transaction lineage, period boundaries, out-of-year isolation, a controlled invoice mutation, genuine first-period absence, missing versus zero versus not-applicable versus available history, and annual Modelo 100 reconciliation without summing cumulative quarter totals.
- Modelo 130 and Modelo 100 exports pass their selected official local structure or schema validators, or the receipt reports the exact refusal and missing field without claiming importability.
- Focused owning tests, `just check-types`, `just check-import-boundaries`, and the applicable acceptance lane pass without duplicating a full run.
- Phase-close and final integrated reviews contain no open critical or high finding.
