---
step_id: S04
tags:
  - '#exec'
  - '#quality-hardening-campaign'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-09-quality-hardening-campaign-audit]]'
---

# `quality-hardening-campaign` S04: QHC-003 dedicated slice, `ensure_deterministic_object_keys`

## Outcome

Cleared the worst remaining cognitive hotspot —
`adapters/persistence/storage/sql/_secure_object_migration.py::ensure_deterministic_object_keys`
(cognitive **26 -> 9**) — behind a byte-exact roundtrip-proof harness built and
committed first. This function owns secure-storage `object_key` HMAC derivation:
a silent drift would strand every existing encrypted record, which is why slice 2
(QHC-018) honestly skipped it. The harness-first order proved byte-identity
across the refactor. Live cognitive over-threshold inventory dropped **13 -> 12**.

## Harness first (commit `2213be104`)

New durable test file
`src/aeat/adapters/persistence/storage/sql/tests/test_secure_object_migration.py`
(5 tests), real `EphemeralMasterKeyProvider` + real SQLite engine, no mocks:

- **`test_migration_rewrites_legacy_keys_to_byte_exact_hashed_lookup_digests`** —
  seeds three namespaces of legacy `EncryptedString` keys (two unique, one with
  a duplicate pair), captures the exact `HashedLookup.compute(natural_key)` bytes
  under the current implementation, runs the migration, and asserts the surviving
  `object_key` bytes equal those captured 32-byte digests across all three
  namespaces (including the duplicate-collapse survivor), plus the loser landing
  in quarantine with its original >32-byte randomized ciphertext.
- **`test_migration_is_idempotent_on_already_deterministic_keys`** — second pass
  leaves byte-identical keys and no new quarantine rows (the bootstrap runs on
  every repository construction).
- **`test_migration_quarantines_unmigratable_legacy_key`** — a non-decryptable,
  non-32-byte key is quarantined verbatim and deleted.
- **`test_migration_returns_early_on_empty_table`** — empty table is a no-op; no
  quarantine table is created.
- **`test_harness_catches_object_key_derivation_drift`** (anti-tautology) —
  captures the digest of a *mutated* natural key, runs the migration that writes
  the *correct* digest, and asserts the byte-exact equality the real harness
  relies on would fail (`surviving_key != wrong_target`), proving the harness
  pins the exact HMAC computation rather than passing vacuously.

The harness mirrors the real repository bootstrap ordering: it adds the
revision-metadata columns (`ensure_table_revision_metadata_columns`) before
running the migration, because the migration `SELECT`s those columns. The
harness passed against the **unmodified** function before the refactor commit.

**Anti-tautology proof reinforced out-of-band:** a scratch probe (run, recorded,
then removed) patched the migration's `HashedLookup.compute` to flip one digest
byte; the byte-exact check failed as required
(`captured=5127bb65... stored=5027bb65...`), confirming the harness would catch a
real one-byte derivation drift.

## Refactor (commit `f42ad2622`)

Three behaviour-preserving helpers extracted, each a faithful lift of an existing
block:

- `_group_rows_by_target_key(rows)` — the classification loop (decryptable key ->
  `HashedLookup` digest; 32-byte undecryptable -> in-place digest; else
  unmigratable). Cognitive 5.
- `_quarantine_and_delete(session, raw, raw_key, *, quarantined_at)` — the
  repeated copy-to-quarantine + delete-active pair. Cognitive 0.
- `_collapse_to_deterministic_winner(session, target_key, entries, *, quarantined_at)`
  — the per-group winner/loser/rewrite block; rewrites the surviving key only
  when it is not already `target_key`. Cognitive 4.

The fetch SQL was hoisted to a module constant `_SELECT_SECURE_OBJECT_ROWS`
(verbatim) and a `_RowKeyPair` type alias replaces the repeated
`tuple[RowMapping, bytes]` signature. The orchestrator retains the exact control
flow: fetch -> early-return-if-empty -> group -> conditionally ensure quarantine
table -> quarantine unmigratable (with the same `logger.debug` line) -> collapse
each group. No SQL string, no sort key, no ordering, no event/log line changed.

## Verification gate

- Harness: 5 passed against the unmodified function (pre-refactor) and again
  after every extraction step.
- Full SQL storage adapter suite (`.../sql/tests/`): **72 passed** — the indirect
  migration coverage in `test_secure_objects_part1.py`
  (`test_repository_migrates_legacy_encrypted_string_object_key`,
  `test_repository_migrates_duplicate_legacy_keys_to_latest_and_quarantines_loser`)
  still green.
- `uv run --no-sync ruff check` clean on the module (one import-order fix:
  `collections.abc.Sequence` added for the widened helper parameter).
- `uv run --no-sync pyright` clean (one fix: `_group_rows_by_target_key` accepts
  `Sequence[RowMapping]`, matching `.mappings().all()`'s return type rather than
  `list`).
- `uv run --no-sync complexipy` on the module: `ensure_deterministic_object_keys`
  **26 -> 9**; helpers 5 / 4 / 2 / 0 — all under the ~12 helper budget; none over
  threshold 20.
- Campaign-wide `python -m dev.audit.complexity`: cognitive > 20 count **13 -> 12**.

## Commits

- `2213be104` test(qhc-003): roundtrip proof harness for ensure_deterministic_object_keys
- `f42ad2622` refactor(qhc-003): extract helpers from ensure_deterministic_object_keys (cognitive 26->9)
