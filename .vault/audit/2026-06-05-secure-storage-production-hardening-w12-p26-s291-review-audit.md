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

## S291-001 | PASS | Corpus manifest is a plaintext integrity sidecar

`src/aeat/core/corpus_manifest/__init__.py` writes and reads plaintext JSON manifests
for CORPUS-class reference data. This is a retained plaintext exception: the manifest
records SHA-256 and byte length for reference files and self-attests its own body
digest. It is not a storage backend for operator financial, tax, profile, or auth
state.

Disposition: close `AFR-189` as a plaintext integrity-manifest exception.

## S291-002 | PASS | Runtime storage is not hidden in the module

The module does not resolve active profiles, inspect bucket sessions, derive SQL
routes, open secure-object repositories, load master keys, or construct remote storage
providers. It only walks a caller-supplied corpus root and handles the manifest sidecar
inside that root.

## S291-003 | PASS | Writes are atomic and reviewed

`save_corpus_manifest()` writes through `tempfile.NamedTemporaryFile`, flushes and
fsyncs the payload, atomically replaces the target with `os.replace`, fsyncs the parent
directory, and cleans up the temporary file on `OSError`. The write is registered in
the sensitive-persistence reviewed-write inventory as non-user corpus manifest
generation.

## S291-004 | PASS | Exceptions are typed and localized

`CorpusManifestError`, `CorpusManifestTamperError`, and `CorpusManifestDriftError`
derive from the AEAT error base, are registered in the core error registry, and have
locale entries across `ca`, `en`, `es`, and `hu`. Structural invalidity, future
manifest versions, self-attesting digest mismatch, and live corpus drift all fail
loudly.

## S291-005 | PASS | Behavior validation is non-tautological

The focused tests build real temporary corpus trees, write real manifest files, reload
them, tamper with manifest JSON, mutate corpus files, and assert real drift/tamper
errors. They do not mock, monkeypatch, skip, xfail, or mirror manifest implementation
logic.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/corpus_manifest/__init__.py src/aeat/core/corpus_manifest/_errors.py src/aeat/core/corpus_manifest/test_manifest.py src/aeat/core/errors/registry/_core.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- `uv run --no-sync pytest -q src/aeat/core/corpus_manifest/test_manifest.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- `uv run --no-sync pytest -q -m docs src/aeat/tests/test_docs_api_stubs.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "corpus manifest plaintext JSON sha256 tamper drift atomic save no secure bucket repository" --type code --port 8766 --max-results 8`
