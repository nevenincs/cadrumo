---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]"
---

# `cli-workflow-redesign` adr: `complementaria external filing path` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Complementaria construction must support filings made outside the tool through
imported official evidence. It must not require the original filing draft to
have been created locally.

## Considerations

The canonical command is already under `app modelo amend`. Filing-record import
and justificante evidence should provide the baseline, but incomplete evidence
must block amendment construction.

## Constraints

No live submit, legacy `aeat filing complementaria submit`, amendment without
official justificante/CSV minimum fields, or fabricated local original draft is
allowed.

## Implementation

Implement:

```text
aeat app modelo amend WORK_UNIT_ID --kind complementaria --from-filing-record ID --set CASILLA=VALUE [--reason TEXT]
```

The amendment path loads the filing record, verifies official justificante/CSV
minimum fields, checks schema compatibility, links the new revision to the
external filing record, and emits bucket events for amendment creation and
verification.

## Rationale

External filings can be legitimate baselines, but only official imported
evidence should unlock amendment construction. Keeping the command in
`app modelo amend` preserves the lifecycle boundary and avoids reviving the old
filing root.

## Consequences

Operators can amend externally filed returns without live submission. The
system refuses incomplete evidence and no longer depends solely on local
original draft persistence.
