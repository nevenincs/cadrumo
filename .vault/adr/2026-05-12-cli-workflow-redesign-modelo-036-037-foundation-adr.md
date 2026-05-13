---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-research]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr]]"
---

# `cli-workflow-redesign` adr: `Modelo 036 and 037 foundation` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Census workflows are foundational for autónomos, but 036/037 registry files are
missing. The design must add a current Modelo 036 foundation while preserving
Modelo 037 only as historical, inactive metadata.

## Considerations

Modelo 036 is event-triggered rather than periodic: alta, modificación, and
baja happen when census state changes. Modelo 037 was suppressed from
2025-02-03 and must not remain an active workflow.

## Constraints

No portal-only support, setup wizard substitute, integer modelo codes, live
submission, or Modelo 037 active shim is allowed. Modelo codes remain strings
so leading-zero codes are preserved.

## Implementation

Add a Modelo 036 registry foundation with sectional decomposition, profile
bindings, and event-triggered work-unit lifecycle for `alta`, `modificacion`,
and `baja`.

Keep Modelo 037 as historical source metadata only, inactive and superseded by
036. Portal discovery may list historical 037 metadata, but `app modelo`
refuses new active 037 work units.

## Rationale

Census state belongs in the modelo/workflow system, not as a setup wizard
substitute. Treating 036 as registry-backed preserves traceability and lets
profile state derive from explicit census history.

## Consequences

The project gains a filing-grade foundation for census workflows without
reviving Modelo 037. Tests must cover string modelo codes, event-triggered
period semantics, and inactive 037 refusal.
