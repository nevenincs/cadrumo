---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
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

Profile-associated secure bucket values are the source of truth for
profile-bound runtime data. `WorkflowState` is a selector and pointer store
only: it keeps profile entries as active profile pointers and callers use the
active pointer to load the selected profile bucket through the secure object
repository.

The application must not read or persist profile-bound values as profile JSON,
profile files, profile paths, flat-file fallback data, shared workflow-state
profile values, or any equivalent compatibility surface.

## Considerations

Profile values live under `PROFILE_BUCKET_NAMESPACE =
"aeat.application.profile.bucket"` and are stored as
`Envelope[ProfileBucket]` with `SensitivityClass.IDENTITY`.

Runtime profile reads start from `WorkflowState` only to identify the active
profile pointer. The application then dereferences that pointer with
`profile_bucket_repository().load(...)` and reads bucket-backed profile values
from the loaded profile bucket.

Wizard persistence writes profile-bound answers through `set_profile_values`
into the active profile bucket. Config and setup reset delete both workflow
pointers and actual profile buckets. Archive registration uses the profile
bucket adapter and derives the secure-object key from `bucket_id`.

## Constraints

Flat-file fallback, dual value paths, compatibility environment variables,
`--profile PATH`, operator-facing profile-envelope references, profile JSON,
profile files, profile paths, and shared workflow-state profile values are
rejected.

`WorkflowState` may select the active profile bucket. It must not store profile
values or become the profile value repository.

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement
business logic, schema conversion logic, validation policy, orchestration
rules, persistence behavior, provider behavior, or compatibility surfaces. CLI
commands MUST call centralized, tested Pydantic backend, storage, error, and
output services.

## Implementation

Use `workflow_state_repository()` only for workflow state, active profile
selection, and profile bucket pointers. Store profile values in the
profile-associated secure bucket through `profile_bucket_repository()`.

Remove operator CLI, tests, settings, and documentation references to
`--profile PATH`, `AEAT_DEFAULT_PROFILE_PATH`, tax-residence profile paths,
JSON draft input providers, and profile-envelope behavior.

CLI help and diagnostics describe active profile bucket selection, not profile
file selection. Events identify the active profile bucket context and the
affected profile object.

## Rationale

Profile-bound runtime state has one durable value source: the
profile-associated secure bucket. Workflow state remains valid as a workflow
selector and active profile pointer store, but it is not a value source.

## Consequences

Profile persistence, reset, archive registration, wizard writes, and filing
runtime reads all converge on the secure object repository model.

Tests and verification must prove real secure-object persistence and must
include negative coverage that rejects JSON/path/profile-value-in-workflow
fallback behavior.

The redesigned CLI exposes no profile file selection path. Root and subcommand
tests must assert absence of `--profile` path compatibility flags on retained
operator commands. Documentation must describe `config profile`, active profile
selection, and profile-associated secure buckets rather than profile envelope
files.
