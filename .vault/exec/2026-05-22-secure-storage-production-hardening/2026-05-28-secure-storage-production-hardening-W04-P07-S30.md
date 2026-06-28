---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S30'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` `W04.P07.S30`

Added compare-and-swap conflict handling for revision-aware secure-object writes.

- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Reviewed: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P07-S30-review.md`

## Description

Secure-object saves now accept `expected_revision_id` on natural-key writes, raw-key writes, and `SecureObjectWrite` batch items. When an expected revision is supplied, the SQL update includes `revision_id == expected_revision_id` and refuses zero-row updates with `SecureObjectRevisionConflictError`.

Missing rows with an expected revision also fail closed instead of creating a new object. Successful expected-revision writes record `compare-and-swap` as the persisted conflict policy; compatibility writes without an expectation retain `last-write-wins`.

## Tests

Validation covered successful CAS updates, stale expected-revision refusal without overwrite, missing-row refusal without creation, transaction rollback for a conflicted batch, and raw-key CAS updates.

- `uv run ruff check src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/core/errors/registry/_adapters.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `uv run python -m aeat.locales audit`
- `git diff --check -- src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
