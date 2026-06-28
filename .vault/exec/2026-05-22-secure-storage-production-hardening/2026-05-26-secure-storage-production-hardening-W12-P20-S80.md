---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S80'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P20-S78]]'
---



# `secure-storage-production-hardening` `W12.P20.S80`

Classified active-profile pointer, manifest, and bucket-layout callers as `manifest-discovery`, `bootstrap-custody`, or `runtime-default`.

## Scan Boundary

S80 uses the active-profile bucket vocabulary from the discovery audit, not every function named `manifest` in the codebase. The classified direct-call set covers direct production calls to:

- `read_pointer`
- `write_pointer`
- `read_profile_bucket`
- `read_profile_bucket_by_id`
- `list_profile_buckets`
- `read_manifest`
- `write_manifest`
- `bucket_paths`
- `manifest_path`

Direct active-profile bucket calls classified: `75` across `18` production files. These calls appear on `71` distinct line references because four lines contain nested `read_manifest(bucket_paths(...))` or `write_manifest(bucket_paths(...), ...)` calls.

Same-name non-profile manifest methods, such as attachment-local and manuals-local manifest writers, are not S80 active-profile bucket callers. Those remain owned by side-store/plaintext classification in S96/S97.

## Adapter Callers

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py:734` | `read_profile_bucket_by_id` for active-profile diagnostic label | `manifest-discovery` | read-only manifest lookup must not unlock encrypted storage; secure reads remain custody/runtime work | diagnostic tests verify label resolution without requiring session | classified |
| `src/aeat/adapters/outbound/google/_oauth_flow.py:77` | `read_profile_bucket_by_id` before reading lifecycle record | `manifest-discovery` | manifest lookup may resolve display/profile identity; encrypted record load must be runtime/custody-bound | OAuth tests split manifest-missing behavior from secure record read | classified |
| `src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py:90` | `bucket_paths` for keystore path derivation | `bootstrap-custody` | keystore path derivation remains physical bucket custody and must preserve separation checks | keystore tests stay filesystem-real and bucket-root isolated | classified |
| `src/aeat/adapters/persistence/storage/bucket/_layout.py:92` | `bucket_paths` inside bucket directory provisioning | `bootstrap-custody` | layout/provisioning is a bucket custody primitive, not runtime attachment | layout tests stay filesystem-real | classified |
| `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py:100,117` | `manifest_path` inside manifest read/write primitives | `bootstrap-custody` | manifest IO remains the single physical manifest primitive used by discovery and lifecycle | manifest IO tests stay filesystem-real and validate schema failures | classified |
| `src/aeat/adapters/persistence/storage/master_key/_master_key.py:1031,1086` | `read_manifest(bucket_paths(...))` for key schedule and provider setup | `bootstrap-custody` | master-key custody may read bucket manifest but must feed a validated session into runtime | master-key tests keep real manifests and sessions | classified |

## Application Callers

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/application/config_reset.py:118` | `list_profile_buckets(include_tombstoned=True)` during reset | `bootstrap-custody` | reset custody may enumerate registered buckets before destructive cleanup | reset tests assert enumeration and cleanup against real profile roots | classified |
| `src/aeat/application/state_projection.py:239,549` | `read_profile_bucket_by_id` for display-label projection | `manifest-discovery` | projection reads plaintext labels only and must not require encrypted runtime unlock | projection tests cover missing/unreadable manifest fallback | classified |
| `src/aeat/application/user_profile/_orchestration.py:106,251,275,308` | `write_pointer`, `read_profile_bucket`, and `bucket_paths` in profile lifecycle orchestration | `bootstrap-custody` | create/switch/delete flows own cold-start pointer and bucket-directory custody before runtime attaches | lifecycle tests prove rollback, duplicate-label handling, and bucket isolation | classified |
| `src/aeat/application/user_profile/_profile_repository.py:226,235,260,261,277,335,336,340,375,376,377,430,449,450,451,502,503,504,539,563,566,568,592,693,716,757` | bucket paths, manifest IO, profile-bucket lookup, and pointer IO in aggregate repository | `bootstrap-custody` | `ProfileRepository` remains the sole physical aggregate writer for bucket directory, manifest, encrypted record, and active pointer | profile repository tests stay real and assert all-or-nothing cross-store behavior | classified |
| `src/aeat/application/wizard/_commands.py:766` | `read_profile_bucket` to resolve wizard-selected profile | `bootstrap-custody` | wizard profile flow should call profile lifecycle/runtime operations rather than own storage attachment | wizard tests validate selected profile resolution and post-create runtime readiness | classified |
| `src/aeat/application/workflow/_profile_bucket_scan.py:89,124,127,130,169,177,204,208,218,230` | profile-bucket scanner built on layout and manifest primitives | `manifest-discovery` | this remains the canonical read-only profile discovery service; it must not open encrypted storage | scanner tests stay filesystem-real and verify tombstone filtering/schema failures | classified |
| `src/aeat/application/workflow/_profile_health.py:88,102` | pointer and registered-bucket reads for health projection | `manifest-discovery` | health assessment can read active pointer and manifest registration without unlocking storage | health tests cover dangling pointer and unreadable manifest states | classified |
| `src/aeat/application/workflow/_profile_health.py:244,275,288,289` | manifest read/write and path derivation for manifest-status repair | `bootstrap-custody` | repair path must remain explicit custody with confirmation before rewriting manifest state | repair tests prove dry-run and confirmed write behavior against real manifests | classified |
| `src/aeat/diagnostics/profile.py:64,75` | `read_profile_bucket` and `read_profile_bucket_by_id` for diagnostics | `manifest-discovery` | diagnostics reads plaintext discovery state without runtime unlock | diagnostics tests verify redacted profile output and missing-profile handling | classified |

## Core Callers

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/core/_bucket_pointer_io.py:82` | `read_pointer` inside active bucket resolution | `manifest-discovery` | pointer file remains the third active-profile precedence rung and must be side-effect free | pointer tests validate precedence and invalid payload handling | classified |
| `src/aeat/core/config.py:953` | `read_pointer` during `Settings.aeat_database_url` route derivation | `runtime-default` | runtime route derivation may consume pointer state, but write/read readiness must still be enforced by `StorageRuntime` | route tests keep explicit database URL cases limited to refusal/classification | classified |

## CLI Callers

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/entrypoints/cli/_config/__init__.py:846,862,953,1633` | profile read/list helpers for command display and active pointer display | `manifest-discovery` | read-only CLI profile display may use manifest discovery without unlocking storage | CLI tests assert no-session profile list/status behavior | classified |
| `src/aeat/entrypoints/cli/_config/__init__.py:993,1208,1351,1574` | profile lookup for switch/delete/create validation and lifecycle commands | `bootstrap-custody` | lifecycle command paths must move behind profile lifecycle/runtime operations while preserving bootstrap exemptions | CLI lifecycle tests use real profile buckets and assert destructive confirmations | classified |
| `src/aeat/entrypoints/cli/_config/_profile_census.py:33` | `read_profile_bucket_by_id` for profile census | `manifest-discovery` | census projection reads registered bucket metadata without encrypted runtime unlock | profile census tests verify display against real manifests | classified |

## Audit-Signaled Non-Callers

The audit also flagged some files with pointer/manifest/bucket terms but no direct active-profile bucket API call in the S80 direct-call vocabulary. They are not omitted; they are deferred to the row that owns their concrete API:

- `src/aeat/adapters/persistence/storage/attachment.py` uses attachment-local manifest methods and remains a side-store/plaintext classification item for S96/S97.
- `src/aeat/adapters/persistence/storage/runtime.py` consumes settings route classification rather than direct manifest calls and remains runtime policy work for S81 and migration work for S83-S95.
- `src/aeat/application/auth/_operator.py`, `src/aeat/application/diagnostics.py`, `src/aeat/application/repair_integrity.py`, `src/aeat/application/workflow/_models.py`, `src/aeat/core/i18n/_render.py`, `src/aeat/entrypoints/cli/__init__.py`, `src/aeat/entrypoints/cli/_common.py`, and `src/aeat/entrypoints/cli/_modelo.py` currently hit active-profile/session/route APIs rather than direct pointer/manifest/bucket APIs. They remain owned by S81.

## Follow-on Work

- S81 must classify active-profile, SQL route, and master-key session callers, including the audit-signaled non-callers above.
- S89 and S90 must preserve the split between profile lifecycle custody and read-only manifest discovery.
- S96/S97 must classify non-profile manifest side stores so attachment/manual/export manifests do not become unreviewed alternate persistence.

## Validation

- Ran direct AST scan for active-profile bucket pointer, manifest, profile-bucket, and layout API calls.
- Cross-checked the direct-call set against the active-profile runtime discovery audit pointer/manifest/bucket production index.
- Ran `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`.

## Review

The mandatory S80 review found no classification defects. It verified the direct-call counts, target vocabulary, same-name non-profile exclusions, and audit-signaled non-caller deferrals. The review identified one supporting-audit frontmatter issue: the active-profile runtime discovery audit had an extra feature tag. That audit frontmatter was corrected to the required `#audit` and `#secure-storage-production-hardening` tag pair.
