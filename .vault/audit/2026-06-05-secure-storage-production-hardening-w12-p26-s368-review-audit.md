---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S368]]'
---

# `secure-storage-production-hardening` `W12.P26.S368` Review

## S368-001 | PASS | Raw transaction models are a plaintext exception, not storage

`_raw_transaction.py` declares strict Pydantic boundary models and enums for financial
ingest rows. It does not construct secure-object repositories, load settings, read
environment variables, open files, or write storage; source paths are stored as
provenance values and resolved as model fields.

## S368-002 | PASS | Validation errors remain typed AEAT errors

The raw transaction validators raise `TransactionValidationError`, which now inherits
from the structured transaction error hierarchy reviewed in S366. The one wrapped
exception path catches `CoreValidationError` from UTC timestamp validation and re-raises
the transaction validation type with the original exception chained.

## S368-003 | PASS | Model behavior is covered by real boundary tests

The inbound financial provider tests exercise raw transaction JSON roundtrip and
immutable raw field behavior. The adjacent transaction model tests exercise raw
transaction construction through stable transaction identity, gross amount invariants,
and currency handling without fakes or monkeypatches.

## S368-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/transactions/_raw_transaction.py src/aeat/domain/transactions/test_models.py src/aeat/domain/transactions/test_catalogue.py src/aeat/domain/transactions/test_gross_invariant.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/inbound/financial/providers/test_base.py` passed with 22 tests and 4 upstream `ofxparse` deprecation warnings.
- `uv run --no-sync pytest -q src/aeat/domain/transactions/test_models.py src/aeat/domain/transactions/test_gross_invariant.py` passed with 26 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-rag search "RawTransaction RawProvenance plaintext exception no storage no secure object transaction ingest model validation" --type code --port 8766 --max-results 8` returned the raw transaction model and inbound provider evidence.
- `uv run --no-sync vaultspec-rag search "transactions raw transaction provenance source_sha256 UTC validation MappingProxyType pydantic model tests" --type code --port 8766 --max-results 8` returned the provenance model and test coverage evidence.

Reviewer note: no critical, high, medium, or low plaintext-exception findings remain
for the S368 slice.

Disposition: close `AFR-266` as `plaintext-exception`.
