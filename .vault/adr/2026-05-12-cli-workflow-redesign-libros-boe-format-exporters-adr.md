---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-research]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` adr: `libros BOE format exporters` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The project can export filing-oriented modelo layouts, but it lacks
libro-registro exporters for ledger record books. These are distinct artifacts
from modelo filing exports.

## Considerations

Libros for facturas emitidas, facturas recibidas, ingresos/gastos, and bienes
de inversión are ledger outputs backed by ledger and business-operation facts.
They are not calculation revisions or filing records.

## Constraints

Do not reuse `app modelo export` for libros. Do not ship JSON-only libro
exports. Do not disguise filing export layouts as libro layouts.

## Implementation

Add `aeat app ledger export libros ...` backed by outbound AEAT/BOE format
adapters. The exporters consume ledger facts and explicit source kinds,
including `payable_invoice`, `collectible_invoice`,
`purchase_invoice_evidence`, and `ledger_transaction` where applicable.

The output formats are versioned per libro schema and validated before write.

## Rationale

Ledger exports answer a different user need from modelo exports. Keeping them
under `app ledger` preserves the boundary between evidence books and modelo
calculation/filing artifacts.

## Consequences

Libro-registro exports become first-class ledger outputs. Modelo export remains
reserved for modelo-compatible declaration artifacts. Tests must cover schema
columns, source-kind mapping, and non-JSON file output.
