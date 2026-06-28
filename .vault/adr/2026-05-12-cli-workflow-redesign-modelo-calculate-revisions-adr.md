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
  - "[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
---



# `cli-workflow-redesign` adr: `Modelo calculate revisions` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

Modelo calculation must support iteration without destroying audit history. If
`modelo calculate` mutates a verified or internally filed revision, later users
cannot prove which inputs, casillas, waivers, and source traces supported the
verified or filed result.

## Considerations

- Calculation is expected to be re-run as ledger financial transaction data,
  profile data, model schemas, prior filing references, filed revision records,
  or live observations change.
- Verified and filed revisions are durable workflow milestones.
- A forward calculation after an internal filing is not a detached draft. It is
  a new revision in the same modelo revision chain, anchored to the active
  filed revision for that bucket, modelo, year, and period.
- Users need a visible distinction between a current draft revision, a verified
  complete revision, and the current internally filed revision.
- The command must serve normal users and advanced users through one workflow,
  without introducing a separate expert command tier.

## Constraints

- `aeat app modelo calculate` creates a new calculation revision or refreshes a
  mutable draft revision.
- The command consumes the active bucket selected by `aeat config bucket`; it
  must not expose bucket management or an `app bucket` selector.
- The command drives bucket contents as part of normal app UX; users should not
  need direct bucket operations to calculate or recalculate a modelo.
- The command must never mutate a revision that is `verified complete`.
- The command must never mutate a revision that has been internally filed.
- Recalculation after verification or filing creates a new draft revision linked
  to the prior revision as its origin.
- When a filed revision exists, forward calculation must record that filed
  revision as the chain anchor and must preserve the filed revision as immutable
  historical state.
- Each revision remains scoped to bucket, modelo, year, period, and modelo schema
  revision.
- Revision status must be queryable so the CLI can show current draft, verified,
  filed, and superseded states without ambiguity.

## Implementation

- Add revision lifecycle handling to `aeat app modelo calculate`.
- Harvest accepted calculation behavior from declaration and filing runtime
  helpers into modelo work units and calculation revision storage.
- When no mutable draft exists, create a new draft calculation revision.
- When a mutable draft exists, refresh that draft and replace only draft-owned
  calculated values and source traces.
- When the selected or current revision is verified or filed, create a successor
  draft revision instead of editing the durable revision.
- Persist predecessor and successor links so users can trace why a new revision
  exists, which filed or verified revision it follows, and which filed revision
  anchors the active chain.
- Treat the revision chain as the forward-calculation path: filed revision,
  successor draft revisions, successor verified revisions, and any later filed
  revision remain linked as one auditable chain.
- `aeat app modelo status` and list-style views must expose revision identity,
  lifecycle state, origin revision, filed-chain anchor, and whether a newer draft
  exists.

## Rationale

Calculation is a working activity, while verification and filing are durable
workflow decisions. Separating mutable drafts from immutable approved revisions
keeps the audit trail intact and makes recalculation safe after new information
arrives.

## Consequences

- Storage must support revision lineage, mutable draft state, and immutable
  verified or filed state.
- Storage must make the filed revision chain explicit enough that later
  calculations can prove which filed revision they moved forward from.
- Status output becomes important because multiple revisions can exist for one
  bucket, modelo, year, and period.
- Tests must cover recalculation before and after verification or filing, and
  must prove durable revisions are not mutated.
