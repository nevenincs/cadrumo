---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-observability-wrapping-decision-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr]]"
---

# `cli-workflow-redesign` adr: `observability wrapping decision` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

CLI observability wrapping exists but is unused. Adding it across the redesigned
CLI would introduce command-run trace concepts without a clear product need.

## Considerations

Bucket event history already owns material state-transition audit. Evidence
bundle replay owns evidence-case replay. Generic command wrapper traces are a
different concept and should not be introduced opportunistically.

## Constraints

Do not wrap every command opportunistically. Do not expose run ids, replay ids,
or generic observability context as root UX. Do not mix observability traces
with evidence-bundle replay.

## Implementation

Retire CLI observability wrapping from this redesign. Do not add root UX for
run ids, replay ids, or generic observability context. Material audit behavior
remains in bucket event history.

The existing helper module is implementation cleanup, not a user-visible
surface.

## Rationale

The redesign is narrowing and normalizing the CLI surface. Introducing unused
observability wrappers would add a parallel audit vocabulary while event
history and evidence bundles already cover the accepted audit use cases.

## Consequences

Retained commands do not expose observability wrapper metadata in normal text
or JSON output. Material state transitions remain represented by bucket event
history, not command wrapper traces. The root command contract stays focused on
`config` and `app`, with no observability-specific root flags or commands.
