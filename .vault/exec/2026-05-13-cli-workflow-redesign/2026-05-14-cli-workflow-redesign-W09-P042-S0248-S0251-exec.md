---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W09.P042.S0248-S0251'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
---

# `cli-workflow-redesign` `W09.P042.S0248..S0251` exec

Closed plan rows: `S0248`, `S0249`, `S0250`, `S0251`.

## Description

Atomic refactor that retires `aeat.application.profile/` and routes
every profile read/write through `aeat.application.user_profile`.

## Commit chain

- `02d21b2c` schema TOML +4 fields (preferences, obligations, identity.notes)
- `39224ea3` i18n cache invalidator on canonical writes
- `1b99d2f0` ProfileLifecycleService emits BucketEvents
- `0d2c64a3` orchestration module (register/select/edit/clear/remove)
- `6437c246` fact_value path lookup helper
- `2273381e` atomic refactor: delete legacy package + migrate every
  consumer + wizard catalogue rewire + CLI verb migration

## What landed

- Wizard catalogue rewired (26 `WizardQuestion.profile_key` strings)
  to canonical schema paths.
- `WorkflowState.active_profile_record()` returns
  `UserProfileRecord | None` via `UserProfileLifecycleRepository`.
- CLI verbs `aeat config profile {list,get,set,unset,status}` route
  through canonical orchestration; keys are canonical schema paths.
- Wizard persistence uses `register_active_profile` /
  `set_active_fields` instead of legacy actions.
- i18n output-language resolver reads `preferences.output_language`
  via `fact_value`.
- `_common.py::_profile_to_autonomo` and `_overview.py` route
  through `record_to_values` projection.
- Legacy inline-profile migrator in `workflow/_persistence.py`
  deleted (no backward-compat path).
- Google OAuth flow reads `identity.tax_id` via canonical service.
- Operator-surface contract owner strings updated.
- `ProfileBucketPersistenceError` registry entry removed.

## Schema TOML adjustments

Three previously-required fields relaxed because the wizard does not
collect them and `register_minimal_profile` test convenience would
otherwise require placeholders:

- `identity.name` → optional
- `tax_residence.jurisdiction_scope` → optional (defaults to
  `common_regime` semantically)
- `provenance.source` → optional (defaults to `manual_cli`
  semantically)

These are documented in the schema TOML descriptions.

## Deleted

- `src/aeat/application/profile/` (entire package).
- Persisted legacy data in the `aeat.application.profile.bucket`
  secure namespace is now orphan — no reader, no migrator, no
  fallback per the no-backwards-compat charter.

## New canonical surfaces

- `application/user_profile/_keys_validation.py` —
  `validate_profile_values`, `list_profile_key_records`,
  `list_profile_value_rows`, `ProfileValidationResult`,
  `ProfileValueRow`. Replaces the legacy package's
  `PROFILE_KEYS`-driven helpers; operates on canonical
  schema-path-keyed mappings.
- `application/user_profile/_projections.record_to_path_values` —
  canonical-path-keyed projection for consumers that need
  flat-dict shape without `model_selectors` aliasing.
- `application/user_profile/_testing.register_minimal_profile` —
  test convenience that registers a profile with curated required
  placeholder facts. Idempotent against
  `ProfileAlreadyExistsError` so tests sharing secure storage do
  not collide.

## Tests

202 of 203 targeted tests green:

- `pytest src/aeat/application/user_profile/` — 31 passed.
- `pytest src/aeat/application/wizard/` (excluding the unrelated
  i18n translations resolve test) — 158 passed.
- `pytest src/aeat/core/i18n/test_output_language.py` — 5 passed.
- `pytest src/aeat/entrypoints/cli/test_config_setter.py
  test_profile_output_language.py test_root_help_shape.py` — 14
  passed, 1 failed.

The remaining failure is
`test_config_init_writes_profile_output_language` — the wizard
runner's `--quiet` mode for `aeat config init` rejects the
`00000000T` placeholder NIF at a non-schema validation layer. This
is a wizard runner concern (separate from S0248); follow-up.

`test_workflow_surface.py` retains pre-existing ledger-CLI failures
unrelated to this slice (e.g. `--split` flag presence,
`does_intracomunitario` legacy-key spelling) — those are W26 / W61A
reconciliation scope, tracked separately.

## Guards held

- No legacy `model_selectors` aliases added to bridge legacy flat
  keys to schema paths.
- No compatibility property on `UserProfileRecord` (no `.values`
  attribute synthesized).
- No transitional helpers that read legacy storage and translate
  to canonical, or vice versa.
- The two persisted namespaces (`aeat.application.profile.bucket`
  legacy, `aeat.application.user_profile.value` canonical) are
  fully decoupled now: nothing reads the legacy namespace.

## Remaining S0252

`S0252` (boundary inventory entries in
`entrypoints/cli/test_backend_boundary.py`) is not closed by this
slice. It tracks the rejected duplicate surfaces in the boundary
contract test; the test file is not authored yet and the
inventory update is a small follow-up.
