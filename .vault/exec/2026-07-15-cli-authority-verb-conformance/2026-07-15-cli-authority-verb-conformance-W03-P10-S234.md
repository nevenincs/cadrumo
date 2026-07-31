---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:31f2f9b2fe0fa40949b123798dbbb11e9fb66f3f4a0fa5c88225617ac12e2247'
step_id: 'S234'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Preserve the mirror object-key structured byte contract but delegate its one-shot digest to sha256_hex without converting it to HMAC

## Scope

- `src/cadrumo/adapters/outbound/storage/_mirror_manifest.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `d0f83e66e7` folded the mirror object key's three sequential `.update()` calls into one `core.hashing.sha256_hex` digest over the same domain-separated bytes, separator included, without converting the digest to a keyed HMAC despite the function's name (which would change object identifiers).

- Fold the three sequential `.update()` calls building the mirror object key into a single `core.hashing.sha256_hex` call over the identical domain-separated byte sequence.
- Preserve the object key's structured byte contract exactly: the namespace bytes, the `\x00` separator, and the object-key bytes stay in the same order and are not converted to a keyed HMAC construction.

## Outcome

`src/cadrumo/adapters/outbound/storage/_mirror_manifest.py` imports `sha256_hex` from `....core.hashing` at line 20 and calls it at four sites: line 85 for a content-hash payload, line 222 for a fallback ciphertext hash, line 232 for a remote-mirror-manifest namespace key (`f"remote-mirror-manifest:{namespace}"`), line 326 for a ciphertext-hash comparison, and line 348 for the object key itself (`namespace.encode() + b"\x00" + object_key`) — the domain-separated structured byte contract this Step protects.

Verified against HEAD: five `sha256_hex` call sites confirmed (the audit brief cited the import plus five call sites collectively as "five sites, none converted to HMAC"), and none constructs an `hmac.new(...)` keyed digest; the function name notwithstanding, the mirror object key stays a plain content digest, so existing remote mirror object identifiers are unchanged.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/adapters/outbound/storage/tests/test_mirror_manifest.py` reports 16 passed.

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work.
