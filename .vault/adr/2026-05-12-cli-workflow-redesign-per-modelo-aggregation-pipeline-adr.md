---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-research]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]"
---

# `cli-workflow-redesign` adr: `per-modelo aggregation pipeline` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Several modelos require aggregation from ledger and business-operation facts,
but the current substrate is split and still admits the forbidden bare
`invoice` source kind. The redesign needs one aggregation boundary that can
serve `app modelo bindings` without reintroducing ambiguous invoice semantics.

## Considerations

Aggregation spans modelo families: retenciones summaries, 347/349 counterpart
aggregation, 720 asset aggregation, Renta expense rollups, and later
modelo-specific requirements. The registry binding layer should consume
normalized source observations rather than each modelo inventing its own local
pipeline.

## Constraints

The only accepted source kinds are `ledger_transaction`,
`purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice`.
Bare `invoice` is forbidden. No `data` root, compatibility shim, or
modelo-local ad hoc aggregator is allowed.

## Implementation

Own modelo aggregation under `src/aeat/application/aggregation`. Expose
aggregation outputs as registry binding providers consumed by
`app modelo bindings` and `app modelo calculate`.

Migrate registry binding source declarations away from bare `invoice` to the
explicit source-kind taxonomy. Each aggregation provider declares its accepted
source kinds, period/modelo selectors, and output binding keys.

## Rationale

Application aggregation is the correct boundary between persisted ledger facts
and modelo registry calculation. It preserves domain purity, avoids duplicated
modelo-local data preparation, and keeps source-kind language aligned with the
invoice-domain-decoupling decision.

## Consequences

Retenciones, counterpart, asset, rental, OSS/IOSS, and future aggregation
pipelines can share one application-layer pattern. The registry binding schema
must be hardened so bare `invoice` cannot be declared or emitted.
