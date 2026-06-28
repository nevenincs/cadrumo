---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-research]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-04-18-auth-protocol-adr]]"
  - "[[2026-04-21-auth-cli-adr]]"
  - "[[2026-05-08-google-oauth-adr]]"
---


# `cli-workflow-redesign` adr: `Config auth command surface` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The historical auth surface lives under `aeat setup auth`, while the redesigned
root contract allows only `aeat config` and `aeat app`. Setup auth combines
provider configuration, login, status, reset, whoami, and logout under a root
that is removed.

The design needs one config-owned AEAT Sede auth surface that handles provider
configuration and session maintenance without preserving setup aliases,
top-level auth commands, Google OAuth drift, representative identity selection,
or live submission semantics.

## Considerations

- Implemented AEAT Sede auth providers are `certificate` and `clave_movil`.
- `clave_pin`, `clave_permanente`, and `dnie_pkcs` are recognized as future
  provider slots but have no auth provider implementation.
- Portal catalogue entries for Cl@ve PIN, Cl@ve Permanente, and DNIe are not
  provider implementations.
- Google OAuth is not AEAT Sede authentication; the Google OAuth ADR places it
  under `aeat config google`.
- Apoderado and representative identity selection are assigned to the
  apoderamientos surface, not to generic provider configuration.
- Auth configuration and session operations must become bucket-scoped and must
  emit append-only bucket events.
- Live AEAT submission remains forbidden and is outside this command surface.

## Constraints

- Root `aeat setup` is removed.
- `aeat setup auth` and all setup auth verbs are removed.
- Top-level `aeat auth` is not introduced.
- No alias, shim, compatibility route, or deprecation route is introduced.
- `aeat config auth` owns only AEAT Sede authentication configuration and
  session maintenance.
- Google OAuth must not appear in the AEAT auth provider registry.
- Apoderado / representation is reserved for a later apoderamientos ADR.
- Every command supports JSON output through `_emit`.
- Auth config and session mutations emit bucket-scoped events and never record
  secrets or raw credentials.

## Implementation

Place AEAT Sede auth configuration and session maintenance under:

```text
aeat config auth
```

Implementation mandate: expose the subcommand grammar below, keep certificate
and Cl@ve Móvil as implemented providers, make reserved providers fail closed,
and remove setup-auth command paths without aliases or shims.

The command tree is:

```text
aeat config auth providers [--format json|text]
aeat config auth configure --provider certificate|clave_movil|clave_pin|clave_permanente|dnie_pkcs [provider flags] [--format json|text]
aeat config auth status [--provider PROVIDER] [--format json|text]
aeat config auth test [--provider PROVIDER] [--format json|text]
aeat config auth clear [--provider PROVIDER|--all] [--sessions] [--locks] [--format json|text]
```

`providers` lists AEAT Sede auth providers and reserved slots, distinguishing
implemented providers from reserved or unsupported slots.

`configure` writes provider configuration for the current bucket. Unsupported
reserved slots fail closed without mutating config, credentials, sessions,
locks, or events.

`status` reports provider configuration and session state for the current
bucket. `--provider` narrows status to one provider.

`test` verifies auth/session readiness for the current bucket. It verifies
certificate and Cl@ve Móvil readiness through their respective backend
implementations. It must not perform live AEAT submission.

`clear` clears provider configuration, sessions, and/or locks for the current
bucket. `--provider` narrows the operation to one provider. `--all` applies to
all AEAT Sede auth providers in the bucket.

Implemented providers:

- `certificate`
- `clave_movil`

Reserved provider slots:

- `clave_pin`
- `clave_permanente`
- `dnie_pkcs`

Google OAuth remains under `aeat config google`, not `aeat config auth`.

Apoderado and representative identity selection are extended by the
apoderamientos-surface ADR under `aeat config auth apoderado ...`.

Auth config and session mutations emit append-only bucket-scoped events:

- `auth.provider.configured`
- `auth.provider.cleared`
- `auth.session.created`
- `auth.session.verified`
- `auth.session.cleared`
- `auth.lock.cleared`

Events are structured, versioned, scoped to the active bucket, and must not
contain secrets, raw credentials, private key material, session tokens, QR
payloads, or equivalent sensitive values.

## Rationale

Authentication configuration is configuration state, not application work.
Placing AEAT Sede auth under `aeat config auth` preserves the two-root contract
while keeping provider config and session maintenance together.

Keeping Google OAuth out of `config auth` prevents a category error: Google is
not an AEAT Sede auth provider and is already assigned to `config google`.

Leaving apoderamientos out of the base grammar prevents representative
identity semantics from being implied by provider configuration.

Failing closed for reserved provider slots allows the CLI to teach the future
provider vocabulary without pretending unsupported authentication works.

## Consequences

Existing `setup auth` behavior must be migrated, not wrapped.

Provider/session behavior must be adapted to bucket-scoped config and
append-only events before implementation is complete.

Config rendering needs to use `_emit` so auth commands support text and JSON
consistently.

The redesigned CLI has a stricter root topology: exactly `aeat config` and
`aeat app`.

Apoderamientos remain a separate design slice. Google OAuth remains a separate
config surface.
