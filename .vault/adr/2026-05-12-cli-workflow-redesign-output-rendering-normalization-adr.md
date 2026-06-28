---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-inventory-placement-adr]]"
---

# `cli-workflow-redesign` adr: `output rendering normalization` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Output behavior is inconsistent across the CLI. Root format capture exists and
`_emit(ctx, payload, lines)` exists, but retained commands still use Rich-only
rendering, command-local JSON flags, and bespoke JSON emitters.

## Considerations

The redesigned CLI needs a single rendering contract so automation users and
human operators see predictable behavior. Rendering must not vary by old command
family.

## Constraints

Per-command `--json`, `--json` aliases, Rich-only text rendering,
command-specific schema emitters, and NDJSON are rejected for this redesign.
Root `--format json|text` is the only format selector.

## Implementation

Every retained command accepts `ctx: typer.Context` and routes both structured
payloads and text lines through `_emit(ctx, payload, lines)`.

Legacy `deadlines` commands are either removed during `app overview` absorption
or rewritten before any remount. Inventory and any harvested command must drop
`json_output_requested()` and `emit_json_success()` in favor of `_emit`.

## Rationale

A single rendering path prevents each command from defining its own JSON or
text contract. It also lets the root command own output behavior, which keeps
subcommands focused on domain semantics.

## Consequences

`--format json` and `--format text` become the only supported output modes for
retained commands. Output rendering remains separate from event recording:
commands do not encode audit or persistence semantics through bespoke JSON
emitters.

Tests for retained surfaces must assert root `--format json` behavior and the
absence of command-local `--json` compatibility flags.

## 2026-05-14 amendment — test-user audit finding P1 #8 (refusal tone)

Audit observation: a previous round flagged the all-caps `REFUSED:` prefix
on validation refusals as tonally hostile to a user who is typically
following the application's own instructions when the refusal fires. The
prefix continues to surface (`REFUSED: The command input failed
validation. Run \`aeat config doctor\` ...`).

Rule:

- The text renderer for boundary refusals (the `CliRefusedBoundaryError`
  output path and any equivalent emitter) MUST NOT print all-caps status
  prefixes. The leading token of a refusal line in `--format text` is
  `Refused:` (sentence case) or an i18n-translated sentence-case
  equivalent.
- The JSON renderer continues to carry the machine-readable status code;
  capitalization in `--format json` is unaffected and stable.
- Stale references to `aeat config doctor` in refusal messages MUST be
  rewritten to `aeat config repair` per the config-repair-shape ADR.
- This is the target shape. No flag toggles the prefix.

Acceptance criteria:

- A test asserts no line in any `--format text` refusal output starts with
  `REFUSED:` (regex `^REFUSED:`); the matching sentence-case token is
  used instead.
- A test asserts no refusal text mentions `aeat config doctor`.
