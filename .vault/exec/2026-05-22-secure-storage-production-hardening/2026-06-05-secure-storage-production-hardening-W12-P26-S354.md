---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S354'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S354 - Close AFR-252 for modelo filing record model

Scope: close `AFR-252` for `src/aeat/domain/modelos/_filing_record.py` with signal
`manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited `ModeloRecord`, `ModeloRecordCatalogue`, `ModeloRecordStatus`,
  `ExternalEvidence`, and `ExternalEvidenceKind` as strict domain data models.
- Confirmed `derive_filing_record_id` is a deterministic content-addressing helper and
  does not read or write storage.
- Confirmed the catalogue enforces key alignment and one-current-record-per-filing
  tuple, but does not resolve buckets or construct repositories.
- Confirmed the paired persistence surface lives in
  `src/aeat/domain/modelos/_filing_repository.py`, which remains tracked by
  `W12.P26.S355`.
- Closed `W12.P26.S354` through `vaultspec-core vault plan step check` and updated the
  `AFR-252` register status to `closed`.

## Outcome

`AFR-252` is closed as `manifest-discovery`. The filing record module describes
bucket-scoped filing-record identity and manifest-like catalogue shape; it does not own
secure-object storage runtime construction.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/modelos/_filing_record.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_external_evidence.py`
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_external_evidence.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "ModeloRecord ModeloRecordCatalogue ExternalEvidence derive_filing_record_id manifest bucket discovery no persistence" --type code --port 8766 --max-results 8`

## Notes

No production code change was required. The paired repository row `W12.P26.S355`
continues to track runtime-default persistence hardening for the encrypted
filing-record catalogue.
