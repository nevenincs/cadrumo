---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P03.S05'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P03.S05

Implement the canonical in-memory wipe primitive at
`src/aeat/adapters/persistence/storage/master_key/_zeroise.py` and route
`BucketSession.close()` through it so the substrate has a single wipe
surface per ADR-1 section 5.

- Created: `src/aeat/adapters/persistence/storage/master_key/_zeroise.py`
- Created: `src/aeat/adapters/persistence/storage/master_key/test_zeroise.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`

## Description

`zeroise(buffer)` overwrites every byte of a `bytearray` with zero in
place. The function refuses immutable `bytes` at the contract layer
because Python provides no portable primitive to overwrite immutable
objects; the caller must own a mutable buffer to begin with.

`BucketSession._bucket_session.py` previously inlined the wipe loop;
the import wires through `_zeroise.zeroise` instead so future
hardening (a native `CRYPTO_cleanse` shim) lands in one module.

The honest-contract docstring documents the Python-runtime limit: the
interpreter may produce short-lived `bytes` copies during property
reads (`session.kek` returns `bytes(self._kek_buffer)`), and the
garbage collector owns the lifetime of those copies. The wipe
guarantees the steady-state `bytearray` content is zeroed; transient
view copies are bounded by GC, not by this primitive.

## Tests

`test_zeroise.py` (6 tests; `pytest.mark.unit` +
`pytest.mark.domain_persistence`):

- Non-zero buffer round-trips to all-zero after wipe.
- Empty buffer is a no-op.
- Long buffer (4 KiB of `\xff`) round-trips to all-zero.
- The buffer object's identity is preserved (the caller's reference
  still points at the same `bytearray`).
- Immutable `bytes` is rejected with a typed `TypeError`.
- Non-bytes-like arguments (`str`) are rejected.

`test_bucket_session.py` re-runs cleanly after the wipe-primitive
refactor (the close-zeroises-buffers assertion still passes).

`uv run pytest src/aeat/adapters/persistence/storage/master_key/test_zeroise.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py -x -q` :
18 passed.

`uv run ruff check` clean.
