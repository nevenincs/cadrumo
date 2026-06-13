---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-08-cli-backend-boundary-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr]]"
  - "[[2026-05-03-calculation-truth-registry-pending-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `Invoice domain decoupling` | (**status:** `superseded`)

> **Superseded (2026-06-10)** on the single point of the operator-facing invoice
> CLI surface by the `ledger-invoice-unification` ADR
> (`2026-06-10-ledger-invoice-unification-adr`). The prohibition on a bare
> `invoice` operator surface stated below (the "Refactor Mandate" and
> "Consequences") is overturned per operator directive: the two `payable-invoice`
> and `collectible-invoice` noun-groups collapse into one `invoice` command gated
> by `--kind issued|received`. Everything else in this ADR remains in force — the
> four-source-kind taxonomy (`ledger_transaction`, `purchase_invoice_evidence`,
> `payable_invoice`, `collectible_invoice`), the distinct-domain decision, and the
> CLI Backend Boundary discipline are all carried forward unchanged.

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

Existing workflow, ledger, and calculation documents use `invoice` for multiple
different concepts. That is a critical domain misunderstanding. It blurs the
line between financial movement facts, deductible expense evidence, and
business-operation invoice objects. If left unresolved, the backend and CLI can
double-count expenses, attach payment-sheet semantics to invoice objects, or
make modelo calculations depend on the wrong source object.

## Considerations

- A ledger row is a financial movement fact.
- A purchase invoice can support deductible expense treatment only when it is
  used as evidence for a ledger financial transaction.
- Payable and collectible business-operation invoices can exist independently
  from bank/payment ledger rows.
- Modelo calculations may consume both ledger facts and business-operation
  invoice objects, but they must know which source kind they are using.
- CLI wording must not present one generic `invoice` domain if the backend
  actually has separate evidence and business-operation concepts.

## Constraints

- `ledger financial transaction` is the canonical persisted movement fact.
- A `ledger financial transaction` may be paired with `purchase invoice
  evidence` for deductible-expense support.
- `purchase invoice evidence` is not a ledger financial transaction and must not
  create a second expense count when it supports an already-counted transaction.
- `payable invoice` and `collectible invoice` are `business operation invoice`
  entities.
- `payable invoice` and `collectible invoice` are not ledger financial
  transaction sheet rows.
- Source typing must use explicit source names:
  - `ledger_transaction`
  - `purchase_invoice_evidence`
  - `payable_invoice`
  - `collectible_invoice`

## Implementation

Backend and CLI surfaces must be refactored or removed so the distinction is
visible in code, event history, source traces, and user-facing command text:

- Any backend/domain reference that means a movement row must use `ledger
  financial transaction` in prose and `ledger_transaction` in source-kind or
  enum contexts.
- Any backend/domain reference that means proof for deductible expenses must use
  `purchase invoice evidence` in prose and `purchase_invoice_evidence` in
  source-kind or enum contexts.
- Any backend/domain reference to vendor/customer invoice objects must use
  `payable invoice` or `collectible invoice` in prose and `payable_invoice` or
  `collectible_invoice` in source-kind or enum contexts.
- CLI command copy, help text, status output, event summaries, and audit docs
  must avoid bare `invoice` where the intended concept is one of these
  narrower objects.
- Legacy code paths or docs that expose a generic `invoice` surface
  must be removed from operator UX and replaced with explicit
  source-kind-specific surfaces before they are treated as approved workflow
  UX.

## Rationale

The product needs both transaction-ledger accounting and invoice-object
workflows, but those are not the same source of truth. Ledger transactions are
movement facts. Purchase invoices can support expense deduction evidence.
Payable and collectible invoices are business-operation entities that may be
used by modelo logic and storage workflows without becoming ledger rows.

Keeping these concepts separate makes calculation provenance, event history,
deductibility checks, and CLI status output defensible.

## CLI flag vocabulary

Where the four source kinds appear as CLI flag values (e.g. `--kind`,
`--source-kind`), both the canonical name and a short-form alias are accepted
on input; help text and machine-readable output always emit the canonical
name. Aliases:

- `ledger_transaction` ← `lt`
- `purchase_invoice_evidence` ← `pie`
- `payable_invoice` ← `pi`
- `collectible_invoice` ← `ci`

Aliases exist only at the CLI parsing boundary. Domain enums, event payloads,
storage columns, audit traces, and source provenance always use the canonical
strings. Short-form aliases are not synonyms inside the backend.

## Refactor Mandate

The locked taxonomy replaces all generic invoice production surfaces:

- `application/review/_enums.py:26` declares `ReviewItemKind.INVOICE =
  "invoice"`; must be replaced by source-kind-specific kinds.
- `application/review/_models.py` `InvoiceReviewItem` / `InvoiceReviewRecord`
  must split into source-kind-specific variants.
- `application/aggregation/_renta_ledger.py` `invoice_id` field and
  `InvoiceCatalogueRepository` import must be replaced by source-kind-keyed
  references.
- `domain/invoices/` is the pre-taxonomy package and must be split into
  source-kind-specific repositories.
- `entrypoints/cli/_invoice.py` and `entrypoints/cli/financial/invoices.py`
  carry bare `invoice` operator surfaces; both retire per the ledger-
  transaction-management ADR.

The drift list is informational only — this ADR locks the target taxonomy;
the source-kind execution ADR and the ledger-execution plan land the
migration.

## Consequences

- Existing ADR language, source enums, trace narratives, backend type names, and
  CLI surfaces must be audited for bare `invoice` usage.
- Renta and modelo aggregation must distinguish transaction counting from
  invoice evidence enrichment.
- Event history and verification reports must record whether a value came from
  `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, or
  `collectible_invoice`.
- CLI compatibility aliases are not supported in the redesigned workflow.
  Operator-facing terminology must use explicit source-kind vocabulary, and
  old aliases must not remain executable, callable, or listed.
- Short-form CLI flag aliases (`lt` / `pie` / `pi` / `ci`) are input-only
  ergonomic aids; they are not domain synonyms.
