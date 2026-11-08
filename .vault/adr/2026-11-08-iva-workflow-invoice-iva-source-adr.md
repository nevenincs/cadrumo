---
tags:
  - "#adr"
  - "#iva-workflow"
date: '2026-11-08'
related:
  - "[[2026-09-21-iva-workflow-adr]]"
supersedes:
  - '2026-09-21-iva-workflow-adr'
modified: '2026-11-08'
body_schema: 'body-v2'
body_hash: 'sha256:0edb750a0c06df793d8454116ae5aedbbc6c2f6210fc460b6c29fee725908e48'
---
# `iva-workflow` adr: `The invoice is the IVA source; the movement is its payment evidence` | (**status:** `accepted`)

Accepted 2026-11-08 by the cadrumo coordinator on the evidence below, under the operator's standing delegation of design and tax-modelling decisions to the coordinator. This record supersedes `2026-09-21-iva-workflow-adr`, whose selected-scope blocking classification it carries forward unchanged and whose ledger-only monetary ownership it reverses.

## Problem Statement

APP-QA finding D11 (build `e621263e8c`) followed the taxpayer's path through the desktop: 39 bank movements classified as business, 39 invoices imported through the Libro de facturas, 39 suggested pairs reviewed and saved as permanent links, then Modelo 303 2025 1T. Calculation refused on `missing_taxable_base` for the first movement and every movement still flagged base, rate and cuota.

The cause is by decision, not by accident. `2026-09-21-iva-workflow-adr` kept invoice document facts and ledger facts under separate owners, made linkage evidence association only, and forbade a copied invoice total. `src/cadrumo/application/aggregation/modelo_bindings.py:1` states Modelo 303 domestic IVA is ledger-owned; `src/cadrumo/application/invoices/transaction_linking.py:45-80` records reciprocal identifiers only; the classify flow sets no tax figure on a business classification (`src/cadrumo/domain/transactions/classification_effects.py:45-56`). The invoice catalogue reached the calculation only as a silence screen (`src/cadrumo/application/aggregation/modelo_bindings_invoice_iva.py:801`). A taxpayer who keeps a Libro de facturas therefore could not calculate a 303 from it, and an issued invoice not yet collected contributed nothing, which under-declares.

## Considerations

- LIVA art. 75 accrues IVA on the operation (entrega or prestación), not on payment. Art. 97 and RIVA art. 99 make the factura the document that grants the right to deduct, and the deduction arises in the period the cuota is soportada. The bank movement records a payment; it neither accrues nor grants deduction.
- The régimen especial del criterio de caja (LIVA art. 163 terdecies) moves accrual to payment, or to 31 December of the following year. The profile already declares enrolment (`iva.cash_accounting_regime_enrolled`) and the ledger carries a per-movement cash treatment, but an invoice carries no payment-date schedule.
- The projection already exists: `invoice_line_iva_observation` (`modelo_bindings_invoice_iva.py:117`) builds an `IvaLedgerObservation` from an invoice line, and `invoice_devengo_in_period` (`src/cadrumo/application/aggregation/invoice_devengo.py:145`) is the single art. 75 period predicate. Using both keeps one canonical observation stream (rule 07); no second aggregation engine is added.
- The registry's deduction catalogue (fact 0085) requires `invoice_evidence` authority for `domestic_current` and `domestic_investment`, so a received invoice is itself the authority for a domestic deduction. Fact 0032 (`iva-bien-inversion-escaso-valor-threshold`, LIVA art. 108) bounds when an acquisition can be a bien de inversión.
- An invoice and its linked payment must never both contribute: the 2026-09-24 lifecycle research records that invoice plus payment must not count twice.
- Tickets and other movements with no invoice still need their own facts; the bank-movement IVA path stays for them.

## Considered options

1. Copy the invoice's base, rate and cuota into the transaction on link. Rejected: two stores would hold the same tax fact, an edited invoice would leave a stale copy, and it still ignores unlinked accrued invoices.
2. Keep the ledger as owner and require the person to type figures on every linked movement. Rejected: it duplicates a document the person already recorded and contradicts art. 75 for uncollected invoices.
3. Make the invoice the IVA source and the movement its payment evidence, projected through the existing invoice-line observation into the one IVA observation stream. Chosen.

## Constraints

- Every in-period invoice of the bucket contributes through `invoice_line_iva_observation`, attributed by `invoice_devengo_in_period`, linked or not, because art. 75 accrual does not wait for payment. Its observation carries provenance `invoice:<invoice_id>`. Nothing is copied into the transaction.
- A link is one fact read from either record: the invoice's `linked_transaction_ids` or the movement's own `invoice_id`. A record written before both sides were stored together still makes its movement payment evidence.
- A movement linked to one or more invoices contributes no IVA observation of its own. If every movement paying an invoice carries its own base and cuota and their sums contradict the invoice's EUR totals, that is a hard refusal.
- One bound: a linked movement classified as a bien de inversión acquisition stays the observation carrier, and the invoices it pays leave the invoice source, because the bienes de inversión register pairs each record with that acquisition movement.
- An unlinked movement keeps its own IVA facts (tickets with no invoice) and is otherwise unchanged. Where the match queue proposes a pair between such a movement, carrying figures of its own, and an in-period invoice, a structured double-count finding blocks calculation until the pair is linked or dismissed. A movement with no figures of its own cannot double count and raises nothing.
- A received domestic invoice is its own deduction authority (`invoice_evidence`). Its deduction kind comes from the linked movements' recorded deduction classification where they agree; otherwise it is `domestic_current` when every cuota line's EUR base is strictly below the registry's art. 108 escaso-valor threshold (fact 0032, "sea inferior a") for the devengo date; otherwise the kind is unresolved and reported as a blocking finding naming the invoice and the movement that pays it. No other default is invented.
- Ledger readiness and calculation run one shared check (`period_invoice_iva_side`) over the same invoices, paying movements and findings, so the ledger never calls a period ready that calculation then refuses. A blocking finding refuses calculation before anything is written: the refusal is `REFUSED` with effect none, names the movement by date, description and amount in the served language, and offers an `open_movement` step.
- A received invoice counts as the art. 97 document when the record holds its source document (an attachment linked to the invoice, which is how a confirmed PDF or structured e-invoice is kept) or a paying movement carries registered purchase-invoice evidence. An invoice with neither is a typed finding with a step that opens the invoice, graded like the existing deductible-evidence gap: advisory at calculation, blocking at verification, export and local filing.
- A sealed revision guards the invoices it declared (its invoice fingerprint rows) against deletion; payment movements are no longer its sources and are not guarded by it.
- An invoice whose category or counterparty cannot place a line (for example a zero-rated foreign line with no declared category) is withheld and reported, never routed by rate alone into a domestic casilla.
- A taxpayer enrolled in the criterio de caja is refused filing-grade calculation from invoices with a typed finding until invoices carry the payment-date accrual the regime requires. The calculation does not guess.
- The selected-scope blocking classification of `2026-09-21-iva-workflow-adr` stays: blocking evidence failures persist and prevent verification and export; reviewed exclusions and out-of-window rows stay non-blocking.
- No frontend computes any of this; surfaces render the served observation provenance and findings.

## Implementation

`src/cadrumo/application/aggregation/invoice_iva_source.py` owns the partition, the findings and the shared period check. `aggregate_iva_ledger_observations_from_repositories` (`src/cadrumo/application/aggregation/iva_ledger.py`) requires the bucket's invoice reader and applies the check, so every consumer — the Modelo 303 resolver, annual deducible totals by regime, prorrata regularisation periods, the prorrata advisory and export accounts — reads the same observation stream. Invoice-line observations carry `invoice:<id>:<line>` identities and `invoice:<id>` provenance. Blocking findings persist as `iva_selected_scope_evidence_failure` diagnostics; the ledger preflight (`src/cadrumo/application/ledger/preflight.py`) projects the same findings into readiness issues keyed on the movement to open. The silence refusal module and its precondition are retired with their callers.

## Rationale

The factura is the legal IVA document and accrual follows the operation, so making the invoice the source aligns the calculation with the law and with how a taxpayer keeps books. Projecting through the existing observation keeps one aggregation path, one period predicate and one provenance channel. Dropping linked movements from the transaction source removes double counting without copying values.

## Consequences

A taxpayer can calculate a 303 from the Libro de facturas with or without bank links, and uncollected issued invoices are declared in their accrual period. Movements need IVA figures only when they have no invoice. Received invoices above the art. 108 threshold need a deduction classification before filing grade. Criterio de caja taxpayers remain refused until invoice payment-date accrual is modelled. The invoice-book import still sets no IVA category, so an intra-community or export invoice imported that way is withheld until its category is recorded; that intake gap is separate work.
