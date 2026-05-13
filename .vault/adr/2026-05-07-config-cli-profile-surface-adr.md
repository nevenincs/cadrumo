---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/adr/ location)
# Feature tag (replace config-cli-profile-surface with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#adr'
  - '#config-cli-profile-surface'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-07'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-05-07-user-profile-schema-research]]"
  - "[[2026-05-07-user-profile-filing-export-dependencies-reference]]"
  - "[[2026-05-07-user-profile-deadline-dependencies-reference]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `config-cli-profile-surface` adr: `Config CLI Profile Operation Surface` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The profile backend is not a one-time setup wizard. It is an ongoing operator
configuration surface for identity, residence, census enrollment, activities,
regimes, filing/export data, Renta family facts, rental facts, and usage-ratio
facts. The current `aeat setup profile` name and command shape imply initial
onboarding and are too narrow for the approved backend design.

The CLI needs a durable facade over the profile backend and related
configuration surfaces. The facade should be named `aeat config`, with profile
operations under `aeat config profile`.

## Considerations

The user-facing surface should loosely mirror the ergonomics of `git config`:
operators should be able to list keys, read values, set values by canonical
section paths, validate configuration, and export or import controlled
configuration payloads.

The CLI is a facade over the backend ADR. It must not own profile schema,
validation, persistence, or model/revision rules. It calls the centralized
application API and displays typed validation results.

Profile keys must be canonical schema paths, such as `identity.name`,
`identity.email`, `tax_residence.ccaa`, `activities.0.cnae`,
`withholding.pays_rent_with_retencion`, or
`iva.intracommunity_operations_exceed_50000_eur`.

The surface must cover lifecycle commands: add, remove, edit, list, show,
read/get, set, unset where schema permits nullability, duplicate, export,
import, validate, and model/revision preflight.

## Constraints

No `aeat setup` compatibility alias is preserved for supported UX. All
setup/first-run/initialization command families are migrated to `aeat config`,
and legacy setup roots are deprecated migration routes only.

The CLI must not write plaintext profile files for live profile persistence.
User-directed portable exports are explicit boundary crossings and must be
handled by the backend export/import API.

The CLI must not implement stringly typed validation, alias normalization, or
per-model header maps. It must delegate schema lookup and validation to the
backend.

Commands must be safe in a shared codebase and must not encourage destructive
git operations or edits outside the intended profile/config boundary.

## Implementation

Rename the operator-facing setup domain to config. The primary command group is
`aeat config`. Profile commands live under `aeat config profile`.

Implement command groups:

| Command group | Responsibility |
|---|---|
| `aeat config profile add` | Create a new secure profile from schema defaults and explicit input. |
| `aeat config profile remove` | Remove a profile through the backend lifecycle API. |
| `aeat config profile edit` | Apply one or more schema-validated changes. |
| `aeat config profile list` | List profile identifiers and display metadata. |
| `aeat config profile show` | Show a redacted or selected view of one profile. |
| `aeat config profile get` | Read a canonical key or section. |
| `aeat config profile set` | Set a canonical key to a typed value. |
| `aeat config profile unset` | Clear nullable fields where the schema allows absence. |
| `aeat config profile duplicate` | Duplicate a profile through backend copy semantics. |
| `aeat config profile export` | Produce a user-directed portable export through backend export policy. |
| `aeat config profile import` | Validate and import a portable profile export. |
| `aeat config profile validate` | Validate profile completeness and schema consistency. |
| `aeat config profile preflight` | Validate profile readiness for a selected modelo/revision/year/period. |

Move setup initialization and profile mutation flows into `aeat config`:

- onboarding/first-run initialization maps to `aeat config init` or explicit
  config bootstrap under `aeat config`
- profile lifecycle maps to `aeat config profile ...`
- legacy root `aeat setup` entrypoints are deprecated and must not remain as
  supported runtime behavior

`aeat config profile remove` follows backend tombstone semantics. It disables
the profile for new reads, selection, preflight, and filing/export work, while
retaining immutable filing/export snapshots for auditability. The command must
communicate that removal is not a purge of historical filing evidence.

CLI output must present schema paths, typed values, validation errors,
effective-date context, redaction state, and model/revision requirements
without exposing secure storage internals.

Remove old `aeat setup profile` command handlers in the same owned slice that
introduces the verified equivalent `aeat config profile` behavior. Old handlers
must not remain reachable as compatibility aliases or fallback paths.

## Rationale

`setup` is semantically too small for a profile backend that remains active
through filing calendars, registry preflight, export, Renta, activity changes,
census changes, and usage-ratio changes.

`config` communicates ongoing operator-owned configuration and gives the
project one facade for profile and future configuration backends.

Keeping CLI schema behavior delegated to the backend prevents a second schema
authority and keeps the TOML/secure DB architecture intact.

## Consequences

Documentation, tests, CLI command discovery, and setup workflows must move from
`setup` to `config`.

Removing `aeat setup` without compatibility requires direct test and
documentation updates in the same rollout.

During development, coexistence is local only and bounded to unmerged owned
slices. A merge-ready slice must not expose both old setup profile commands and
new config profile commands for the same live behavior.

Command UX must handle typed nested sections, repeatable collections, redacted
sensitive values, effective dates, and model/revision preflight without
becoming a free-form key/value store.

The plan must sequence backend API availability before the CLI facade removes
the old setup surface.
