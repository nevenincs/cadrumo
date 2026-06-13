---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-foreign-currency-normalization-research]]"
  - "[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]"
---

# `cli-workflow-redesign` adr: `foreign currency normalization` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Financial inputs can carry non-EUR currency values, but modelo calculations
need normalized monetary values with auditable rate provenance. The current
provider layer exposes currency hints without a shared normalization path.

## Considerations

Currency conversion must happen before modelo bindings, after provider ingest
has preserved source evidence. The original currency and amount remain part of
the evidence trail.

## Constraints

Do not normalize inside BOE exporters. Do not silently assume EUR from
`default_currency` when row-level currency exists or is missing. Do not put
conversion logic in provider-specific adapters. Do not coerce currencies at
binding time through a shim.

## Implementation

Add FX normalization to `application/aggregation`. For each monetary source
fact, retain original amount and currency, resolve rate source and date,
compute normalized EUR amount, and expose normalization status to binding
providers.

Rows with missing or unsupported currency data become blocking readiness
findings before modelo calculation.

## Rationale

Aggregation is the boundary where source evidence becomes modelo-ready facts.
Putting normalization there keeps providers simple, keeps export serializers
format-focused, and makes binding inputs consistent.

## Consequences

Modelo builders receive EUR-normalized monetary facts with provenance. Evidence
keeps original currency data. Tests must cover non-EUR rows, missing currency,
rate-date selection, and rate-source persistence.
