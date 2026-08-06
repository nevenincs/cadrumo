---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-07-17'
body_hash: 'sha256:62b1010991fe34b6cf564cbd01114f019c86f60beb8915c6b5c1bfad93b73f2a'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
---

# `cli-workflow-redesign` adr: `domain harvest OSS/IOSS` | (**status:** `accepted`)

This decision governs the current IVA implementation under
`cadrumo.domain.iva`. It retains the Modelo 369 orchestration, profile keys,
typed OSS/IOSS binding flow, destination-country rate validation, and rejected
shapes described below. No `domain.vat` package or migration path is retained.
> See `2026-05-19-spanish-stem-terminology-authority-adr` for the canonical
> rename ledger and Spanish-stem terminology authority.

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `cadrumo.core.logging.get_logger(__name__)`, `cadrumo.core.logging.SecretScrubbingFilter`, `cadrumo.core.errors.CadrumoError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `cadrumo.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `cadrumo.entrypoints.cli._common._emit`, `cadrumo.entrypoints.cli._schemas.emit_json_success`, and `cadrumo.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Modelo 369 OSS/IOSS support has registry and domain substrate, but it lacks the
application binding that makes the feature usable through the redesigned CLI.
The design must decide whether OSS/IOSS becomes a separate user surface or is
harvested into the existing modelo calculation workflow.

## Considerations

The root contract permits only `aeat config` and `aeat app`. The app-modelo
shape already owns modelo work units, bindings, calculation revisions,
verification, file/export, and history. Current OSS/IOSS substrate lives in
`domain/iva/_oss.py`, while Modelo 369 TOML uses structured
`ledger_oss_aggregation` bindings. OSS/IOSS enrollment is profile state, not
calculation workflow state.

## Constraints

The 2026-05-06 Modelo 369 centralization ADR must be accepted or superseded
before execution begins. No live AEAT submission surface may be introduced. No
compatibility shim, legacy root, or support-only facade is allowed.

## Implementation

Use `aeat app modelo` as the only application surface for Modelo 369 OSS/IOSS
calculation. Do not introduce an OSS/IOSS mini-app or public VAT wrapper.

Add an application wrapper as a Modelo calculation-path binding provider. The
wrapper loads bucket, profile, and ledger facts; creates real
`OssIossLedgerObservation` rows; resolves `ledger_oss_aggregation` binding
values; feeds bound casillas into the Modelo 369 registry calculate path;
persists the calculation revision; and emits the modelo calculation event.

Keep `domain/iva/_oss.py` as pure substrate for `OssIossRegime`, filer roles,
periodicity, `regime_allows_deduction`, and destination-country VAT rate lookup.
Per-destination-country rate resolution remains in the VAT substrate through
`lookup_rate(member_state, kind, date)`. The application wrapper validates the
persisted IVA amount against the destination member-state rate and rejects
invalid lines before calculation output is persisted.

Configure OSS/IOSS through `config profile` using `iva.regime` and
`iva.oss_enrolled`. `app modelo` consumes profile state but does not own regime
configuration.

Route Modelo 369 bindings through `app modelo calculate`. TOML bindings use
`ledger_oss_aggregation` for exterior, union, and importacion revisions with
structured selectors.

## Rationale

OSS/IOSS is a Modelo 369 calculation requirement, not a standalone operator
domain. Keeping it inside `app modelo` avoids a domain-specific mini-app while
still exposing the calculation engine through the same lifecycle used by every
other modelo. Keeping VAT substrate pure lets ledger classification and
calculation aggregation reuse shared legal rules without turning the domain
module into CLI orchestration.

## Consequences

Modelo 369 OSS/IOSS remains centralized in the registry calculate path. VAT
substrate stays reusable and pure while `app modelo` owns orchestration,
persistence, events, and user workflow. Invalid destination-country VAT amounts
fail before calculation output is persisted or emitted.

`bindings list` and `bindings preview` are read-only and emit no bucket event.
`calculate` creates or refreshes a calculation revision and emits a material
bucket event. JSON output from calculation includes `operation`, `work_unit_id`,
`modelo`, `year`, `period`, `schema_revision_id`, `calculation_revision_id`,
`revision_state`, `resolved_binding_ids`, `missing_requirements`, and
`event_id`.

Rejected shapes are root `oss` or `ioss` commands, `app vat oss` commands,
direct CLI calls into `domain/iva/_oss.py`, compatibility shims, Decimal-only
binding flow for structured selectors, and conflating OSS/IOSS aggregation with
ledger VAT classification.
