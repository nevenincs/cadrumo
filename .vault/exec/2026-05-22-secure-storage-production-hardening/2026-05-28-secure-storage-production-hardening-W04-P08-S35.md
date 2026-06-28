---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S35'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` `W04.P08.S35`

Added higher-level real-behavior coverage for fail-closed secure-object listing and explicit partial diagnostics.

- Modified: `src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py`
- Reviewed: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P08-S35-review.md`

## Description

The secure-bound repository tests now corrupt an actual encrypted SQL secure-object row and assert that `SecureBoundRepository.iter_ids()` raises `SecureObjectUnreadableError` instead of yielding a readable subset. A companion test exercises the explicit underlying `iter_records_with_failures` path and verifies it returns one readable record plus one unreadable diagnostic outcome for repair-style callers.

This complements the lower-level SQL repository tests by proving higher-level storage consumers inherit the fail-closed default listing contract without losing explicit partial-read diagnostics.

## Tests

Validation covered the storage-envelope test module against real SQLite-backed encrypted storage.

- `uv run ruff check src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py`
- `uv run pytest src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py -q`
- `git diff --check -- src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md .vault/audit/2026-05-28-secure-storage-production-hardening-W04-P08-S35-review.md .vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-28-secure-storage-production-hardening-W04-P08-S35.md`
