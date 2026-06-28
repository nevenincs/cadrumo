---
tags:
  - '#adr'
  - '#aeat-cli-config-vs-setup-namespace'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-08-aeat-cli-gap-closure-plan]]"
  - "[[2026-05-12-cli-design-research]]"
  - '[[2026-06-04-aeat-cli-config-vs-setup-namespace-research]]'
---

# `aeat-cli-config-vs-setup-namespace` adr: `aeat config vs setup namespace boundary` (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

W2 of the aeat-cli-gap-closure rollout shipped IVA / IRPF / modelo enrolment / SII / Verifactu / ROI profile keys behind `aeat setup profile set <key> <value>`. UX-016 asks for a peer `aeat config list / get / set / unset` family. Choice: alias the new family to the existing profile backend, or carve out a separate config store.

## Considerations

- Single source of truth (the WorkflowState.profiles mapping) is easier to reason about, easier to back up, easier to migrate.
- Operators in some shells already type `setup profile`; some auditors expect `config`. Both surfaces sharing one backend lets each muscle memory work without divergence.
- Settings keys (`format`, `language`, `verbosity`) are not profile fields; they belong to the env-var-driven Settings module.
- Named multi-config support (`aeat config configurations *`) presupposes a global selector or context switch that the deadline engine, the filing pipeline, and the workflow state machine do not yet have.

## Constraints

- The W2 PROFILE_KEYS registry is authoritative for profile validation.
- The structured-error emitter and the `_normalise_key` normaliser must be reused, not duplicated.
- Settings keys must continue to flow through env vars; the project's settings module does not yet expose a mutation surface.

## Implementation

Alias mode. `aeat config` is a thin wrapper that routes keyed operations through the same `aeat.application.profile._actions` backend that powers `aeat setup profile set`. One source of truth (the WorkflowState.profiles mapping); two co-equal CLI presentations.

Concrete contract:

- `aeat config list` reads every registered PROFILE_KEYS row plus the operator settings (format, language, verbosity) and renders one row per key with the current value (or `<unset>`).
- `aeat config get KEY` resolves through the same code path `aeat setup profile get` uses.
- `aeat config set KEY VALUE` writes through `set_profile_values` for profile keys; for the operator settings keys it returns the read-only-via-env explanation.
- `aeat config unset KEY` mirrors `aeat setup profile unset`.

The `aeat config configurations` family is deferred. No concrete use case requires multi-config switching today.

## Rationale

Aliasing keeps the W2 PROFILE_KEYS schema authoritative, avoids divergence between two key stores, and leaves the door open to promote `aeat config` to a parallel namespace later (the alias contract does not foreclose it).

## Consequences

- Both `aeat setup profile` and `aeat config` remain available; deprecating one later is mechanical because the backend is shared.
- Settings keys are read-only through `aeat config get` for this slice; `aeat config set format json` will emit a refusal pointing at the env-var route.
- The parallel-mode option remains a future possibility — promoting `aeat config` to a parallel namespace would only require adding a separate config store and dispatching on key prefix.
