---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S33'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` `W04.P08.S33`

Streamed explicit secure-object diagnostic listing in bounded batches.

- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Reviewed: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P08-S33-review.md`

## Description

`iter_records_with_failures` now accepts a positive `batch_size` and applies SQLAlchemy `stream_results` plus `yield_per` options to the raw secure-object row scan. The iterator processes rows inside the session instead of materialising the full result set before yielding typed outcomes.

The S32 fail-closed default listing contract is unchanged. `list_records` still buffers outcomes from `iter_records_with_failures` and raises `SecureObjectUnreadableError` before yielding a readable subset when any row is unreadable.

## Tests

Validation covered real SQLite listing with a bounded `batch_size`, execution-option instrumentation through SQLAlchemy events, rejection of invalid batch sizes, and the existing fail-closed and diagnostic iterator behavior.

- `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `git diff --check -- src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md .vault/audit/2026-05-28-secure-storage-production-hardening-W04-P08-S33-review.md .vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-28-secure-storage-production-hardening-W04-P08-S33.md`
