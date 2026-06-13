---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S288'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S288 - Close AFR-186 for core TOML helpers

Scope: close `AFR-186` for `src/aeat/core/_toml.py` with signals `plain-file`,
target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited `read_toml()`, `parse_toml_text()`, `to_str_keyed_dict()`, and TOML freeze
  helpers.
- Confirmed the module is a shared plaintext TOML parser/freeze helper for committed
  TOML and already-loaded manifest text.
- Confirmed the helper does not resolve active profiles, discover manifests, open
  secure-object repositories, call remote providers, read settings, or read environment
  variables.
- Confirmed TOML decode and file I/O failures are raised through caller-provided
  exception factories and chained from the original exceptions.
- Ran direct usage search and vaultspec RAG semantic search for duplicate TOML parsing
  surfaces and bucket manifest reuse.
- Closed `W12.P26.S288` through `vaultspec-core vault plan step check` and updated
  the `AFR-186` register status to `closed`.

## Outcome

`AFR-186` is closed as a retained plaintext-exception parser boundary. No production
code change was required for `src/aeat/core/_toml.py`; the existing helper centralizes
the duplicated TOML parsing/freeze behavior and remains outside runtime secure bucket
storage backend selection.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/_toml.py src/aeat/core/test_toml.py src/aeat/adapters/persistence/storage/bucket/_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py src/aeat/core/access_gate/test_authorization_manifest.py src/aeat/domain/user_profile/test_schema.py`
- `uv run --no-sync pytest -q src/aeat/core/test_toml.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py src/aeat/core/access_gate/test_authorization_manifest.py src/aeat/domain/user_profile/test_schema.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "parse_toml_text bucket manifest toml text loader error_factory no duplicate TOML parser" --type code --port 8766 --max-results 8`

## Notes

The existing `src/aeat/core/test_toml.py` uses a local sample exception only to prove
the caller-supplied error factory contract. It does not monkeypatch, stub, skip, xfail,
or mirror production TOML parsing logic. The downstream broad fallback in
`src/aeat/core/config.py` remains tracked by the next `core/config.py` ledger row.
