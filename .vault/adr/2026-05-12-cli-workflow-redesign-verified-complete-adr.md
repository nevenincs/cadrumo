---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `Modelo verified complete state` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The `modelo file` command needs a precise approval gate before it can mark a
modelo revision as internally filed. Without a concrete `verified complete`
state, the CLI could file a partially calculated revision, a revision with
unresolved required inputs, or a revision whose calculation trail cannot be
audited later.

## Considerations

- `modelo file` is an internal filing marker, not a live AEAT submission.
- A modelo work unit is scoped by active bucket, modelo, tax year, period, and
  revision.
- A calculation can depend on ledger financial transaction data, purchase
  invoice evidence metadata, payable invoice metadata, collectible invoice
  metadata, profile facts, prior filed modelo revisions, modelo schema rules,
  and explicitly recorded live-data observations.
- A user may need to acknowledge unavailable or intentionally excluded inputs,
  but that acknowledgement must be stored as an auditable decision rather than
  hidden in command output.
- Verification must be strong enough to protect production buckets and clear
  enough for a CLI user to understand why a revision can or cannot be filed.

## Constraints

- A revision cannot enter `verified complete` unless calculation has completed
  for its bucket, modelo, year, period, and revision identity.
- Required ledger, profile, prior-filing, and live-observation inputs must be
  satisfied or explicitly waived with a persisted reason.
- Waivers are typed decisions. A waiver cannot suppress required casilla
  resolution unless the modelo schema allows that input to be waived.
- All schema-required casillas for the selected modelo revision must be
  resolved.
- Blocking validation findings must be zero.
- The source trace for every calculated value must be persisted before the state
  is granted.
- The verification event must persist timestamp, verifier identity or source,
  command context, and the verification report used to make the decision.
- A verified revision is immutable. Any recalculation after verification creates
  a new revision instead of mutating the verified one.

## Implementation

- Introduce `verified complete` as a modelo revision lifecycle state.
- Grant this state only through the registered modelo revision lifecycle and
  `aeat app modelo verify`.
- `aeat app modelo verify` evaluates the active revision and writes a
  verification report containing completeness status, blocking findings,
  resolved casillas, source traces, and waiver records.
- `aeat app modelo file` requires the target revision to already be in
  `verified complete` state.
- The storage layer records verification reports as bucket-scoped relational
  data linked to the modelo work unit, calculation revision, profile snapshot,
  `ledger_transaction` sources, purchase invoice evidence, payable invoices,
  collectible invoices, prior filing references, and waiver decisions.
- Re-running calculation or verification after a verified revision exists must
  produce a new revision or a new verification attempt, not overwrite the
  accepted verification record.

## Rationale

`modelo file` is an approval command. Treating `verified complete` as its
required precondition keeps the approval meaningful: the user is not merely
renaming a working draft, but marking a specific, traceable, complete revision
as the current internally filed record for that bucket and period.

This separates three ideas that must not collapse into each other: calculation
drafts, verified complete revisions, and internally filed revisions. The
separation also keeps live AEAT submission permanently disabled and prevents
`file` terminology from overloading it.

## Consequences

- The calculation backend must emit structured completeness and blocking-finding
  reports before `modelo file` can be implemented safely.
- Modelo schemas must declare which inputs and casillas are required, which are
  conditionally required, and which can be waived.
- Bucket storage must support immutable calculation snapshots, verification
  reports, source traces, and waiver records.
- CLI tests must exercise real verification behavior and real storage links
  rather than asserting command text only.
- The command surface becomes slightly more deliberate: users calculate, verify,
  then file. The extra step is justified because filing is the durable approval
  event.
