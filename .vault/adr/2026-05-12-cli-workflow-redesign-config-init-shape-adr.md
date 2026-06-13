---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-04-12-setup-wizard-adr]]"
  - '[[2026-06-03-profile-lifecycle-cli-cascade-supersession-adr]]'
---


# `cli-workflow-redesign` adr: `Config init first-run shape` | (**status:** `superseded by [[2026-05-16-profile-lifecycle-cli-adr]]`)

> Supersession reader note: the named 2026-05-16 ADR is archived.
> Current active orientation is the `2026-05-16-profile-lifecycle-cli-plan`
> plus `2026-06-03-profile-lifecycle-cli-cascade-supersession-adr`.
> Treat the first-run shape below as historical unless a later accepted
> profile-lifecycle authority re-enrols it.

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The redesigned CLI root is exactly `aeat config` and `aeat app`, but current
first-run behavior is split across root `aeat init`, root `aeat setup`, and
legacy setup internals. `aeat config init` is not mounted, even though
configuration owns profile, bucket, auth bootstrap, and environment setup.

The design needs one first-run command that creates the active profile and its
bucket atomically, emits bucket events, and removes all setup/root-init
compatibility surfaces.

## Considerations

- Current root `aeat init` writes profile-like values through
  `workflow_state_repository().update(...)`.
- Current `aeat setup init` creates and activates a workflow profile, then
  directs the user toward `aeat setup auth configure ...`.
- Current `aeat config` has only flat key/value commands and `doctor`.
- `SetupWizard` exists and is tested, but it writes `.env` and a legacy
  `AutonomoProfile` envelope instead of the active workflow profile state.
- Current workflow state has profiles and active profile, but no `bucket_id`
  and no bucket event collection.
- Profile actions can create, select, set, and clear profiles, but do not
  create buckets or emit events.
- The bucket ADR requires profile creation to create a bucket atomically and
  store profile data in that bucket.
- The bucket-event-history ADR requires append-only events for persisted
  bucket-scoped mutations.

## Constraints

- Root `aeat init` is removed.
- Root `aeat setup` and all `setup init/status/reset/auth/profile` routes are
  removed.
- Root `aeat archive` remains rejected by this slice; the replacement is
  `aeat config bucket`.
- No aliases, compatibility shims, deprecation routes, or support-only routes
  are introduced.
- No `aeat config init wizard` command is introduced.
- No `aeat config setup` command is introduced.
- All output uses `_emit`, including JSON output.
- Profile reads route through `workflow_state_repository()`.
- The `load_profile_envelope` path is retiring and must not be extended.
- Every persisted mutation is bucket-scoped and emits a bucket event.

## Implementation

First-run configuration is owned by:

```text
aeat config init
```

The command shape is:

```text
aeat config init [--profile NAME]
                 --tax-id NIF
                 --activity TEXT
                 --iva-regime REGIME
                 [--tax-residence CCAA]
                 [--auth-provider certificate|clave_movil|none]
                 [--certificate-path PATH]
                 [--certificate-password-env VAR]
                 [--output-language LANG]
                 [--drafts-dir PATH]
                 [--submissions-dir PATH]
                 [--manuals-root PATH]
                 [--from PATH]
                 [--non-interactive]
                 [--dry-run]
                 [--format json|text]
```

Interactive `aeat config init` prompts for omitted fields directly. There is no
`wizard` subcommand.

Non-interactive `aeat config init --non-interactive` requires required values to
come from explicit flags or `--from PATH`.

`aeat config init` creates the config bucket and profile atomically. The
profile data is stored in that bucket, and the created bucket/profile become
active in the same operation.

The command runs readiness validation and performs internal migration from old
setup-mounted state without exposing old CLI routes.

The command emits, as applicable:

- `bucket.created`
- `profile.created`
- `profile.activated`
- `profile.updated`
- `auth.provider.configured`
- `config.env.updated`, only if env-file persistence survives
- `setup.state.migrated`, only for backend-only migration from legacy setup
  state

`SetupWizard` is not exposed as a CLI surface. It is retired as a command
backend unless it is refactored to call the new bucket/profile initialization
service. The reusable pieces are limited to typed answers, prompter
abstraction, and verifier checks.

## Rationale

`config init` is the correct owner because first-run setup is configuration and
identity bootstrap, not application work. Keeping it under `config` preserves
the strict root contract while allowing profile, bucket, auth bootstrap, and
environment validation to happen in one operator flow.

Atomic bucket/profile creation prevents a profile without a storage bucket and
prevents a bucket without an associated active profile. Emitting bucket events
from initialization gives later `config bucket history` and app status surfaces
a consistent audit trail.

Rejecting `SetupWizard` as a direct command backend prevents legacy `.env` and
profile-envelope side effects from becoming the new canonical persistence path.
The useful wizard pieces can still be reused if they are refactored behind the
new bucket/profile service.

## Consequences

The implementation needs a new bucket/profile initialization service or an
equivalent refactor of existing services. That service must be the only command
backend for `aeat config init`.

Legacy setup state may be migrated internally, but old CLI routes must not
remain available for compatibility.

The auth backend catalogue remains usable, but the mounted command surface moves
from `setup auth` to the config-owned workflow.

Output rendering must be normalized so `aeat config init` and related config
commands support `--format json` through `_emit`.

The retirement of `load_profile_envelope` must continue; new profile reads must
not depend on it.

## 2026-05-14 amendment — test-user audit finding P1 #6 (next-step hint)

Audit observation: a successful `aeat config init …` prints
`Próximo paso: ejecuta \`aeat config init --tax-id … --activity …\`` style
hints whose target ends with `aeat app overview`, but `app overview` is a
Typer group and bare invocation prints group help, not the operator's
intended status view.

Rule:

- Every post-command "next step" hint emitted by any leaf in this ADR's
  scope MUST point at a leaf command, never at a Typer group. The
  renderer MUST treat group-target hints as a programmer error.
- The post-`init` hint specifically points at `aeat app overview status`,
  which is the operator's first read after a fresh profile.
- This rule is cross-cutting and applies to every hint surface in the
  redesigned CLI, including help footers and i18n-translated variants.
  The translation table MUST carry the full leaf-target command, not a
  shortened group name.
- A construction-time guard (a Pydantic validator on the hint model, or an
  equivalent assertion in the central hint emitter) refuses to emit a
  hint whose target resolves to a group inside the Typer app graph.

Acceptance criteria:

- A unit test enumerates every post-command hint string the CLI may emit
  and asserts each one is registered as a leaf command in the Typer app
  graph.
- The `aeat config init` smoke run emits a hint that resolves to a leaf
  when invoked verbatim by the operator.
