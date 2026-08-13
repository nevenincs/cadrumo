---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2354bf27797f35d9915587f10cbe63de6ca14b08b6595b2702184f48a546e52a'
step_id: 'S63'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# cross-field tax-identity consistency audit for every model `W06.P10.S46` retyped

## Scope

- `src/cadrumo/`

## Description

- Same ADR-scoped check as `W06.P09.S62`: model-INTERNAL only (two-or-more
  fields on ONE model naming ONE party), per the ADR `Consequences`
  section's own framing ("a sibling field on the SAME model").
- `S46` retyped 9 sites across 5 models. Checked every one:
  - `application/ledger/_evidence_draft.py`'s `InvoiceDraft`:
    `supplier_tax_id` AND `customer_tax_id` — TWO tax-identity fields on
    ONE model. Read both field docstrings and the model's own construction
    sites before judging: these deliberately name TWO DIFFERENT parties
    (the invoice's supplier and its customer), never the same party twice.
    **Disposition: N/A by design** — the row's criterion is fields "meant
    to name the SAME party"; a supplier and a customer are definitionally
    different parties, so no agreement invariant applies. (A DIFFERENT
    invariant — supplier != customer, since a party should not invoice
    itself — is a distinctness check, not an agreement check, and is not
    what this row asks for; not added.)
  - `entrypoints/cli/_ledger_business_payloads.py`'s
    `EvidenceExtractResult`: same shape, `supplier_tax_id` /
    `customer_tax_id`, same two-different-parties reasoning. **Disposition:
    N/A by design.**
  - `llm/_suggestions.py`'s `ExtractionPayload`: same shape and reasoning.
    **Disposition: N/A by design.**
  - `domain/calculations/registry/_invoice_bindings.py`'s
    `_OperatorClaveAccumulator` and `_OperatorClavePeriodAccumulator`: ONE
    `party_tax_id` field each. **Disposition: N/A, single identity field.**
  - `domain/calculations/registry/_donativo_bindings.py`'s
    `_DonativoRowAccumulator`: ONE `donor_tax_id` field. **Disposition:
    N/A, single identity field.**
- Checked whether `InvoiceDraft`'s two fields are ever independently
  duplicated onto a THIRD field that could disagree with either — traced
  `CounterpartyDraftSide` (the `W06.P09.S45` semantic-misclassification
  finding) to its one producer, `counterparty_draft_side()`. It is a pure
  derived PROJECTION: `tax_id=draft.customer_tax_id` or
  `tax_id=draft.supplier_tax_id`, selected exclusively by `kind`, never
  both, never independently supplied. Structurally safe by construction —
  there is no second input that could diverge from the source field, so no
  cross-field check is needed there either. The function's own extensive
  docstring already documents the exact historical incident (a silent
  fall-back that let an issued document's counterparty resolve to the
  filer) this total, no-fallback selection was hardened against.

## Outcome

COMPLETE against the row's own gate, and against "the same
shape-versus-agreement limit named in the ADR Consequences" the row cites.
All five models `W06.P10.S46` retyped are checked and recorded. The two
models genuinely carrying two tax-identity fields (`InvoiceDraft`,
`EvidenceExtractResult`, `ExtractionPayload` — three, not two, all sharing
the identical supplier/customer shape) do NOT need a consistency validator
because their two fields deliberately name two different parties, not one
— the row's stated defect (one party misrepresented by two disagreeing
fields) cannot occur in a model that structurally has no second field for
the SAME party. No code changed.

## Notes

No adjacent out-of-scope finding on this side comparable to `W06.P09.S62`'s
`build_complementaria` gap — counterparty-facing identity here either lives
on a single field per model or is a total, no-fallback derived projection
with no second independent input to diverge from its source.
