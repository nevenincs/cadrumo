---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-live-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-doctor-shape-adr]]"
---



# `cli-workflow-redesign` adr: `app registry boundary` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The registry CLI mixes local registry inspection, structural
verification, oracle binding audits, workbook verification, parity execution,
and live AEAT filed-declaration reads.

Apex §4.5 assigns registry authority to local registry inspection and
verification. Static modelo introspection belongs under `aeat app modelo`.

The app-live-shape ADR accepts filed declaration workflows under
`aeat app live filed`. Config repair is limited to readiness, connectivity, and
integrity diagnosis.

## Considerations

Live AEAT session behavior, sede declaration traversal, and
filed-observation persistence cross the registry boundary and make the CLI
shape unclear.

Registry still needs to own local authority checks, registry structure
verification, oracle binding audit, workbook verification, parity run/replay,
and local filed-state verification against captured observations.

Filed declaration traversal is remote AEAT observation. It belongs with the
accepted `app live` boundary.

## Constraints

- No compatibility aliases or shims are allowed.
- No root `aeat live` is introduced.
- `config repair` receives no filed-data, NIF-IVA/TGVI operational read, or
  registry parity workflow.
- All retained and moved commands use shared `--format json|text` and `_emit`
  typed reports.
- Legacy per-command `--json`, manual `json.dumps`, and metric-only rendering
  are removed.

## Implementation

`aeat app registry` remains the home for local registry authority and
verification workflows only.

Implementation mandate: move filed-data live-read commands
(`list-filed-data`, `capture-filed-data`, `capture-source-filed-data`) out of
registry and into `app live filed`. Registry keeps local authority and
verification only.

The following commands stay under `aeat app registry`:

```text
aeat app registry inspect [--registry-root PATH] [--format json|text]
aeat app registry verify [--registry-root PATH] [--source-root PATH] [--format json|text]
aeat app registry audit-oracles [--registry-root PATH] [--environment production|test_environment|both] [--format json|text]
aeat app registry verify-filed-state --observation PATH [--source-observation PATH ...] [--registry-root PATH] [--source-root PATH] [--casilla ID ...] [--format json|text]
aeat app registry workbooks verify [--root PATH] [--limit N] [--per-file-timeout SECONDS] [--output PATH] [--resume-from PATH] [--format json|text]
aeat app registry parity run --scenario PATH [--registry-root PATH] [--source-root PATH] [--store-root PATH] [--output PATH] [--format json|text]
aeat app registry parity replay --tape PATH [--registry-root PATH] [--source-root PATH] [--format json|text]
```

Filed declaration live reads move to `aeat app live filed`:

```text
aeat app live filed list --modelo MODELO --from-year YYYY --to-year YYYY [--format json|text]
aeat app live filed capture --modelo MODELO --year YYYY [--period PERIOD] [--expediente ID] [--limit N] [--format json|text]
aeat app live filed capture-sources --modelo MODELO --year YYYY --period PERIOD [--format json|text]
```

Static registry introspection remains with `aeat app modelo`.

Move `list_filed_data`, `capture_filed_data`, and
`capture_source_filed_data` out of `registry.py` into the app live filed
implementation.

Keep `require_live_read()` before authenticated live AEAT session access.

Persisted captures use `live.filed.capture_created`.

Remove or move old registry filed-data command registrations in the same
refactor that introduces `app live filed`.

## Rationale

Registry should answer whether local calculation registry material is
structured, complete, bound, and parity-verified. It should not be the
operator's live AEAT session traversal surface.

Moving live filed-data reads to `app live filed` aligns with the accepted
app-live-shape ADR and makes remote-contact intent visible to the operator.
Keeping local filed-state verification in registry is still coherent because it
compares captured observations against local registry/source expectations
without initiating remote reads.

## Consequences

The registry CLI has a narrower authority boundary: inspect local registry
state, verify registry structure, audit oracle bindings, verify filed
observations against registry/source state, verify workbooks, and run/replay
parity.

Live filed declaration reads become operational live workflows under
`aeat app live filed`.

Tests assert the old registry filed-data paths are absent and the new app live
filed grammar is present.

Rejected alternatives:

- Keep filed-data reads under `app registry`.
- Put filed-data reads under `config repair`.
- Add root `aeat live`.
- Keep compatibility aliases from old registry filed-data verbs.
- Preserve legacy `--json` on redesigned registry/live commands.
- Add shims for old command paths.
