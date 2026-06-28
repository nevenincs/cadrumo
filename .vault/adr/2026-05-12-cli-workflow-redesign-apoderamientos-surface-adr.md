---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
---

# `cli-workflow-redesign` adr: `apoderamientos surface` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Representative operation is a real AEAT workflow, but the current auth surface
does not support representative selection. The CLI needs an explicit design
that makes representation visible without implying live AEAT mutation or filing
authority.

## Considerations

Apoderamiento concerns identity and authorization configuration, so it belongs
under `aeat config auth`. Live checks may contact AEAT read-only, but
registration, extension, revocation, confirmation, and renunciation are not
accepted operator actions in this redesign.

## Constraints

No automatic representation form submission, live apoderamientos mutation,
filing-as-representative shortcut, or compatibility shim is allowed. Live AEAT
submission remains forbidden.

## Implementation

Add `aeat config auth apoderado ...` as a configuration and read-only status
surface:

```text
aeat config auth apoderado status [--format json|text]
aeat config auth apoderado configure --represented-nif NIF --scope SCOPE [--format json|text]
aeat config auth apoderado clear [--format json|text]
aeat config auth apoderado check [--format json|text]
```

`configure` and `clear` mutate local bucket-scoped auth configuration and emit
auth events. `check` is read-only live verification and calls
`require_live_read()` before remote contact.

## Rationale

Representation is part of auth configuration, not the tax workflow itself.
Making it explicit prevents accidental own-name assumptions while refusing
dangerous live mutation paths.

## Consequences

The CLI can report and configure represented identity intent without modifying
AEAT apoderamientos. Downstream live and modelo workflows must refuse
representative operation unless configuration and read-only checks are
satisfied.
