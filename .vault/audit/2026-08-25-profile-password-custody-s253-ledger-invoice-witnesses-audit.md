---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:940b32cd59cb6ca007be902c57a2d220d15910745d5b1045f4c28423c4d32f50'
related:
  - '[[2026-08-13-profile-password-custody-plan]]'
  - '[[2026-08-13-profile-password-custody-W06-P12-S253]]'
  - '[[2026-07-17-ledger-evidence-atomicity-adr]]'
  - '[[2026-07-24-evidence-revision-identity-adr]]'
---

# `profile-password-custody` audit: `s253 ledger invoice witnesses`

## Scope

Formal review of `W06.P12.S253`: the ledger-evidence and manage-invoices
sequence contracts, their changed generated JSON records, and the Step execution
record. Vaultspec RAG located the canonical evidence, invoice, linking, and
Modelo 349 calculation authorities; exact-symbol tracing then confirmed the
contracts only consume their emitted identities and projections.

The review accounts separately for concurrent commit `98f34aa7b01`, which had
already replaced a fixed evidence-link id with the captured evidence id and
changed evidence removal from a cumulative catalogue-count assertion to a
target-specific not-found refusal. The remaining current S253 changes extend
that approach across the two pages without claiming the earlier edits as new
work.

Authority ownership remains intact:

- `derive_purchase_invoice_evidence_id` and
  `PurchaseInvoiceEvidenceService` remain the evidence identity and persistence
  authorities. Contracts capture `result.evidence_id` and compare it with a
  later view result; they do not reconstruct its metadata digest.
- `derive_invoice_id`, `build_catalogue_invoice`, and the canonical `Invoice`
  model remain responsible for invoice identity, kind, totals, and operation
  type. `link_invoice_transaction_catalogues` remains the bidirectional link
  mutation authority. Contracts only address the captured invoice and
  transaction ids and read back `linked_transaction_ids` from the catalogue
  projection.
- `InvoiceCatalogueSourceResolver` remains the invoice-to-calculation source
  authority, including the explicit Modelo 349 operation-type clave.
  `calculate_modelo_revision_from_bucket_aggregation` remains the calculation
  authority. The example creates a work unit explicitly for Modelo 349, captures
  that work-unit id, calculates that same target, and independently checks the
  returned `borrador` state.
- The changed JSON files are sequence-runner records, not authored behavioural
  declarations. Only the three records whose runtime identities or current
  Modelo 349 calculation payload moved are changed. Re-running the owning
  `python -m dev.docs.sequences check` command reports both pages clean in
  isolated-golden and cumulative-coherence modes, confirming the records
  reproduce from their `.seq` owners.

The capture-backed assertions are non-tautological where persistence or linkage
is the subject: the captured identity comes from the creating command and the
comparison comes from a later `view`, linked catalogue projection, removal
refusal, or calculation result. Independent semantic assertions remain beside
the identity checks: supplier and invoice number, linked evidence provenance,
invoice direction, grand and base totals, intra-community country and operation
type, updated notes, target-specific removal refusal, and calculation operation
and state. Thus a projection could preserve the id while corrupting its fiscal
or lifecycle meaning and these examples would still fail.

## Findings

No findings. The scoped documentation replaces unstable generated literals and
cumulative catalogue-size assumptions with captured, target-specific witnesses
while retaining independent checks of identity, provenance/linkage, totals,
kind, intra-community classification, removal refusal, and the Modelo 349 draft
target.

The known catalogue CLI localisation assertion failure is outside S253: it
expects an English field token while the current command emits the Spanish
refusal envelope, and none of the reviewed contracts or generated records alter
that localisation path.

## Recommendations

Approve `W06.P12.S253` for closure. Keep the unrelated catalogue localisation
assertion in its owning workstream and do not widen this documentation Step into
a product or repository-wide repair.
