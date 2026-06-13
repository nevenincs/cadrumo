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

## S288-001 | PASS | Shared TOML helper is a plaintext parser boundary

`src/aeat/core/_toml.py` centralizes TOML parse, string-key validation, and recursive
freeze behavior for committed TOML and already-loaded TOML text. The helper does not
open secure-object repositories, resolve active profiles, scan bucket directories, call
remote providers, or handle master-key material. Its `parse_toml_text()` entrypoint is
used by bucket manifest I/O after the manifest text is already loaded, preserving the
manifest parser as a plaintext validation boundary rather than a storage backend.

Disposition: close `AFR-186` as a retained plaintext-exception helper.

## S288-002 | PASS | Exceptions are caller-typed and chained

`read_toml()` wraps `tomllib.TOMLDecodeError` and `OSError` through the supplied
`error_factory`, and `parse_toml_text()` wraps TOML decode errors through the same
contract. Both functions raise from the original exception. `to_str_keyed_dict()` also
uses the caller-provided factory when parsed mappings contain non-string keys. No
exception is swallowed or converted to a silent default in this module.

## S288-003 | PASS | Settings and environment isolation

No settings or environment wrangling is present in `src/aeat/core/_toml.py` or its
unit tests. The module has no `os.environ`, `getenv`, `load_settings`, settings object,
runtime-route, or active-profile access. This keeps configuration resolution with the
callers that own storage or domain loading context.

## S288-004 | PASS | Duplication and runtime storage review

Direct usage search shows the helper is reused by access-gate authorization manifests,
domain registry loaders, user-profile schema loading, IVA/deadline/category catalogues,
and bucket manifest I/O. Vaultspec RAG clustered the slice with `src/aeat/core/_toml.py`,
`src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`, bucket manifest
roundtrip tests, and workflow manifest error compaction. No duplicate TOML parser or
freeze helper was found in the secure-bucket runtime path.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/_toml.py src/aeat/core/test_toml.py src/aeat/adapters/persistence/storage/bucket/_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py src/aeat/core/access_gate/test_authorization_manifest.py src/aeat/domain/user_profile/test_schema.py`
- `uv run --no-sync pytest -q src/aeat/core/test_toml.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py src/aeat/core/access_gate/test_authorization_manifest.py src/aeat/domain/user_profile/test_schema.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "parse_toml_text bucket manifest toml text loader error_factory no duplicate TOML parser" --type code --port 8766 --max-results 8`

One broader RAG query for committed TOML parser usage timed out after returning the
expected `_toml.py`, bucket manifest, workflow manifest error, and helper-test cluster;
the completed narrower query above was retained as the recorded validation gate.
