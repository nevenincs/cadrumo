---
tags:
  - '#reference'
  - '#core-authority-action-tracker'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-constants-reference]]"
  - "[[2026-05-31-core-authority-shims-reference]]"
  - "[[2026-05-31-core-authority-duplicates-reference]]"
  - "[[2026-05-31-core-authority-compat-markers-reference]]"
  - "[[2026-05-31-core-authority-import-map-reference]]"
  - "[[2026-05-30-identity-primitives-adr]]"
---

# core-authority-action-tracker reference: unified action inventory

> **Enum audit pending.** The core-authority-enums-reference audit is still in flight at
> the time this tracker was drafted. This document will receive a v2 update - adding new
> action rows under the appropriate categories - once that audit returns. No existing rows
> will be renumbered; new rows will be appended with the next available IDs in each category.

## 1. Campaign summary

This campaign centralises authority over all shared constants, module-level identifiers,
time utilities, import direction, and duplicate declarations across src/aeat/. The codebase
currently carries cross-layer constant leakage (domain values imported by entrypoints;
adapter URLs imported by application), two parallel time implementations, split import paths
for the same function, duplicate class and constant names across sibling modules, and one
confirmed hexagonal-direction violation in production code. The goal is a single canonical
declaration site for every cross-cutting symbol, clean import-direction everywhere in
production, and no shim or split-path ambiguity for callers. The findings here feed a
planned ADR amendment to the existing `2026-05-30-identity-primitives-adr` (and a companion
new ADR where scope exceeds that document existing rule surface). The Plan will order
execution; this tracker only enumerates what must move, merge, delete, or stay.

---

## 2. Action table

### Relocate-to-core

| Action ID | Category | Current site(s) | Target site | Consumer count | Source audit | ADR rule | Risk |
|---|---|---|---|---|---|---|---|
| RELOC-001 | relocate-to-core | `domain/modelos/_row_models.py:276` (`M347_THRESHOLD_EUR`) | `core/statutory_thresholds.py` (new module) | 1 production (`entrypoints/cli/_modelo.py`) | `2026-05-31-core-authority-constants-reference` | (amend) statutory-value placement rule | low |
| RELOC-002 | relocate-to-core | `core/config.py:60` (`PROJECT_ROOT` duplicate) | `core/paths.py:23` (canonical; remove from config) | 2 production + 2 test: `application/diagnostics.py`, `adapters/outbound/llm`, `tests/test_release_config.py`, `entrypoints/cli/test_retired_cli_literals.py` | `2026-05-31-core-authority-constants-reference`, `2026-05-31-core-authority-duplicates-reference` | (amend) single-declaration rule for cross-cutting paths | low |
| RELOC-003 | relocate-to-core | `domain/transactions/_repository.py:28` (`TX_BUCKET_NAMESPACE`) | `adapters/persistence/storage/_namespace_registry.py`; domain module receives namespace as constructor arg | 1 production: `application/ledger/_actions.py` | `2026-05-31-core-authority-constants-reference` | (amend) namespace-string placement rule | low |

### Fix-import-direction

| Action ID | Category | Current site(s) | Target site | Consumer count | Source audit | ADR rule | Risk |
|---|---|---|---|---|---|---|---|
| FIX-001 | fix-import-direction | `domain/user_profile/_registry_contract.py` imports `aeat.application` | Refactor contract to use domain-layer types only; or move `_registry_contract.py` to application layer | 1 production violation | `2026-05-31-core-authority-import-map-reference` | Hexagonal Rule 2 (domain must not import application) | medium |
| FIX-002 | fix-import-direction | `adapters/outbound/aeat/sede/_iva_compensation_wallet.py:64-65` (`IVA_COMPENSATION_WALLET_URL`, `PRE303_PRESENTATION_SERVICE_URL`) imported by `application/live/__init__.py` | Application reads `Settings.external_constants().aeat.sede_paths.*` directly; module constants deleted | 1 production | `2026-05-31-core-authority-constants-reference` | (amend) adapter-to-application import prohibition | low |
| FIX-003 | fix-import-direction | `domain/calculations/registry/_groi_oracle.py:64` (`AEAT_GROI_URL`) imported by `adapters/outbound/aeat/sede/_groi_check.py` | Adapter reads `Settings.external_constants()` directly; domain oracle drops module-level URL constant | 1 production | `2026-05-31-core-authority-constants-reference` | (amend) domain-to-adapter export prohibition | low |
| FIX-004 | fix-import-direction | `domain/calculations/registry/_aeat_nif_iva_oracle.py:44,50` (`AEAT_NIF_IVA_VERIFICATION_URL`, `AEAT_NIF_IVA_ENTRY_URL`) imported by `adapters/outbound/aeat/sede/_nif_iva_check.py` | Adapter reads `Settings.external_constants()` directly; domain oracle drops module-level URL constants | 1 production | `2026-05-31-core-authority-constants-reference` | (amend) domain-to-adapter export prohibition | low |

| MERGE-003 | merge-duplicates | `_Holder` in 5 test files |
| MERGE-003 | merge-duplicates | `_Holder` BaseModel fixture in 5 test files: `domain/attachments/test_ids.py:15`, `domain/invoices/test_ids.py:15`, `domain/modelos/test_verification_report_id.py:15`, `domain/transactions/test_id_normalization.py:15`, `domain/user_profile/test_snapshot_hash_equality.py:15` | `src/aeat/tests/fixtures/identity_holder.py` | 5 test files | `2026-05-31-core-authority-duplicates-reference` | (amend) test-fixture deduplication rule | low |
| DELETE-001 | delete-shim | `adapters/outbound/llm/_providers/__init__.py:11-12` (re-aliases `_ProviderAdapter` and `_DeterministicAdapter` under same private names; absent from `__all__` but importable through package) | Remove re-aliases; callers use canonical sites `_providers.base._ProviderAdapter` and `_providers.deterministic._DeterministicAdapter` | 0 external callers (internal-only) | `2026-05-31-core-authority-shims-reference` | Architecture boundary: no re-export shims | low |
### Merge-duplicates

| Action ID | Category | Current site(s) | Target site | Consumer count | Source audit | ADR rule | Risk |
|---|---|---|---|---|---|---|---|
| MERGE-001 | merge-duplicates | `domain/iva/_invoice_classification.py:63` (`_IVA_RATE_TO_VAT_KIND`, 5 entries) and `domain/invoices/_enums.py:76` (3 entries - missing RATE_0 and EXEMPT) | Expand `domain/invoices/_enums.py` to 5 entries; delete copy in `_invoice_classification.py`; that module imports from `_enums.py` | Domain-internal; eliminates latent classification hole for zero-rated and exempt lines | `2026-05-31-core-authority-constants-reference` | (amend) single-declaration rule | low |
| MERGE-002 | merge-duplicates | `adapters/persistence/storage/_namespace_registry.py:221,230` (NamespaceDef objects) shadowed by plain strings at `application/user_profile/_repository.py:44-45` (same names, different types) | Remove application-layer string shadows; import canonical NamespaceDef from registry | 1 production (application-internal) | `2026-05-31-core-authority-constants-reference`, `2026-05-31-core-authority-duplicates-reference` | (amend) single-declaration rule | low |
| MERGE-003 | merge-duplicates | `_Holder` BaseModel fixture in 5 test files: `domain/attachments/test_ids.py:15`, `domain/invoices/test_ids.py:15`, `domain/modelos/test_verification_report_id.py:15`, `domain/transactions/test_id_normalization.py:15`, `domain/user_profile/test_snapshot_hash_equality.py:15` | `src/aeat/tests/fixtures/identity_holder.py` | 5 test files | `2026-05-31-core-authority-duplicates-reference` | (amend) test-fixture deduplication rule | low |
| MERGE-004 | merge-duplicates | `_EmptyAnswersBase` in 4 wizard test files: `application/wizard/test_commands_helpers.py:41`, `test_compile.py:35`, `test_models.py:32`, `test_audit_rules.py:28` | `src/aeat/application/wizard/test_fixtures.py` | 4 test files | `2026-05-31-core-authority-duplicates-reference` | (amend) test-fixture deduplication rule | low |
| MERGE-005 | merge-duplicates | `_DummyRepository` in 3 test files: `core/resources/test_registry.py:60`, `adapters/persistence/storage/envelope/test_secure_bound_repository.py:46`, `test_secure_bound_repository_contract.py:57` | `src/aeat/tests/fixtures/repositories.py` | 3 test files | `2026-05-31-core-authority-duplicates-reference` | (amend) test-fixture deduplication rule | low |
| MERGE-006 | merge-duplicates | `_IsolatedSettings` in 3 test files: `domain/manuals/test_loader.py:28`, `domain/manuals/test_verify.py:19`, `adapters/outbound/llm/test_client.py:32` | `src/aeat/tests/fixtures/settings.py` | 3 test files | `2026-05-31-core-authority-duplicates-reference` | (amend) test-fixture deduplication rule | low |

### Delete-shim

| Action ID | Category | Current site(s) | Target site | Consumer count | Source audit | ADR rule | Risk |
|---|---|---|---|---|---|---|---|
| DELETE-001 | delete-shim | `adapters/outbound/llm/_providers/__init__.py:11-12` (re-aliases `_ProviderAdapter` and `_DeterministicAdapter` under same private names; absent from `__all__` but importable through package) | Remove re-aliases; callers use canonical sites `_providers.base._ProviderAdapter` and `_providers.deterministic._DeterministicAdapter` | 0 external callers (internal-only) | `2026-05-31-core-authority-shims-reference` | Architecture boundary: no re-export shims | low |
| DELETE-002 | delete-shim | `adapters/outbound/storage/_google_drive.py:698-699` (dead `import json` retained for speculative future use, no current caller) | Delete unused import | 0 callers | `2026-05-31-core-authority-shims-reference` | Source hygiene | low |
| DELETE-003 | delete-shim | `application/calculations/_observations_repository.py:139` (`_legacy_iva_wallet_decision_key` - legacy key-format fallback called at `load_decision:269`) | Track removal timeline explicitly; delete fallback path when pre-hardening data migration window closes | 1 internal call site | `2026-05-31-core-authority-compat-markers-reference` | (amend) shim-removal timeline tracking rule | medium |

### Rename-collision

| Action ID | Category | Current site(s) | Target site | Consumer count | Source audit | ADR rule | Risk |
|---|---|---|---|---|---|---|---|
| RENAME-001 | rename-collision | `domain/profile/inventory/__init__.py:34` and `domain/profile/assets/__init__.py:20` (both `SCHEMA_VERSION` - identical name and value in sibling modules) | Rename in-place to `INVENTORY_SCHEMA_VERSION` and `ASSETS_SCHEMA_VERSION` | Domain-internal only; no cross-module consumers currently | `2026-05-31-core-authority-constants-reference`, `2026-05-31-core-authority-duplicates-reference` | (amend) unambiguous-naming rule | low |
| RENAME-002 | rename-collision | `application/user_profile/_repository.py:44-45` plain-string names `USER_PROFILE_VALUE_NAMESPACE` and `USER_PROFILE_SNAPSHOT_NAMESPACE` shadow adapter NamespaceDef objects of the same name | Rename local strings (e.g. `_PROFILE_VALUE_NS_KEY`, `_PROFILE_SNAPSHOT_NS_KEY`) or eliminate via MERGE-002 | 1 application module | `2026-05-31-core-authority-constants-reference`, `2026-05-31-core-authority-duplicates-reference` | (amend) unambiguous-naming rule | low |
| RENAME-003 | rename-collision | `entrypoints/cli/test_stdio.py:95` (`_ReconfigurableStream`) shadows production protocol at `core/json_contract.py:112` | Rename test helper to `_MockRedirectableStream` | 1 test file | `2026-05-31-core-authority-duplicates-reference` | Source hygiene | low |
| RENAME-004 | rename-collision | `entrypoints/cli/test_common_output.py:15` (`_EnvelopePayload`) shadows production type at `adapters/persistence/storage/master_key/_master_key.py:99` | Rename test helper to `_TestPayload` | 1 test file | `2026-05-31-core-authority-duplicates-reference` | Source hygiene | low |
| RENAME-005 | rename-collision | `application/portals/_service.py:24` (`PortalRow`) collides with ORM model at `adapters/persistence/storage/sql/_orm.py:52` | Rename application class to `PortalServiceRow` | Application-internal callers | `2026-05-31-core-authority-duplicates-reference` | (amend) naming clarity across layers | low |
| RENAME-006 | rename-collision | `application/export/_errors.py:8` and `adapters/outbound/aeat/export/_errors.py:12` (both `ExportFormatError` - same name across layer boundary) | Establish hierarchy: adapter error inherits from application error, or rename adapter variant to `AEATExportFormatError` | Cross-layer import sites | `2026-05-31-core-authority-duplicates-reference` | (amend) error-hierarchy clarity rule | medium |

### Migrate-to-settings

| Action ID | Category | Current site(s) | Target site | Consumer count | Source audit | ADR rule | Risk |
|---|---|---|---|---|---|---|---|
| MIGRATE-001 | migrate-to-settings | `domain/calculations/registry/_groi_oracle.py:60` (`GROI_ORACLE_ID`) exposed as public module constant | Make private (`_GROI_ORACLE_ID`) or move to `external_constants.toml [aeat.oracles]`; remove public export | Adapter test only; 0 production callers | `2026-05-31-core-authority-constants-reference` | (amend) settings-as-authority rule | low |
| MIGRATE-002 | migrate-to-settings | `adapters/outbound/aeat/auth/_clave_movil.py:83` (`CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE`) imported indirectly by `application/auth/_diagnostics.py` | Move to `external_constants.toml` or make private and inject at construction time | 1 indirect consumer | `2026-05-31-core-authority-constants-reference` | (amend) settings-as-authority rule | low |

### Split-path consolidation

| Action ID | Category | Current site(s) | Target site | Consumer count | Source audit | ADR rule | Risk |
|---|---|---|---|---|---|---|---|
| SPLIT-001 | fix-import-direction | `application/workflow/_models.py:29` re-exposes `resolve_active_bucket_id` from `core._bucket_pointer_io` creating a second importable path | All 14 import sites migrated to `from aeat.core._bucket_pointer_io import resolve_active_bucket_id`; bare module-level name removed from `_models.py` | 14 sites: `entrypoints/cli/test_profile_census_verbs.py:65,176`, `test_repair_privacy_contract.py:19`, `test_ratios_verbs.py:14`, `test_profile_lifecycle_verbs.py:396,423,922,963`, `application/user_profile/test_orchestration.py:168`, `application/workflow/test_active_profile_resolution.py:23`, `entrypoints/cli/_config/__init__.py:40,339,917,1242` | `2026-05-31-core-authority-shims-reference` | (amend) no-split-path rule | high |
| SPLIT-002 | delete-shim | `core/_time.py:8` (`utc_now`, 4 production callers) and `core/time/_clock.py` (`_now`, 11 callers via package re-export) - two parallel datetime.now(tz=UTC) implementations | Retire one; consolidate all 15 import sites to the surviving canonical function | 15 sites: 4 on `utc_now` (`domain/user_profile/_values.py:16`, `application/workflow/_utils.py:5`, `application/auth/_actions.py:7`, `application/filing/__init__.py:10`); 11 on `_now` (workflow engine, calc sheets, live services, ledger) | `2026-05-31-core-authority-shims-reference` | (amend) single-implementation rule for time utilities | high |

### Name-surface hygiene (private-named public exports)

| Action ID | Category | Current site(s) | Target site | Consumer count | Source audit | ADR rule | Risk |
|---|---|---|---|---|---|---|---|
| HYGIENE-001 | delete-shim | `core/time/__init__.py:14-21` re-exports `_now`, `_coerce_utc_aware`, `_validate_utc_aware` via `__all__` (entire public surface is private-named) | Either rename all three to public names and update 11 callers, or remove the `__init__` re-export and have callers import from `._clock` / `._utc` directly | 11 callers importing `_now` via the package | `2026-05-31-core-authority-shims-reference` | (amend) no-private-named public surface rule | medium |
| HYGIENE-002 | delete-shim | `core/parsing/__init__.py:15-18` re-exports `_parse_bool`, `_parse_date`, `_parse_ddmmyyyy_date`, `_parse_iso8601_date` - all private-named in `__all__`; double-alias at `adapters/outbound/aeat/sede/_censo.py:158` and `domain/deadlines/_profiles.py:18` | Rename to public names or remove `__init__` re-export; eliminate double-aliases | 2 double-alias callers plus broader package surface | `2026-05-31-core-authority-shims-reference` | (amend) no-private-named public surface rule | low |

### Test-fixture consolidation (high-redeclaration functions)

| Action ID | Category | Current site(s) | Target site | Consumer count | Source audit | ADR rule | Risk |
|---|---|---|---|---|---|---|---|
| FIXTURE-001 | merge-duplicates | `_isolated_backend` fixture declared in 28 test files | Shared `conftest.py` at appropriate scope | 28 test files | `2026-05-31-core-authority-duplicates-reference` | (amend) test-fixture deduplication rule | medium |
| FIXTURE-002 | merge-duplicates | `secure_objects` fixture declared in 22 test files | Shared fixture module | 22 test files | `2026-05-31-core-authority-duplicates-reference` | (amend) test-fixture deduplication rule | medium |
| FIXTURE-003 | merge-duplicates | `cli_runner` fixture declared in 21 test files | CLI-level `conftest.py` | 21 test files | `2026-05-31-core-authority-duplicates-reference` | (amend) test-fixture deduplication rule | medium |
| FIXTURE-004 | merge-duplicates | `_transaction` fixture declared in 17 test files | Domain fixture module | 17 test files | `2026-05-31-core-authority-duplicates-reference` | (amend) test-fixture deduplication rule | medium |
| FIXTURE-005 | merge-duplicates | `_isolated_cli_backend` fixture declared in 16 test files | CLI `conftest.py` | 16 test files | `2026-05-31-core-authority-duplicates-reference` | (amend) test-fixture deduplication rule | medium |

---

## 3. Categories summary

| Category | Count |
|---|---|
| relocate-to-core | 3 (RELOC-001 to RELOC-003) |
| fix-import-direction | 5 (FIX-001 to FIX-004, SPLIT-001) |
| merge-duplicates | 11 (MERGE-001 to MERGE-006, FIXTURE-001 to FIXTURE-005) |
| delete-shim | 7 (DELETE-001 to DELETE-003, HYGIENE-001, HYGIENE-002, SPLIT-002, DELETE-002) |
| rename-collision | 6 (RENAME-001 to RENAME-006) |
| migrate-to-settings | 2 (MIGRATE-001, MIGRATE-002) |
| **Total** | **34** |

---

## 4. Protect list

The following five package APIs were confirmed legitimate by the shims audit
(`2026-05-31-core-authority-shims-reference`). They are NOT represented in any
action row above and must not be modified as part of this campaign.

1. **aeat.core.identity** - flat public surface for all identity primitives
   (`BucketId`, `ProfileId`, `SnapshotId`, `TransactionId`, `SubjectTaxId`,
   `IdentityDocument`, `IdentityError`, `validate_identity`, `validate_spanish_tax_id`).
   Sub-modules are intentionally private. Caller migration cost is very high;
   the `__init__` wall is the canonical public API.

2. **aeat.adapters.persistence.storage** - persistence-layer public boundary contract
   (~80 names across crypto, envelope, master-key, SQL, rotation, namespace-registry).
   Caller migration cost is very high.

3. **aeat.domain.calculations.registry** - registry authority public surface
   (`ValidatedRegistryAuthority`, `RegistryValidator`, ~30 snapshot/calculation types).
   Caller migration cost is very high.

4. **aeat.adapters.persistence.storage.sql** - SQL substrate public surface
   (`SecureObjectRepository`, engine, session, records, repositories - 15 names,
   ~20 direct callers). Caller migration cost is high.

5. **aeat.application.auth** - auth application public surface (catalogue, models,
   sessions, diagnostics, operator-view names). Caller migration cost is high.

---

## 5. Open questions for the ADR

The following items require an explicit ADR-level decision before any execution
agent can dispatch the corresponding action rows.

- **Statutory-threshold placement** (RELOC-001): Should `M347_THRESHOLD_EUR`
  (RD 1065/2007 art. 31.1, Decimal 3005.06) live in a new `core/statutory_thresholds.py`
  typed module with inline BOE citation, or in `core/external_constants.toml` read
  through `Settings.external_constants()`? The typed-module path enables static references;
  the TOML path is consistent with existing URL and OAuth-scope centralisation but loses
  static-type safety for a numeric threshold.

- **Private-named public surface legality** (HYGIENE-001, HYGIENE-002): Do
  `core/time/__init__.py` and `core/parsing/__init__.py` re-exporting
  underscore-prefixed names via `__all__` violate the no-shim rule, or do they
  represent a legitimate intra-core internal-use surface where callers are intentionally
  expected to use implementation details? The answer determines whether HYGIENE-001/002
  are renames or full deletions of the `__init__` walls.

- **utc_now vs _now consolidation direction** (SPLIT-002): Is
  `core/_time.py:utc_now` (public name, 4 callers) or `core/time/_clock.py:_now`
  (private name, 11 callers re-exported through the package) the canonical survivor?
  The choice also determines whether `core/time/__init__.py` is retained at all
  after HYGIENE-001.

- **resolve_active_bucket_id rename on consolidation** (SPLIT-001): The workflow module
  may have introduced the shim path to give the function a workflow-contextual home.
  Should consolidation to `core._bucket_pointer_io` also rename the function,
  or is the existing name stable at its canonical core location?

- **domain/user_profile/_registry_contract.py import direction** (FIX-001): Is the
  domain -> application import a genuine Rule 2 violation requiring purging and replacement
  with domain-layer-only types, or does this contract module legitimately need
  application-layer types to fulfil its role - in which case the structural fix is to move
  `_registry_contract.py` to the application layer rather than rewriting its imports?

---

## Module(s)

src/aeat/core/, src/aeat/domain/, src/aeat/application/,
src/aeat/adapters/, src/aeat/entrypoints/, src/aeat/tests/

## File(s)

Primary production files referenced across all five source audits:

- src/aeat/core/paths.py, src/aeat/core/config.py, src/aeat/core/_time.py
- src/aeat/core/time/_clock.py, src/aeat/core/time/__init__.py
- src/aeat/core/parsing/__init__.py, src/aeat/core/_bucket_pointer_io.py
- src/aeat/domain/modelos/_row_models.py
- src/aeat/domain/transactions/_repository.py
- src/aeat/domain/iva/_invoice_classification.py
- src/aeat/domain/invoices/_enums.py
- src/aeat/domain/profile/inventory/__init__.py, src/aeat/domain/profile/assets/__init__.py
- src/aeat/domain/user_profile/_registry_contract.py
- src/aeat/domain/calculations/registry/_groi_oracle.py
- src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py
- src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py
- src/aeat/adapters/outbound/aeat/sede/_groi_check.py
- src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py
- src/aeat/adapters/outbound/llm/_providers/__init__.py
- src/aeat/adapters/outbound/storage/_google_drive.py
- src/aeat/adapters/persistence/storage/_namespace_registry.py
- src/aeat/application/user_profile/_repository.py
- src/aeat/application/calculations/_observations_repository.py
- src/aeat/application/workflow/_models.py
- src/aeat/application/export/_errors.py
- src/aeat/adapters/outbound/aeat/export/_errors.py
- src/aeat/application/portals/_service.py
- src/aeat/entrypoints/cli/_modelo.py
- src/aeat/entrypoints/cli/_config/__init__.py

## Related

- `2026-05-31-core-authority-constants-reference`
- `2026-05-31-core-authority-shims-reference`
- `2026-05-31-core-authority-duplicates-reference`
- `2026-05-31-core-authority-compat-markers-reference`
- `2026-05-31-core-authority-import-map-reference`
- `2026-05-30-identity-primitives-adr`
