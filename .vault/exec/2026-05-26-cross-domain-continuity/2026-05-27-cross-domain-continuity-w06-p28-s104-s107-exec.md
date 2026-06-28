---
step_id: S104
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W06.P28.S104-S107 — bundled-export schema v2 + serializer + deserializer + roundtrip test

## Outcome

Four steps delivered in one commit (`af81954a6`): S104 schema extension,
S105 serializer, S106 deserializer + CLI wiring, S107 real-CLI roundtrip test
with anti-tautology proof and D5 collision-guard refusal tests.

All four roundtrip tests pass (4/4). Broader CLI test suite: 53/54 (one
pre-existing auth blocker unrelated to this work). Plan steps S104-S107 closed
via `vault plan step check`.

## S104 — UserProfilePortableExport schema v2

Extended `UserProfilePortableExport` in
`src/aeat/domain/user_profile/_values.py` with `bundle_schema_version=2`
(default) and four financial-history tuple fields:

- `work_units: tuple[WorkUnit, ...]`
- `ledger_transactions: tuple[Transaction, ...]`
- `calculation_revisions: tuple[CalculationRevision, ...]`
- `filing_records: tuple[ModeloRecord, ...]`

All four default to empty tuples so v1 facts-only bundles remain importable
(ADR D3). Cross-domain imports added at the top of `_values.py`; no circular
dependency (modelos and transactions are domain siblings with no upward dep on
user_profile).

## S105 — Bundled serializer

New module `src/aeat/application/user_profile/_bundle.py`.
`serialize_profile_bundle(*, bucket_id)` reads all four catalogue repositories
for the active bucket and assembles a v2 `UserProfilePortableExport`. The
caller is responsible for an active `BucketSession` (ADR D2: decrypted
domain-model payloads only, no encrypted blobs).

## S106 — Bundled deserializer + CLI import wiring

`deserialize_profile_bundle(bundle, *, target_bucket_id)` in the same module:

- Validates `bundle_schema_version` against `SUPPORTED_BUNDLE_SCHEMA_VERSIONS
  = frozenset({1, 2})` before any writes (ADR D4); raises
  `UnsupportedBundleSchemaVersionError` on mismatch.
- v1 bundles return immediately (no financial-history objects to write).
- v2 bundles import all four categories via typed catalogue repository save
  paths (ADR D3: pydantic models flow directly, no `dict[str, Any]`
  intermediate).

`config_profile_import` in `src/aeat/entrypoints/cli/_config/__init__.py`
updated with:

- D5 tier-1: `read_profile_bucket_by_id(bundle_profile_id)` UUID collision guard.
- D5 tier-2: `read_profile_bucket(target_label)` label-taken-by-different-UUID guard.
- `_atomic_create_profile` gains optional `profile_id` parameter to preserve
  the bundle's UUID identity (ADR D5).
- `with profile_storage_session(target_id)` context wrapping
  `deserialize_profile_bundle` so the session is active for all four repo writes.

## S107 — Real-CLI roundtrip test + anti-tautology proof

`src/aeat/entrypoints/cli/test_profile_export_roundtrip.py` (NEW, 310 lines):

- `test_v2_bundle_export_import_roundtrip` — seeds one profile with facts, one
  ledger transaction, one work unit, one calculation revision (with
  `CasillaObservation` carrying non-empty `legal_refs`), and one filing record.
  Exports via `config profile export`. Re-imports to a fresh storage root via
  `config profile import`. Asserts strict pydantic equality across all four
  financial-history categories and D5 `profile_id` preservation.
- `test_v2_bundle_anti_tautology_legal_refs_mutation` — mutates `legal_refs` on
  a casilla observation inside the exported JSON, reloads the bundle, and asserts
  `mutated_revision.observations != original_bundle_revision.observations`.
  Proves the equality test in the roundtrip is not tautological.
- `test_import_refuses_uuid_collision` — re-importing the same bundle file
  raises `CliRefusedBoundaryError` (D5 tier-1).
- `test_import_label_collision_different_uuid_is_refused` — importing a bundle
  whose label is already taken by a different UUID raises
  `CliRefusedBoundaryError` (D5 tier-2).

## Files changed

- `src/aeat/domain/user_profile/_values.py` (MODIFIED — S104: +23 lines)
- `src/aeat/application/user_profile/_bundle.py` (NEW — S105+S106: 190 lines)
- `src/aeat/entrypoints/cli/_config/__init__.py` (MODIFIED — S106 CLI wiring: +79 net lines)
- `src/aeat/entrypoints/cli/test_profile_export_roundtrip.py` (NEW — S107: 310 lines)
