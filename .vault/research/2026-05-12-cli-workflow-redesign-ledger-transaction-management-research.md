---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-08-cli-backend-boundary-reference]]"
  - "[[2026-05-08-ledger-renta-pipeline-reference]]"
  - "[[2026-05-08-cli-backend-boundary-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-adr]]"
---



# `cli-workflow-redesign` research: `ledger transaction management`

## Findings

The current codebase already has enough backend functionality to support a
ledger-first CLI posture. The transaction import path parses provider files,
deduplicates movement rows, persists a transaction catalogue, and returns
diagnostics through `import_ledger_with_diagnostics`,
`merge_raw_transactions`, `derive_transaction_id`, and the transaction
catalogue repository.

Transaction classification and history are also backend-shaped. The
transaction domain owns immutable transaction/catalogue structures and mutable
classification transitions through transaction services. This makes ledger
transaction management a better CLI domain than a generic finance or invoice
command family.

The active CLI surface is still split across old ownership boundaries.
`_ledger.py` exposes import, review, and edit. `_invoice.py` exposes a generic
invoice import/review/edit/match workflow. `financial/txs.py` and
`financial/invoices.py` still contain direct command logic for classification,
matching, suggestions, and reconciliation. These surfaces make invoice-oriented
language appear more central than the transaction-management domain actually
requires.

The `financial/invoices.py` entrypoint is especially problematic for the
redesign. It currently presents invoice list/show/link/reconcile/verify flows as
a finance command family, but those flows mix three concerns that must be kept
separate: ledger movement reconciliation, data quality sanitization, and
business-operation/modelo data preparation.

Attachment and evidence infrastructure already exists. Attachment manifests can
link to transaction identifiers and invoice identifiers, but the user-facing
workflow does not yet expose purchase invoice evidence as a clear ledger
evidence operation. This is why the ledger design needs an evidence path rather
than a primary invoice path.

Renta/modelo integration already consumes ledger-backed facts through
repository-backed aggregation. Renta aggregation reads transaction and invoice
repositories, emits issue taxonomies, and produces binding-ready observations.
That logic belongs at the ledger-to-modelo boundary. It should not be recreated
inside CLI heuristics or hidden inside generic invoice commands.

The bucket ADRs already place storage lifecycle and event history under
profile/bucket ownership. Ledger commands should mutate bucket-scoped
transaction state and emit bucket history events, while bucket browse/search and
storage recovery remain under `config bucket`.

## Terminology Constraints

The redesigned CLI must treat `ledger_transaction` as the primary movement fact.
Receipts and supplier purchase invoices can support a ledger transaction as
`purchase_invoice_evidence`, but they do not become the transaction itself.

Issued income invoices, payable invoices, and collectible invoices are
business-operation objects. They may explain why an income or payment movement
appears in the ledger later, and they may be needed by IRPF/modelo calculations,
but they are not primary ledger row controls.

The CLI must therefore distinguish:

- `ledger_transaction`: bank/payment movement fact.
- `purchase_invoice_evidence`: receipt or supplier purchase invoice evidence
  supporting deductible-expense treatment.
- `payable_invoice`: business-operation object representing an amount the user
  owes.
- `collectible_invoice`: business-operation object representing an amount owed
  to the user.

## Drift

Current ADR direction says the workflow is ledger-led and invoice-decoupled, but
the code still has generic invoice commands and `ISSUED`/`RECEIVED` terminology
at user-facing boundaries.

Transaction import and classification are partly backend-backed, but the CLI
still keeps orchestration responsibilities that should either become thin
transport wrappers or move into application services.

Evidence attachment is backend-capable but not yet first-class in the ledger
CLI. This leaves users without a clear path for adding receipts and purchase
invoice evidence to business expense transactions.

The sanitize-to-modelo handoff is not fully explicit. The CLI needs a visible
ledger sanitization step before ledger facts are consumed by modelo calculation
workflows.

## Recommendation

Adopt `aeat app ledger` as the primary transaction-management surface. Its
scope should cover import, list, status, review, classify, split, attach,
evidence, link, sanitize, and export of sanitized ledger facts.

Remove generic invoice-first command surfaces from operator CLI. `_invoice.py`
and `financial/invoices.py` should be removed from CLI registration, command
discovery, and help, with behavior replaced by ledger evidence/link commands or
business-operation/modelo surfaces using explicit terminology.

Keep actual modelo calculation under `aeat app modelo`. Ledger provides
sanitized and evidenced movement facts; modelo consumes those facts plus
business-operation invoice objects according to each modelo's calculation
schema.

## Research Notes

- Command ownership is split today: `_ledger.py` currently exposes `import`,
  `review`, and `edit` while classify, split, evidence, and verify behaviors
  are still spread across legacy groups.
- `financial/txs.py` still exposes transaction classification and LLM
  classification pathways. Under this ADR, those paths must be moved to
  approved ledger/backend services or removed from operator CLI.
- `financial/invoices.py` still carries link, reconcile, verify, and unmatched
  flows and must be removed from operator CLI for this redesign.
- Aggregation readiness already exists in `_renta_ledger.py` through blocker
  reasons such as `UNCLASSIFIED_BUSINESS_STATE`, `MISSING_CATEGORY`,
  `UNSUPPORTED_INVOICE_KIND`, `INVOICE_LINK_MISMATCH`,
  `PARTIAL_OR_MULTI_TRANSACTION_INVOICE`, and `AMOUNT_MISMATCH`.
- Aggregation already consumes tax inputs such as `taxable_base` and
  `iva_amount`.
- Attachment manifests are secure-bucket stored and support links by id, but
  they are not inherently one-to-one for transaction evidence. The
  one-canonical-evidence rule is therefore a CLI/domain validation policy.
- The next hardening step should explicitly introduce command-facing artifacts:
  `ledger_sanitization`, `transaction_aggregation_trace`, and
  `modelo_input_graph`, with complete traces for complete/modelo verification.
