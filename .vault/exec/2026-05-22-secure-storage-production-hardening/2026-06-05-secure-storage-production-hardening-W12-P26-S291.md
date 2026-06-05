---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
step_id: 'S291'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S291 - Close AFR-189 for corpus manifest

Scope: close `AFR-189` for `src/aeat/core/corpus_manifest/__init__.py` with signals
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited the CORPUS-class plaintext manifest builder, saver, loader, verifier, and
  drift assertion helpers.
- Confirmed the module is an integrity manifest boundary for reference data, not a
  runtime secure bucket storage backend.
- Confirmed load, tamper, drift, and write failures log and raise typed AEAT-derived
  exceptions instead of being swallowed.
- Confirmed atomic manifest writes and relative-path validation.
- Ran vaultspec RAG semantic searches for corpus manifest duplication and runtime
  storage overlap.
- Closed `W12.P26.S291` through `vaultspec-core vault plan step check` and updated
  the `AFR-189` register status to `closed`.

## Outcome

`AFR-189` is closed as a retained plaintext-exception integrity manifest boundary.
No production code change was required for `src/aeat/core/corpus_manifest/__init__.py`.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/corpus_manifest/__init__.py src/aeat/core/corpus_manifest/_errors.py src/aeat/core/corpus_manifest/test_manifest.py src/aeat/core/errors/registry/_core.py src/aeat/core/errors/test_registry.py`
- `uv run --no-sync pytest -q src/aeat/core/corpus_manifest/test_manifest.py src/aeat/core/errors/test_registry.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "corpus_manifest plaintext corpus integrity manifest sha256 atomic save load tamper exception" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "CORPUS class plaintext reference data manifest secure storage runtime bucket exception" --type code --port 8766 --max-results 8`

## Notes

The plaintext corpus manifest is intentionally retained because CORPUS-class
reference material is plaintext-at-rest and integrity-tracked. Runtime secure bucket
object storage remains separate.
