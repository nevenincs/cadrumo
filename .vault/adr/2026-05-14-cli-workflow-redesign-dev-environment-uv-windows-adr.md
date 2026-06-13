---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-root-help-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `dev environment - uv on windows` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`.

## Problem Statement

On Windows, `uv run aeat` re-syncs the project environment on every
invocation. The sync attempts to rewrite `Scripts/aeat.exe`, which Windows
holds open while the previous invocation's process is still cleaning up
or while any other tool has the binary mapped. The result is a file-lock
error that fails the command. A regular operator cannot reasonably be
expected to discover the `uv run --no-sync aeat` workaround on their own.

## Considerations

The redesigned CLI's first-run experience runs through `aeat config init`
and `aeat app overview status`. If the developer-facing invocation path
fails on the OS the project officially supports, the entire onboarding
loop is blocked behind tooling friction unrelated to the CLI's own
design.

`uv` is the project's chosen package manager. Its sync-on-every-run
behavior is correct for development and for CI but pathological for
Windows interactive shells where the previous process's handle on the
shim `.exe` has not yet released.

## Constraints

- The CLI root contract remains exactly `aeat config` and `aeat app`.
  This ADR does not alter that contract.
- No compatibility shim, deprecation alias, or "legacy launcher" is
  introduced. The fix is the target invocation path.
- No third-party process manager or supervisor is bundled.

## Implementation

The project ships an explicit, documented Windows invocation path that
bypasses `uv`'s sync-on-run for interactive shells:

- The canonical Windows interactive invocation is `uv run --no-sync
  aeat ...`. Sync is run explicitly by the operator (or by CI) via `uv
  sync` ahead of time.
- The repository root carries a Windows launcher (a `.cmd` or
  PowerShell-friendly script under the established scripts location;
  the exact filename is for the implementation step to pick) that
  shells out to `uv run --no-sync aeat` with all argv forwarded. The
  launcher is the documented Windows entry point.
- The launcher MUST NOT mask `aeat` exit codes or stderr. It is a
  pass-through.
- The `aeat config repair` `connectivity` and `environment` checks
  surface a warn-level diagnostic when the running Python is on Windows
  and the most recent `uv sync` is older than the project's
  `pyproject.toml`. The diagnostic carries a `next:` line pointing at
  `uv sync`.

## Rationale

The root cause is environmental, not a CLI design defect, but the
operator who hits it is blocked at the entrypoint. The fix lives at the
boundary between dev tooling and CLI surface: a documented launcher
plus a `repair`-surface diagnostic that surfaces stale-sync state. Both
are inside the existing CLI Backend Boundary contract (launcher is a
pass-through; the diagnostic is a normal `DiagnosticCheck` row).

## Consequences

- The README and any dev-environment onboarding text are updated to
  document `uv run --no-sync aeat` as the canonical Windows interactive
  invocation and to point at the launcher.
- The `aeat config repair` diagnostic surface gains the stale-sync row;
  the row follows the always-actionable contract from the
  config-repair-shape ADR.
- No code path inside `aeat` itself depends on whether the launcher or
  raw `uv run` was used. The fix is purely at the developer entry
  point.
