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

## S295-001 | PASS | Core registry is declaration-only

`src/aeat/core/errors/registry/_core.py` declares `ErrorCode` rows for core,
resource, locale, corpus-manifest, lock, active-profile, and observability errors.
It does not perform plain-file I/O, read environment variables, load settings, open
secure storage, or select a runtime storage backend. Plain-file behavior remains in
the owning modules, while this file stays the central error-code authority for those
exception classes.

Disposition: close `AFR-193` as a plaintext-exception registry boundary. No production
code change was required for this row.

## S295-002 | PASS | Plain-file failures use AEAT exception bases

The audited classes derive from `AeatError` or `CoreError`: `CorpusManifestError`,
`LockAcquisitionError`, `ResourceLoadError`, `LocaleError`, `ActiveProfilePointerError`,
and related core errors are registry-bound and render through locale message keys.
The corpus-manifest classes retain `ValueError` compatibility only through
multiple-inheritance with the AEAT base.

## S295-003 | PASS | Localized operator output remains centralized

Every audited row carries a `message_key` under the error locale tree, and the locale
audit passed through `python -m aeat.locales audit`. No new user-facing literal error
message was added in this step.

## S295-004 | PASS | Duplication search found no second authority

Vaultspec RAG returned `src/aeat/core/errors/registry/_core.py`, the corpus/resource
exception classes, the lock error type, locale YAML, and focused registry tests. No
duplicate core error registry or alternate plaintext-exception table was found.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/errors/registry/_core.py src/aeat/core/errors/__init__.py src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/core/errors/test_core_error_root.py src/aeat/core/errors/test_envelope.py src/aeat/core/resources/_errors.py src/aeat/core/resources/test_registry.py src/aeat/core/corpus_manifest/_errors.py src/aeat/core/corpus_manifest/test_manifest.py src/aeat/core/locks_errors.py`
- `uv run --no-sync pytest -q src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/core/errors/test_core_error_root.py src/aeat/core/errors/test_envelope.py src/aeat/core/resources/test_registry.py src/aeat/core/corpus_manifest/test_manifest.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "core error registry plain file plaintext exception resource corpus manifest lock locale ErrorCode message_key" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "CoreError ResourceLoadError CorpusManifestError LockAcquisitionError LocaleError error registry plaintext file exception" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
