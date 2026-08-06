---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:5f172f73ab3c07c50f51863525cff4c378cac879c344eec80366155dd0451252'
step_id: 'S226'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Delegate declaracion parser and pdfplumber one-shot PDF digests to core sha256_hex without changing byte inputs or digest representation

## Scope

- `src/cadrumo/adapters/inbound/declaracion/_parser.py`
- `src/cadrumo/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `a1f1160e0c` routed the declaracion parser's source digest and the pdfplumber byte-cache key through `core.hashing.sha256_hex`, dropped the pdfplumber site's function-local `hashlib` import (the deferred-import cycle break it existed for was not needed for the canonical helper), and shrank the hashing recurrence-gate baseline in the same commit.

- Route `parse_declaracion_pdf`'s path-based source digest through `sha256_file` (imported from the shared `adapters.inbound.pdf` bridge, itself delegating to `core.hashing.sha256_file`) instead of a hand-rolled read-and-hash.
- Route `parse_declaracion_bytes`'s bytes-based source digest through `core.hashing.sha256_hex` directly.
- Route the pdfplumber backend's pdfium byte-cache key through `core.hashing.sha256_hex` instead of an inline `hashlib.sha256(...).hexdigest()` body.
- Preserve every argument expression unchanged on all call sites so the digest bytes are identical by construction.

## Outcome

`src/cadrumo/adapters/inbound/declaracion/_parser.py` carries two digest call sites: `sha256_hex` imported from `....core.hashing` at line 31 and called at line 214 for the bytes-based `parse_declaracion_bytes` path; `sha256_file` imported from `..pdf` at line 53 and called at line 150 for the path-based `parse_declaracion_pdf` path, with that bridge (`adapters/inbound/pdf/_utils.py:15,33`) delegating to `core.hashing.sha256_file`. `_pdfplumber_backend.py` imports `sha256_hex` from `.....core.hashing` at line 25 and calls it at line 136 for the pdfium byte-cache key. None of the three call sites constructs `hashlib.sha256` inline.

Verified against HEAD: all four cited line numbers (`_parser.py:31,53,150,214`) resolve exactly as the audit brief described.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/adapters/inbound/declaracion/tests/test_parser_source_digest_identity.py src/cadrumo/adapters/inbound/declaracion/tests/test_pdfplumber_backend_privacy.py` reports 6 passed; the source-digest-identity file proves a parsed observation's `source_pdf_sha256` equals `hashlib`'s digest of the bytes it was parsed from, against real multi-kilobyte corpus PDF bytes and the published NIST "abc" vector.

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work.
