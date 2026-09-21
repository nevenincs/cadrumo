---
tags:
  - '#adr'
  - '#iva-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:8bf28f9a30091d2159fce4ad9b6d582ce34be16b847171785722279ddcb010a4'
related:
  - "[[2026-09-21-iva-workflow-reference]]"
  - "[[2026-09-17-filing-chain-reconciliation-adr]]"
---

# `iva-workflow` adr: `IVA filing settlement evidence lifecycle` | (**status:** `accepted`)

## Problem Statement

IVA calculation and filing records distinguish local intent from AEAT-confirmed
declarations, and the compensation chain owns credit arithmetic. They do not
durably distinguish declared liability from evidenced payment or refund intent
from approval and payment. Without an explicit evidence lifecycle, a successful
calculation, export, or local filing can be misread as settlement.

## Considerations

- The accepted filing-chain decision already owns local, pending, confirmed and
  superseded declaration identity; a second filing history is prohibited.
- Compensation history and carry-forward arithmetic remain the single owners of
  opening, generated, applied and remaining credit
  (`2026-09-21-iva-workflow-reference`).
- Payment and refund outcomes change after declaration and require independent
  evidence; neither calculation nor export is evidence of them.
- Superseded filings must remain auditable while contributing nothing twice to
  the effective carry chain.

## Considered options

1. Add an immutable IVA settlement snapshot to the existing filing-chain entry,
   while leaving active credit arithmetic in compensation history. Chosen
   because settlement evidence qualifies one declaration without creating a
   second chain.
2. Put filing, payment and refund lifecycle into IVA compensation history.
   Rejected because it duplicates filing identity and makes settlement a
   universal calculation-history dependency.
3. Create a separate settlement ledger. Rejected because it introduces another
   store and reconciliation problem where an existing filing owner exists.

## Constraints

- A calculation or export can establish only prepared local intent. It never
  implies submission, AEAT confirmation, payment evidence, refund approval or
  refund payment.
- Filing state remains the accepted chain vocabulary; this decision does not
  replace origin, confirmation, status, supersession or amendment links.
- Payment state is one of `not_applicable`, `awaiting_evidence`,
  `partially_evidenced`, or `evidenced`. Declared liability and evidenced amount
  remain separate; full evidence requires equality, and excess/conflict is an
  issue rather than success.
- Refund state is one of `not_requested`, `requested`, `approved`, or `paid`.
  Evidence-backed amounts satisfy `paid <= approved <= requested`; approval and
  payment each require their own secure evidence reference.
- Credit snapshot values are non-negative and satisfy
  `remaining = opening + generated - applied`, with
  `applied <= opening + generated`.
- A refund disposition and carry-forward application cannot consume the same
  credit. Each effective filing contributes once; a superseded filing remains
  queryable and contributes nothing to the active chain.
- Evidence references and effective dates are retained through approved secure
  storage. Raw payment or taxpayer payloads are not added to CLI output.

## Implementation

Extend the existing immutable filing record with an optional typed IVA
settlement snapshot bound to its calculation revision. The snapshot records
declared liability, evidence-backed payment state and amount, refund lifecycle,
and a copy of the credit disposition needed to audit that filing. Compensation
history remains authoritative for the effective carry chain; the snapshot is an
audit fact, not a second calculator.

Evidence updates replace the stored immutable value for the same filing record
identity through the existing catalogue persistence path. They never mint a new
tax declaration or rewrite the calculation revision. A superseding amendment
creates the normal successor filing record, preserves its predecessor and
recomputes the affected active compensation chain once.

Public local operations may create prepared intent and accept explicitly
supplied secure evidence. Live AEAT submission, automatic confirmation,
approval discovery and refund-payment discovery remain outside this decision.

## Rationale

Settlement is evidence about a particular declaration, so the filing chain is
its natural identity and supersession owner. Keeping arithmetic in compensation
history preserves the existing single source for the active balance. The chosen
split makes false success states unrepresentable without multiplying stores or
requiring settlement data for calculations that do not depend on it.

## Consequences

Readback can state precisely what was declared and what has independent evidence,
including unknown or partial settlement, without implying AEAT activity. An
amendment keeps both historical settlement evidence and one effective chain.
The cost is a filing-record schema extension and evidence-transition validation.
Until external evidence is supplied, payment, approval and paid-refund states
remain explicitly incomplete; this campaign does not discover them live.
