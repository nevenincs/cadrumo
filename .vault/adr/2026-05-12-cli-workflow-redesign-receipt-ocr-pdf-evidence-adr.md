---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-research]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---

# `cli-workflow-redesign` adr: `receipt OCR PDF evidence` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

`app ledger attach` needs a path for purchase receipts and purchase invoice
evidence, but the existing PDF parsing work targets AEAT filing justificantes,
not supplier evidence.

## Considerations

Purchase receipt OCR/PDF extraction supports ledger transaction evidence. It
must produce `purchase_invoice_evidence`, not a generic invoice and not a
modelo filing receipt.

## Constraints

Do not treat AEAT justificante parsing as receipt OCR. Do not emit bare
`invoice`. Do not use LLM/OCR extraction without stored evidence provenance.
Do not place justificante PDFs into casilla data.

## Implementation

Add an `app ledger attach` evidence adapter for receipt and purchase invoice
PDF/image inputs. Store the source file hash, extraction method, extraction
confidence, extracted fields, manual-review state, and transaction link inside
the active bucket.

The adapter emits `purchase_invoice_evidence` and records bucket events for
attachment creation, review, replacement, and removal.

## Rationale

Supplier evidence and AEAT filing receipts are different artifacts. Keeping
them separate protects filing-record semantics and gives ledger classification
the evidence it actually needs.

## Consequences

Ledger ingestion can be completed with traceable purchase evidence. Any OCR or
LLM output remains reviewable evidence, not an unproven calculation input.
