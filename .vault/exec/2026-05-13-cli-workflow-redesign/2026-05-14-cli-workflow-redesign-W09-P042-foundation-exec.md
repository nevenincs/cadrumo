---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W09.P042.S0248-foundation'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
---

# `cli-workflow-redesign` `W09.P042.S0248` foundation work

## Description

Landed the canonical-side infrastructure that S0248 needs in order to
delete `aeat.application.profile/`. The legacy package is NOT yet
deleted; this commit chain only prepares the canonical replacement
surfaces. No shims, no shadow paths, no compat aliases.

Closed plan rows: none yet — S0248 remains `[ ]` until the atomic
consumer-migration commit lands.

## Commit chain

- `8dd911d8` Apex CLI ADR: reconciliation amendment (W71A-W85A track, CRUD verb contract)
- `3a08f880` Land in-flight W61 + W62 implementation bundle and supporting vault records
- `02d21b2c` W09.P042 schema TOML: add preferences, obligations sections + identity.notes
- `39224ea3` W09.P042 i18n cache: fire on canonical UserProfileLifecycleRepository writes
- `1b99d2f0` W09.P042 user_profile lifecycle: emit BucketEvent on every persisted mutation
- `0d2c64a3` W09.P042 user_profile orchestration: WorkflowState-aware helpers
- `6437c246` W09.P042 user_profile orchestration: add fact_value path lookup helper

## What landed

- **Schema TOML**: four real new fields (no `model_selectors` legacy
  aliases): `preferences.output_language` (enum es/en/ca/eu/gl,
  operational), `identity.notes` (string, identity),
  `obligations.third_party_transactions_above_347_threshold` (bool,
  financial), `obligations.bienes_extranjero_above_threshold` (bool,
  financial). Schema `field_paths` grew from 59 to 63.
- **`UserProfileLifecycleRepository.save/delete`** now fires the i18n
  output-language cache invalidator (lazy import so persistence cannot
  block on i18n).
- **`ProfileLifecycleService`** now emits append-only `BucketEvent` on
  every `register / edit_field / edit_section / remove / duplicate`.
  Two new `BucketEventType` enum members: `PROFILE_TOMBSTONED`,
  `PROFILE_DUPLICATED`. Constructor accepts an explicit events
  repository for testability.
- **`application.user_profile._orchestration`** new module:
  `register_active_profile / select_profile / set_active_field /
  set_active_fields / remove_active_profile / read_active_profile /
  fact_value`. Threads `WorkflowState.profiles` + `active_profile` and
  appends `profile.created / profile.selected / profile.values.updated
  / profile.values.cleared / profile.tombstoned` workflow events.
  Bucket-identity convention `bucket_id == profile_id` is the single
  place the legacy conflation lives (W74A scope will split into
  one-bucket-many-profiles).
- **Targeted tests**: 31 user_profile tests green
  (test_lifecycle: 8, test_orchestration: 6, test_projections: 5,
  test_repository: 7, test_services: 5).

## What is NOT yet landed

The legacy `aeat.application.profile/` package and all its consumers
are still on the legacy flat-key shape. The atomic refactor that
closes S0248 requires:

1. **Wizard catalogue rewire** (`application/wizard/_catalogue.py`):
   26 `WizardQuestion.profile_key` strings change to canonical schema
   paths. Mapping table is in this exec record's "Wizard key mapping"
   section. `_compiler.compile_profile_keys` passes through, so
   `PROFILE_KEYS` derived tuple becomes schema paths automatically.
2. **`WorkflowState.active_profile_record`** return type changes to
   `UserProfileRecord | None`. Body switches to
   `UserProfileLifecycleRepository(bucket_id=pointer.bucket_id).load(self.active_profile)`.
3. **CLI verbs** (`entrypoints/cli/_config/__init__.py`): `list / get
   / set / unset / status / reset` route through orchestration
   helpers. Help-text key examples switch to canonical schema paths.
4. **`core/i18n/_render.py::_active_profile_output_language`** reads
   `preferences.output_language` via `fact_value`, not `record.values.get("output.language")`.
5. **`entrypoints/cli/_common.py::_profile_to_autonomo`** projects
   via `record_to_values(record)` instead of `record.values`.
6. **`entrypoints/cli/_overview.py`** same projection adjustment.
7. **`application/wizard/_status.py`** moves `validate_profile(record.values)`
   and `project_answers(SETUP_FLOW, values)` to canonical equivalents
   (the canonical `ProfileValidationService` already exists; SETUP_FLOW
   projection needs a canonical replacement that walks
   `UserProfileRecord.facts`).
8. **`application/wizard/_persistence.py::project_answers` and
   wizard runner** write through `application/user_profile/_orchestration.register_active_profile`
   on first run, `set_active_fields` on subsequent edits — instead of
   `application.profile._actions.set_profile_values`.
9. **`adapters/outbound/google/_oauth_flow.py`** drops
   `profile_bucket_repository` import; routes Google OAuth credential
   persistence through the canonical bucket (or a dedicated canonical
   namespace if the OAuth flow is conceptually independent of the
   user profile).
10. **`application/operator_surface/_contract.py`** updates owner
    strings from `"aeat.application.profile"` to
    `"aeat.application.user_profile"`.
11. **`core/errors/registry/_application.py`** drops the
    `ProfileBucketPersistenceError` FQN entry (the canonical service
    does not emit it).
12. **Tests** in `application/test_config_reset.py`,
    `application/test_setup_reset.py`,
    `application/test_diagnostics.py`,
    `application/test_config_parity.py`,
    `application/test_apex_workflow_verification.py`,
    `application/wizard/test_status.py`,
    `core/i18n/test_output_language.py`,
    `entrypoints/cli/test_workflow_surface.py`,
    `entrypoints/cli/test_root_help_shape.py`,
    `entrypoints/cli/test_profile_output_language.py`,
    `entrypoints/cli/test_config_setter.py` rewrite to use canonical
    orchestration + `UserProfileLifecycleRepository`.
13. **`application/profile/test_actions.py`** and `test_validate.py`
    delete with the package.
14. **`src/aeat/application/profile/` deletion** + plan tick + final
    exec record.

The migration cannot be staged in smaller commits than (1) +
everything else, because the moment the wizard switches writers to
canonical schema paths, every reader still on legacy flat-key shape
gets nothing back. Tested estimate: ~30 files, 1500-2500 lines of
diff, 1-2 hours of careful work on a fresh context budget.

## Wizard key mapping (for the next session)

| Wizard `profile_key` | Schema path |
|---|---|
| `tax.id` | `identity.tax_id` |
| `name` | `identity.name` |
| `surnames` | `identity.surnames` |
| `activity` | `activities.description` |
| `address.postcode` | `contact.postcode` |
| `declaration.type` | `filing_export.declaration_type` |
| `output.language` | `preferences.output_language` |
| `notes` | `identity.notes` |
| `tax.residence.ccaa` | `tax_residence.ccaa` |
| `iva.regime` | `iva.regime` (unchanged) |
| `taxpayer.sex` | `renta_taxpayer.sex` |
| `taxpayer.marital_status` | `renta_taxpayer.marital_status` |
| `taxpayer.birth_date` | `renta_taxpayer.birth_date` |
| `taxpayer.disability_grade` | `renta_taxpayer.disability_grade` |
| `taxpayer.death_date` | `renta_taxpayer.death_date` |
| `spouse.tax.id` | `renta_spouse.tax_id` |
| `spouse.name` | `renta_spouse.name` |
| `spouse.surnames` | `renta_spouse.surnames` |
| `spouse.birth_date` | `renta_spouse.birth_date` |
| `spouse.sex` | `renta_spouse.sex` |
| `spouse.disability_grade` | `renta_spouse.disability_grade` |
| `spouse.non_resident_irpf` | `renta_spouse.non_resident_irpf` |
| `spouse.eu_eea_resident` | `renta_spouse.eu_eea_resident` |
| `spouse.eu_eea_country` | `renta_spouse.eu_eea_country` |
| `family.descendants_eu_eea_deduction` | `renta_family.descendants_eu_eea_deduction` |
| `family.minor_children_in_unit` | `renta_family.minor_children_in_unit` |
| `third_party_transactions_above_347_threshold` | `obligations.third_party_transactions_above_347_threshold` |
| `bienes_extranjero_above_threshold` | `obligations.bienes_extranjero_above_threshold` |

## Tests

- `pytest src/aeat/application/user_profile/` — 31 passed (canonical
  surface).
- `pytest src/aeat/domain/buckets/` — 21 passed (new enum members
  honoured by existing serialization).
- `pytest src/aeat/domain/user_profile/` — 13 passed (schema TOML
  loads + 4 new fields visible).

## Guards held

- No `model_selectors` aliases bridging legacy flat keys to schema
  paths (the two test aliases added at the start of this session were
  reverted before commit).
- No `aeat.application.profile` re-exports inside `aeat.application.user_profile`.
- No `record.values` compatibility property on `UserProfileRecord`.
- No transitional helpers that read legacy storage and translate to
  canonical, or vice versa.
- Two parallel storage namespaces remain alive
  (`aeat.application.profile.bucket` and
  `aeat.application.user_profile.value`) only because the consumer
  migration is unfinished. The canonical namespace is currently
  unused at runtime; nothing writes to it from CLI surfaces.
