---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S233'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Delegate local manuals file verification to core hash_file while retaining the distinct network-stream hashing path

## Scope

- `src/cadrumo/domain/manuals/_fetch.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `d0f83e66e7` retired a hand-rolled length accumulator by taking digest and length from one `core.hashing.hash_file` call, while the `httpx` network-stream path stays incremental because no path-based helper can consume a stream.

- Delegate local manual-PDF verification to `core.hashing.hash_file`, retiring the hand-rolled length accumulator that previously paired with a separate digest read.
- Leave `_stream_to_file`'s network download on incremental `hashlib.sha256()` `.update()` calls, since the bytes arrive as an `httpx` stream and no path-based helper can consume a stream.

## Outcome

`src/cadrumo/domain/manuals/_fetch.py` imports `hash_file` from `...core.hashing` at line 23 and calls it at line 346 to verify a local manual PDF against its manifest, returning `(sha256, length)` in one call. The module also keeps `import hashlib` at line 14, used only by `_stream_to_file` (lines 203-227), which streams the `httpx` GET response in 64 KiB chunks, updating an incremental `hashlib.sha256()` digest and a length counter in flight so the file need not be re-read from disk after download.

Verified against HEAD: the local-verification delegation and the retained network-stream path match the audit brief exactly.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/domain/manuals/tests/test_fetch.py` reports 12 passed.

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work.
