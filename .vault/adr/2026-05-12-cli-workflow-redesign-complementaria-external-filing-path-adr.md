---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]"
---

# `cli-workflow-redesign` adr: `complementaria external filing path` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Complementaria construction must support filings made outside the tool through
imported official evidence. It must not require the original filing draft to
have been created locally.

## Considerations

The canonical command is already under `app modelo amend`. Filing-record import
and justificante evidence should provide the baseline, but incomplete evidence
must block amendment construction.

## Constraints

No live submit, legacy `aeat filing complementaria submit`, amendment without
official justificante/CSV minimum fields, or fabricated local original draft is
allowed.

## Implementation

Implement:

```text
aeat app modelo amend WORK_UNIT_ID --kind complementaria --from-filing-record ID --set CASILLA=VALUE [--reason TEXT]
```

The amendment path loads the filing record, verifies official justificante/CSV
minimum fields, checks schema compatibility, links the new revision to the
external filing record, and emits bucket events for amendment creation and
verification.

## Rationale

External filings can be legitimate baselines, but only official imported
evidence should unlock amendment construction. Keeping the command in
`app modelo amend` preserves the lifecycle boundary and avoids reviving the old
filing root.

## Consequences

Operators can amend externally filed returns without live submission. The
system refuses incomplete evidence and no longer depends solely on local
original draft persistence.

## 2026-05-15 amendment - reconcile-from-justificante interface

The 2026-05-15 ground-truth audit found that `aeat app modelo
reconcile from-justificante PATH` (W64 / W85.S2342 dependency) was
never wired despite the W85 closure claim. This amendment locks the
verb shape so the gap is closed in a follow-up wave.

Required CLI surface: a dedicated justificante-sourced reconcile verb,
`aeat app modelo reconcile-from-justificante PATH WORK_UNIT_ID`. It
shares the `modelo_reconcile` application service entry point with
the `--from-justificante` flag variant of the parent verb (decided
under app-modelo-shape ADR amendment); this verb is sugar for
operators who think "reconcile from this justificante" rather than
"reconcile, source = justificante".

The verb ships as a hyphenated sibling of `reconcile` rather than a
nested Typer subgroup (`reconcile from-justificante`). The nested
form was attempted and rejected: Click's argument parser resolves
the parent positional (`WORK_UNIT_ID`) before any subcommand token,
so `reconcile WORK_UNIT_ID --from-justificante PATH` parses
`--from-justificante` as a subcommand name and raises "No such
command". Preserving the canonical flag form on the parent verb —
and the apex CLI convention of positionals-before-options — requires
the justificante verb to be a flat hyphenated sibling. The hyphenated
form `reconcile-from-justificante` is the canonical realisation of
this amendment's "subverb" intent and is normative; the prose
"subverb under reconcile" describes the operator's mental model, not
a Typer subgroup requirement.

Required behaviour: parse the supplied justificante PDF via
`JustificanteRepository`; produce a `ReconciliationReport` keyed by
work unit; emit the reconciliation event on the bucket-event
catalogue; refuse if the work unit is in a non-reconcileable state
(e.g. pre-DRAFT) or if the parser yields invalid evidence.

Required errors: `ReconciliationEvidenceInvalidError` for malformed
justificantes; `ReconciliationMismatchError` is a verdict carried in
the report payload, not a hard CLI error (operators must be able to
inspect mismatches without a non-zero exit).

The verb is local-only and does not invoke `require_live_read`.
