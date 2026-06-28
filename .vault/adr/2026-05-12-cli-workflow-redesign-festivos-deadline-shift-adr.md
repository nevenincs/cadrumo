---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-festivos-deadline-shift-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
---

# `cli-workflow-redesign` adr: `festivos deadline shift` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Deadline computation must not use registry close dates directly for
operator-facing calendar and agenda views because AEAT deadlines can
shift when the close date falls on a non-business day, with modelo-specific
exceptions.

## Considerations

The correct behavior belongs in the deadline domain, not in CLI rendering.
Overview needs explainable deadline rows that show both the registry close date
and the adjusted legal due date.

## Constraints

No Rich-only CLI patch, hardcoded CLI calendar table, profile-path legacy read,
silent shift, or compatibility shim is allowed. The deadline engine must keep
the adjustment source and exception reason explainable.

## Implementation

Add a pure holiday-adjustment service under `domain/deadlines`. The service
uses national plus CCAA/local holiday sources and supports modelo-specific
exceptions such as Modelo 369.

`app overview calendar` and `app overview agenda` consume adjusted deadline
records containing original close date, adjusted close date, jurisdiction
layer, source id, and explanation.

## Rationale

Deadline adjustment is legal/domain behavior. Putting it in the domain layer
keeps every app surface consistent and avoids duplicating holiday logic in the
CLI.

## Consequences

Overview calendar and agenda views become legally explainable. Tests must cover
normal shifts, CCAA/local shifts, weekends, and modelo-specific exception
behavior.
