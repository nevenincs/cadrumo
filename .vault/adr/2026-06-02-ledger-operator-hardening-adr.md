---
tags:
  - '#adr'
  - '#ledger-operator-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-05-08-ledger-renta-pipeline-adr]]"
  - "[[2026-05-14-ledger-transaction-lifecycle-adr]]"
  - '[[2026-06-04-ledger-operator-hardening-research]]'
---



# `ledger-operator-hardening` adr: `ledger operator-testimonial corpus and persona-driven hardening` | (**status:** `accepted`)

## Problem Statement

The ledger is the backbone that feeds every modelo calculation engine: the
three aggregation pipelines (`_iva_ledger` -> M303/M390, `_renta_ledger` -> M100,
`_renta_income_ledger` -> M130) project transaction facts into casillas. Yet the
only end-to-end fixture is a 2-row `synthetic-transactions.csv`. There is no
realistic, calculation-grounded body of data exercising the full ledger CLI
surface at operating scale (1000s of categorizable, filterable, amendable
transactions), no oracle binding raw imports to expected modelo projections, and
no operator-perspective evidence that the import -> classify -> filter -> amend
-> export -> verify workflows hold together for a real taxpayer's year. Drift in
the ledger silently corrupts every downstream modelo.

## Considerations

- The fixture must be *raw* (bank-export shaped, no tax facts on the wire) so it
  imports through the real provider registry exactly as a real statement would;
  tax facts belong in a separate typed oracle, not the CSV.
- Coverage must be exhaustive across the projection axes: all 16 `IvaCategory`,
  all 43 `SpendingCategory`, every `TransactionDirection` / `BusinessClassification`
  / lifecycle state, multicurrency (`fx_rate`/`value_in_eur` via ECB
  normalization), and cross-period / cross-year windows (devengo-vs-caja, M130
  cumulative).
- Per `aeat-quality-gates` and `no-tautological-calculation-tests`, the oracle
  must assert structural projection and arithmetic base sums, never re-compute
  registry tax formulas.
- Two complementary verification surfaces are needed: durable pytest
  operator-journeys (CI gate) and live agent-persona testimonials (qualitative
  UX/rendering/filtering evidence) per `aeat-campaign-close-honesty-review`.

## Constraints

- Multicurrency rows gate as `UNSUPPORTED_CURRENCY` unless a
  `CurrencyNormalizationService` supplies a rate at the row's value date; the
  fidelity test must wire ECB rates for the corpus's foreign-currency dates.
- Persona runs operate the real CLI against a real profile/bucket
  (`SecureObjectRepository`, `SensitivityClass.FINANCIAL`); they must respect
  `aeat-safety-legal-gates` (no live AEAT submission) and the worktree-safety
  prohibitions.
- Live Google Drive/Gmail export is deferred behind explicit operator go-ahead
  (publishing to an external service is hard to reverse).
- Parent features are stable: the renta pipeline
  (`[[2026-05-08-ledger-renta-pipeline-adr]]`) and transaction lifecycle
  (`[[2026-05-14-ledger-transaction-lifecycle-adr]]`) are accepted and shipped.

## Implementation

A hand-authored corpus under `tests/fixtures/financial/ledger-corpus/` for one
coherent fictional autonoma (Marta Rios Velasco): four raw bank exports (BBVA
EUR business, CaixaBank EUR personal/mixed, Revolut GBP/USD/EUR, N26 EUR
savings) totalling 500+ rows across 2025 H1..2026 H1, plus a
`ground-truth.manifest.json` oracle keyed by natural key giving each row's
expected classification facts, its casilla projection, and per-modelo aggregate
base sums. A corpus-fidelity pytest imports the raw files through the real
providers, applies the manifest classifications, runs the real aggregations, and
asserts projections and base sums equal the oracle. Operator-journey suites then
drive the ledger CLI (import, classify single + `--from-csv`, filter/`review`,
search, batch edit, split/merge, allocate/ratios, attach/link,
archive/stash/remove, export CSV/JSON/XLSX, multicurrency normalize, preflight,
status, history/track, verify) over the corpus. Finally, agent personas drive
the live CLI end-to-end and persist testimonials as vault audits; findings
become hardening Steps with verification gates. Any regression a persona touches
is absorbed in scope.

## Rationale

A calculation-grounded corpus turns the modelo engines' inputs into a testable
contract: the oracle is the single source of truth personas and CI both verify
against. Separating raw-import data from the typed oracle mirrors reality and
keeps the anti-tautology discipline intact. Pairing durable CI journeys with
live persona testimonials catches both structural regressions and the
qualitative UX failures (rendering, filtering at scale, batch amendment) that no
single-shot test surfaces.

## Consequences

- Gains: end-to-end regression protection from raw bank file to modelo casilla;
  a reusable operating-scale dataset for UX/rendering/filtering work; honest
  operator evidence on the real CLI.
- Costs: 500+ rows and their oracle are a large hand-authored artifact that must
  be maintained as taxonomies evolve (mitigated by the fidelity test failing
  loudly on drift).
- Opens: cross-profile (second taxpayer/bucket) extension; live Drive/Gmail
  export review; LLM-classification accuracy benchmarking against the oracle.

## Codification candidates

- **Rule slug:** `ledger-corpus-is-raw-plus-oracle`.
  **Rule:** Ledger end-to-end fixtures must ship as raw bank-export files plus a
  separate typed ground-truth manifest; never encode tax facts (IVA category,
  classification, casilla) inline in the import CSV.
