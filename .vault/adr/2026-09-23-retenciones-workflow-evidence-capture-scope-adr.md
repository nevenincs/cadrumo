---
tags:
  - '#adr'
  - '#retenciones-workflow'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:5032404d2798ee221b44bb84f442aa7693af806ca01ba89d4b2fb956bbc0dbdb'
related:
  - "[[2026-09-21-retenciones-workflow-observation-payment-contract-adr]]"
  - "[[2026-09-21-retenciones-workflow-observation-payment-contract-reference]]"
---

# `retenciones-workflow` adr: `Withholding evidence capture scope` | (**status:** `accepted`)

Accepted 2026-09-23 by the coordinator's ruling under the user's standing pre-approval for this campaign.

## Problem Statement

The withholding workflow's public capture was limited to invoice-backed professional and urban-rent evidence. An earlier policy refused every capital-income capture together with Modelo 123 (`src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py`, the "Modelo 123 public capture is incomplete" refusal), because the official Modelo 123 "Número de rentas" count is unresolved. Refusing to store the evidence hides real withholding data from Modelo 193. The 2025-and-later 193 design is officially published, and the registry already resolves it, so the gap is not missing authority. Payroll (work income) also had no public producer, although the accepted payment contract names one.

## Considerations

- The accepted contract `2026-09-21-retenciones-workflow-observation-payment-contract-adr` already requires invoice, payroll, rent, capital and manual producers to submit typed payment allocations through one shared service, with CLI and TUI as transports.
- The Modelo 123 count has no official definition. The evidence record is `.agents/session-briefs/handoffs/2026-09-22-retenciones-m123-count-evidence.md`, 22 and 23 Sep sections.
- Modelo 193 for ejercicio 2025 and later is governed by Orden HAC/1430/2025 with no end year. The evidence record is `.agents/session-briefs/handoffs/2026-09-23-retenciones-m193-later-year-evidence.md`.
- Payroll and capital income do not arrive as received invoices. Their payment is a ledger transaction, and their liability terms are declared by the payer.

## Considered options

- Keep refusing capital capture until Modelo 123 is resolved. Rejected: it blocks Modelo 193, which is fully grounded, and discards withholding the taxpayer must still report.
- Open capture and let Modelo 123 calculate with an inferred count. Rejected: that is a silent under- or over-declaration on an ungrounded rule.
- Open capture through the shared producer, and keep Modelo 123 calculation and filing refused with their typed count-authority reason. Chosen.

## Constraints

- Modelo 123 calculation, verification and filing must stay refused, typed and visible in both frontends until an official count authority exists. Captured evidence must never make 123 look complete or filed.
- Modelo 193 materialization reuses `src/cadrumo/application/aggregation/m193_phase_materialization.py` through the canonical aggregation mechanism, with no second summation path.

## Implementation

Payroll and capital income each get a public producer anchored to the ledger transaction that paid the recipient. The request declares the liability terms (gross base, withholding, net settlement) and the legally required annual detail. The paid amount must equal the declared settlement. Recognition follows the contract's rules: `PAID_OR_SATISFIED` for work, `EXIGIBILITY_OR_EARLIER_PAYMENT` for ordinary movable capital. Both producers submit through the shared service, the CLI and TUI expose them as transports, and invoice capture is unchanged. The capital capture path stores evidence into the Modelo 123 window without making that window calculable: the existing count-authority refusal moves from capture to calculation and filing. The Modelo 193 export consumes the phase materializer's PENDING and SETTLED_PRIOR_ACCRUAL rows through the canonical aggregation mechanism and is validated against the official 2025 design.

## Rationale

This is the only option that neither hides grounded withholding (the refusal option) nor invents law (the inference option). It stays inside the accepted payment contract. Capture of evidence and a modelo's ability to count it are separate facts, and the count-authority refusal belongs where the count is used.

## Consequences

Modelo 193 and payroll withholding become reachable in both frontends. Modelo 123 keeps a stored but deliberately uncalculable window. The operator sees captured capital evidence next to a typed refusal, not a partial return. A test must prove that 123 is still refused after capital capture. The earlier capture refusal for 123 is retired, and its message is replaced by the calculation-time refusal.
