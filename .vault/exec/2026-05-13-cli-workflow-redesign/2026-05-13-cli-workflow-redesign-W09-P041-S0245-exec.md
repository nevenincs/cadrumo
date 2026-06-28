---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W09.P041.S0245'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w09-p041-s0241-profile-service-ownership-audit]]"
---

# `cli-workflow-redesign` `W09.P041.S0245`

Closed plan rows:

- `W09.P041.S0245`

## Description

Routed every register / read / edit / remove / duplicate / list operation for the schema-driven user-profile backend through one canonical `ProfileLifecycleService` (`src/aeat/application/user_profile/_lifecycle.py`). The service is the sole sanctioned write path for live `UserProfileRecord` aggregates — CLI thin adapters (W09.P045) and migrated consumers (W09.P042) call this surface; no caller constructs records or touches the secure repository directly.

Lifecycle surface:

- `register(RegisterProfileCommand)` — schema-validates the supplied facts, refuses on `required_field_missing` (or any other ERROR-severity issue) with `ProfileSchemaValidationError`, refuses duplicate `profile_id` with `ProfileAlreadyExistsError`, persists a new `UserProfileRecord` with `status=ACTIVE`.
- `read(profile_id)` — returns the live aggregate or raises `ProfileNotFoundError`.
- `edit_field(EditProfileFieldCommand)` — upserts one effective-dated fact and re-validates the resulting aggregate.
- `edit_section(EditProfileSectionCommand)` — replaces every fact in one schema section with the supplied facts and re-validates.
- `remove(RemoveProfileCommand)` — tombstones the live root via `UserProfileRecord.tombstone()`; immutable filing snapshots are retained per ADR policy.
- `duplicate(DuplicateProfileCommand)` — copies an existing live profile under a new id/display name; refuses tombstoned sources and duplicate target ids.
- `list_profiles()` — returns a sorted `ProfileListResult` walking the bucket-scoped secure-object namespace.

The service is composed from the `UserProfileLifecycleRepository` (S0244) and `ProfileValidationService` (S0243), so both the validation contract and the persistence contract are honored on every write.

## Modified Paths

- `src/aeat/application/user_profile/_lifecycle.py` (created)
- `src/aeat/application/user_profile/__init__.py` (lazy export of `ProfileLifecycleService`)
- `src/aeat/application/user_profile/test_lifecycle.py` (created — 7 tests)
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

`pytest src/aeat/application/user_profile/` — 19 passed (5 service + 7 repository + 7 lifecycle).

The lifecycle tests cover: schema-violation refusal at register time, persistence of a fully-populated profile, duplicate-id refusal, field-level upsert, tombstone on remove, duplicate to a new id, and sorted listing. Every test uses the real `registry/aeat/user_profile/schema.toml` and a real `SecureObjectRepository` against an in-memory SQLite engine — no mocks, fakes, stubs, or monkeypatches.

Next: W09.P042 (shadow duplicate removal). The legacy `aeat.application.profile` package (`ProfileBucket`, `ProfileBucketRepository`, `ProfileRecord`) and the 41 `PROFILE_KEYS` / `AutonomoProfile` / `ProfileRecord` consumers must migrate to this canonical service per the S0241 service ownership map.
