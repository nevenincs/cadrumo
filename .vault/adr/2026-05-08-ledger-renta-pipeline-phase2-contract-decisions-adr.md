---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/adr/ location)
# Feature tag (replace ledger-renta-pipeline-phase2-contract-decisions with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#adr'
  - '#ledger-renta-pipeline'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-08'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-05-08-ledger-renta-pipeline-research]]"
  - "[[2026-05-08-ledger-renta-pipeline-reference]]"
  - "[[2026-05-08-ledger-renta-pipeline-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ledger-renta-pipeline` adr: `phase2-contract-decisions` | (**status:** `accepted`)

## Problem Statement

Phase 1 confirmed that the ledger-to-Renta bridge does not exist for
Modelo 100 or Modelo 130 direct-estimation inputs. The codebase does
have typed IVA/OSS ledger observations and binding resolvers, plus a
canonical transaction catalogue, invoice catalogue, category profiles,
and registry calculation runtime.

Implementation cannot safely begin until the feature fixes the
contract between those pieces. Without that contract, later code would
have to guess source-kind names, observation fields, review-state
authority, invoice/transaction precedence, duplicate prevention, period
semantics, sign handling, and first-slice exclusions.

This ADR defines those contracts for the first supported Renta slice:
Modelo 100 annual direct-estimation deductible expenses derived from
classified outgoing ledger transactions.

## Considerations

The calculation registry already uses explicit binding source names
such as `ledger_iva_aggregation` and `ledger_oss_aggregation`. Renta
should follow that pattern with a source name that describes the
semantics being aggregated rather than a generic `ledger` source.

The transaction catalogue is the canonical calculation source for
classified ledger state. CLI review overlays, imported review queues,
or UI-only decisions are not calculation facts until persisted into a
canonical transaction classification record or a typed bridge record.

Invoice facts are valuable evidence and can supply tax-base, IVA,
counterparty, and document provenance. They should not create duplicate
Renta expense observations when linked to a transaction that already
represents the same economic fact.

Renta direct-estimation expenses require deductible amount, not only
transaction amount. Category, proportionality, statutory caps,
business-use ratio, and legal provenance must therefore be present
before binding resolution.

The first slice should avoid difficult legal/accounting cases that need
separate design: amortization, partial payments, provisions, refunds
without original linkage, mixed-use vehicle exclusive-use gates,
uncertain category projections, income aggregation, Modelo 130
quarterly projection, and legally refreshed category lists.

## Decision

Use `ledger_renta_expense_aggregation` as the Renta binding source kind
for deductible expense binding definitions. The source kind aggregates
already-evaluated Renta deductible expense observations by target
modelo, tax year, activity scope, target casilla, category, and legal
profile year.

Introduce a first-slice observation model named conceptually
`RentaDeductibleExpenseObservation`. The model must be strict and must
carry:

- Source identity: transaction id, optional invoice id, source
  catalogue id, and observation id.
- Filing identity: tax year, modelo, period, activity key, target
  casilla, and binding source kind.
- Dates: operation date, optional invoice issue date, optional posting
  date, optional payment date, and selected filing date.
- Money: gross amount, optional taxable base, optional IVA amount,
  deductible amount, non-deductible amount, currency, and sign.
- Classification: direction, closed `SpendingCategory`, category
  family, profile year, proportionality kind, applied ratio, cap bucket
  when relevant, and calculation eligibility status.
- Provenance: legal references, category profile reference,
  proportionality explanation, invoice evidence status, and
  reconciliation status.

For the first implementation slice, only observations with outgoing
expense direction, closed category membership, positive deductible
eligibility, target Modelo 100 expense casilla, and a resolvable filing
date are calculation-eligible.

CLI review state is non-canonical. A reviewed category or split can
participate only after it is persisted into transaction catalogue state
or into an explicit typed reconciliation record consumed by the
aggregator. If the aggregator sees conflicting CLI review data and
transaction catalogue data, transaction catalogue state wins and the
conflict must be surfaced as provenance or a validation error according
to the caller mode.

Transaction versus invoice precedence:

- A linked transaction is the primary counting unit for first-slice
  Renta expenses.
- A linked invoice enriches the observation with document, counterparty,
  tax-base, IVA, and evidence fields.
- A linked invoice must not create a second observation for the same
  expense.
- Unlinked supplier invoices are out of scope for the first slice
  unless a later ADR declares accrual-only invoice aggregation.
- Multiple transactions linked to one invoice, partial payments, and
  mismatched totals are excluded from calculation until allocation
  rules exist.

Date-axis rules for the first slice:

- Modelo 100 uses annual period `0A`.
- The filing date is invoice issue date when a linked invoice exists
  and transaction operation date otherwise.
- Posting date and payment date remain provenance fields in the first
  slice; they do not select the filing period.
- Inclusion is half-open: filing date >= January 1 of the tax year and
  < January 1 of the next tax year.

Sign and correction rules for the first slice:

- Normal outgoing expenses produce positive deductible amounts.
- Linked refunds, reversals, or credit notes produce negative
  deductible observations only when they preserve the original category
  and target casilla.
- Unlinked refunds and ambiguous incoming transactions are calculation
  ineligible.
- The resolver sums signed deductible amounts and rejects a binding
  group if mandatory provenance or category eligibility is missing.

The first source-to-casilla set is limited to high-confidence direct
expense categories: `cuotas_autonomos_ss` to `0186`, `asesoria_*` to
`0199`, `gastos_bancarios` and `gastos_financieros` to `0203`, and
`arrendamiento_local` to `0192`. Broader mappings remain candidates
until Phase 6 legal refresh and hardening.

## Constraints

The calculation registry remains pure. Repository access, period
filtering, invoice reconciliation, category normalization,
proportionality evaluation, and legal provenance construction happen
before `calculate_registry_snapshot`.

All persisted category strings must normalize to closed
`SpendingCategory` members before they become observations. Unknown,
deprecated, or free-text categories are calculation ineligible.

Deductible amount must be computed before binding resolution. Registry
formulas must not implement category proportionality, statutory caps,
or invoice/transaction reconciliation.

Duplicate prevention is mandatory. The aggregation key must include the
transaction id for transaction-counted observations and must also carry
the invoice id when an invoice is linked.

This ADR does not claim that the category list is legally current as of
2026-05-08. Official AEAT/BOE refresh remains a Phase 6 task before
the feature can advertise a legally updated category catalogue.

## Implementation

Phase 3 will implement strict observation and deductibility result
models consistent with this ADR. These models should be usable without
repository access and should reject incomplete or ambiguous first-slice
facts.

Phase 4 will implement repository-backed aggregation. It will load
transaction catalogue data, optionally enrich from linked invoice
catalogue data, apply the date-axis rules, normalize category values,
evaluate deductibility/proportionality, and emit signed
`RentaDeductibleExpenseObservation` records.

Phase 5 will add registry binding definitions using
`ledger_renta_expense_aggregation` and a resolver that sums signed
deductible amounts into binding values for the covered Modelo 100
expense casillas. `_aggregate_filing_inputs` will call the repository
aggregator and pass explicit binding values to the existing registry
calculation path.

The first implementation must include real-behavior tests that create
real transaction catalogue objects and, where invoice enrichment is
covered, real invoice catalogue objects. Tests must prove observation
shape, period inclusion/exclusion, duplicate prevention, sign handling,
source provenance, binding values, and final Modelo 100 consumption.

## Rationale

An explicit `ledger_renta_expense_aggregation` source kind matches the
implemented IVA/OSS resolver architecture while avoiding an overloaded
generic ledger source.

Using transaction records as the counting unit matches the current
canonical ledger-state decision and prevents invoice links from double
counting expenses. It also leaves room for a future accrual-only invoice
path without silently changing first-slice semantics.

Restricting the first casilla set keeps Phase 3 through Phase 5
implementable and testable. It avoids categories that need amortization
tables, statutory daily caps, legal subtyping, or current-law refresh
before they can be safely bound.

Keeping review overlays out of calculation prevents UI state from
altering tax results without an auditable domain transition.

## Consequences

The first implementation slice will be narrower than the full ledger
category catalogue. That is intentional: it creates a verified
end-to-end pipeline before expanding into legally denser categories.

Modelo 130 remains inventoried but not implemented by this contract.
It should reuse the same observation substrate later, with separate
quarterly period and income/expense rules.

Unlinked invoices, partial payments, amortization, uncertain IVA
treatment, broad category-to-casilla mapping, and official legal
refresh remain explicit follow-up work. They must not be smuggled into
the first slice through permissive fallbacks.

The aggregation layer will need strong diagnostics because many real
ledger rows will initially be calculation ineligible. That is better
than silently dropping or guessing taxable values.
