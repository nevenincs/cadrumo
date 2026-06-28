---
tags:
  - '#exec'
  - '#core-authority'
step_id: S85
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W10.P26.S85 - collapse _hash_file copies to core/hashing

## Outcome

Extended `src/aeat/core/hashing.py` with `hash_file(path: Path) -> tuple[str, int]`
returning `(sha256_hex, byte_count)`. `sha256_file` now delegates to `hash_file`
eliminating duplicate chunked-read logic.

Deleted `_hash_file` from `application/ledger/_evidence.py`; imported `sha256_file`
from `core.hashing` instead. Removed unused `hashlib` import.

`domain/calculations/registry/_workbook_parity.py` was already migrated by W06.P29
(commit `5b45dd58c`), confirming no-op for that file.

## Commit

`dcd17671a` — refactor(hashing): W10.P26.S85 - collapse _hash_file copies to core/hashing

## Files touched

- `src/aeat/core/hashing.py` — added `hash_file`, `sha256_file` delegates to it
- `src/aeat/application/ledger/_evidence.py` — `_hash_file` deleted, `sha256_file` from core

## Verification

Identity and ledger suites pass. Pre-existing registry catalogue coverage failure
(modelo 036/390 workbook parity) confirmed pre-existing, unrelated to hashing.
