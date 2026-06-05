---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S291-001 | PASS | Corpus manifest is plaintext integrity, not secure storage

`src/aeat/core/corpus_manifest/__init__.py` owns a plaintext JSON manifest for
CORPUS-class reference material. It records relative paths, SHA-256 digests, byte
lengths, and a self-attesting manifest digest. It does not resolve active buckets,
open secure-object repositories, inspect master keys, route SQL, call remote providers,
or read `Settings`.

Disposition: close `AFR-189` as a plaintext-exception integrity manifest boundary.

## S291-002 | PASS | Exceptions are typed and logged

Corpus manifest failures derive from `AeatError` through
`CorpusManifestError`, `CorpusManifestTamperError`, and
`CorpusManifestDriftError`. Structural load failures are logged with traceback before
being wrapped as `CorpusManifestError`; manifest digest mismatches and drift failures
are logged at error or warning level before raising typed exceptions. Atomic write
failures log and re-raise `OSError`.

## S291-003 | PASS | Plain-file writes are atomic and scoped

`save_corpus_manifest()` writes to a sibling temporary file, flushes and fsyncs the
file, atomically replaces the target with `os.replace`, and fsyncs the parent
directory. Path records are validated as relative POSIX paths and reject absolute,
dot-token, and backslash traversal forms.

## S291-004 | PASS | Duplication and runtime review

Vaultspec RAG clustered this slice with the corpus manifest module, its tests, the
core error registry, locale integrity keys, and bucket manifest code as a separate
plaintext manifest family. No duplicate CORPUS integrity manifest implementation or
runtime secure bucket storage backend dependency was found in this slice.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/corpus_manifest/__init__.py src/aeat/core/corpus_manifest/_errors.py src/aeat/core/corpus_manifest/test_manifest.py src/aeat/core/errors/registry/_core.py src/aeat/core/errors/test_registry.py`
- `uv run --no-sync pytest -q src/aeat/core/corpus_manifest/test_manifest.py src/aeat/core/errors/test_registry.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "corpus_manifest plaintext corpus integrity manifest sha256 atomic save load tamper exception" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "CORPUS class plaintext reference data manifest secure storage runtime bucket exception" --type code --port 8766 --max-results 8`
