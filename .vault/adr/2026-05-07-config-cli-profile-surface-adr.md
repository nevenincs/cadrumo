---
tags:
  - '#adr'
  - '#config-cli-profile-surface'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - "[[2026-05-07-user-profile-schema-research]]"
  - "[[2026-05-07-user-profile-filing-export-dependencies-reference]]"
  - "[[2026-05-07-user-profile-deadline-dependencies-reference]]"
  - '[[2026-06-04-config-cli-profile-surface-research]]'
---



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

## 2026-05-15 amendment - profile export / import verbs

The 2026-05-15 ground-truth audit found that `aeat config profile
export` and `aeat config profile import` were named in the original
verb set but never shipped, and the matching bucket events
(`profile.exported`, `profile.imported`, `profile.activated`) are
absent from `BucketEventType`. This amendment locks the export / import
surface so the gap is closed in a follow-up wave.

Required service surface in `aeat.application.user_profile`:

- `export_profile(bucket_id, output_path)` - snapshot the active
  profile (bucket pointer + bucket contents) to a portable encrypted
  archive with `format_version` field. Encrypted fields stay
  encrypted; `SensitivityClass` labels transfer; emits
  `profile.exported`.
- `import_profile(source_path, force_replace=False)` - validate
  signature + manifest; schema-migrate if archive's `format_version`
  is older; refuse identity collision unless `force_replace`; emits
  `profile.imported`.

Required CLI surface: `aeat config profile {export, import}` thin
handlers under the existing profile group. `import` requires `--yes`
for force-replace.

Required `BucketEventType` additions: `PROFILE_EXPORTED`,
`PROFILE_IMPORTED`, `PROFILE_ACTIVATED`. The implementation note: the
existing `PROFILE_SELECTED` event covers active-profile switch
semantically; `PROFILE_ACTIVATED` is added as a distinct event to mark
post-import or post-export activation transitions, not as an alias.

Archive format: encrypted ZIP with manifest (object inventory,
checksums, `format_version`, profile id, source toolchain version).
Round-trip stability is required across schema-version bumps.
