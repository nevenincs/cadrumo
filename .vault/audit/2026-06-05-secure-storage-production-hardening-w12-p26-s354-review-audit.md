---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S354]]'
---

# `secure-storage-production-hardening` `W12.P26.S354` Review

## S354-001 | PASS | Filing record model is not a persistence authority

`src/aeat/domain/modelos/_filing_record.py` defines strict Pydantic models, lifecycle
enums, external-evidence metadata, and content-addressed filing-record IDs. It does not
open files, read environment values, resolve active buckets, construct secure-object
repositories, or persist catalogue data.

## S354-002 | PASS | Manifest-discovery classification is coherent

The module carries bucket and filing tuple fields because filing records are scoped by
bucket, modelo, year, and period. Those fields describe the shape and identity of
bucket-local records; storage enrollment belongs to the paired repository row, not this
model module.

## S354-003 | PASS | Schema consistency is explicit

`ModeloRecord` enforces content-addressed IDs and lifecycle metadata invariants.
`ModeloRecordCatalogue` enforces key alignment and one current filing record per
bucket/modelo/year/period tuple. `ExternalEvidence` is a strict frozen model for
imported AEAT evidence metadata and does not initiate live submission.

## S354-004 | PASS | Ignore pragma is scoped and justified

`ModeloRecordCatalogue.__iter__` carries static-analysis ignore comments for the
intentional Pydantic catalogue iterator override. The pragma is tied to the iterator
return-shape mismatch and does not suppress storage, exception, localization, or
runtime logic failures.

## S354-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/modelos/_filing_record.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_external_evidence.py` passed.
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_external_evidence.py` passed with 8 tests.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync vaultspec-rag search "ModeloRecord ModeloRecordCatalogue ExternalEvidence derive_filing_record_id manifest bucket discovery no persistence" --type code --port 8766 --max-results 8` returned filing record model, repository, and application consumers.

Reviewer note: no critical, high, medium, or low runtime-storage findings remain for
the S354 slice.

Disposition: close `AFR-252` as `manifest-discovery`.
