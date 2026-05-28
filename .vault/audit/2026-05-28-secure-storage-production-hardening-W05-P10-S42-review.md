---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
  - '[[2026-05-28-secure-storage-production-hardening-W05-P10-S41-review]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `secure-storage-production-hardening` Code Review

Status: REVISION REQUIRED.

HIGH findings were found. No CRITICAL findings were found.

## Review Scope

Reviewed W05.P10.S42 only: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`,
`src/aeat/adapters/outbound/storage/_records.py`,
`src/aeat/adapters/outbound/storage/_mirror_manifest.py`,
`src/aeat/adapters/outbound/storage/__init__.py`,
`src/aeat/adapters/outbound/storage/test_mirror_manifest.py`,
`src/aeat/adapters/outbound/storage/test_foundation.py`, and
`src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`.

No implementation code or plan checkboxes were modified.

## Findings

S42-001 | HIGH | Manifest object identifiers do not match remote ciphertext objects
 `build_remote_mirror_namespace_manifest` writes each manifest entry's
 `object_key_hmac` from the raw SQL object-key digest as `row.object_key.hex()`.
 The existing mirror push path uploads ciphertext objects under a different
 provider key: `sha256(namespace + NUL + row.object_key)`. A manifest produced
 by S42 therefore cannot be used to locate, compare, or conflict-check the
 remote ciphertext object it claims to describe. This breaks the remote mirror
 contract before S43 partial-upload, stale-mirror, and revision-conflict
 detection can consume the manifest. The S42 test only maps manifest entries
 back to raw SQL rows, so it does not catch this mismatch against the actual
 provider object identity.

S42-002 | HIGH | Production mirror push still does not persist remote manifests
 S42 adds `put_remote_mirror_namespace_manifest` and exports it, but the
 existing production mirror push path still iterates raw rows, uploads each
 ciphertext payload, and finishes with a CLI summary without calling the
 manifest builder or persister. A normal remote mirror operation therefore
 leaves no `_sync-state` namespace manifest containing ciphertext hashes and
 revision watermarks. Manual tests against the helper prove the helper can
 write a manifest, but they do not prove S42 stores manifests during the
 real mirror workflow required by the plan row.

## Review Notes

PASS-S42-001 | PASS | Raw secure-object iteration now exposes revision metadata and ciphertext hashes
 `SecureObjectRawRow` includes revision id, previous revision id, payload hash,
 ciphertext hash, and revision timestamp fields. `iter_all_records_raw` selects
 those columns without decrypting payload bytes, preserving the opaque
 ciphertext walk used by remote mirror code.

PASS-S42-002 | PASS | Manifest payload avoids plaintext application payloads
 The manifest model records namespace metadata, classification, schema version,
 ciphertext byte length, ciphertext hash, revision ids, and timestamps. The
 reviewed helper does not serialize decrypted payload bytes. The test persists
 real encrypted rows and verifies the original plaintext payload bytes are not
 present in the stored manifest payload.

PASS-S42-003 | PASS | Tests are real-behavior but have the two coverage gaps above
 The scoped tests use a real `SecureObjectRepository`, real SQLite database,
 real `EphemeralMasterKeyProvider`, and real `LocalFileSystemProvider`. No
 fakes, mocks, stubs, monkeypatches, skips, or xfails were found in the scoped
 test files. The remaining issue is not test hygiene; it is that the test
 stops at helper persistence and never proves alignment with the actual remote
 mirror upload path or provider object identity.

## Validation

- `uv run pytest src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
  passed: 50 tests.
- `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/__init__.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
  passed.
- `git diff --check -- src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/__init__.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
  passed with Git's pre-existing CRLF notice for `src/aeat/adapters/outbound/storage/test_foundation.py`.
