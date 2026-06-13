---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S32'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` `W04.P08.S32`

Made default secure-object namespace listing fail closed when any row is unreadable.

- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Reviewed: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P08-S32-review.md`

## Description

`list_records` now buffers readable rows from the explicit diagnostic iterator and raises `SecureObjectUnreadableError` on the first unreadable outcome before yielding any subset. This prevents default sensitive namespace listing from silently degrading to partial plaintext when rows are unreadable under the active key or fail row-level metadata contracts.

`iter_records_with_failures` remains the opt-in diagnostic path and now returns typed `SecureObjectUnreadable` outcomes for decryption failures, unknown classifications, classification mismatches, caller-supported-version drift, and registry-bound schema drift.

## Tests

Validation covered fail-closed default listing, no partial subset yield before failure, normal readable listing, explicit mixed readable/unreadable diagnostics, metadata contract failures, and registry schema drift diagnostics.

- `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `git diff --check -- src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md .vault/audit/2026-05-28-secure-storage-production-hardening-W04-P08-S32-review.md .vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-28-secure-storage-production-hardening-W04-P08-S32.md`
