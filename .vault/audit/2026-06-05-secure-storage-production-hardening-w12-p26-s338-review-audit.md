---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S338-001 | PASS | Amendment repository is runtime-default enrolled

`src/aeat/domain/filing/_complementaria_repository.py` resolves a bucket id through
`resolve_filing_repository_bucket_id()` and constructs its backing
`SecureObjectRepository` with `secure_objects_for_filing_bucket()`. That helper delegates
to the runtime repository factory for the selected bucket, so default construction does
not create an unscoped storage repository.

## S338-002 | PASS | Amendment payloads remain encrypted AUDIT records

The save path wraps amendments in an AUDIT `Envelope`, writes through the secure-object
repository, and existing tests prove the SQLite database does not contain amendment CSV,
reason text, or amendment id plaintext after save. The load path enforces AUDIT
classification and max envelope version.

## S338-003 | PASS | Tests are real behavior and non-tautological

The focused suites use the real isolated runtime profile and real SQL/encryption path.
They verify successful roundtrip, classification mismatch refusal, unsafe id rejection,
and a negative corrupted-payload case that must raise validation on load.

## S338-004 | TRACKING | Prior checked rows have stale pending register entries

During S338 selection, the plan showed several already-checked W12.P26 rows whose AFR
register rows still read `pending`. This is not a S338 code defect, but it is a plan
tracking defect. It should be reconciled explicitly in a tracking repair step so future
rollout review does not report false open work.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/filing/_complementaria_repository.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/application/filing/test_complementaria_repository.py src/aeat/domain/filing/test_secure_storage_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/application/filing/test_complementaria_repository.py src/aeat/domain/filing/test_secure_storage_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "ModeloAmendmentRepository complementaria filing amendments secure_object_repository_for_bucket AUDIT encrypted runtime bucket" --type code --port 8766 --max-results 8`
