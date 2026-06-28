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
  - "[[2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-verified-complete-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
---



# `cli-workflow-redesign` adr: `Modelo filing record` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

Marking a modelo revision as internally filed must not overload the calculation
revision itself with every later filing concern. A filed calculation revision is
the immutable approved calculation state; the workflow also needs a paired
filing record that tracks the local filing event and any later export or
submission status.

## Considerations

- `aeat app modelo file` is a local workflow approval command, not a live AEAT
  submission.
- A calculation revision may be verified complete before it is filed.
- A filing event must preserve which exact calculation revision was filed.
- Submission and export readiness are related to filing, but they are not the
  same thing as calculation correctness.
- Future live-compatible export or submission tracking needs a place to record
  state without mutating the filed calculation revision.
- Bucket event history is a missing backend capability that this decision
  depends on for auditability.

## Constraints

- Every successful `aeat app modelo file` creates a filing record paired with the
  filed calculation revision.
- The filing record is scoped by bucket, modelo, year, period, modelo schema
  revision, and calculation revision identity.
- The bucket scope comes from the active bucket selected by `aeat config bucket`;
  filing record commands must not introduce bucket management under `app`.
- Filing records are created by normal app workflow commands. Direct bucket
  operations are not required for normal filing-record creation or inspection
  through modelo status.
- The filed calculation revision remains immutable.
- The filing record must record local filed status independently from
  AEAT-acceptance status.
- AEAT-acceptance status must be tracked explicitly via the `aeat_accepted`
  field and must default to `false` (not accepted by AEAT). The field name
  `aeat_accepted` (not `submitted`) prevents the field from being read as a
  pending submission slot.
- A filing record tracks exportable and exported states. Live AEAT
  submission is permanently forbidden; the `aeat_accepted` field exists
  only to record an externally-observed AEAT acceptance imported into the
  bucket through read-only live signals. The filing record itself never
  initiates a live submission.
- A new filing record can supersede the current filing record only by filing a
  later verified revision in the same revision chain.

## Implementation

- `aeat app modelo file` creates a filing record after confirming the target
  revision is `verified complete`.
- Introduce the paired filing-record object, current-filed pointer, and
  bucket-event writes as part of the modelo filing lifecycle.
- The filing record stores the filed revision id, filing timestamp, actor or
  command source, filed status, `aeat_accepted` status (default `false`),
  optional export status, and supersession relationship.
- The calculation revision stores or exposes a link to its paired filing record,
  but filing status is represented by the filing record, not by mutating
  calculation payloads.
- The current filed pointer for a bucket, modelo, year, and period resolves to a
  filing record, which then resolves to the filed calculation revision.
- Filing record creation must emit a bucket-scoped history event once bucket
  event history exists; that history is exposed through the config bucket
  surface, not an app bucket command.

## Rationale

This separates four concerns that need different lifecycles: calculation drafts,
verified complete revisions, internal filing approvals, and possible future
submission/export state. A filing record gives the CLI a clear object to show in
status output and gives the backend a stable place to track whether a locally
filed modelo has ever been exported or submitted.

## Consequences

- Storage must add a filing-record concept instead of using only calculation
  revision state.
- Status/list output must explain revision identity and filing record identity
  without making the workflow feel fragmented.
- Filing records must write a `modelo.filed` event to the bucket-scoped event
  history (locked by the bucket-event-history ADR) in the same logical
  transaction as the filing-record creation.
- Tests must prove that filing creates a paired filing record, does not mutate
  the filed revision, defaults `aeat_accepted` to `false`, and preserves
  superseded filing records.
