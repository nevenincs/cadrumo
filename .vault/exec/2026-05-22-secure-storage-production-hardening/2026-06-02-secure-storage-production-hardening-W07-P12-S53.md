---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S53'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W07.P12.S53`

## Description

- Classify the domain repository hygiene candidates from the S50 inventory after confirming ownership and runtime isolation.
- Verify representative domain repository tests for attachment, invoice, justificante, and submission persistence.
- Select whether a domain repair slice should displace the S51 application/modelo candidate.

## Outcome

Closed.

Domain ownership classification:

- `src/aeat/domain/attachments/test_repository.py` is domain-owned and uses autouse `isolated_runtime_profile(..., bucket_id="attachment-test")`.
- `src/aeat/domain/invoices/test_repository.py` is domain-owned and uses autouse `isolated_runtime_profile(..., bucket_id="test")`.
- `src/aeat/domain/justificante/test_repository.py` is domain-owned and uses autouse `isolated_runtime_profile(..., bucket_id="justificante-test")`.
- `src/aeat/domain/submission/test_repository.py` is domain-owned and uses autouse `isolated_runtime_profile(..., bucket_id="submission-test")`.

Selected domain disposition:

- No domain secure-SQL isolation repair is selected ahead of the S51 application/modelo slice. The representative domain files already use the central runtime helper and do not require the S52 pattern validation.
- `src/aeat/domain/attachments/test_repository.py` remains a domain follow-up candidate for a separate persistence-content assertion issue: its focused test currently expects the SHA-256 digest object key not to appear in the SQLite database, but the current secure-object layout stores lookup keys in a queryable form.
- Three representative domain files have pre-existing Ruff import-order drift and should be fixed with their owning domain cleanup, not mixed into this selection row.

Verification:

- `uv run --no-sync pytest -q src/aeat/domain/attachments/test_repository.py src/aeat/domain/invoices/test_repository.py src/aeat/domain/justificante/test_repository.py src/aeat/domain/submission/test_repository.py` -> 45 passed, 1 failed. Failure: `src/aeat/domain/attachments/test_repository.py::test_blob_and_manifest_round_trip_without_plaintext_files` because the digest object key appears in the SQLite bytes.
- `uv run --no-sync ruff check src/aeat/domain/attachments/test_repository.py src/aeat/domain/invoices/test_repository.py src/aeat/domain/justificante/test_repository.py src/aeat/domain/submission/test_repository.py` -> failed with import-order findings in invoice, justificante, and submission tests.

## Notes

No HIGH or CRITICAL issue was identified for secure-SQL isolation ownership. The attachment plaintext-digest assertion is a domain persistence follow-up, not evidence of cross-test SQL contamination.
