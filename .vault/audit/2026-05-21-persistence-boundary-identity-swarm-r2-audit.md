---
tags:
  - '#audit'
  - '#codebase-health'
date: '2026-05-21'
modified: '2026-05-21'
related: []
---



# `codebase-health` audit: `persistence-boundary-identity-swarm-audit-r2`

## Scope


## Findings


## Recommendations



## Context

## Scope

Persistence-boundary identity audit after ~136 commits landed in the 6 hours preceding 2026-05-21. Campaigns covered include: state-architecture / profile-state-aggregate (BucketManifest gained a required `status` lifecycle field), schema-hardening (PERS-1 through PERS-9), cross-campaign hardening, and taxpayer-axis / wizard additions. The six boundaries examined:

1. **Encrypted SQL via `SecureObjectRepository`** — column-level AES-256-GCM, `HMAC-SHA256` keyed object-key hashing.
2. **TOML manifests (`BucketManifest`)** — plaintext per-bucket manifest including the new required `status` field.
3. **JSON envelopes (`Envelope[T]`)** — typed schema-versioned encrypted wrapper for every domain record.
4. **Fichero-BOE bytes** — CP1252 wire format for AEAT export submission.
5. **Worksheet export/pull** — Google Sheets calc-sheets boundary (export plan → pull result → compute).
6. **CLI emit-over-wire (`SchemaEnvelope`)** — `--json` output envelope consumed by external tooling.

Method: grep / glob / read only. No production code was modified. Reference rule: `.claude/rules/aeat-roundtrip-discipline.md`.

---

## Findings

### F1 — CLEAN: BucketManifest.status roundtrip and anti-tautology fully covered

**Pathway:** TOML manifest boundary — `BucketManifest.status` (new required field, commit `fb1dcad4c`)
**File:line:** `src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py:30–161`

The roundtrip test (`test_bucket_manifest_round_trips_strictly_via_toml`) builds a `_populated_manifest` fixture with `status=BucketLifecycleStatus.TOMBSTONED` — a non-default value — writes via `write_manifest`, reads via `read_manifest`, and asserts strict pydantic equality plus an explicit per-field witness at line 94: `assert loaded.status is BucketLifecycleStatus.TOMBSTONED`. A second test covers the `last_unlocked_at=None` TOML-null code path. The anti-tautology proof (`test_manifest_status_mutation_surfaces_as_strict_inequality`) rewrites the on-disk TOML from `"tombstoned"` to `"active"` and asserts the reloaded manifest is strictly unequal to the original. `BucketManifest.status` has no default — the validator rejects any manifest missing the field at parse time (fail-closed). **No gap.**

### F2 — CLEAN: SecureObjectRepository roundtrip, anti-tautology, and key-rotation isolation fully covered

**Pathway:** Encrypted SQL — `SecureObjectRepository.save` / `load` / `list_records` / `peek_metadata`
**File:line:** `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py:40–609`

Six test functions covering: payload encryption verified at SQLite byte level, full-record roundtrip with non-default `schema_version=3` and `written_at`, schema-version mutation anti-tautology (mutate `schema_version` in SQLite → `EnvelopeVersionError` on load), key-rotation isolation (`list_records` skips unreadable rows sealed under a rotated key with a structured warning), `iter_records_with_failures` typed outcome per row, `peek_metadata` consistency plus on-disk drift anti-tautology, and upsert convergence (two writers of the same key → one row). All tests use a real `EphemeralMasterKeyProvider`, real SQLite engine, no mocks. **No gap.**

### F3 — CLEAN: UserProfileRecord / UserProfileSnapshot roundtrip well-covered but roundtrip test has non-isolated storage path

**Pathway:** Encrypted SQL — `UserProfileLifecycleRepository` / `UserProfileSnapshotRepository`
**File:line:** `src/aeat/application/user_profile/test_repository_roundtrip.py:99–330`

The two anti-tautology proofs (lines 156 and 242) correctly inject `objects=objects` so both the corrupted-write and the reload use the same in-`tmp_path` engine. **However**, the primary roundtrip test at line 99 creates `UserProfileLifecycleRepository(bucket_id=bucket_id)` at **line 117 without injecting `objects=`**. `_secure_objects_for_bucket` is then called, which calls `load_settings().aeat_local_storage_root` and constructs the engine at `<PROJECT_ROOT>/var/storage/buckets/profile-bucket-A/db/aeat.db` — NOT inside `tmp_path`. The test is internally consistent (save and load share the same computed path), so the roundtrip itself is not tautological, but it writes persisted data to a shared on-disk location between test runs. If a prior run left a row at that path encrypted under a different `EphemeralMasterKeyProvider` key, the load would fail with a `DecryptionError`, making the test environment-sensitive. The `monkeypatch.setenv("AEAT_DATABASE_URL", ...)` at line 108 has no effect on `_secure_objects_for_bucket` because that helper ignores `AEAT_DATABASE_URL` and constructs its own path from `aeat_local_storage_root`.

**Data at risk:** None — the roundtrip is behaviorally correct and `var/` is gitignored. The risk is inter-run pollution and false negatives on a dirty workspace.

**Remediation:** Inject `objects=SecureObjectRepository(engine=engine)` at line 117 and line 118, matching the pattern used in the anti-tautology tests in the same file (lines 199 and 285). Alternatively, add `monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path))` and call `dispose_engine()` in teardown so `_secure_objects_for_bucket` also resolves to `tmp_path`.

### F4 — CLEAN: JSON Envelope (SchemaEnvelope) CLI boundary roundtrip covered

**Pathway:** CLI `--json` emit-over-wire — `SchemaEnvelope[T]` / `emit_json_success`
**File:line:** `src/aeat/core/test_json_envelope_roundtrip.py:1–146`

Three tests: full pydantic dump/validate cycle asserts `roundtripped == original` with explicit `schema_version`, `operand_refs` (tuple), `legal_refs`, and `warnings` witnesses; a stdout-stream test re-parses captured bytes via `model_validate_json`; and an `extra="forbid"` rejection test. Uses non-default `formula_id`, multi-member `operand_refs`, and `warnings` list. **No gap.**

### F5 — CLEAN: Fichero-BOE bytes boundary fully covered with anti-tautology

**Pathway:** AEAT wire format — `serialise` / `deserialise`
**File:line:** `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py:1–339`

Eight tests covering: `INLINE_SIGN` negative value (`N` byte-0 marker), positive value (space marker), `YYYYMMDD` and `DDMMYYYY` date formats, `pad_char='0'` alphanumeric, blank CURRENCY rejection, blank INLINE_SIGN magnitude rejection, CP1252 `ñ` single-byte encoding, and a RESERVED-literal corruption anti-tautology (mutates `AEAT` → `XXXX` on disk, expects `ExportFormatError`). All use inline `record_field` / `record_spec` construction — no reused registry data. **No gap.**

### F6 — CLEAN: Google Sheets export/pull boundary covered with structural count guard

**Pathway:** Worksheet export/pull — `build_export_plan` → `PullResult` → `compute_from_pull`
**File:line:** `src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py:82–196`

Two tests: `test_workbook_input_values_survive_export_pull_compute_loop` supplies real `Decimal("10000.50")` / `Decimal("2000.25")` inputs, drains plan back to pull shape, and asserts computed casilla 03 = ingresos − gastos with exact Decimal equality; `test_workbook_input_count_matches_pulled_edit_count` guards casilla-count drift between export and pull shapes using a real modelo-130/2025-1T registry snapshot. Uses `_registry_sha` for metadata binding. No mocks. **No gap.**

### F7 — CLEAN: BucketManifest.status fail-closed on missing field at load

**Pathway:** TOML manifest `read_manifest` — missing `status` field
**File:line:** `src/aeat/adapters/persistence/storage/bucket/_manifest.py:118` (no default on `status` field)

`BucketManifest.status` has no `default=` or `default_factory=` — the field is a bare `BucketLifecycleStatus` with no fallback. A manifest TOML file missing the `status` key causes pydantic's strict validation to raise `ValidationError` at the `read_manifest` call site, not silently re-default to `ACTIVE`. This is the fail-closed posture required by the disaster ADR. The `repair_active_profile_manifest_status` function in `_profile_health.py` provides the out-of-band backfill path for legacy manifests that predate the required field. **No gap.**

### F8 — CLEAN: UserProfileRecord / UserProfileSnapshot anti-tautology proofs inject `objects=` correctly

**Pathway:** Anti-tautology proofs — `test_user_profile_active_with_removed_at_surfaces_at_load` and `test_user_profile_snapshot_canonical_hash_drift_surfaces_at_load`
**File:line:** `src/aeat/application/user_profile/test_repository_roundtrip.py:156–330`

Both proofs create `UserProfileLifecycleRepository(bucket_id=bucket_id, objects=objects)` with an explicit `objects=` injection, ensuring the surgical payload mutation and the subsequent load operate on the same `tmp_path` engine. The lifecycle invariant proof confirms `removed_at` + `ACTIVE` status trips on load. The snapshot canonical-hash proof confirms a mutated fact with a stale hash trips on load. **No gap in the anti-tautology tests themselves.**

### F9 — CLEAN: Taxpayer-axis facts survive encrypted SQL roundtrip

**Pathway:** Encrypted SQL — taxpayer-axis `UserProfileFact` rows
**File:line:** `src/aeat/application/user_profile/test_taxpayer_axes_persistence_roundtrip.py:122–245`

The fixture sets every taxpayer-axis fact to a NON-DEFAULT value: `entity_type=legal_entity`, `legal_entity_form=cooperativa`, `irpf_income_categories=trabajo,capital_inmobiliario,pension` (multi-member, non-sorted), `irpf.estimation_regime=directa_simplificada`, `iva.regime=REAGP` (W01-added member), `iva.sii_enrolled=True`, `iva.redeme_enrolled=True`. The test uses real `EphemeralMasterKeyProvider` and real `SecureObjectRepository`. A forward-compatibility test confirms a v1-shaped record (no taxpayer-axis facts) still loads cleanly under v2 without inventing axis values. **No gap.**

### F10 — CLEAN: ProfileRepository dual-write (manifest + encrypted record) lifecycle maintained

**Pathway:** Profile UUID identity as the sole storage key
**File:line:** `src/aeat/application/user_profile/_repository.py:86–113` (key construction)

`user_profile_value_object_key` and `user_profile_snapshot_object_key` both use the immutable `profile_id` (UUIDv4) as the primary key segment. The `display_name` is stored as a payload field inside the encrypted record — it is never used as a lookup key. The roundtrip in `test_repository_roundtrip.py:127–129` explicitly asserts `loaded_record.profile_id != loaded_record.display_name` and pins both survive as independent fields. **No gap.**

### F11 — CLEAN: Envelope schema_version discipline enforced at load boundaries

**Pathway:** `Envelope[T]` schema_version gate — `UserProfileLifecycleRepository.load`, `UserProfileSnapshotRepository.load`, `WorkflowStateRepository`
**File:line:** `src/aeat/application/user_profile/_repository.py:153–157`; `test_secure_objects.py:133–174`

Every `load` path checks `envelope.schema_version > _USER_PROFILE_VALUE_VERSION` and raises `EnvelopeVersionError`. The `SecureObjectRepository` similarly checks `schema_version > max_supported_version` and raises the same error. The anti-tautology proof at `test_secure_objects.py:133` mutates the on-disk `schema_version` to 4 via raw SQLite and confirms `EnvelopeVersionError` fires. **No gap.**

---

## Recommendations

1. **Fix test isolation defect (F3, medium priority):** In `test_user_profile_value_and_snapshot_survive_encrypted_storage_roundtrip` at `test_repository_roundtrip.py:117–118`, replace the no-injection construction of `UserProfileLifecycleRepository` and `UserProfileSnapshotRepository` with `objects=SecureObjectRepository(engine=engine)` injected explicitly. This aligns the roundtrip test with the anti-tautology tests in the same file and eliminates the on-disk persistence at `var/storage/buckets/profile-bucket-A/`. The test's correctness is not in doubt — it is internally consistent — but runs on a shared path that can be poisoned by a prior test session's stale encrypted rows.

2. **BucketManifest.status migration path exercised by tests:** `repair_active_profile_manifest_status` in `_profile_health.py` covers the legacy-manifest backfill path (manifest missing `status` → reads encrypted record → writes backfilled manifest). `test_profile_health.py:155–192` exercises this path end-to-end with a real encrypted record and verifies `status=ACTIVE` is recovered. This path is clean.

3. **All other boundaries are clean.** The recent PERS-1 through PERS-9 hardening campaign has driven all six primary boundaries to have: (a) a strict roundtrip test asserting `model_a == model_b` through a real adapter cycle, (b) an anti-tautology proof test that mutates the on-disk payload and asserts detection, and (c) no save-drops-field / load-re-defaults-field gaps at the fixture level (all fixtures use non-default values on defaultable fields).
