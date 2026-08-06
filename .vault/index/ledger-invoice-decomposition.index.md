---
generated: true
tags:
  - '#index'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:be6e6c399f254026e3ad0a258ea4ae766e2d2c6f571c8982ad847d8bd59eeeeb'
related:
  - '[[2026-08-05-ledger-invoice-decomposition-P01-S01]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P01-S02]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P01-S03]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P01-S04]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P01-S05]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P01-S06]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P02-S07]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P02-S08]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P02-S09]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P02-S10]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P02-S18]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P02-S19]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P02-S21]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P02-S27]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P03-S11]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P03-S12]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P03-S13]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P03-S20]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P03-S38]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P04-S14]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P05-S15]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P05-S16]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P05-S17]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P05-S22]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P05-S23]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P05-S24]]'
  - '[[2026-08-05-ledger-invoice-decomposition-P05-S26]]'
  - '[[2026-08-05-ledger-invoice-decomposition-adr]]'
  - '[[2026-08-05-ledger-invoice-decomposition-loader-fingerprint-format-trap-audit]]'
  - '[[2026-08-05-ledger-invoice-decomposition-plan]]'
  - '[[2026-08-05-ledger-invoice-decomposition-reference]]'
  - '[[2026-08-05-ledger-invoice-decomposition-research]]'
  - '[[2026-08-06-ledger-invoice-decomposition-research]]'
---

# `ledger-invoice-decomposition` feature index

Auto-generated index of all documents tagged with `#ledger-invoice-decomposition`.

## Documents

### adr

- `2026-08-05-ledger-invoice-decomposition-adr` - `ledger-invoice-decomposition` adr: `Invoice decomposition and income grounding` | (**status:** `proposed`)

### audit

- `2026-08-05-ledger-invoice-decomposition-loader-fingerprint-format-trap-audit` - `ledger-invoice-decomposition` audit: `loader fingerprint format trap`

### exec

- `2026-08-05-ledger-invoice-decomposition-P01-S01` - Remove the fact default from the renta ledger income selector so an omitting binding fails registry validation loudly
- `2026-08-05-ledger-invoice-decomposition-P01-S02` - Remove the divergent fact default from the impatriado income selector so both siblings are required
- `2026-08-05-ledger-invoice-decomposition-P01-S03` - Rename the renta and impatriado fact gross_income_sum to cash_received_sum, leaving the accurately-named Modelo 210 member untouched
- `2026-08-05-ledger-invoice-decomposition-P01-S04` - Add the income-side missing-substrate issue reason mirroring the gasto pipeline, with an explicit observation grounding marker
- `2026-08-05-ledger-invoice-decomposition-P01-S05` - Surface the missing-substrate advisory on both the preflight and calculate paths through the typed notice channel
- `2026-08-05-ledger-invoice-decomposition-P01-S06` - Stop taxable_base_sum coercing a missing base to zero, routing base-less rows into the ungrounded class
- `2026-08-05-ledger-invoice-decomposition-P02-S07` - Declare the per-category component-expectation table as registry-grounded data derived from the existing cuota-less frozensets, never a parallel list
- `2026-08-05-ledger-invoice-decomposition-P02-S08` - Gate the table for completeness across every IvaCategory member and for non-divergence from the frozensets it derives from
- `2026-08-05-ledger-invoice-decomposition-P02-S09` - Land the legal catalogue entries every component-expectation row cites, each resolving to bundled authoritative corpus text
- `2026-08-05-ledger-invoice-decomposition-P02-S10` - Land the RIRPF article 95 retencion rate parameters as registry data rather than feature-module literals
- `2026-08-05-ledger-invoice-decomposition-P02-S18` - Re-key the component-expectation table on the category and invoice-kind pair, declaring the retencion role per row so an issued credit and a received liability stop sharing a shape
- `2026-08-05-ledger-invoice-decomposition-P02-S19` - Reconcile the rich-invoice IvaRate enum against the registry rate table, closing the missing members rather than leaving a rate the registry knows and the record cannot express
- `2026-08-05-ledger-invoice-decomposition-P02-S21` - Bundle the place-of-supply articles governing cross-border category selection, so the judgement is grounded rather than derived from counterparty country
- `2026-08-05-ledger-invoice-decomposition-P02-S27` - Correct the six-entry LIVA batch document_id to its BOE identifier as one coherent change, then hand it to the operator for re-stamp
- `2026-08-05-ledger-invoice-decomposition-P03-S11` - Relax the withheld-inference precondition to category-determinable cuota so exempt invoices recover their retencion, keeping the registry max-rate bound
- `2026-08-05-ledger-invoice-decomposition-P03-S12` - Add the invoice retencion consistency validator, holding retencion outside the grand total
- `2026-08-05-ledger-invoice-decomposition-P03-S13` - Add the partial-invoice decomposition contract so an ungrounded record is excluded but visible rather than silently dropped
- `2026-08-05-ledger-invoice-decomposition-P03-S20` - Route received-invoice retencion into the existing per-perceptor store behind retenciones_aggregation, never a second parallel retencion path
- `2026-08-05-ledger-invoice-decomposition-P04-S14` - Escalate the advisory to a verify-stage refusal only for a row declaring a cuota-less category with no taxable base, pending operator ratification
- `2026-08-05-ledger-invoice-decomposition-P05-S15` - Ground the chain on an AEAT worked example carrying retencion, asserting against the published figure and never against the formula under test
- `2026-08-05-ledger-invoice-decomposition-P05-S16` - Ground the chain on an exempt-services example proving the under-declaration direction is closed
- `2026-08-05-ledger-invoice-decomposition-P05-S17` - Add strict roundtrip coverage for every new persisted field, with an anti-tautology proof that a deleted field is refused on load
- `2026-08-05-ledger-invoice-decomposition-P05-S22` - Prove one well-formed ledger invoice surfaces consistently in renta income, retenciones and IVA together in a single scenario, with the three figures reconciling to the same decomposition
- `2026-08-05-ledger-invoice-decomposition-P05-S23` - Prove an ambiguous or incomplete invoice is excluded from all three domains WITH a visible advisory, never silently dropped and never silently folded
- `2026-08-05-ledger-invoice-decomposition-P05-S24` - Prove each cross-domain assertion fails when the code is wrong, by mutating the decomposition and confirming the scenario reddens rather than passing vacuously
- `2026-08-05-ledger-invoice-decomposition-P05-S26` - Name the dropped retencion credit in the ungrounded advisory, not only the income mis-measurement, since the lost credit is the larger half of the harm
- `2026-08-05-ledger-invoice-decomposition-P03-S38` - Let the income aggregation read a linked sales invoice for its base, cuota and retencion, following the derive-on-read shape the expense pipeline already proves

### plan

- `2026-08-05-ledger-invoice-decomposition-plan` - `ledger-invoice-decomposition` plan

### reference

- `2026-08-05-ledger-invoice-decomposition-reference` - `ledger-invoice-decomposition` reference: `invoice decomposition and income grounding`

### research

- `2026-08-05-ledger-invoice-decomposition-research` - `ledger-invoice-decomposition` research: `Calculation chain fragmentation across ledger, invoice, modelo and engine`
- `2026-08-06-ledger-invoice-decomposition-research` - `ledger-invoice-decomposition` research: `{topic}`
