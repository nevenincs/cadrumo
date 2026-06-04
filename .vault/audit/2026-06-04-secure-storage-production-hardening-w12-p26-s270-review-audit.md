---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S270]]'
---

# `secure-storage-production-hardening` `W12.P26.S270` Review

## S270-001 | PASS | Repository construction stays runtime-bound

The user-profile value and snapshot repositories continue to construct their default
secure-object repository through the bucket storage runtime. The reviewed module uses
registered storage namespace constants and strict envelope records rather than
duplicating storage routing, physical SQL paths, or record shapes.

## S270-002 | PASS | Missing loads use localized AEAT errors

Missing live profile records and missing profile snapshots now raise the existing
user-profile AEAT error classes with registered translation keys and structured
context. The raw English not-found messages were removed from the repository boundary.

## S270-003 | PASS | Nonblocking cache invalidation is observable

Output-language cache invalidation remains deliberately nonblocking for persistence,
but import and runtime failures now emit debug diagnostics before being ignored. The
repository no longer contains a silent broad exception swallow on that path.

## S270-004 | PASS | Duplication and test review

Vaultspec RAG semantic search clustered this row with the real repository roundtrip
tests, the orchestration lifecycle service wiring, and the missing-load tests. The
implementation reuses the runtime repository factory and core/domain models instead of
adding another storage path.

## S270-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/user_profile/_repository.py src/aeat/application/user_profile/test_repository.py src/aeat/locales`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_repository.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

Disposition: close `AFR-168`.
