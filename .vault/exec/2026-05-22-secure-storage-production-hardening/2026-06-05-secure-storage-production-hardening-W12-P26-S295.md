---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S295'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S295 - Close AFR-193 for core error registry

Scope: close `AFR-193` for `src/aeat/core/errors/registry/_core.py` with signal
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited the core error registry rows for core, resource, locale, corpus-manifest,
  file-lock, active-profile, and observability exception classes.
- Confirmed the registry module is declaration-only and does not perform plain-file
  persistence, environment access, settings resolution, or secure-storage backend
  selection.
- Confirmed audited exception classes derive from `AeatError` or `CoreError` and render
  through locale message keys.
- Ran vaultspec RAG semantic searches for duplicate core registry and plaintext-file
  exception-code surfaces.
- Closed `W12.P26.S295` through `vaultspec-core vault plan step check` and updated
  the `AFR-193` register status to `closed`.

## Outcome

`AFR-193` is closed as the canonical core-registry plaintext-exception boundary. No
production code change was required for `src/aeat/core/errors/registry/_core.py`.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/errors/registry/_core.py src/aeat/core/errors/__init__.py src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/core/errors/test_core_error_root.py src/aeat/core/errors/test_envelope.py src/aeat/core/resources/_errors.py src/aeat/core/resources/test_registry.py src/aeat/core/corpus_manifest/_errors.py src/aeat/core/corpus_manifest/test_manifest.py src/aeat/core/locks_errors.py`
- `uv run --no-sync pytest -q src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/core/errors/test_core_error_root.py src/aeat/core/errors/test_envelope.py src/aeat/core/resources/test_registry.py src/aeat/core/corpus_manifest/test_manifest.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "core error registry plain file plaintext exception resource corpus manifest lock locale ErrorCode message_key" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "CoreError ResourceLoadError CorpusManifestError LockAcquisitionError LocaleError error registry plaintext file exception" --type code --port 8766 --max-results 8`

## Notes

The plan check still reports the known `PLAN022` monotonic identifier warning. No S295
specific plan-shape violation was introduced.
