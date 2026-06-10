---
tags:
  - '#research'
  - '#zero-legacy-purge'
date: '2026-06-10'
related: []
---



# `zero-legacy-purge` research: `zero-legacy purge inventory`

Operator directive recorded 2026-06-10: "we should NOT be supporting any
legacy migration, legacy schema, legacy, retired or old backwards
compatibility. Basically old is to be deleted, and we're working towards
the future with ZERO legacy code support. This is an unreleased pre-beta
project. There's no backwards looking functionality support to carry."

This is the complete deletion inventory of every legacy / backwards-
compatibility surface in `src/aeat/`. Every finding is classified into
exactly one of: DELETE-NOW (pure legacy support for data or behaviour
produced by older versions of this unreleased app), KEEP-NOT-LEGACY
(lexically legacy-looking but genuinely forward-functional — fresh-schema
bootstrap, external-world resilience, or current AEAT regulatory revision
handling), or JUDGMENT (genuinely ambiguous, with the question the owner
must answer). DELETE-NOW items are grouped into coherent deletion slices
so a follow-up campaign can land each slice as one atomic commit.

Discovery method: lexical `rg` sweeps across `src/aeat` and `src/aeat/_data`
(production and tests separately) on the terms
`legacy|backward|backwards|compat|deprecat|retired|migration|migrate|old[_-]|pre[_-]envelope|unmigrat|quarantine|tolerat|fallback`,
seeded with the two operator-confirmed targets, then per-finding source
inspection at HEAD (branch `chore/eliminate-shims`) to read call sites,
tests, and constraint shapes.

Foundational fact anchoring the whole inventory: the SQL substrate's own
package docstring (`adapters/persistence/storage/sql/__init__.py`) declares
"the codebase is forward-only and carries no migration history." Two
subsystems contradict that stated invariant (the deterministic-object-key
migration and the revision-metadata ALTER pass); those are the load-bearing
DELETE-NOW slices below.

## Findings

### Summary counts

- DELETE-NOW slices: 5 (Slice 1 secure-object key migration; Slice 2
  revision-metadata ALTER bootstrap; Slice 3 attachment pre-envelope read
  tolerance; Slice 4 iva-wallet cleartext-key migration bridge; Slice 5
  profile-binding string-coercion legacy path).
- KEEP-NOT-LEGACY: 11 surfaces (with one-line justifications).
- JUDGMENT: 3 items (each with the owner question).

---

## DELETE-NOW slices

### Slice 1 — secure-object randomized-key → HMAC-digest migration

The single largest legacy surface. It exists only to rewrite `object_key`
ciphertexts written by a pre-`HashedLookup` version of this app into
deterministic digests, quarantining duplicate/unmigratable survivors. On a
codebase where every `object_key` is a deterministic `HashedLookup` digest
from birth, this pass scans every row on every repository construction and
finds nothing to do — pure legacy support.

- `adapters/persistence/storage/sql/_secure_object_migration.py` — ENTIRE
  MODULE. `ensure_deterministic_object_keys` (line 35) plus the four private
  helpers `_group_rows_by_target_key` (56), `_quarantine_and_delete` (84),
  `_collapse_to_deterministic_winner` (96), `_lookup_migration_sort_key`
  (121). Supports: rewriting legacy randomized `EncryptedString` object keys
  to HMAC digests. Shape: delete the module.
- `adapters/persistence/storage/sql/secure_objects.py:44` — the import
  `from ._secure_object_migration import ensure_deterministic_object_keys`.
  Shape: delete the import line.
- `adapters/persistence/storage/sql/secure_objects.py:105` — the call site
  `self._ensure_deterministic_object_keys()` inside the repository
  constructor (the runs-on-every-construction bootstrap hook). Shape: delete
  the call line.
- `adapters/persistence/storage/sql/secure_objects.py:122-132` — the wrapper
  method `_ensure_deterministic_object_keys` and its docstring. Shape: delete
  the method.
- `adapters/persistence/storage/sql/tests/test_secure_object_migration.py` —
  ENTIRE FILE (the roundtrip-proof harness, ~313 lines, calls
  `ensure_deterministic_object_keys` at lines 161/204/208/249/269/313).
  Shape: delete the test file with the production path it exercises.

Note on the quarantine TABLE machinery: `ensure_quarantine_table`,
`copy_row_to_quarantine`, `quarantine_timestamp` (in `_secure_object_schema.py`)
and `quarantine_unreadable_rows` (in `_secure_object_integrity.py`) are ALSO
consumed by the live `aeat config repair quarantine` operator verb
(`application/diagnostics.py:1019`, `config_reset.py:143`). That verb is a
forward operator repair surface (move undecryptable rows aside), NOT legacy
migration — see KEEP-NOT-LEGACY. So Slice 1 removes the migration's USE of
quarantine, but the quarantine table helpers stay. Verify after deletion that
`ensure_quarantine_table` / `copy_row_to_quarantine` / `quarantine_timestamp`
retain a live caller (the integrity path); if Slice 1 removal leaves
`copy_row_to_quarantine` with zero callers, fold its removal into this slice.

### Slice 2 — revision-metadata ALTER-from-older-shape bootstrap

The secure-object table's full current column shape is materialised by
`local_table.create(self._engine, checkfirst=True)`
(`secure_objects.py:103`) — that CREATE is fresh-schema bootstrap and is
KEEP. The separate `ensure_table_revision_metadata_columns` ALTER pass exists
only to add the revision-lineage columns to a table that was CREATEd by an
OLDER version before those columns existed. On a fresh-from-birth schema the
CREATE already includes every column, so the ALTER finds nothing missing —
pure legacy support and a direct contradiction of the "no migration history"
package docstring.

- `adapters/persistence/storage/sql/_secure_object_schema.py:33-52` — the
  function `ensure_table_revision_metadata_columns` (ALTER TABLE ADD COLUMN
  loop). Supports: upgrading a pre-existing older `secure_objects` table to
  the current column set. Shape: delete the function.
- `adapters/persistence/storage/sql/_secure_object_schema.py:55-65` — the
  helper `is_duplicate_column_race` exists only to tolerate a concurrent
  ALTER race; with no ALTER it is dead. Shape: delete the function (verify no
  other caller; `secure_objects.py:118` `_is_duplicate_column_race` is its
  only wrapper).
- `adapters/persistence/storage/sql/_secure_object_schema.py:97` — inside
  `ensure_quarantine_table`, the trailing call
  `ensure_table_revision_metadata_columns(engine, "secure_objects_quarantine")`.
  The quarantine CREATE DDL (lines 74-95) already declares every revision
  column inline, so this ALTER call is a no-op on a fresh quarantine table.
  Shape: delete the call line (keep the CREATE).
- `adapters/persistence/storage/sql/secure_objects.py:61` — the import of
  `ensure_table_revision_metadata_columns`. Shape: delete the import.
- `adapters/persistence/storage/sql/secure_objects.py:104` — call site
  `self._ensure_table_revision_metadata_columns("secure_objects")`. Shape:
  delete the call line.
- `adapters/persistence/storage/sql/secure_objects.py:107-116` — wrapper
  method `_ensure_table_revision_metadata_columns`. Shape: delete the method.
- `adapters/persistence/storage/sql/secure_objects.py:118-120` — wrapper
  `_is_duplicate_column_race`. Shape: delete the method.
- `adapters/persistence/storage/sql/tests/test_secure_objects_part1.py:266`
  — `test_secure_object_repository_bootstraps_old_table_revision_columns`
  (builds a deliberately-old table at `db_path = legacy-revision-bootstrap.db`
  and proves the ALTER ran). Delete this test with the path it exercises. The
  sibling `test_secure_object_repository_creates_lineage_columns` (line ~234,
  "Fresh SQL bootstrap creates nullable lineage and integrity columns") tests
  the CREATE path and is KEEP — re-read it to confirm it does not depend on
  the ALTER helper.

Cross-dependency: Slice 1's `_secure_object_migration.py` imports
`ensure_quarantine_table`, `copy_row_to_quarantine`, `quarantine_timestamp`
from `_secure_object_schema`. Land Slice 1 before or with Slice 2 so the
schema-module edits in Slice 2 do not break Slice 1's imports mid-flight; or
land both in one commit since they share the same two files
(`_secure_object_schema.py`, `secure_objects.py`).

### Slice 3 — attachment pre-envelope read tolerance

Operator-confirmed seed. The blob-envelope prefix wraps stored attachment
bytes so `payload_hash` is not the bare content digest. The READ path
tolerates un-prefixed ("pre-envelope") rows written by an older version.
With every blob enveloped from birth, no un-prefixed row can exist, so the
tolerance branch is unreachable legacy support.

- `adapters/persistence/storage/attachment.py:145-149` — `_unwrap_blob_payload`
  body: the `if stored.startswith(PREFIX): return stored[len:]` / `return
  stored` fall-through. Shape: delete the read-tolerance fall-through — a
  post-purge implementation strips the prefix and REFUSES (raises an
  `AttachmentValidationError`) on a missing prefix rather than silently
  returning raw bytes, because a missing prefix can now only mean corruption,
  not legacy data.
- `adapters/persistence/storage/attachment.py:135-136` — the docstring
  sentence "Reads tolerate legacy pre-envelope blobs (no prefix) so existing
  on-disk data stays readable." Shape: delete the sentence (it documents the
  removed tolerance).
- Tests: `rg` `_unwrap_blob_payload|pre-envelope|legacy.*blob` under
  `adapters/persistence/storage/tests/` for the attachment store test that
  asserts pre-envelope tolerance; delete that specific assertion/test and keep
  the round-trip (wrap→unwrap) test. (No test hit surfaced in the production
  sweep; confirm the test surface at deletion time.)

### Slice 4 — iva-wallet cleartext-key migration bridge

Self-documenting migration bridge: a pre-hardening cleartext storage key
(`<NIF>:<year>:<period>`) kept only as a read fallback under the current
hardened (digest-event) key. The function's own docstring says "this fallback
can be removed once persisted records are confirmed migrated ... if count == 0
across all environments, delete this function and the load_decision fallback
call." On an unreleased app there are no pre-hardening records in any
environment, so the precondition holds trivially.

- `application/calculations/_observations_repository.py:164-176` — the
  function `_legacy_iva_wallet_decision_key`. Shape: delete the function.
- `application/calculations/_observations_repository.py:298-299` — in
  `load_decision`, the `if payload is None: payload = super().load(
  _legacy_iva_wallet_decision_key(...))` fallback. Shape: delete the two-line
  fallback branch (keep the primary `super().load(iva_wallet_decision_key(...))`).
- `application/calculations/tests/test_observations_repository.py` — the
  legacy-bridge tests: `test_legacy_decision_key_year_guard` (line 155),
  `test_load_decision_falls_back_to_legacy_cleartext_key` (line 219), and the
  "Site 5" / "legacy decision-key bridge behaviour" blocks (lines 150, 178,
  187, 223-284). Shape: delete these tests with the production bridge they
  defend; keep any test of the current digest-event key path.

### Slice 5 — profile-binding string-coercion legacy path

A `_decimal_value` branch that tolerates string-encoded booleans and numeric
strings "that may arrive from older serialised records or direct callers."
Now that `_profile_fact_index` preserves the typed value (the comment at
lines 257-261 states bool/Decimal/int arrive typed), the string branch only
serves "older serialised records" — legacy support.

- `application/modelo/_profile_binding.py:268-286` — the
  `if isinstance(value, str):` branch (the "Legacy path" comment at line 269
  through the `decimal_from_string(...)` return). Shape: delete the string
  branch so a string-typed profile fact falls through to the existing typed
  `ProfileBindingResolutionError` at line 287.

JUDGMENT caveat for Slice 5: this branch also names "direct callers" (not
only older records). If any current production caller still passes a numeric
STRING for a Decimal-channel binding, deleting the branch turns a tolerated
input into a hard error. Owner must confirm (via `rg` over binding-resolution
call sites and a test run) that no live caller relies on string coercion
before landing. If a live caller exists, fix the caller to pass a typed value
in the same slice rather than retaining the tolerance.

---

## KEEP-NOT-LEGACY

These match the lexical sweep but are forward-functional. Do not delete.

- `adapters/persistence/storage/sql/secure_objects.py:103`
  `local_table.create(checkfirst=True)` — fresh-schema CREATE bootstrap.
  Creating the current schema on first access is not legacy support.
- `adapters/persistence/storage/sql/_secure_object_schema.py:68-96`
  `ensure_quarantine_table` CREATE DDL — backs the forward `aeat config repair
  quarantine` operator verb (move undecryptable rows aside), not migration.
- `application/diagnostics.py:999-1053`,
  `adapters/persistence/storage/sql/_secure_object_integrity.py:19`
  `quarantine_unreadable_rows` / `preview_quarantine_unreadable_secure_objects`
  — a forward operator repair surface for genuinely-undecryptable rows (key
  loss, corruption), not a version-upgrade path.
- `adapters/persistence/storage/sql/secure_objects.py:550-552` the
  `max_supported_version` ceiling that detects rows written by a FUTURE
  schema version — forward-compat (reads a higher version safely), not legacy.
- `core/secure objects + envelopes` `schema_version` FIELD (e.g.
  `secret_store/_secret_store.py:145` "Forward-compatibility marker",
  `Envelope.schema_version`, namespace `schema_version` ClassVars) — the
  version FIELD on records is forward-useful for future evolution; only code
  that BRANCHES on OLD versions is legacy, and none was found (the only
  branch is the forward `> ceiling` refusal above).
- `_data/registry/aeat/modelos/100/.../0004-...trimestrales.toml:7`
  `source_output = "03-legacy"` — an AEAT modelo-123 output-slot identifier
  (registry authority naming the AEAT surface), CURRENT law for filing year
  2020, not our code's legacy.
- `adapters/inbound/justificante/_extract.py:134` "Legacy 2021 modelos
  (iText 2.1.4 producer)" value-then-label parsing — resilience for an
  EXTERNAL AEAT PDF producer variation; external-world variability is not our
  legacy.
- `adapters/inbound/sanitizer/_streams.py:337` PDFDocEncoding "for legacy
  literal strings" — handling an EXTERNAL PDF encoding variant, not our data.
- `core/_modelo.py:31-93` retired `Modelo.M037` / `NON_REGISTRY_MODELOS` —
  the enum carries retired-but-supported AEAT modelo CODES so the registry
  gate can exclude them; this is AEAT regulatory surface modelling (a real
  AEAT code that was suppressed), KEEP as domain data. (JUDGMENT-adjacent —
  see below if the owner wants the retired code removed from the enum.)
- `application/operator_surface/_contract.py:57+` `RETIRED_OPERATOR_SURFACES`
  / `retired_surface_suggestion` — forward redirects that instruct an operator
  who types an old command root toward the current one. This is a deliberate
  CLI UX affordance for THIS unreleased app's own consolidation, not data
  migration. JUDGMENT-adjacent: under a strict zero-legacy reading these
  redirects could be dropped (no released CLI muscle-memory to honour). See
  JUDGMENT item 1.
- `application/workflow/_models.py:214` "The historical `profiles` field has
  retired" — the field is ALREADY gone; this is a doc note about an absent
  field, no actionable code. KEEP (no-op).

---

## JUDGMENT items

### JUDGMENT 1 — retired CLI command-root redirects

`application/operator_surface/_contract.py` `RETIRED_OPERATOR_SURFACES`
(setup/archive/data/filing/invoice/declaration/sanitize/llm/topic/submit/
presentation/preflight/workflow) and `retired_surface_suggestion`, plus the
backing locale keys `cli.operator_surface.retired.*` and the
`RetiredOperatorSurface` model. These forward an operator who types an old
root to the current one. Question for the owner: this is an UNRELEASED app
with no released CLI surface to honour for muscle-memory — do we keep these
instructive redirects as pure UX (a help affordance for consolidations that
happened during development), or does "zero retired support" mean the redirect
table and `RetiredOperatorSurface` model are deleted and an unknown root just
falls through to `aeat --help`? If deleted, the slice spans `_contract.py`,
`_models.py` (`RetiredOperatorSurface`), `operator_surface/__init__.py`
exports, the `cli.operator_surface.retired.*` locale keys (all four locales,
via `aeat.locales remove`), and the tests asserting the redirects.

### JUDGMENT 2 — `BucketKeySchedule.LEGACY_MASTER_KEY`

`adapters/persistence/storage/bucket/_manifest.py:88` declares
`LEGACY_MASTER_KEY = "legacy-master-key"` and line 108 makes it the DEFAULT
`key_schedule` for `BucketManifest`. The data path at
`master_key/_master_key_bucket_dek.py:116-121` routes `LEGACY_MASTER_KEY`
buckets through "the legacy master-key data path" (KEK == DEK, no separated
DEK document), distinct from the current `BUCKET_DEK_V1`. Question for the
owner: is `LEGACY_MASTER_KEY` a real CURRENT mode some buckets are minted in
(in which case it is a live key schedule, mis-named, and stays), or is every
freshly-created bucket minted as `BUCKET_DEK_V1` so `LEGACY_MASTER_KEY` only
describes pre-DEK-separation buckets that cannot exist on a fresh install? If
the latter, DELETE-NOW: the enum member, the default (change default to
`BUCKET_DEK_V1`), the `if key_schedule is BucketKeySchedule.LEGACY_MASTER_KEY`
branch, the `_master_key_bucket_dek.py:50-64` "Legacy manifest without status"
direct-parse fallback, and the tests at
`master_key/tests/test_master_key.py:108`,
`test_adverse_sessions.py:193`, `bucket_maintenance/tests/test_manifest_digest.py:48`.
Owner must confirm the bucket-creation path's key_schedule before this is
actionable — this is a key-management boundary; a wrong deletion strands
encrypted data.

### JUDGMENT 3 — `core/_modelo.py` retired AEAT modelo codes in the enum

`core/_modelo.py` carries `Modelo.M037` (censo simplificada) and the
`NON_REGISTRY_MODELOS` set explicitly so the registry-coverage gate can
exclude "retired-but-supported codes." Classified KEEP above because retired
AEAT CODES are domain data (the code existed; AEAT suppressed it). Question
for the owner: does "zero retired support" extend to removing AEAT codes that
AEAT itself retired (M037), or is the AEAT modelo enum a historical-faithful
catalogue that legitimately carries codes no longer fileable? If the former,
this becomes a small DELETE-NOW (remove `M037` from the enum and
`NON_REGISTRY_MODELOS`, plus the gate that special-cases it). Default reading:
KEEP — an AEAT code AEAT retired is regulatory history, not our code's legacy.

---

## Deletion-slice landing order

1. Slice 4 (iva-wallet bridge) and Slice 3 (attachment pre-envelope) are
   independent, low-risk, single-file production changes — land first.
2. Slice 5 (profile-binding) after the owner confirms no live string caller
   (its JUDGMENT caveat).
3. Slices 1 + 2 (secure-object key migration + revision-metadata ALTER) share
   `_secure_object_schema.py` and `secure_objects.py`; land them together (or
   1 then 2) as one or two atomic commits, and after landing update the
   `sql/__init__.py` docstring's "forward-only ... no migration history" claim
   so it becomes literally true.
4. JUDGMENT 1/2/3 only after explicit owner answers; JUDGMENT 2 is a
   key-management boundary and must not be deleted on inference.
