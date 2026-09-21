---
tags:
  - '#adr'
  - '#retenciones-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:61ab703548420d5b176bd980ee1513aba65c1cbe71f84aef8463bb21272ff142'
related:
  - "[[2026-09-21-retenciones-workflow-observation-payment-contract-reference]]"
  - "[[2026-09-21-retenciones-recognition-property-authority-research]]"
---

# `retenciones-workflow` adr: `observation payment contract` | (**status:** `accepted`)

## Problem Statement

The withholding workflow needs one durable contract for payment recognition, observation
mutation, identity, atomic projection, and annual reconstruction. Local fixes to invoice dating
or CLI defaults would preserve destructive replacement, evidence collision, split-store writes,
and annual re-entry. The grounding is
`2026-09-21-retenciones-workflow-observation-payment-contract-reference`.

## Considerations

- Keep the canonical invoice and the two accepted encrypted observation meanings unchanged.
- Omission, explicit clearing, replay, correction, missing evidence, and zero must be observable.
- Payment recognition must support partial and multiple payments across periods and source types.
- CLI and TUI must invoke one application-owned mutation and calculation path.
- Resident-family producers must refuse non-resident or unknown-residence evidence.

## Considered options

- Patch omitted versus empty tuples only: rejected because identity collision, invented timing,
  split-store writes, and annual re-entry remain.
- Replace both observation stores with one event store: rejected because it reverses two accepted
  source and counting decisions and unnecessarily expands every resolver.
- Reuse IVA cash-accounting evidence: rejected because its legal owner and field taxonomy are IVA.
- Add staged payment state to invoices: rejected because payroll, rent, and capital are not
  invoice-only sources.
- Keep both stores and add one withholding-owned evidence and mutation authority: selected.

## Constraints

The accepted canonical invoice, retencion source, percepcion source, atomic evidence, CLI
composition, and idempotency decisions remain authoritative. The accepted TUI satellite-family
decision requires a narrow amendment from unconditional replace-set editing to this shared
mutation contract before TUI implementation proceeds.

## Implementation

Introduce an application-owned `WithholdingObservationService`. Its optional mutation envelope
supports `APPEND`, compare-and-swap `REPLACE`, and compare-and-swap `CLEAR`; absence means no
mutation and calculation reads persisted state. Supplying rows requires a mode, clear cannot carry
rows, exact idempotent replay is a no-op, conflicting replay and stale baselines refuse, and
corrections create revisions rather than erasing evidence.

Add withholding-owned recognition events, optional settlement events, and allocations with
stable recognition/allocation identities, amount and currency, source identity and revision,
transaction provenance, recipient tax regime and residence, scheme, recognized base and
withholding, and legally required annual detail. Payment identity participates only when payment
or settlement evidence exists. Projection identity is source/recognition/allocation/role based;
recipient and scheme remain grouping axes rather than storage identity. Validated cumulative
allocations cannot exceed the source liability.

One adapter unit of work atomically commits the evidence revision and every required retencion and
percepcion projection while preserving the two accepted encrypted source meanings. Failure leaves
either the complete prior generation or complete new generation.

The application selects a recognition rule from authority revision, recipient tax regime,
residence, income classification, and operation kind. `PAID_OR_SATISFIED` requires a dated
satisfaction or credit event. `EXIGIBILITY_OR_EARLIER_PAYMENT` requires the exigibility basis and
date and derives the earlier of that date and any payment or delivery. `FORMALIZATION` requires a
supported operation kind and formalization date. Callers supply or correct evidence through the
revision contract; they cannot choose the rule or override derived `recognized_on`. Missing,
contradictory, ambiguous, or unsupported combinations refuse before mutation.

For the grounded resident-IRPF scope, work, professional income, and urban rent use
`PAID_OR_SATISFIED`; ordinary movable-capital income uses
`EXIGIBILITY_OR_EARLIER_PAYMENT`. Financial-asset, IIC, and subscription-right cases may use
`FORMALIZATION`, but refuse 123/193 materialization until the exact modelo mapping is enrolled.
Supported IS income may use the RIS article 65 mapping. IRNR permanent-establishment, unknown
residence, and every ungrounded regime/modelo branch refuse rather than inheriting an IRPF rule.
Derived `recognized_on`, never invoice date, selects the periodic projection.

Annual 180, 190, and scoped 193 are deterministic materializations over active recognition and
settlement evidence. For 2025 Modelo 193 keys A, B, and D only, income recognized but unpaid
because the holder did not present for collection produces the official `PENDING` disclosure in
the recognition year. Later collection produces `SETTLED_PRIOR_ACCRUAL` in the payment-year
Modelo 193 with the original accrual year and actual recipient; it does not create a second
economic allocation or Modelo 123 liability and does not by itself amend the earlier filing.
Other unpaid scenarios refuse. Reconciliation classifies current recognitions, pending carry-out,
and prior-accrual settlement carry-in rather than asserting blanket current-year equality.

Every supported Modelo 180 allocation references exactly one property and explicitly attributed
amounts. Property evidence carries situation, conditional cadastral reference, stable property
key, official structured address, modality, recipient detail, and accrual year. Situations 1-3
require their cadastral reference; situation 4 requires it absent and uses a stable local key.
Amounts spanning properties refuse unless explicitly split. Positive annual rows group by filing
year, recipient NIF, modality, accrual year, and property identity; reimbursements additionally
separate by sign. Missing or conflicting property detail yields an incomplete result and blocks
export. Required annual detail is captured with the allocation or yields a structured incomplete
result; an annual cache may exist only as a digest-bound atomically rebuilt derivative.

Invoice creation records liability terms only. Invoice, payroll, rent, capital, and manual
producers submit typed payment allocations through the shared service. CLI and TUI are transports
over the same commands and baseline rules. Non-resident and unknown-residence rows refuse before
resident-family mutation. The current schema receives a pre-release hard cut: all internal callers
move together, old keys and tolerant readers are deleted, and unsupported stored schemas require
explicit local reset or re-entry rather than silent conversion.

## Rationale

This is the only option that fixes all grounded failure classes while preserving the canonical
invoice and both accepted legal source/counting boundaries. It applies the existing atomicity,
application-composition, and idempotency patterns without assigning withholding law to IVA or an
invoice-only aggregate. See `2026-09-21-retenciones-workflow-observation-payment-contract-reference`.

## Consequences

The workflow gains explicit safe mutation, replay and correction semantics, authority-grounded
recognition periods, non-colliding repeated events, atomic detail/totals coherence, annual
reconstruction, and frontend parity. The cost is a new evidence schema, multi-namespace unit of work, hard-cut
migration, producer rewiring, annual materializer, and a narrow accepted-TUI ADR amendment.
Existing developer observations are not silently migrated. Implementation must prove failure
atomicity, stale-baseline refusal, replay behavior, partial/multiple payment timing, quarterly to
annual reconciliation, current-schema anti-tolerance, and all four frontend paths.
