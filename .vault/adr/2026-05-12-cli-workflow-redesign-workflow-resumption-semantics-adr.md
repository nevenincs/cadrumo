---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-research]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cli-workflow-redesign` adr: `workflow resumption semantics` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Modelo filing resume needs a single user-facing command placement and a precise
contract. The existing workflow engine persists terminal `DONE` and `ABORTED`
`WorkflowResult` records, but it does not persist checkpoints or stage cursors.

Run-trace replay already exists as a separate diagnostic and audit concept. It
reproduces recorded CLI argv with corpus hash gating and `replay_of`.
Observability traces are not workflow-engine runs.

## Considerations

The CLI design keeps root commands limited to `config` and `app` entry points.
Modelo lifecycle behavior belongs under app modelo, and WorkflowEngine remains
behind the app modelo file boundary.

Resume should help the operator continue after an aborted modelo filing gate,
but the current engine cannot resume mid-stage. It can only load a terminal
result and start a new current-state attempt.

## Constraints

- No root `aeat workflow` or `aeat run` command is introduced.
- Resume accepts workflow-engine run ids, not observability or run-trace ids.
- Resume is continue semantics, not replay semantics.
- Resume does not reconstruct historical argv or force old inputs.
- Resume does not add compatibility shims.
- Resume does not duplicate filing state.

## Implementation

Adopt this command as the only user-facing resume placement:

```text
aeat app modelo resume <workflow_run_id>
```

`workflow_run_id` is a workflow-engine run id loaded through workflow
persistence.

Resume means continue from a prior terminal aborted modelo filing result, not
replay. The command loads the prior `WorkflowResult`, verifies that
`final_stage` is `ABORTED`, verifies enough modelo filing context to identify
the modelo, period, and target work unit, then starts a new current-state filing
attempt through the normal app modelo lifecycle.

Resume re-runs lifecycle gates from the beginning. It does not resume
mid-stage.

A resumed run creates a new workflow run id. The new `WorkflowResult` records
`resumed_from` with the prior workflow run id. It does not use replay metadata
and is not a reconstructed invocation.

If the target work unit or revision is already filed, resume is idempotent and
creates no new filing record.

If the prior run was `DONE`, resume returns either an already-complete no-op or
a nonzero domain error pointing to app modelo status or history. It does not
duplicate filing state.

Invalid observability or run-trace ids are refused with a typed error.

Failures are structured and nonzero without traceback output. Error output
includes:

- error
- prior workflow run id
- new workflow run id, if created
- stage
- aborted reason
- summary
- diagnostics

## Rationale

Resume belongs under `app modelo` because it continues a modelo filing
lifecycle, not an overview read model and not a generic workflow runner.

Continue semantics fit the current engine. Replay semantics belong to
observability/run-trace tooling because replay reconstructs an invocation;
resume works against current bucket state.

## Consequences

Resume remains part of the app modelo lifecycle and does not introduce a
workflow root.

Workflow persistence only needs terminal result loading and linking for this
ADR. Checkpoint continuation is out of scope.

Run-trace replay remains separate diagnostic and audit functionality. Resume
creates a new workflow result linked by `resumed_from`; replay reproduces
recorded CLI argv and uses replay-specific metadata.
