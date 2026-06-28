---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S25'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C1-2 Delegate the five chunked-read SHA-256 loops to core.hashing.hash_file/sha256_file

## Scope

- `src/aeat/core/hashing.py`

## Description

- Re-verified the five candidate sites at HEAD and applied the substitutability
  pre-filter: three delegate cleanly, two were excluded as not substitutable.
- `inbound/pdf/_utils.sha256_file` delegates to `core.hashing.sha256_file`,
  wrapping `OSError` in `PdfModeloImportError`; removed the inline `hashlib`
  loop and the now-unused chunk-size constant.
- `registry/_sources._source_file_fingerprint` uses `hash_file` (kept the
  lru_cache key and the `(length, hex)` return order).
- `sanitizer/_pipeline._digest_source` delegates the `Path` branch to
  `hash_file` and the `bytes` branch to `sha256_hex`.

## Outcome

Committed as `c72f2e8fd`, tagged `relocation:hash_file`. Ruff clean; 466
pdf/sanitizer/registry tests green, including the source-path redaction-hygiene
test.

## Notes

A first pass raised the sanitizer error with `from exc`, which broke
`TestSourceParseErrorHygiene` (it asserts `__cause__` AND `__context__` are
None so the OSError's filesystem path never leaks). Restored the original
deferred-raise pattern (capture the error in the except, raise after the block)
so both slots stay clean. Two sites excluded with rationale: `manuals/_fetch`
hashes the httpx stream while writing (never re-reads the file) and
`attachment.put_file` interleaves the digest with byte accumulation under a
typed read error — neither is a clean `hash_file` delegation.
