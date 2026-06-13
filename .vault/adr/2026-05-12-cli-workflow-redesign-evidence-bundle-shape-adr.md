---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-evidence-bundle-shape-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
---



# `cli-workflow-redesign` adr: `evidence bundle shape` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The CLI workflow redesign needs a concrete evidence packaging model for modelo
audit workflows.

The system needs durable evidence packaging for verification, export, and
replay. The package must not replace domain records as the source of truth, must
not create root audit/run command surfaces, and must not allow live AEAT
submission during replay.

## Considerations

Modelo verification reports, filing records, source-kind references, bucket
events, run traces, ledger snapshots, and profile snapshots already describe
the material needed for an audit handoff. The missing decision is how to package
them into a user-visible surface without turning the package into the truth
owner.

Evidence export and replay must be reproducibility tools. They do not contact
AEAT and do not become submission paths.

## Constraints

- No root `aeat audit` or `aeat run` command is introduced.
- No compatibility shims are added.
- Replay never contacts AEAT and never performs live submission.
- EvidenceBundle is bucket-scoped and work-unit-bound.
- Domain records remain authoritative.
- Bucket event history remains the chronological index.

## Implementation

Adopt an EvidenceBundle model surfaced through:

```text
aeat app modelo audit show WORK_UNIT_ID [--revision REV | --filing-record ID] [--format json|text]
aeat app modelo audit check WORK_UNIT_ID [--revision REV | --filing-record ID] [--format json|text]
aeat app modelo audit export WORK_UNIT_ID --output PATH [--revision REV | --filing-record ID] [--force-incomplete] [--format json|text]
aeat app modelo audit replay WORK_UNIT_ID [--revision REV | --filing-record ID] [--format json|text]
```

EvidenceBundle is bucket-scoped and work-unit-bound. Durable manifests and
verification reports are stored inside the active bucket under the modelo work
unit or filing case.

Bucket event history records:

- `modelo.audit.verified`
- `modelo.audit.exported`
- `modelo.audit.replayed`

Target selection defaults to the current filed filing record when one exists.
Otherwise, it uses the selected calculation revision. `--filing-record` is the
strongest selector.

The manifest includes bundle identity, schema version, creation time,
bucket/work-unit/modelo period identity, calculation revision, optional filing
record, verification report, profile snapshot/hash, ledger snapshot hash,
catalogue fingerprint, source-kind refs, export artefact refs and SHA-256
hashes, filed revision refs, run trace refs, replay digests, per-item status,
and final verdict.

Allowed per-item statuses are:

```text
present
missing
stale
mismatch
not_required
```

Allowed verdicts are:

```text
pass
fail
partial
replay_degraded
replay_corrupt
```

Exports are ZIP archives. `manifest.json` is written last. The archive contains
the manifest, verification report, filing record when present, calculation
revision, profile snapshot or redacted projection, ledger fingerprint/source
refs, export digest records, and redacted trace/events when referenced.

`audit export` runs verification first. Failed verification refuses export.
Partial verification requires `--force-incomplete`.

Replay is evidence-case replay. It uses stored traces, hashes, snapshots, and
inputs. It is not root argv replay. Replay can report match, degraded, or
corrupt states.

## Rationale

EvidenceBundle provides a stable provenance and reproducibility package without
changing domain ownership. Keeping the surface under `app modelo audit` ties it
to the work unit and filing case that it explains.

Writing the manifest last makes the ZIP export deterministic around a complete
payload. Requiring verification before export prevents quietly handing off a
failed bundle unless the operator explicitly accepts a partial package.

## Consequences

Modelo filing records, calculation revisions, profile snapshots, ledgers,
catalogues, and source records remain the truth-owning records.

Audit export becomes deterministic around a manifest-led ZIP shape and explicit
verification gate.

Replay is constrained to evidence validation and cannot become a submission
path.

The CLI surface remains inside `aeat app modelo audit`, avoiding root command
expansion and compatibility aliases.
