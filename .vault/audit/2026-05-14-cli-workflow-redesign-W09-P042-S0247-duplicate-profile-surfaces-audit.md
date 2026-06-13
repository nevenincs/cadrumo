---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-07-user-profile-backend-schema-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-w09-p041-s0241-profile-service-ownership-audit]]'
---

# `cli-workflow-redesign` `W09.P042.S0247` Audit — Duplicate Profile Surface Inventory

## Canonical (KEEP)

W09.P041 landed the canonical schema-driven user-profile backend:

- `aeat.domain.user_profile` — `ProfileSchemaDefinition`, `UserProfileRecord`, `UserProfileFact`, `UserProfileSnapshot`, `UserProfileSelectorIndex`, six typed errors.
- `aeat.application.user_profile` — Pydantic command/result contracts, `ProfileValidationService`, `ProfilePreflightService`, `ProfileLifecycleService`, `UserProfileLifecycleRepository`, `UserProfileSnapshotRepository`.
- `registry/aeat/user_profile/schema.toml` — 659-line schema definition.

These are the target surfaces for W09.P042-P045 migration.

## Legacy duplicates (DELETE)

The ADR's "Constraints" section names six legacy duplicate surfaces:

### 1. `aeat.application.profile` package — full replacement

`src/aeat/application/profile/` (the legacy package, distinct from `aeat.application.user_profile`):

- `_models.py` — `ProfileRecord` (untyped `values: dict[str, Any]` shape; replaced by `UserProfileRecord` + `UserProfileFact`).
- `_repository.py` — `ProfileBucket`, `ProfileBucketRepository`, `profile_bucket_id`, `profile_bucket_object_key`, `profile_bucket_repository`, `ProfileBucketPersistenceError` (replaced by `UserProfileLifecycleRepository` at the per-bucket secure-object namespace `aeat.application.user_profile.value`).
- `_actions.py` — register-profile and edit-profile lifecycle actions on top of `ProfileBucketRepository` (replaced by `ProfileLifecycleService`).
- `__init__.py` — public re-exports.
- `test_actions.py`, `test_validate.py` — legacy-shape tests (replaced by `application/user_profile/test_lifecycle.py`, `test_services.py`, `test_repository.py`).

Consumers (8 application files + 2 CLI entrypoints):

- `application/test_config_reset.py`, `application/test_setup_reset.py` — reset-flow tests that assert `ProfileBucketRepository` behavior. Replace with `UserProfileLifecycleRepository` round-trip + tombstone checks.
- `application/wizard/_verifier.py` — wizard reads `ProfileRecord.values`. Replace with `ProfileLifecycleService.read(profile_id).facts` projection.
- `application/workflow/_persistence.py` — workflow state persistence references `ProfileRecord` indirectly via `WorkflowState.active_profile_record()` which still returns `ProfileRecord | None`. Replace with `UserProfileRecord | None`.
- `application/workflow/_models.py` `WorkflowState.active_profile_record()` — lazy-loads via `profile_bucket_repository().load(pointer.bucket_id)`. Re-wire to `UserProfileLifecycleRepository(bucket_id=…).load(profile_id)`.
- `entrypoints/cli/test_config_setter.py` — uses old `ProfileRecord` storage shape; rewrite with `UserProfileRecord` shape and `ProfileLifecycleService` interactions.

### 2. `AutonomoProfile` + `autonomo_profile_from_mapping` — partial replacement

`aeat.domain.deadlines.AutonomoProfile` and the mapping coercer at `aeat.domain.deadlines.autonomo_profile_from_mapping` flatten `ProfileRecord.values` into a typed deadlines projection.

Sites:

- `domain/deadlines/_profiles.py` — defines `AutonomoProfile`. Replace with a projection `UserProfileRecord.projection_for_deadlines() -> DeadlineProfile` added to `aeat.application.user_profile`.
- `domain/deadlines/_engine.py`, `_models.py`, `_errors.py`, `__init__.py` — consume `AutonomoProfile`. Wire to the new projection.
- `domain/deadlines/test_engine.py`, `test_models.py`, `domain/calculations/registry/test_filing_schedule_selection.py` — tests that build `AutonomoProfile` directly. Rewrite to build `UserProfileRecord` and project.
- `application/filing/runtime.py` `FilingOperatorProfile` consumes `ProfileRecord.values` (legacy). Replace with `UserProfileRecord` projection-for-filing.
- `application/overview/__init__.py`, `application/overview/test_calendar.py` — use `AutonomoProfile` for calendar. Wire to projection.
- `application/wizard/_status.py` — consumes `AutonomoProfile`. Wire to projection.
- `application/workflow/_adapters.py`, `_engine.py`, `_protocols.py`, `test_adapters.py`, `test_engine.py` — workflow plumbing carries `AutonomoProfile`. Wire to projection.
- `entrypoints/cli/test_workflow_surface.py`, `entrypoints/cli/_common.py` `_profile_to_autonomo` — build the `AutonomoProfile` from `WorkflowState.active_profile_record().values` (legacy). Replace `_profile_to_autonomo(state)` with `read_active_profile(state).projection_for_autonomo(filing_year)`.

### 3. `PROFILE_KEYS` enum / module-constant — full replacement

`PROFILE_KEYS` enumerates allowed scalar profile keys with their TOML aliases. The schema TOML supersedes this enumeration; the `[[sections.fields]]` declarations are now the sole source of truth.

Sites (11 hits):

- The defining module (need to locate exact path; grep showed 11 files use the name).
- Tests asserting per-key shape.
- Wizard catalogue and CLI key lookup.

Rewire wizard / CLI / registry consumers to read field metadata via `aeat.domain.user_profile.ProfileSchemaDefinition.iter_fields()` and the existing `UserProfileSelectorIndex`.

### 4. Tax-residence profile storage — already partly absorbed

The schema TOML carries a `tax_residence` section with the same fields as the legacy storage. Migration is purely consumer-side: re-route the deadline calendar and Renta projection callers to read via the new projection helpers.

### 5. Usage-ratio root storage — defer to W26 (`app ledger ratios`)

The schema TOML covers usage ratios under a dedicated section, but the W26 wave (already on the plan) owns the lifecycle and CLI for ratios. W09.P042 does not delete the usage-ratio storage; it only stops consumers from reading the legacy root after their migration.

### 6. Untyped CLI profile dictionaries — DELETE in P045

CLI commands such as `aeat config init` accept scalar `--tax-id`, `--activity`, etc. options and persist them as `ProfileRecord.values` entries. The new shape persists `UserProfileFact` rows. W09.P045 wires the CLI commands to the canonical `ProfileLifecycleService.register(RegisterProfileCommand)` boundary; the untyped flow is removed in the same slice.

## Migration order (S0248-S0252)

S0248 — Delete duplicate backend branches: remove `aeat.application.profile` package after migrating the 5 consumers below to `aeat.application.user_profile`.

- `application/wizard/_verifier.py`
- `application/workflow/_persistence.py` and `_models.WorkflowState.active_profile_record`
- `application/test_config_reset.py`, `application/test_setup_reset.py`
- `entrypoints/cli/test_config_setter.py`

S0249 — Remove stale CLI aliases: `_profile_to_autonomo` and any direct `ProfileRecord` consumers in `entrypoints/cli/_common.py`, plus the un-typed `aeat config init` scalar flow.

S0250 — Migrate internal callers: every `AutonomoProfile` consumer in `domain/deadlines`, `application/filing/runtime.py`, `application/overview`, `application/wizard/_status.py`, `application/workflow/_adapters.py`/`_engine.py`/`_protocols.py` wires through the new `UserProfileRecord` projections.

S0251 — Remove stale fixtures and tests: delete the old `profile/test_*.py`, rewrite `deadlines/test_engine.py` and `test_models.py` to construct via the new projection.

S0252 — Update boundary inventory in `entrypoints/cli/test_backend_boundary.py` to record the deleted shim/duplicate files so a future regression sweep keeps them out.

## Required projection helpers (block S0250)

Before S0250 can land, `aeat.application.user_profile` needs three projection helpers on the lifecycle service (or as standalone functions on the record):

- `projection_for_deadlines(record: UserProfileRecord, filing_year: int) -> DeadlineProfile` — maps schema facts to the typed deadline engine input.
- `projection_for_filing(record: UserProfileRecord, filing_year: int) -> FilingOperatorProfile` — maps schema facts to the filing-runtime profile.
- `projection_for_autonomo(record: UserProfileRecord, filing_year: int) -> AutonomoProfile` — the bridge replacement so consumers that still want the legacy shape get a thin façade.

These projections compose against the immutable snapshot (`UserProfileSnapshot.facts`) when filing approval is the consumer, and against the live record (`UserProfileRecord.facts`) for everything else.

Block: S0250 cannot ship until the three projection helpers exist. They are the natural S0249.5 / pre-S0250 step (formally added under S0248 along with the legacy-package deletion).

## Test coverage gates

After each migration slice, the targeted test slice must remain green:

- `pytest src/aeat/application/user_profile/` — 19 tests (already green).
- `pytest src/aeat/domain/deadlines/` — wave-current count, must remain green after the projection lands.
- `pytest src/aeat/application/filing/` — must remain green after `FilingOperatorProfile` migration.
- `pytest src/aeat/application/overview/` — calendar tests must remain green.
- `pytest src/aeat/application/workflow/` — engine and adapters tests must remain green.

No source changes were made by this audit step.
