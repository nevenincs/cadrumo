---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-engine-harvest-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cli-workflow-redesign` adr: `workflow engine harvest` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The CLI workflow redesign needs a single modelo filing surface. The existing
workflow engine is useful as a read/preflight lifecycle gate, but exposing it as
a separate command family would create a second lifecycle beside
`aeat app modelo file`.

Apex assigns WorkflowEngine `run_next` and `run_for_period` targeting to
`app modelo file`, while app-modelo-shape rejects an app declaration lifecycle
root, filing root, submit/presentation/preflight commands, and live submission
behavior.

## Considerations

The modelo-file decision defines `file` as local/internal filing state, not live
submission. Filing requires a verified complete revision and creates a filing
record plus bucket event.

Current WorkflowEngine behavior is read/preflight-only. `run_for_period`
targets modelo/period, stops after preflight `DONE`, creates no submission id,
and tests pin that no submission id exists.

Historical workflow docs are stale: they describe dry-run submit stages and
double-gate submit behavior that no longer exist in the current engine.

## Constraints

- No standalone workflow root is introduced.
- No per-stage workflow verbs are exposed.
- No standalone `app modelo preflight` command is exposed.
- No command performs or implies live submission.
- No compatibility shims from `app declaration` approve/file or `filing` paths
  are provided.
- Domain gate failures return non-zero without traceback.

## Implementation

Use WorkflowEngine as an application-layer lifecycle gate behind
`aeat app modelo file`.

Do not expose WorkflowEngine as public CLI structure.

Keep `WorkflowEngine.run_for_period` as a public application method, but not as
a public CLI command.

Keep `WorkflowEngine.run_next` application-only.

`aeat app modelo file` will:

1. Resolve the active bucket/profile and work unit.
2. Require a calculated and verified-complete revision.
3. Call `WorkflowEngine.run_for_period(profile, modelo, period, as_of=...)`.
4. Translate the workflow result into command output, errors, and bucket
   events.

On `DONE`, `aeat app modelo file` creates internal filing state:

- filing record
- bucket event
- current-filed pointer update

Success output includes:

- work-unit id
- modelo
- year
- period
- revision
- filing-record id
- event id
- actor
- filed-at
- `internal_file=true`

On `ABORTED`, the command creates no filing state and emits structured failure
output:

- error
- workflow run id
- stage
- aborted reason
- summary
- step diagnostics

Usage errors remain CLI parameter errors.

Rejected public shapes:

- `aeat workflow`
- per-stage workflow verbs
- `aeat app modelo preflight`
- submit, presentation, or live-submit aliases
- shims from app declaration approve/file/filing paths
- standalone workflow root

## W80 closure note

W80 closes the implementation path as WorkflowEngine-only preflight routing for
modelo verify/file. `verify_modelo_revision` runs `_run_modelo_workflow_gate`
after local completeness grants and before verification report/state
persistence. `file_modelo_revision` runs the same gate before filing writes.

`_run_modelo_workflow_gate` builds the revision-backed filing draft from the
immutable `CalculationRevision` output, auto-approves the `READY_TO_SUBMIT`
draft for preflight, runs `WorkflowEngine.run_for_period`, saves the workflow
result, and raises `ModeloWorkflowGateError` when the result is not `DONE`.
`WorkflowEngine` remains the only caller of `SubmissionEngine.preflight`
through `SubmissionEngineAdapter`.

Consequences: no standalone `aeat workflow`, `aeat run`, `app modelo
preflight`, or direct modelo `SubmissionEngine.preflight` command is exposed.
The verify path aborts before report/state persistence and the file path
aborts before filing writes on workflow/preflight failure. Modelo 180 deadline
support and cross-year filing-window coverage were added as part of the W80
verification surface.

## Rationale

The workflow engine is valuable as an internal readiness/preflight gate, but it
is not the operator's workflow language. The operator approves a modelo work
unit revision as internally filed through `app modelo file`; the engine verifies
that the relevant workflow conditions are satisfied before that local state
transition occurs.

Keeping `run_for_period` out of CLI avoids exposing engine plumbing and stale
stage vocabulary. It also preserves the no-submission invariant by making the
only public filing action an internal-file command.

## Consequences

WorkflowEngine is harvested without creating a second CLI lifecycle.

`app modelo file` becomes the only filing command surface.

The old app declaration lifecycle path is moved or retired.

The implementation preserves the current no-submission invariant: internal file
is local state only and does not perform live submission.
