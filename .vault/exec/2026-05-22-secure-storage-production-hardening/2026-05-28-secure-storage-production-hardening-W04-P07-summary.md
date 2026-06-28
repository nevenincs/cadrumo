---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` `W04.P07` summary

Completed the secure-object revision metadata phase.

- Modified: `src/aeat/adapters/persistence/storage/sql/_orm.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Created: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P07-S28-S31-review.md`
- Created: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P07-S29-review.md`
- Created: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P07-S30-review.md`
- Created: step records for `W04.P07.S28`, `W04.P07.S29`, `W04.P07.S30`, and `W04.P07.S31`

## Description

`W04.P07` now gives `secure_objects` storage-level revision lineage. The ORM carries nullable revision and integrity metadata columns. Repository construction bootstraps older tables before ORM reads, and quarantine archives preserve the same metadata so repair does not discard lineage.

Save paths now write revision ids, previous revision references or previous payload hashes, plaintext and ciphertext hashes, write timestamps, write provenance, source event ids, and the current conflict policy. Revision-aware writes can supply an expected revision and are enforced through a SQL compare-and-swap predicate; stale or missing current rows raise `SecureObjectRevisionConflictError` without overwriting or creating data.

## Tests

Focused validation covered fresh schema creation, old-table bootstrap, quarantine metadata preservation, natural-key saves, raw-key saves, batched saves, legacy-row overwrites, stale expected-revision refusal, missing-row expected-revision refusal, and batch rollback on conflict.

- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `uv run ruff check src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/core/errors/registry/_adapters.py src/aeat/adapters/persistence/storage/sql/_orm.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
