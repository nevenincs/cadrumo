---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
---

# `cli-workflow-redesign` adr: `domain harvest normatives and manuals` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The CLI workflow redesign needs to expose existing legal citation and manual
corpus inspection without introducing new domain-root commands or write-capable
fetch behavior.

Normatives and manuals already provide read-only APIs for loading, lookup,
citation, rule discovery, and verification. The CLI needs to harvest those APIs
into an existing app surface without turning legal/manual corpus maintenance
into operator workflow.

## Considerations

The normatives domain exposes `load_catalogue`, `find_reference`,
`find_articulo`, `cite`, and `verify_catalogue`. The manuals domain exposes
`load_manual`, `load_catalogue`, `iter_sections`, `find_rules`, and
`verify_manual_dir`.

The `app registry` boundary is the correct home because these commands inspect
local reference catalogues and local legal authority metadata. They do not
contact AEAT and do not mutate active bucket data.

## Constraints

Do not introduce `aeat normatives`, `aeat manual`, or top-level
`aeat registry`. Do not expose operator-facing manual fetch behavior because it
writes PDFs and manifests and is not bucket-scoped or evented. Do not use
Rich-only rendering, command-local `--json`, or schema-only JSON emitters as the
redesigned command contract.

## Implementation

Add citations commands under `aeat app registry citations`:

```text
aeat app registry citations list [--tag TAG] [--format json|text]
aeat app registry citations show NORMATIVE_ID [--articulo NUM] [--format json|text]
aeat app registry citations verify [--format json|text]
```

Wire these commands to the existing normatives catalogue, lookup, citation, and
verification APIs.

Add manuals commands under `aeat app registry manuals`:

```text
aeat app registry manuals list [--manual renta|iva] [--year YYYY] [--format json|text]
aeat app registry manuals show --manual renta|iva --year YYYY --part PART [--section SECTION] [--format json|text]
aeat app registry manuals rules --manual renta|iva --year YYYY --part PART [--kind KIND] [--format json|text]
aeat app registry manuals verify --manual renta|iva --year YYYY --part PART [--format json|text]
```

Wire these commands to the existing manual catalogue, section traversal, rule
discovery, and verification APIs.

All commands return typed payloads through `_emit` and honor the root
`--format json|text` output contract. These commands are read-only; they do not
require an active bucket and emit no bucket event.

Exclude manual fetch from this harvest. Any later persistence-capable manual
workflow must be redesigned as a bucket-scoped, evented operation before it is
exposed to operators.

## Rationale

The legal and manual corpus is reference material. Keeping inspection under
`aeat app registry` makes its authority clear: it inspects local reference
catalogues and does not mutate operator state.

Harvesting existing domain APIs avoids duplicating lookup and verification
logic. The CLI becomes an output and workflow layer over established corpus
APIs, not a new source of legal interpretation.

## Consequences

Operators gain app-level citation and manual inspection commands without new
root surfaces. Normatives and manuals remain read-only local reference
workflows in this redesign. Typed `_emit` payloads become the durable command
contract instead of Rich tables or command-local JSON emitters.

Any future persistence or fetch behavior must be explicitly redesigned around
active bucket events before it can be exposed.
