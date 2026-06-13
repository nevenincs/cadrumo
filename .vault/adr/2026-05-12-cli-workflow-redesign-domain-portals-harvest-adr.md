---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-portals-harvest-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-live-shape-adr]]"
---

# `cli-workflow-redesign` adr: `domain portals harvest` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The portals domain has existing local registry discovery APIs, but the current
CLI shape conflicts with the redesigned app workflow.

The domain-local portals CLI exposes a root-style `aeat portals` app using
`--json`, Rich tables, and legacy JSON emitters. That bypasses the accepted
root `--format` and `_emit` contract.

## Considerations

Portal registry discovery helps operators understand which AEAT portals are
known for a modelo or category. It is not itself a live operation unless the
CLI performs remote reachability checks or navigation.

The app-live shape already lists portal discovery under `aeat app live`, making
it the correct user-visible area for live-facing portal metadata.

## Constraints

Do not introduce root `aeat portals`. Do not place portals under
`aeat app registry portals`. Do not expose `open`, `submit`, `present`, `sign`,
`pay`, or navigation commands. Payment portals are metadata only.

Use root `--format json|text` and `_emit`. Do not keep domain-local `--json`,
Rich table output as the command contract, or `emit_json_success`.

Portal discovery is local unless a future `--check-live` mode is explicitly
designed and guarded by `require_live_read()`.

## Implementation

Replace the domain-local portals CLI with app-live local discovery commands:

```text
aeat app live portals list [--category CATEGORY] [--modelo MODELO] [--active-only] [--format json|text]
aeat app live portals show PORTAL [--format json|text]
```

Wire `list` to `PORTAL_REGISTRY`, `portals_for_modelo`, and
`portals_by_category` for local filtering and grouping. Wire `show` to
`get_portal` for local metadata lookup.

Both commands emit typed payloads through `_emit` and honor the root output
contract. They emit no bucket event.

Do not add action verbs. The commands only describe known portal metadata.
Payment portal entries may be listed or shown as metadata, but no payment
action is available.

## Rationale

Placing portal discovery under `aeat app live portals` keeps portal metadata
near live-facing workflows while making the current command behavior explicitly
metadata-only.

Rejecting `aeat portals` prevents domain internals from bypassing the
redesigned app grammar. Rejecting `aeat app registry portals` keeps registry
focused on local calculation and reference authority rather than live-facing
portal metadata.

Rejecting action verbs avoids implying that the CLI can navigate, submit, sign,
present, or pay through this surface.

## Consequences

The portals surface becomes a narrow local discovery interface with typed
output. Existing domain registry APIs are reused without exposing the old
domain-local CLI contract.

Portal metadata can be inspected by modelo or category, including
payment-related portal metadata, but no live portal actions are available.

Any future live check must be added deliberately as a live-read operation
guarded by `require_live_read()`.
