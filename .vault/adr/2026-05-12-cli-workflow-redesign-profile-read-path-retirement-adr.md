---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-profile-read-path-retirement-research]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
---

# `cli-workflow-redesign` adr: `profile read path retirement` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Production code has moved to workflow-state profile reads, but old profile-file
language remains in tests and documentation. The redesign needs one profile
read path and no compatibility surface for envelope-era flat files.

## Considerations

Deadlines and filing runtime already read active workflow state. The legacy
profile envelope loader is gone from production code. Remaining references are
drift in tests, docs, and setup environment terminology.

## Constraints

Flat-file fallback, dual read paths, compatibility environment variables,
`--profile PATH`, and operator-facing profile-envelope references are rejected.
No command may keep an old profile-file path for compatibility.

## Implementation

Keep `workflow_state_repository()` as the only production profile read path.
Remove operator CLI, tests, and documentation references to `--profile PATH`,
`AEAT_DEFAULT_PROFILE_PATH`, and profile-envelope behavior.

CLI help and diagnostics describe active workflow-state selection, not profile
file selection. Events identify the active workflow-state-backed profile
context, not a profile file path.

## Rationale

The active workflow state is now the material runtime source. Keeping legacy
file-path affordances would create an unsupported compatibility surface and
obscure the actual execution model.

## Consequences

The redesigned CLI exposes no profile file selection path. Root and subcommand
tests must assert absence of `--profile` compatibility flags on retained
operator commands. Documentation must describe `config profile` and active
workflow state rather than profile envelope files.
