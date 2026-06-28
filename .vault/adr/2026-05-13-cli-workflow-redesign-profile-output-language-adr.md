---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-cli-workflow-redesign-profile-output-language-research]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
---

# `cli-workflow-redesign` adr: `profile-owned output language` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

Output language is currently controlled by settings/environment only. The normal operator workflow creates an active profile and bucket, but that profile does not store the language that the user expects to see through the CLI, wizard, profile status, errors, and app output.

This causes a UX regression: tests and local workflows pin English by setting `AEAT_OUTPUT_LANGUAGE=en`, while the actual config/profile backend has no equivalent persisted field. The environment variable remains useful as an explicit override, but it is not the primary user preference model.

## Considerations

The active profile is the user-owned configuration object. It already stores identity, tax residence, IVA regime, obligations, and other workflow inputs through descriptor-backed profile keys.

The first-run wizard is descriptor-driven. Adding a descriptor question creates a first-run flag and profile key without writing CLI-local parsing logic.

The i18n resolver runs before many command handlers, especially while rendering help text. A profile-backed resolver must therefore be low-level, read-only, fail-soft, and independent of CLI command execution.

The current shipped locales are `es`, `en`, `ca`, and `hu`. A profile language value must be validated against the shipped locale catalogue.

`AEAT_OUTPUT_LANGUAGE` remains an explicit runtime override for development, automation, and one-off command sessions.

## Constraints

- Root remains exactly `aeat config` and `aeat app`.
- No top-level language command is introduced.
- No CLI-local language registry is introduced.
- No compatibility alias, shim, or deprecated spelling is introduced.
- The profile key is canonical as `output.language`.
- `aeat config init --output-language LANG` writes the same profile key as `aeat config profile set output.language LANG`.
- Supported values are the shipped locale codes: `es`, `en`, `ca`, and `hu`.
- Language reads do not emit bucket events.
- Language mutations are profile mutations and emit the normal bucket-scoped profile event path.
- Explicit `AEAT_OUTPUT_LANGUAGE` overrides the active profile value.
- Without `AEAT_OUTPUT_LANGUAGE`, the active profile value controls CLI rendering.
- Without a profile value, settings default to Spanish.

## Implementation

Add `output.language` to the descriptor-backed profile schema as a wizard question under the profile/config section. The descriptor supplies the `--output-language` flag for `aeat config init`, validates the supported locale choices, and contributes the key to `PROFILE_KEYS`.

Extend the typed setup answers model with `output_language`, defaulting to `es`, and validate it through the descriptor choice set. Serialization persists it as `output.language`.

Update `core.i18n.output_language()` and the error-registry language resolver to use this precedence:

1. `AEAT_OUTPUT_LANGUAGE` when present and non-empty.
2. Active profile `output.language` from `workflow_state_repository().load()`.
3. Settings default, which remains `es`.

The profile lookup is read-only and fail-soft. Missing storage, missing active profile, malformed profile state, or absent `output.language` falls through to the settings default. The lookup does not write, migrate, emit events, or require the CLI boundary.

`aeat config profile list`, `get`, `set`, and `unset` expose `output.language` through the existing profile command handlers. `set` uses the existing wizard descriptor validation path. Unsupported language values fail through the central command error boundary.

Tests assert real behavior:

- `PROFILE_KEYS` includes `output.language`.
- `aeat config init --output-language en` persists `output.language=en`.
- `aeat config profile set output.language ca` persists `ca`.
- `core.i18n.output_language()` returns active profile language when `AEAT_OUTPUT_LANGUAGE` is absent.
- `AEAT_OUTPUT_LANGUAGE` overrides the active profile language when present.
- unsupported language values are rejected without traceback.
- help/output assertions remain user-observable and do not assert ADR filenames, wave ids, phase ids, plan row ids, or other development metadata.

## Rationale

Language is a user preference and belongs with the active profile. The profile already identifies the current operator and bucket, so it is the correct storage owner for operator-facing CLI language.

Keeping `AEAT_OUTPUT_LANGUAGE` as an explicit override preserves useful automation behavior without making environment state the normal UX path.

Descriptor-backed implementation keeps the CLI thin: the wizard defines valid values, profile services persist the value, and i18n services resolve it. CLI commands only expose existing descriptor/profile functionality.

## Consequences

The profile schema gains one new key, `output.language`.

First-run config can set language directly through `aeat config init --output-language LANG`.

Existing profile commands can inspect and update language without a separate command family.

The i18n resolver gains a dependency on read-only workflow state. The dependency is fail-soft and must not mutate state or produce bucket events during rendering.

Tests that force English with `AEAT_OUTPUT_LANGUAGE` remain valid only when explicitly testing environment override behavior. Normal CLI language tests should prefer profile-backed state.
