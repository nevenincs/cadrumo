---
tags:
  - '#adr'
  - '#ledger-fx-conversion'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-ledger-fx-conversion-research]]"
  - "[[2026-06-02-modelo-filing-ledger-snapshot-adr]]"
---



# `ledger-fx-conversion` adr: `ECB euro reference rates as the canonical FX source for ledger-to-modelo conversion` | (**status:** `accepted`)

## Problem Statement

The ledger holds foreign-currency rows (GBP/USD) that must convert to
`value_in_eur` before they can project into the modelos. A persona testimonial
surfaced that the CLI import path never wires a `CurrencyNormalizationService`,
so foreign rows persist `value_in_eur = None` and silently gate at aggregation —
the multicurrency goal is broken end to end. Wiring the normalizer was blocked on
an unmade decision: which exchange rate is legally correct, and which production
data source supplies it per date, stably and freely. This ADR makes that decision
on a researched legal/accounting basis (see the sibling research document).

## Considerations

- The rate must be the one Spanish tax law treats as official, so the same
  conversion is defensible for IRPF, IVA, and the bookkeeping basis.
- The data source must be free, per-date, stable, official, and usable offline in
  a deterministic/auditable tax application (no paid feed, no per-run network
  dependency that breaks reproducibility or CI).
- Conversion must be auditable: the rate, its source, and its effective date must
  be recordable as provenance, dovetailing with the
  `[[2026-06-02-modelo-filing-ledger-snapshot-adr]]` snapshot (the snapshot
  fingerprints `fx_rate`/`value_in_eur`, so the chosen rate becomes part of the
  filing's immutable provenance).

## Constraints

- ECB reference rates are EUR-base (`1 EUR = rate CCY`); conversion is
  `value_in_eur = amount_ccy / rate`, an inversion the implementation must get
  right (the corpus manifest stores the inverse convenience form).
- ECB publishes only on TARGET working days — no weekend/holiday rate; a
  most-recent-prior-working-day fallback is mandatory and must be tested.
- The existing `CurrencyNormalizationService` already takes an
  `ExchangeRateProvider` protocol (`get_eur_rate(currency, date)`); no production
  implementation exists yet — this ADR authorises one. Parent feature
  (the normalizer + import seam `_apply_fx_conversion`) is stable and accepted.
- ECB rates are reference (indicative) rates, not transaction rates; this is an
  accepted, documented approximation (it is the legally-official rate per Ley
  46/1998 art. 36 and what AEAT examples use).

## Implementation

Adopt the **ECB euro foreign exchange reference rates** (`eurofxref`) as the
canonical source. Acquire them by bundling a **versioned point-in-time snapshot
of `eurofxref-hist.xml`** under the data tree (deterministic, offline,
reproducible, refreshed on release), rather than a per-run network fetch. Add a
production `EcbReferenceRateProvider` implementing the existing
`ExchangeRateProvider` protocol: it parses the bundled history into a
`{date: {currency: rate}}` table and `get_eur_rate(currency, date)` returns the
operation-date rate or the most-recent-prior working-day rate, inverted for the
caller as needed by `CurrencyNormalizationService`. Wire this provider into the
CLI import path so `import_ledger_transactions` receives a `currency_normalizer`
and foreign rows persist `fx_rate` + `value_in_eur` at import time. Record the
rate source and rate date as provenance so the filing snapshot and any read
surface can audit the conversion. A refresh utility re-downloads the ECB history
to update the bundled snapshot on release; the runtime never depends on the
network.

## Rationale

`Ley 46/1998` art. 36 makes the ECB-published euro rate the official exchange rate
of Spanish law; IRPF (LIRPF art. 14.2.e, DGT V2422-20) converts foreign income at
that official rate on the operation date; IVA art. 79.Once converts at the rate in
force at devengo (the Banco de España now relays the ECB reference rates); and PGC
NRV 11ª books foreign transactions at the spot rate on the transaction date. All
four resolve to one free, official, per-date source — the ECB euro reference
rates — so a single provider satisfies every modelo uniformly. Bundling the
history makes the tax calculation deterministic and reproducible, which the
filing-snapshot provenance requires.

## Consequences

- Gains: legally-grounded, uniform, free, offline, auditable FX; unblocks the
  multicurrency import wiring; conversion provenance flows into the filing
  snapshot.
- Costs: a bundled data file to refresh on release; an XML parser + date-fallback
  logic that must be roundtrip/edge tested; the EUR-base inversion is an easy
  off-by-direction bug if untested.
- Pitfalls/known approximations: ECB reference (mid) rate is used where IVA art.
  79.Once literally says "tipo vendedor" — documented as immaterial given BdE now
  publishes the ECB rates; if AEAT ever challenges, a spread adjustment can be
  layered on the same provider without changing the source.

## Codification candidates

- **Rule slug:** `fx-conversion-uses-ecb-official-rate`.
  **Rule:** Every foreign-currency amount converted for a Spanish tax calculation
  MUST use the ECB euro reference rate (the official rate per Ley 46/1998 art. 36)
  at the operation/devengo date, with most-recent-prior-working-day fallback, and
  MUST record the rate, source, and rate-date as provenance — never an ad-hoc or
  paid-feed rate.
