---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-live-shape-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-doctor-shape-adr]]"
---



# `cli-workflow-redesign` adr: `app live shape` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The CLI needs an explicit home for commands that directly observe AEAT remote
systems.

Current command placement is drifting. `app registry` mixes registry
inspection, local validation, oracle audit, and live AEAT reads. Some captures
persist outside the active bucket event surface. The apex leaves live app
placement open, while existing adapters already implement guarded read-only
remote observation.

The operator needs a clear signal that a command may contact AEAT. Registry,
model history, overview, and config diagnostics should not obscure that
boundary.

## Considerations

Existing live-read surfaces are not one domain's lifecycle. Notifications,
expedientes, filed declarations, NIF-IVA verification, TGVI/GROI verification,
Borrador 100, and portal discovery cross modelo, overview, registry, and
diagnostics.

The backend already has safety primitives: live reads are gated by the access
gate, live writes are forbidden, Renta WEB Open guards unsafe navigation, GROI
refuses form-action drift, notifications are read-only, and NIF-IVA is a
read-only public verification path.

Persisted live observations are operational records. Under the bucket ADR and
bucket-event-history ADR, they must be bucket-linked and evented.

## Constraints

- Root command shape remains exactly `aeat config` and `aeat app`.
- `aeat app live` is read-only.
- No live command name uses `submit`, `present`, `sign`, or `pay`.
- Every command that performs remote navigation or remote requests calls
  `require_live_read()` before remote contact and authenticated session
  creation.
- No `app live` command calls `require_live_write()`, except refusal tests that
  assert writes remain forbidden.
- All command output goes through `_emit` typed reports.
- Non-persisting live reads emit no bucket event.
- Persisted captures and snapshots resolve an active bucket and emit material
  operation events.

## Implementation

Accept `aeat app live` as the explicit app root for direct AEAT live-read
workflows.

Implementation mandate: mount `aeat app live`, move filed-data commands from
`app registry` to `app live filed`, wire notification and expediente
parsers/adapters into this surface, and expose portal discovery here without
compatibility aliases.

`aeat app live` owns remote observation commands for notifications,
expedientes, filed declarations, NIF-IVA verification, TGVI/GROI verification,
Borrador 100 snapshots, and portal discovery.

The accepted grammar is:

```text
aeat app live notifications list [--summary] [--format json|text]
aeat app live notifications show ID [--format json|text]

aeat app live expedientes list [--modelo MODELO] [--year YEAR] [--format json|text]
aeat app live expedientes show EXPEDIENTE_ID [--format json|text]

aeat app live filed list --modelo MODELO --from-year YYYY --to-year YYYY [--format json|text]
aeat app live filed capture --modelo MODELO --year YYYY [--period PERIOD] [--expediente ID] [--limit N] [--format json|text]
aeat app live filed capture-sources --modelo MODELO --year YYYY --period PERIOD [--format json|text]

aeat app live verify nif-iva NIF_IVA [--expected valid|invalid|unknown] [--format json|text]
aeat app live verify tgvi NIF [--expected valid|invalid|unknown] [--format json|text]

aeat app live borrador 100 fetch [--payload PATH] [--format json|text]
aeat app live borrador 100 show SNAPSHOT_ID [--format json|text]

aeat app live portals list [--category CATEGORY] [--modelo MODELO] [--format json|text]
aeat app live portals show PORTAL [--format json|text]
```

`app registry` keeps registry inspection, registry verification, oracle binding
audits, workbook verification, and parity run/replay.

`modelo` consumes live observations and snapshots but does not own live session
traversal. `modelo verify` calls live verification only when the operator
passes the explicit `--with-live` option.

`overview` summarizes after bucket snapshots.

`config repair` diagnoses readiness only.

Persisted captures and snapshots emit:

- `live.notifications.snapshot_captured`
- `live.expedientes.snapshot_captured`
- `live.filed.capture_created`
- `live.verify.nif_iva_checked`
- `live.verify.tgvi_checked`
- `live.borrador100.snapshot_captured`

Event payloads include bucket id, command source and argv, timestamp, live
surface, remote operation kind, sanitized subject ids, object refs, and count
summary. Event payloads do not leak raw NIF or name values beyond redaction.

## Rationale

`aeat app live` gives the operator a visible boundary for remote observation:
the command may contact AEAT now, but it cannot file, present, sign, pay, or
submit. That boundary is clearer than hiding live reads under registry, modelo,
overview, or config diagnostics.

Registry should describe and validate local schemas. Modelo should consume
captured observations inside calculate/verify/file workflows. Overview should
summarize snapshots. Config repair should diagnose readiness. None of those
surfaces should become the general AEAT session traversal entry point.

## Consequences

The live-read boundary becomes visible in command shape.

Registry commands stop owning AEAT session traversal.

Bucket and event rules apply consistently to persisted live observations.

Read-only adapter guards remain central, including notifications read-only
behavior, Renta WEB Open safety guards, GROI drift refusal, public VIES
NIF-IVA verification, and refusal-only live-write behavior.

Rejected alternatives:

- Put everything under `registry`.
- Distribute live reads into `modelo`.
- Put live reads under `config repair`.
- Source notifications under `overview`.
- Add root-level `aeat live`.

## 2026-05-14 amendment — test-user audit finding P1 #7 (list semantics)

Audit observation: `aeat app live filed list` requires `--modelo` and is
thus a query, not a list. A user who only knows "show me what I have filed"
cannot reach an answer without first guessing or discovering a modelo code.

Rule:

- `aeat app live filed list` MUST default to the unfiltered set of filings
  visible through the live read-only adapters for the active profile.
  `--modelo`, year, and period selectors MUST be optional refining
  filters.
- When `--modelo` is supplied, the value MUST be validated against the
  registry-derived enum.
- `--help` MUST expose the accepted `--modelo` set.

Acceptance criteria:

- `aeat app live filed list` with no flags returns every filed record the
  live read adapter exposes for the active profile.
- `aeat app live filed list --modelo BOGUS` refuses with a typed
  validation error.
