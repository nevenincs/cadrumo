---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S231'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Delegate whole-file corpus manifest hashing to core hash_file without changing manifest semantics

## Scope

- `src/cadrumo/core/corpus_manifest/__init__.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `d0f83e66e7` deleted the module's private `_hash_file` reimplementation and aliased the canonical `core.hashing.hash_file`, leaving both call sites untouched.

- Delete `corpus_manifest`'s private `_hash_file` helper, which was a verbatim reimplementation of `core.hashing.hash_file` (same 64 KiB chunking, same `"rb"` open, same `(digest, length)` tuple return).
- Alias the canonical helper under the module's existing private name so both call sites need no further edit.
- Prove byte-identity, not assume it: the old and new algorithms are shown to agree at 0, 1, 65535, 65536, 65537, and 200000 byte boundaries, so the chunk-size boundary is demonstrably irrelevant.

## Outcome

`src/cadrumo/core/corpus_manifest/__init__.py` imports `hash_file as _hash_file` from `..hashing` at line 47 and `sha256_hex as _sha256_hex` at line 48. `_hash_file` is called at lines 288 and 353 for the manifest build and bundle-verification whole-file reads; `_sha256_hex` is called at lines 306 and 637 for the manifest body digest. No private reimplementation of the chunked file-read loop remains in the module.

Verified against HEAD: all five cited line numbers (`47-48, 288, 306, 610, 637`) resolve exactly as the audit brief described — line 610 is `actual_sha256 = _sha256_hex(actual_bytes)` inside the bundle-verification loop, and line 637 is the embedded-manifest tamper check.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/core/corpus_manifest/tests/test_bundle.py src/cadrumo/core/corpus_manifest/tests/test_manifest.py` reports 15 passed.

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work.
