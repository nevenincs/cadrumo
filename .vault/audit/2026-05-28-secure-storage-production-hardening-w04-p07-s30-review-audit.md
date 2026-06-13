---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` Code Review

W04.P07.S30-001 | HIGH | CAS check is not atomic and can lose concurrent revision-aware writes
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:1080` reads the target row id, `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1087` reads the current revision metadata, and `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1098` compares `expected_revision_id` against that earlier read. The later write at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1118` updates by `id` only, with no `revision_id = expected_revision_id` predicate and no affected-row check. Two writers that both read the same revision can both pass the Python comparison; the later commit overwrites the earlier committed payload and records lineage as if it followed the stale revision. That violates the ADR contract that upserts which would lose lineage must fail through compare-and-swap, and it means W04.P07.S30 is not complete. This blocks commit.

W04.P07.S30-002 | LOW | Revision conflict error renders as a generic repository failure
`src/aeat/core/errors/registry/_adapters.py:482` declares a distinct `SecureObjectRevisionConflictError` code, but its message key is `errors.fail.fail_storage_repository`. `_revision_conflict` in `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1207` also passes and stores the same generic key. The typed exception and structured context are useful, and locale audit passes, but operator-facing rendering says only that a repository operation failed rather than that a stale secure-object revision was refused. This weakens the "explicit conflict" surface called out by W04.P07.S30 and the revision-lineage ADR. This does not block commit by itself.

## Verification

- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -k "revision or cas"` passed: 12 passed, 18 deselected.
- `uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

## Follow-up review

W04.P07.S30-001 | RESOLVED | CAS update now carries the expected revision predicate
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:1118` builds the update statement for the current row, `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1120` adds `revision_id == expected_revision_id` for compare-and-swap writes, and `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1132` checks the affected row count before revision metadata is written. A zero-row update re-queries the current revision and raises `SecureObjectRevisionConflictError`, so the prior read-then-unconditional-update defect is closed.

W04.P07.S30-002 | RESOLVED | Revision conflicts now have a dedicated locale-backed message key
`src/aeat/core/errors/registry/_adapters.py:486` now points `SecureObjectRevisionConflictError` at `errors.fail.fail_storage_secure_object_revision_conflict`, and `_revision_conflict` in `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1221` uses the same key for direct rendering and `translated_message`. The key exists in all audited locales.

W04.P07.S30-003 | LOW | Atomic rowcount conflict branch is not directly covered by a real concurrent-write test
The committed tests cover successful expected-revision writes, stale expected-revision refusal, batch rollback, and raw-key expected-revision writes in `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py:890`, `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py:938`, `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py:989`, and `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py:1042`. The stale test fails at the pre-update comparison in `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1098`; it does not exercise the new `rowcount != 1` branch at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1132`, which is the branch that protects against stale-after-read concurrent writers. This is a residual regression-test gap, not an implementation correctness finding, and it does not block commit.

## Follow-up verification

- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed: 30 passed.
- `uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/core/errors/registry/_adapters.py` passed.

## Final follow-up review

W04.P07.S30-003 | RESOLVED | Existing-row stale writes now exercise the rowcount conflict branch
The stale expected-revision path for an existing row now reaches the SQL compare-and-swap branch: `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1113` adds the expected revision predicate and `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1126` raises on zero affected rows. The previous test-coverage concern for the existing-row stale branch is closed.

W04.P07.S30-004 | HIGH | Expected-revision writes create missing rows instead of conflicting
Removing the pre-update mismatch check also changed the absent-row path. When no row exists, `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1099` inserts a new `SecureObjectRow` before any expected-revision comparison, and `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1136` then writes revision metadata with `conflict_policy="compare-and-swap"` at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1148`. A caller that supplies `expected_revision_id` for a missing object therefore succeeds with `previous_revision_id=None` instead of receiving `SecureObjectRevisionConflictError`. This violates the compare-and-swap contract for revision-aware writes: an expected revision names a current row state, and absence is not that state. It also permits stale-after-delete or stale-wrong-key writers to recreate an object without lineage. This blocks commit.

## Final follow-up verification

- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed: 30 passed.
- `uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/core/errors/registry/_adapters.py` passed.

## Absent-row CAS follow-up review

W04.P07.S30-004 | RESOLVED | Expected-revision writes now conflict when the row is missing
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:1098` now raises `SecureObjectRevisionConflictError` when `expected_revision_id` is supplied and no row exists, before the insert branch at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:1105`. `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py:989` covers the behavior with a real repository write attempt and asserts that `secure_objects` remains empty. The prior stale-after-delete/wrong-key recreation defect is closed.

## Absent-row CAS follow-up verification

- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed: 31 passed.
- `uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/core/errors/registry/_adapters.py` passed.
