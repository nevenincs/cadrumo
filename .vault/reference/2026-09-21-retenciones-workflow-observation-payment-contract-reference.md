---
tags:
  - '#reference'
  - '#retenciones-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:ce57cb98b8fce835be121b3228fbd0234a29e3ea557375d6f8732415ea06233f'
related: []
---

# `retenciones-workflow` reference: `observation payment contract`

## Summary

Commit `7ff67d4026` was inspected for the RETENCIONES-01 acceptance baseline. The live CLI,
invoice, ledger, secure persistence, aggregation, TUI, and accepted cross-feature decisions
were then audited to ground the observation mutation and payment-timing decision.

## Observation command and mutation boundary

Repeatable aggregate flags default to empty tuples in
`src/cadrumo/entrypoints/cli/_modelo_nonwork_common_command_parameters.py:117` and are parsed
through `values or ()` in `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py:162`. The
application command also defaults every observation family to an empty tuple at
`src/cadrumo/application/aggregation/service.py:105`. Omission and an explicitly empty set are
therefore indistinguishable before persistence.

`aggregate_modelo` persists Modelo 190 percepciones and then the retenciones-family window at
`src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py:221`. Each repository contract exposes
only exact-window load and complete-window replacement:
`src/cadrumo/application/aggregation/retencion_observations_repository.py:95` and
`src/cadrumo/application/aggregation/percepciones_observations_repository.py:99`. The shared
algorithm validates then replaces the complete set at
`src/cadrumo/application/aggregation/observation_window.py:119`; empty replacement is a valid
clear. Consequently, omitted flags currently clear a stored window and calculation uses the
empty ephemeral command rather than the existing window.

The established presence analogue is amendment detail rows: `None` means omitted and `()` means
explicit clear in `src/cadrumo/entrypoints/cli/_modelo.py:352`, with its CLI declaration at
`src/cadrumo/entrypoints/cli/_modelo_core_command_specs.py:203`.

Retencion storage identity is `(modelo, year, period, NIF, scheme)` at
`src/cadrumo/adapters/persistence/profile/retencion_observations.py:83`; percepcion identity is
`(modelo, year, period, tax-id, clave, subclave)` at
`src/cadrumo/adapters/persistence/profile/percepciones_observations.py:83`. Source/payment
identity is absent from both keys. Multiple same-recipient/scheme rows in one window collide in
the secure writer at `src/cadrumo/adapters/persistence/storage/sql/_secure_object_writes.py:404`,
so the last value replaces earlier evidence instead of preserving the pure aggregator's sum.

Each repository replacement is atomic through
`src/cadrumo/adapters/persistence/storage/envelope/secure_bound_repository.py:351`, but the two
Modelo 190 writes are not one transaction. Existing co-commit patterns operate on one secure
write set in `src/cadrumo/adapters/persistence/profile/calculation_observations.py:434`,
`src/cadrumo/adapters/persistence/profile/participation_index.py:182`, and
`src/cadrumo/adapters/persistence/profile/transactions.py:778`.

## Payment evidence and timing boundary

The canonical invoice holds issue/operation dates, scalar payment status, scalar payment id,
and multiple transaction links, but no dated payment events or allocations:
`src/cadrumo/domain/invoices/models.py:272`. Lifecycle creation and patching cannot supply them:
`src/cadrumo/application/invoices/catalogue_creation.py:358` and
`src/cadrumo/application/invoices/catalogue_lifecycle.py:146`. The invoice-devengo contract
explicitly cannot represent staged partial payments at
`src/cadrumo/application/aggregation/invoice_devengo.py:11`.

Invoice-to-transaction linking is atomic and permits several transaction ids per invoice at
`src/cadrumo/application/invoices/transaction_linking.py:42`, while a transaction has only one
invoice id at `src/cadrumo/domain/transactions/models.py:427`. Reconciliation compares one
transaction with the whole invoice net at `src/cadrumo/domain/invoices/service.py:209`; existing
income evidence refuses partial or multiple transactions at
`src/cadrumo/application/aggregation/_renta_income_evidence.py:100`.

Ledger rows provide booked/value dates in
`src/cadrumo/domain/transactions/raw_transaction.py:136`. The nearest reusable dated allocation
contract is IVA cash-accounting evidence, which preserves multiple payment events and validates
their total in `src/cadrumo/domain/iva/schema.py:126` and
`src/cadrumo/domain/transactions/cash_accounting_validation.py:29`. It is IVA-specific and cannot
be reused as withholding evidence without a new shared or withholding-owned type.

`RetencionObservation` has only one `accrued_on` date and no payment/allocation identity at
`src/cadrumo/application/aggregation/retenciones.py:62`. Received-invoice routing currently
assigns the issue date at `src/cadrumo/application/aggregation/invoice_retencion.py:245`.
The TUI and CLI invoice entry surfaces capture scalar retention only:
`src/cadrumo/entrypoints/tui/ledger/invoice_entry.py:19` and
`src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:244`. No payroll, rent, capital, or
withholding-payment producer derives persisted observations from ledger payments.

Annual resolvers load only the exact annual period at
`src/cadrumo/application/aggregation/modelo_bindings_retenciones.py:110` and
`src/cadrumo/application/aggregation/withholding_source.py:94`. The aggregation primitive expects
the caller to union annual observations at `src/cadrumo/application/aggregation/retenciones.py:384`,
but persistence performs no quarterly carry-up.

Non-resident suppliers are explicitly excluded from the resident route at
`src/cadrumo/application/aggregation/invoice_retencion.py:106`; no resident-family fallback is
valid.

## Existing decision coverage and translation limits

Accepted records `2026-08-06-invoice-canonical-structure-adr`,
`2026-06-24-retenciones-perceptor-count-adr`, and
`2026-06-25-modelo-190-percepciones-count-adr` fix the canonical invoice and the two distinct
encrypted observation sources. They do not decide payment-event shape, omission/clear semantics,
source-aware storage identity, annual materialisation, or cross-store mutation atomicity.

Accepted record `2026-07-17-ledger-evidence-atomicity-adr` supplies the atomic evidence-write
pattern, and `2026-06-03-cli-workflow-redesign-adr` requires composition of application-owned
atomic primitives. Accepted record `2026-06-30-ledger-add-idempotency-adr` supplies replay
vocabulary but does not cover observation windows. These patterns translate, but extending them
to withholding observations is a new costly commitment rather than unchanged ADR reuse.
