---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `Modelo file command internal filing approval` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The modelo lifecycle needs an explicit approval command that records a
calculated modelo revision as the current internally filed revision for the
active profile bucket. Current terminology risks conflating local approval,
local logical filing state, export generation, and live AEAT submission.

The CLI needs a precise command for the calculation workflow approval moment:
the operator has reviewed and verified a modelo revision, and now wants the
local system to treat that revision as filed inside the bucket.

## Considerations

- `modelo` is the primary calculation and internal filing domain.
- Modelo work units are bucket-scoped and keyed by modelo, year, period, and
  revision.
- A calculated revision must be verified complete before it can become current
  filed state.
- Internal local filed state is not live AEAT submission.
- Live-compatible export remains a separate concern.
- The command name should be plain user language. `file` is acceptable here
  because it means "mark this verified modelo revision as filed internally",
  not "submit to AEAT live".

## Constraints

- `aeat app modelo file` must never perform live AEAT submission.
- `aeat app modelo file` must require a verified complete modelo revision.
- The command must persist a timestamped bucket event and create the paired
  filing record defined for internal filing state.
- The command must mark exactly one current filed revision for the relevant
  bucket/modelo/year/period tuple by updating the current filed pointer to the
  new filing record.
- The command must preserve prior filed markers and decision history for audit.
- The command must be bucket-scoped through the active profile and active bucket
  selected by `aeat config bucket`.
- `aeat app modelo file` must not introduce bucket management or an `app bucket`
  selector. Any future bucket override belongs to the config surface.
- The command is normal app UX and writes filing state into the active bucket
  through backend services; it must not send users to bucket commands for normal
  filing approval.
- CLI copy must make the local/internal nature of the transition explicit.

## Implementation

Approve `aeat app modelo file` as the calculation workflow approval command.

Implementation mandate: expose `aeat app modelo file` under the modelo
work-unit, filing-record, bucket-event, and internal-filing semantics defined
here. Harvest accepted declaration/filing approval behavior into this surface
and remove incompatible command paths without aliases or shims.

Command semantics:

- Input: target modelo work unit, addressed by modelo/year/period/revision or a
  stable work-unit id.
- Preconditions:
  - active profile bucket exists
  - target work unit belongs to the bucket
  - target work unit is calculated
  - target work unit is verified complete
- State transition:
  - create a filing record with timestamp, actor/source, target revision,
    submitted status, and reason/notes where supplied
  - append a bucket history event linked to the filing record and target
    revision
  - mark the filing record as current filed state for the
    bucket/modelo/year/period tuple
  - leave prior filed revisions and events readable for audit
- Non-actions:
  - does not submit to AEAT
  - does not imply AEAT acceptance
  - does not overwrite source ledger/profile data
  - does not erase prior calculation revisions

Command shape:

- `aeat app modelo file --modelo 303 --year 2026 --period Q1 --revision REV`
- `aeat app modelo file WORK_UNIT_ID`

The full selector grammar is locked by the app-modelo-shape ADR.

## Rationale

`file` is the clearest verb for the operator approval moment if the product
defines it precisely as local internal filing state. It names the business event
better than `approve`, which can mean generic review approval, and better than
`submit`, which must remain reserved for live AEAT submission and is disabled.

The command also gives the modelo domain a concrete lifecycle endpoint:
calculate, verify, then file internally. That endpoint is needed before bucket
export/import and historical decision review can be meaningful.

## Operator-visible submission disambiguation (apex review 2026-05-12)

The English verb `file` is widely read by Spanish autónomo operators as
"presentar/submit to AEAT", which `aeat app modelo file` explicitly does not
do. The disambiguation is non-optional and is enforced at three points:

- The command's help text first line reads "Mark a verified modelo revision
  as internally filed in the active bucket. Does NOT submit to AEAT."
- Every successful invocation prints a final output line including the
  parenthetical "(internal only — does not submit to AEAT)".
- Every interactive confirmation (where one is shown) repeats the same
  parenthetical.

In machine-readable output the structured fields `kind: "internal_filing"`
and `live_submission: false` carry the same disambiguation. The qualifier is
a UX constraint, not a stylistic choice; the wording is fixed so localization,
JSON output, and help text remain in lockstep.

## Consequences

- Modelo storage must support immutable calculation revisions and a mutable
  current-filed pointer per bucket/modelo/year/period that resolves through a
  filing record.
- Filing-record storage and bucket event history must be implemented before this
  command is safe.
- Existing declaration/filing approval language must be audited and reconciled
  with `modelo file`.
- Export commands must not be described as filing commands.
- Live AEAT submission terminology remains reserved and disabled.
- The submission-disambiguation qualifier in help, output, and confirmations is
  mandatory; it is not stylistic.
- The selector grammar is locked by the app-modelo-shape ADR; the verified-
  complete state definition by the verified-complete ADR; the filing-record
  schema by the modelo-filing-record ADR; the bucket event-history schema by
  the bucket-event-history ADR. No further ADRs are required for this
  command.
