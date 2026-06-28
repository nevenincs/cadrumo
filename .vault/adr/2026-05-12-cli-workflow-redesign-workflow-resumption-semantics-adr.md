---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-research]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
---



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

Adopt this command as the only user-facing resume placement in the reconciled
modelo work-unit surface:

```text
aeat app modelo work resume <workflow_run_id>
```

`workflow_run_id` is a workflow-engine run id loaded through workflow
persistence.

Resume means continue from a prior terminal aborted modelo filing result, not
replay. The command loads the prior `WorkflowResult`, verifies that
`final_stage` is `ABORTED`, verifies enough modelo filing context to identify
the modelo and period, then returns the current-state retry context the normal
modelo lifecycle will consume.

Resume validation does not reconstruct argv, mutate the prior run, emit bucket
events, or resume mid-stage.

The returned context records `resumed_from_run_id` with the prior workflow run
id. It does not use replay metadata and is not a reconstructed invocation.

Resume itself creates no filing record. A later verify or file attempt uses
the normal current-state lifecycle gates for already-filed or non-resumable
conditions.

If the prior run was `DONE`, resume returns either an already-complete no-op or
a nonzero domain error pointing to app modelo status or history. It does not
duplicate filing state.

Invalid observability or run-trace ids are refused with a typed error.

Failures are structured and nonzero without traceback output. Error output
includes:

- error
- prior workflow run id
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

Resume remains part of the `app modelo work` lifecycle and does not introduce
a workflow root.

Workflow persistence only needs terminal result loading and linking for this
ADR. Checkpoint continuation is out of scope.

Run-trace replay remains separate diagnostic and audit functionality. Resume
returns current-state context linked by `resumed_from_run_id`; replay
reproduces recorded CLI argv and uses replay-specific metadata.

## 2026-05-14 reconciliation amendment — shipped command surface

Wave W80 closes the absent-resume regression through
`aeat app modelo work resume WORKFLOW_RUN_ID`. The handler delegates to
`resume_modelo_workflow`, accepts workflow-engine run ids only, emits the
resumable modelo/period/obligation context, and stays local-only. It does not
introduce root `aeat workflow`, root `aeat run`, flat `aeat app modelo resume`,
observability replay ids, argv reconstruction, mid-stage continuation, bucket
events, or compatibility surfaces.

## 2026-05-15 amendment - engine linkage requirement

The 2026-05-15 ground-truth audit found that the W59 and W80 execution
records claim a `WorkflowResult.resumed_from` field and a
`WorkflowEngine.run_for_period(resumed_from=...)` parameter exist;
neither is present in `src/aeat/application/workflow/_models.py` or
`_engine.py`. This amendment locks the engine-linkage contract so the
gap is closed in a follow-up wave rather than left implicit.

Required engine surface:

- `WorkflowResult.resumed_from: str | None` field carrying the prior
  workflow_run_id when the run was launched from a resume context.
- `WorkflowEngine.run_for_period(..., resumed_from: str | None = None)`
  parameter; when provided, the engine validates the prior run is
  terminal-aborted and belongs to the same profile + modelo + period
  scope before proceeding, refuses unknown run ids, and propagates the
  value into the produced `WorkflowResult`.
- `resume_modelo_workflow` does not invoke the engine itself; it
  returns the `WorkflowResumeContext` and the caller (typically the
  filing or verify path on the next operator action) passes
  `resumed_from=context.resumed_from_run_id` to `run_for_period`.

The CLI `aeat app modelo work resume` surface is unchanged.

## 2026-05-16 closure — engine linkage shipped

The engine-linkage gap recorded above is now closed:

- `WorkflowResult.resumed_from: str | None` ships in
  `src/aeat/application/workflow/_models.py` with field validation.
- `WorkflowEngine.run_for_period(..., resumed_from: str | None = None)`
  ships in `src/aeat/application/workflow/_engine.py` and validates the
  parameter shape at the boundary (16-char lowercase hex), forwarding
  the value into the produced `WorkflowResult`.
- The revision-verify gate
  (`_run_revision_workflow_gate` in
  `src/aeat/application/modelo/_actions.py`) accepts an optional
  `resumed_from` and forwards it to `run_for_period`, so callers
  driving a fresh attempt over a prior aborted run preserve the
  linkage end-to-end.

Real-behavior coverage:

- Unit: `test_run_for_period_propagates_resumed_from_into_result`,
  `test_run_for_period_rejects_malformed_resumed_from`
  (`src/aeat/application/workflow/test_engine.py`).
- End-to-end: `test_resume_context_run_id_satisfies_engine_resumed_from_contract`,
  `test_resume_is_idempotent_for_a_persistently_aborted_run`,
  `test_resume_for_unknown_run_id_is_indistinguishable_from_stale`
  (`src/aeat/application/workflow/test_resume.py`).

Existence verification of the prior run remains the upstream resume
action's responsibility — the engine validates shape only.
