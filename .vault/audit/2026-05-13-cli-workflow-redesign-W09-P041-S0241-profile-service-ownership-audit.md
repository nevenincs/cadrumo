---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-07-user-profile-backend-schema-adr]]'
---

# `cli-workflow-redesign` `W09.P041.S0241` Audit — User Profile Backend Service Ownership Mapping

## Decision (per `2026-05-07-user-profile-backend-schema-adr`)

The profile is a centrally-owned, schema-driven backend artifact. The TOML schema at `registry/aeat/user_profile/schema.toml` is the sole authority for section/field metadata, selector projections, snapshot policy, and remove policy. Live values and immutable filing snapshots live only in the secure DB backend. Every consumer (registry validation, deadlines, filing/export, Renta, rental, usage ratios, VAT context, setup/config flows) reads through canonical profile projections — no compatibility adapters over the fragmented legacy surfaces (`PROFILE_KEYS`, `AutonomoProfile`, `ProfileRecord`, tax-residence storage, usage-ratio root, untyped CLI profile dicts).

## Current implementation status

### Already built (domain layer)

`src/aeat/domain/user_profile/` is the centralised schema and value domain package. It exposes:

- `_schema.py` — strict Pydantic records for `ProfileSchemaDefinition`, `ProfileSectionDefinition`, `ProfileFieldDefinition`, `ProfileFieldType`, `ProfileSnapshotPolicy`, `ProfileRemovePolicy`.
- `_loader.py` — `load_user_profile_schema(path=DEFAULT_USER_PROFILE_SCHEMA_PATH)` reads the TOML and validates it through the Pydantic records.
- `_values.py` — `UserProfileFact`, `ProfileFactValue` typed value records.
- `_registry_contract.py` — `validate_user_profile_registry_contract` cross-checks the calculation registry's selector inventory against the profile schema's selector projections (`UserProfileSelectorIndex`).
- `_errors.py` — `UserProfileSchemaLoadError`.
- Three test modules: `test_schema.py`, `test_values.py`, `test_registry_contract.py`.

The schema TOML covers identity, contact, tax residence, census/enrollment, activities, IRPF/withholding, IVA, filing/export context, Renta taxpayer/spouse/family, properties/rental, usage ratios, and provenance/effective dating sections — 659 lines.

### Not yet built (application layer + migration)

There is no `src/aeat/application/user_profile/` package. The application-layer service API for profile lifecycle does not exist:

- `add` / `register_profile`
- `remove` (tombstone the live root; retain immutable filing snapshots by id+hash)
- `edit_section` / `edit_field`
- `list_profiles` / `read_profile`
- `duplicate_profile`
- `export_profile` / `import_profile` (user-directed portable bundles only; not retained as live state)
- `validate_profile`
- `preflight_modelo_revision(modelo, revision_id, filing_year, period)` — surface required-but-missing fields for the selected calculation context
- `create_filing_snapshot(profile_id, modelo, revision_id, filing_year, period)` — immutable snapshot with deterministic canonical hash, persisted in the secure DB
- `compute_profile_stale_check(draft.profile_snapshot_id, draft.profile_snapshot_hash)` — detect stale filing approvals when the live projection diverges from the snapshot

There is no secure-DB persistence wiring for live profile values or filing snapshots. Today profile state still flows through `aeat.application.profile` (`ProfileBucket`, `ProfileBucketRepository`, `ProfileRecord`) which is the legacy fragmented surface the ADR is replacing.

41 source files still import `PROFILE_KEYS`, `AutonomoProfile`, or `ProfileRecord`. Consumer migration is not started.

## Non-CLI service ownership map

Implementing the remaining W09 phases requires the following ownership split.

### `aeat.application.user_profile` (new application package)

Owns the lifecycle API and is the only write surface for live profile values. Surfaces:

- `ProfileLifecycleService` (add / remove / edit / duplicate / list / read).
- `ProfileSnapshotService` (create_filing_snapshot, compute_profile_stale_check).
- `ProfileExportService` / `ProfileImportService` (portable bundles; not retained).
- `ProfileValidationService` (schema validation + cross-field + effective-period selection).
- `ProfilePreflightService` (per-(modelo, revision, filing_year, period) requirement check).

Pydantic command and result records: `RegisterProfileCommand`, `RemoveProfileCommand`, `EditProfileSectionCommand`, `EditProfileFieldCommand`, `ProfileSnapshotRequest`, `ProfileSnapshot`, `ProfilePreflightReport`, `ProfileValidationReport`, `ProfileStaleCheckReport`, `ProfileExportBundle`, `ProfileImportResult`.

### `aeat.domain.user_profile` (existing — minor additions)

Owns the typed schema, value records, registry contract validation, and the selector / export / projection helpers. Already built; W09.P041.S0244 may extend with effective-period selection helpers and snapshot canonical-hash helpers that today's `_values.py` does not provide.

### `aeat.adapters.persistence.storage` (existing — extension)

Persistence routes through `SecureObjectRepository`. Two new namespace + object-key shapes are needed:

- `aeat.application.user_profile.value` — live profile facts per `(profile_id, section_id)`. Classification follows the section's `sensitivity` declaration in the TOML.
- `aeat.application.user_profile.snapshot` — immutable filing snapshots per `(profile_id, modelo, revision_id, filing_year, period)`; deterministic canonical hash drives the lookup key.

The bucket-scoping work landed in W61.P301 (transaction catalogue) is the template. The profile-bucket integration point is `aeat.application.workflow.WorkflowState.active_profile_bucket_id()` → derive `profile_id`.

### `aeat.core.errors` (existing — extension)

Register new error codes for the profile lifecycle:

- `REFUSED_PROFILE_NOT_FOUND` — `ProfileNotFoundError`
- `REFUSED_PROFILE_ALREADY_EXISTS` — `ProfileAlreadyExistsError`
- `VALIDATION_PROFILE_SCHEMA_VIOLATION` — `ProfileSchemaValidationError`
- `VALIDATION_PROFILE_PREFLIGHT_MISSING` — `ProfilePreflightMissingError` (a modelo/revision selector has no live profile value)
- `INTEGRITY_PROFILE_SNAPSHOT_HASH_MISMATCH` — `ProfileSnapshotHashMismatchError`
- `INTEGRITY_PROFILE_SNAPSHOT_NOT_FOUND` — `ProfileSnapshotNotFoundError`

### `aeat.entrypoints.cli` (W09.P045 only — last phase)

The CLI surface is a thin adapter that delegates to `aeat.application.user_profile`. Commands land under `aeat config profile`:

- `aeat config profile add` / `remove` / `list` / `show` / `edit` / `duplicate` / `export` / `import` / `validate` / `preflight`.

The CLI must not implement any business logic and must not read from the legacy `aeat.application.profile.ProfileBucketRepository` for new code.

## Migration boundaries (W09.P042 onwards)

Each existing consumer of the legacy profile surfaces moves to canonical projections in its own slice, then the old read site is removed:

| Consumer | Legacy surface used | Canonical projection target |
| --- | --- | --- |
| `domain/calculations/registry/_validate.py` | none (consumes selector index directly) | already integrated via `validate_user_profile_registry_contract` |
| `application/filing/runtime.py` `FilingOperatorProfile` | `ProfileRecord.values` | `aeat.application.user_profile.read_profile(profile_id).projection_for_filing()` |
| `application/overview/__init__.py` `build_overview_calendar` | `ProfileRecord.values` | `read_profile(profile_id).projection_for_deadlines()` |
| `application/wizard/_catalogue.py` and friends | `PROFILE_KEYS`, scalar profile keys | `aeat.application.user_profile.list_required_fields(schema_section)` |
| `application/aggregation/_renta_ledger.py` and Renta family | `AutonomoProfile`, `RentaFamily` | `read_profile(profile_id).projection_for_renta(filing_year)` |
| `application/aggregation/_usage_ratios.py` | usage-ratio root storage | `read_profile(profile_id).projection_for_usage_ratios(activity_key)` |
| `application/aggregation/_vat_*` | scalar IVA regime keys | `read_profile(profile_id).projection_for_vat(period)` |
| `entrypoints/cli/_common.py` `_profile_to_autonomo` | `state.active_profile_record().values` | `read_profile(active_profile_id).projection_for_autonomo(filing_year)` |

Once a slice migrates, the legacy read site is deleted, not adapted.

## Filing draft integration

The W09 work extends `FilingDraft` with three fields:

- `profile_snapshot_id: str` — secure-DB object key of the immutable snapshot used at draft-creation time.
- `profile_snapshot_hash: str` — deterministic canonical SHA-256 of the snapshot payload.
- `profile_schema_version: int` — the `[schema] version` of the TOML at draft time.

`compute_current_approval_basis` (already bucket-id-threaded by W61.P301.S1803) gains a fourth fingerprint over the profile snapshot. `approval_stale_reasons` returns `PROFILE_SNAPSHOT_CHANGED` when the live projection hashes differently from the recorded `profile_snapshot_hash`.

## Recommendation for S0242-S0246

S0242 should land the application-layer Pydantic command/result records in a new `aeat.application.user_profile` package — no business logic, just typed contracts.

S0243 should wire the lifecycle services (`ProfileLifecycleService`, `ProfileSnapshotService`, `ProfileValidationService`, `ProfilePreflightService`) calling into `aeat.domain.user_profile`.

S0244 should add the two `SecureObjectRepository` namespaces (`aeat.application.user_profile.value`, `aeat.application.user_profile.snapshot`) and tie them to `state.active_profile_bucket_id()` for per-bucket isolation.

S0245 should route existing canonical profile reads (registry validation, filing runtime, overview, wizard) through the new application API but only by *moving the read site* — no parallel paths.

S0246 should register the six error codes named above in `aeat.core.errors.registry._application` and add the matching message keys.

No source changes were made by this audit step.
