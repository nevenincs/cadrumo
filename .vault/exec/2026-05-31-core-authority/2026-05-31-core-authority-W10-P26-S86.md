---
tags:
  - '#exec'
  - '#core-authority'
step_id: S86
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W10.P26.S86 - migrate SHA-256 one-liner sites to sha256_hex

## Outcome

Added `sha256_hex(data: bytes) -> str` to `core/hashing.py` as the single
authoritative in-memory SHA-256 helper for byte payloads.

Migrated five sites (and one bonus adjacent site in `application/live/__init__.py`)
that previously inlined `hashlib.sha256(data).hexdigest()`:

- `adapters/inbound/financial/providers/_base.py` — `_compute_sha256` static method
- `adapters/persistence/storage/blob_store/_blob_store.py` — `_hex_digest` function
- `application/filing/_review.py` — `_sha256_payload` function
- `application/live/__init__.py` — `_taxpayer_ref`, `_evidence_ref`, manifest digest
- `core/redaction/__init__.py` — `_sha256_prefix`, `_fingerprint` functions

Removed `hashlib` imports where no longer needed.

## Commit

`39f748cf6` — refactor(hashing): W10.P26.S86 - migrate SHA-256 one-liner call sites to sha256_hex

## Files touched

- `src/aeat/core/hashing.py` — added `sha256_hex`
- `src/aeat/adapters/inbound/financial/providers/_base.py`
- `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py`
- `src/aeat/application/filing/_review.py`
- `src/aeat/application/live/__init__.py`
- `src/aeat/core/redaction/__init__.py`

## Verification

All touched files import cleanly. `hashlib` removed where no longer needed.
