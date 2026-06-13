---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-145-foundation-research]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
---

# `cli-workflow-redesign` adr: `Modelo 145 foundation` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Modelo 145 is missing from the registry, but it is relevant for autónomos with
simultaneous employment or payer withholding communications. The design must
represent it without pretending it is an AEAT filing.

## Considerations

Modelo 145 is a communication to the payer. It is retained by the payer and is
not presented to AEAT through the filing lifecycle.

## Constraints

Do not fold Modelo 145 into Modelos 111 or 190. Do not use profile-only fields
without a registry/modelo foundation. Do not add filing-submission shims.

## Implementation

Add `registry/aeat/modelos/145.toml`, a form schema, and profile/binding
contract for employee withholding communication.

`app modelo` creates, verifies, exports, and marks the communication as
completed for local records. It does not file Modelo 145 with AEAT.

## Rationale

Modelo 145 has modelo-shaped data and lifecycle needs, but the lifecycle is a
non-filing communication. A registry-backed representation keeps the model
explicit while preserving the no-live-submission charter.

## Consequences

Modelo 145 becomes a first-class non-filing communication workflow. The `file`
verb must not imply AEAT submission for 145; wording should use local completion
or communication record language where needed.
