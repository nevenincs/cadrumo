---
tags:
  - '#audit'
  - '#codebase-health'
date: '2026-05-21'
modified: '2026-05-21'
related: []
---



# `codebase-health` audit: `persistence-boundary-identity-swarm-audit`

## Scope


## Findings


## Recommendations



## Context

## Scope

Audit axis: **persistence-boundary identity and roundtrip integrity** following three concurrent churn campaigns:

- Profile UUID identity cutover — immutable UUIDv4 `profile_id` decoupled from mutable `display_name`; bucket directory name equals the UUID.
- Disaster-recovery campaign — reworked `profile create` / `edit` / `delete` as an all-or-nothing cross-store unit of work (`ProfileRepository`).
- Schema-hardening campaign (M100 cluster) — churned registry-backed records and `RegistryModeloObservation` / `CasillaObservation` provenance.

Boundaries examined:

1. Encrypted SQL via `SecureObjectRepository` (`UserProfileRecord`, `UserProfileSnapshot`, `ModeloDraft`, `WorkflowState`, `WorkflowResult`, `RegistryModeloObservation`, inventory ledger, assets ledger)
2. TOML manifests (`BucketManifest`, `BucketPointer`)
3. JSON CLI emit envelope (`SchemaEnvelope[T]`)
4. Fichero-BOE bytes (`serialise` / `deserialise`)
5. Google-Sheets worksheet export / pull roundtrip
6. Cross-archive bundle (raw-key mirror path `iter_all_records_raw` → `save_with_raw_key`)
7. Profile cross-store identity chain (bucket directory name → manifest `bucket_id` → encrypted `profile_id` → active-profile pointer `bucket_id`)

Reference rules applied: `.claude/rules/aeat-roundtrip-discipline.md`.

---

## Findings

### F1 — CLEAN: `UserProfileRecord` encrypted SQL boundary

**Pathway:** `UserProfileLifecycleRepository.save` → `SecureObjectRepository` → `UserProfileLifecycleRepository.load`

**Files:** `src/aeat/application/user_profile/_repository.py`, `src/aeat/application/user_profile/test_repository_roundtrip.py`, `src/aeat/application/user_profile/test_repository_anti_tautology.py`

The boundary is covered by three independent test proofs:

- `test_user_profile_value_and_snapshot_survive_encrypted_storage_roundtrip` — uses a real `EphemeralMasterKeyProvider`, real SQLite engine, and `model_a == model_b` strict equality. Fixture populates `schema_version=2`, 5 facts with `valid_from`/`valid_to`, non-default `created_at`/`updated_at`, and a `Decimal` fact. Per-field witnesses pin Decimal fidelity, fact-tuple order, and the `profile_id` / `display_name` separation.
- `test_user_profile_active_with_removed_at_surfaces_at_load` — anti-tautology: stamps `removed_at` on an ACTIVE record on-disk; asserts the `model_validator` lifecycle check trips on load.
- `test_boundary_catches_simulated_field_drop_via_corrupted_payload` — anti-tautology: deletes `display_name` from the encrypted JSON envelope; asserts `ValidationError` or strict inequality on load. Confirms `display_name` is serialised into the payload and is required.

`UserProfileSnapshot` is covered by a separate content-hash anti-tautology proof (`test_user_profile_snapshot_canonical_hash_drift_surfaces_at_load`) that mutates a persisted fact without recomputing `canonical_hash` and confirms the `model_validator` rejects the drift.

**Storage key discipline:** `user_profile_value_object_key(profile_id)` at `src/aeat/application/user_profile/_repository.py:86-96` produces `"user-profile:{profile_id}"` — the UUID, never the display name. The snapshot key is `"user-profile-snapshot:{profile_id}:{snapshot_id}"`. `display_name` is present only as payload, never as a key segment. Confirmed clean.

### F2 — CLEAN: Cross-store profile identity chain

**Pathway:** bucket directory `<root>/buckets/<uuid>/` → `manifest.toml` `bucket_id` → encrypted `UserProfileRecord.profile_id` → `active-profile` pointer `bucket_id`

**Files:** `src/aeat/application/user_profile/_profile_repository.py`, `src/aeat/application/user_profile/test_profile_repository.py`, `src/aeat/application/setup/test_atomic_create_roundtrip.py`

`ProfileRepository.create` at `_profile_repository.py:230` calls `new_profile_id()` (a `uuid4()` string), then uses it as both the bucket directory name (`bucket_paths(self._root, resolved_id)`) and the `BucketManifest.bucket_id` and `BucketPointer.bucket_id`. The encrypted record's `profile_id` is also this same UUID. The `_profile_bucket_scan` module resolves operator labels to UUIDs via the plaintext manifest, never using `display_name` as a directory or key lookup.

Test `test_load_surfaces_manifest_uuid_drift` at `test_profile_repository.py:158` corrupts the manifest `bucket_id` and asserts `ProfileIntegrityError` on `load` — confirming the three-way identity check (directory name, manifest `bucket_id`, record `profile_id`) is enforced. `test_failed_create_leaves_no_half_live_profile` proves the unit-of-work rollback restores the pointer exactly. `test_atomic_create_roundtrip_identity_is_consistent_across_verbs` drives the full `create → list → show → switch → show` cycle via the real CLI confirming UUID stability across verbs.

**Risk note (minor, no action required):** `test_repository_roundtrip.py:116` uses `bucket_id="profile-bucket-A"` (not a UUID) when constructing `UserProfileLifecycleRepository`. This is only the repository-layer test, not the cross-store `ProfileRepository` layer, and the repository itself does not validate UUID format on `bucket_id`. The cross-store tests (`test_profile_repository.py`, `test_atomic_create_roundtrip.py`) exercise the real UUID path end-to-end, so this is a cosmetic inconsistency, not a coverage gap.

### F3 — CLEAN: `BucketManifest` TOML boundary

**Pathway:** `write_manifest` → disk → `read_manifest`

**Files:** `src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py`, `src/aeat/adapters/persistence/storage/bucket/_manifest.py`

Full strict roundtrip coverage including: salt bytes (base64 encoding), `last_unlocked_at=None` (TOML has no null; the absent-key hydration is asserted), `BucketLifecycleStatus.TOMBSTONED` (non-default status, verified to persist and reload). Anti-tautology proof (`test_manifest_status_mutation_surfaces_as_strict_inequality`) rewrites the on-disk `status` string and asserts strict inequality. Legacy-compatibility test confirms a manifest without `status` hydrates as `ACTIVE`. The model uses `ConfigDict(strict=True, frozen=True, extra="forbid")` throughout.

### F4 — CLEAN: `BucketPointer` TOML boundary

**Pathway:** `write_pointer` → disk → `read_pointer`

**Files:** `src/aeat/core/test_bucket_pointer_io.py`, `src/aeat/core/_bucket_pointer.py`

Roundtrip tests cover: write-then-read equality, atomic write (no `.tmp` lingers), overwrite replaces, torn-write leaves previous pointer intact, unknown key rejected by `extra="forbid"`. Anti-tautology is embedded in `test_read_rejects_unknown_key` which confirms the strict model rejects a payload that diverges from the schema. The pointer carries only `bucket_id` (the UUID) and `schema_version` — `display_name` is absent by design.

### F5 — CLEAN: JSON CLI `SchemaEnvelope[T]` boundary

**Pathway:** `emit_json_success` → stdout bytes → `model_validate_json`

**Files:** `src/aeat/core/test_json_envelope_roundtrip.py`

Three tests: full `model_dump_json` / `model_validate_json` cycle with strict equality; `emit_json_success` stdout capture parsed back through `model_validate_json`; extra outer-key rejected via `extra="forbid"`. The fixture uses a typed `_ProvenancePayload` with tuple fields (`operand_refs`, `legal_refs`) that are the most fragile JSON-to-pydantic coercion surface (list → tuple). Confirmed clean.

### F6 — CLEAN: Fichero-BOE bytes boundary

**Pathway:** `serialise` → bytes → `deserialise`

**Files:** `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`

Covers: signed-currency `INLINE_SIGN` negative value (byte-0 `N` marker), DATE fields in both `YYYYMMDD` and `DDMMYYYY` conventions, ALPHANUMERIC non-default filler, CP1252 encoding for non-ASCII bytes. Each test asserts strict Decimal or string equality. No mocks; real `serialise`/`deserialise` against inline-built record specs.

### F7 — CLEAN: Google-Sheets worksheet export / pull boundary

**Pathway:** `build_export_plan` → `OperatorEdit` → `compute_from_pull`

**Files:** `src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py`

Uses real `build_export_plan` against a real registry snapshot (modelo 130, 2025/1T). No mocks. Covers string-vs-Decimal drift, casilla completeness on export, metadata-SHA match refusal.

### F8 — CLEAN: `SecureObjectRepository` archive-bundle boundary

**Pathway:** `save` → `iter_all_records_raw` → wipe → `save_with_raw_key` → `load`

**Files:** `src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py`

Three-row roundtrip asserting HMAC-digest, namespace, classification, schema_version, and plaintext payload bytes all survive the mirror-then-restore cycle. Real `EphemeralMasterKeyProvider` and SQLite.

### F9 — CLEAN: Inventory ledger encrypted SQL boundary

**Pathway:** `InventoryLedgerRepository.save` → `SecureObjectRepository` → `InventoryLedgerRepository.load`

**Files:** `src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py`

Strict roundtrip with non-default `opening_layers` (2 SKUs), non-default `period_movements` (PURCHASE + COGS), explicit VAT decomposition fields. Anti-tautology proof halves `opening_stock` on-disk and asserts the `model_validator` layer-balance check fires. Real `EphemeralMasterKeyProvider` and SQLite throughout.

### F10 — CLEAN: Assets ledger encrypted SQL boundary

**Pathway:** `AssetsLedgerRepository.save` → `load`, `AmortizacionLedgerRepository.save` → `load`

**Files:** `src/aeat/adapters/persistence/profile/test_assets_roundtrip.py`

Non-default fixture populates every optional VAT / allocation / `LibertadAmortizacionElection` axis. Anti-tautology proof halves `cost_basis` on-disk to violate the VAT-decomposition `model_validator`. Real adapters throughout.

### F11 — CLEAN: Fincas register SQL boundary

**Pathway:** `FincaRepository.upsert` → `get`

**Files:** `src/aeat/domain/fincas/test_roundtrip_anti_tautology.py`

Non-default fixture sets every optional field. Anti-tautology proof sets `valor_catastral_construccion > valor_catastral_total` directly on the ORM row and asserts the `model_validator` invariant trips on reload.

### F12 — CLEAN: `WorkflowState` and `WorkflowResult` encrypted SQL boundaries

**Pathway:** `WorkflowStateRepository.save` / `load`, `save_run` / `load_run`

**Files:** `src/aeat/application/workflow/test_state_persistence_roundtrip.py`, `src/aeat/application/workflow/test_run_persistence_roundtrip.py`

`WorkflowState` fixture includes non-default `AuthState`, two profile-bucket pointers, declarations mapping, and a `WorkflowEvent` tuple. `WorkflowResult` fixture uses `final_stage=ABORTED` (requires `aborted_reason`, the model_validator enforces the pairing) and two `WorkflowStep` entries. Real adapters.

### F13 — CLEAN: `ModeloDraft` filing anti-tautology

**Pathway:** `ModeloDraftRepository.save` / `load`

**Files:** `src/aeat/domain/filing/test_roundtrip_anti_tautology.py`

Deletes `snapshot_ref` from the on-disk envelope; asserts either `ValidationError` or `loaded.snapshot_ref is None` (strict inequality against the original). Confirms the typed reference-bearing field is not silently re-defaulted on load.

### F14 — CLEAN: `CalculationObservationRepository` encrypted SQL boundary

**Pathway:** `CalculationObservationRepository.save` / `load`

**Files:** `src/aeat/application/calculations/test_observations_repository_roundtrip.py`

Non-default fixture: two `CasillaObservation` entries with full provenance (`formula_id`, `operand_refs`, `operand_values`, `legal_refs`, `source_refs`). Per-field witnesses on the grounding tuple members. Real adapters.

### F15 — OBSERVATION: `InventoryLedgerRepository` engine resolution relies on ambient env var

**Pathway:** `InventoryLedgerRepository()` → `SecureObjectRepository()` → `get_engine()`

**File:** `src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py:102-104`, `src/aeat/adapters/persistence/profile/inventory.py:105`

`InventoryLedgerRepository.__init__` does not accept an engine injection parameter — it always constructs `SecureObjectRepository()` which resolves its engine from `get_engine()` (which reads `Settings.aeat_database_url`). The roundtrip test sets `AEAT_DATABASE_URL` via `monkeypatch.setenv` and pre-creates the ORM schema against the explicit engine, so the implicit lookup lands on the correct test database. This works but relies on the `monkeypatch`-set env var being active throughout the test. A future refactor that adds per-bucket engine resolution (as `_secure_objects_for_bucket` does for the user-profile repos) would be safer. No current regression, no immediate action required — record for awareness.

### F16 — CLEAN: `SecureBoundRepository` contract suite

**Files:** `src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository_contract.py`, `src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py`

A shared contract harness (`assert_secure_repository_contract`) exercises roundtrip equality and anti-tautology (field drop surfaces) for any `SecureBoundRepository[T]` subclass. The self-test confirms the contract is honest before consumer test files adopt it. Real `EphemeralMasterKeyProvider` and SQLite.

### F17 — CLEAN: Session idle-timeout lifecycle roundtrip

**Files:** `src/aeat/entrypoints/cli/test_session_lifecycle_roundtrip.py`

Drives open-session → write/read → touch → expire → refusal cycle with real adapters. Confirms `SessionExpiredError` fires and names the recovery verb. The test mutates the session's idle deadline in-place (no clock mock needed) to force expiry deterministically.

---

## Recommendations

- **No critical gaps found.** Every boundary enumerated in the roundtrip discipline rule has a dedicated strict roundtrip test asserting `model_a == model_b` through real adapters, and every major boundary has at least one anti-tautology proof test confirming the boundary is not trivially passable with corrupted state.

- **Profile UUID identity chain is coherent.** The bucket directory name, the manifest `bucket_id`, the encrypted record `profile_id`, and the active-profile pointer `bucket_id` all key on the same immutable UUIDv4. `display_name` appears nowhere as a storage key, path segment, or lookup discriminator. The three-way integrity check in `ProfileRepository.load` catches cross-store UUID drift before serving any aggregate.

- **`Envelope[T]` schema_version discipline holds.** The outer transport envelope (`_USER_PROFILE_VALUE_VERSION = 1`) and the inner payload's own `schema_version` field are tracked independently. The test fixture explicitly uses `schema_version=2` on `UserProfileRecord` to detect any version-collapsing regression.

- **F15 (ambient env var coupling in `InventoryLedgerRepository`)** is a cosmetic coupling, not a correctness defect. If the inventory ledger ever needs to support per-bucket resolution (matching the user-profile pattern), the natural fix is to add an optional `objects: SecureObjectRepository | None = None` injection parameter, mirroring `UserProfileLifecycleRepository.__init__`.

- **No shims, no compatibility layers, no deprecated aliases were found** in any persistence boundary — consistent with the eliminate-shims branch objective.

