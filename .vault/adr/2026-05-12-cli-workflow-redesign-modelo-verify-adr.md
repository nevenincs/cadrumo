---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-design-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-verified-complete-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---



# `cli-workflow-redesign` adr: `Modelo verify command` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The workflow needs a visible command that decides whether a modelo revision is
ready to become `verified complete`. If verification is hidden inside
calculation or filing, users cannot understand whether a failure came from
calculation mechanics, missing data, unresolved schema obligations, or the final
approval step.

## Considerations

- `modelo calculate` produces or refreshes a calculation revision.
- `modelo verify` evaluates whether that revision meets the `verified complete`
  contract.
- `modelo file` marks an already verified revision as the current internally
  filed revision.
- Verification must be usable by non-expert users without introducing a separate
  expert command tier.
- Verification output must explain missing requirements in domain language:
  bucket, ledger source, profile fact, prior filed revision, live observation,
  casilla, waiver, and blocking finding.

## Constraints

- `aeat app modelo verify` is the only command that grants `verified complete`
  state.
- The command is bucket-scoped through the active bucket selected by
  `aeat config bucket` and operates on one modelo, year, period, and revision at
  a time.
- The command must not manage, browse, rename, delete, or switch buckets.
- The command is normal app UX and must drive verification records inside the
  active bucket without asking the user to operate on the bucket directly.
- The command refuses verification, without mutating the target revision,
  whenever any blocking condition is not met.
- Refusal must persist a verification attempt report when it uses current bucket
  state to make a decision.
- The command must never submit, transmit, or live-file data with AEAT.
- The command must not be hidden behind an expert mode. Advanced detail can be
  controlled by output format or verbosity flags, but the workflow remains one
  workflow.

## Implementation

- Add `aeat app modelo verify` as the command that evaluates the active or
  selected calculation revision.
- Harvest accepted declaration verification/export behavior into modelo work
  units, calculation revisions, bucket-scoped verification reports, and the
  no-live-submission contract.
- On success, persist a verification report and set the revision lifecycle state
  to `verified complete`.
- On failure, persist a verification attempt report with blocking findings,
  missing inputs, unresolved casillas, invalid waivers, and the next action the
  user can take.
- Verification reports are stored in the active bucket and linked to the modelo
  work unit, calculation revision, source trace, profile snapshot, ledger
  financial transaction inputs, purchase invoice evidence records, payable
  invoice records, collectible invoice records, prior filing references, live
  observations, and waiver decisions.
- `aeat app modelo file` checks for `verified complete`; it does not rerun or
  silently grant verification.

## Rationale

Verification is a distinct decision in the CLI workflow. Keeping it explicit
lets the user inspect readiness before filing, keeps calculation repeatable, and
prevents `file` from becoming a command that both validates and approves durable
state.

This also preserves the project goal of helping users through complex tax
workflows without splitting the command tree into normal and expert paths.

## Consequences

- The modelo backend must expose a structured verifier rather than only computed
  totals.
- CLI output needs a clear failure report that maps backend findings to user
  actions.
- The storage schema must retain both successful verification reports and failed
  verification attempts.
- Tests must cover real calculate, verify, and file transitions across bucketed
  data, including refusal cases.
