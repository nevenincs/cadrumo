---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P03.S01'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P03.S01

Introduce the `BucketSession` instance-scoped lock/unlock state object at
`src/aeat/adapters/persistence/storage/master_key/_bucket_session.py` per
ADR-1 section 5 and ADR-2 section 7. The session holds the unlocked KEK
and DEK in `bytearray` buffers keyed to one bucket id, exposes
`open` / `close` / `is_expired` / `touch`, and zeroises every buffer at
close.

- Created: `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`
- Created: `src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py`

## Description

`BucketSession` is the per-bucket replacement for the module-global
`ClassVar` caches that previously survived a bucket switch on
`KeyringMasterKeyProvider` and `FileFallbackMasterKeyProvider`. Each
instance binds to exactly one `bucket_id`; the KEK and DEK are held in
`bytearray` buffers so `close()` can overwrite the bytes in place before
dropping the reference.

The class exposes:

- `BucketSession.open(*, bucket_id, kek, dek, idle_minutes, opened_at)`
  classmethod constructor that copies the supplied KEK/DEK into freshly
  allocated `bytearray` buffers, records the unlock timestamp, and stores
  the configured idle-lock window.
- `session.kek` / `session.dek` read-only properties returning the
  immutable `bytes` view of the live buffer. Reads against a sealed
  session raise `BucketLockedError` (P01.S06).
- `session.touch(now)` resets the idle deadline.
- `session.is_expired(now)` evaluates the idle window without mutating
  state.
- `session.close()` zeroises both buffers in place, then drops the
  references; the session is sealed thereafter.

The `bytearray` zeroisation is best-effort: Python may have made copies
of the KEK/DEK during the `bytes(...)` view materialisations along the
unlock pipeline, and the GC owns the lifetime of those copies. The
contract documented in S05's `_zeroise` helper covers the limit honestly.

## Tests

`test_bucket_session.py` (10 tests; `pytest.mark.unit` +
`pytest.mark.domain_persistence`):

- `open` round-trip: the session exposes the supplied KEK/DEK byte-for-byte.
- `close` zeroises both buffers (we capture the underlying `bytearray`
  via the private attribute before close and assert every byte is `0`
  after close).
- Reads against a sealed session raise `BucketLockedError`.
- `close` is idempotent (a second call is a no-op).
- Two sessions for different bucket ids do not alias their KEK/DEK
  bytearrays (the in-memory `id()` of the buffers differs and a mutation
  to one does not affect the other).
- `is_expired` returns `False` at `opened_at + idle_minutes - 1s` and
  `True` at `opened_at + idle_minutes + 1s`.
- `touch` resets the deadline so a previously-expired window is
  no longer expired after `touch` at a fresh `now`.
- `BucketSession.open` rejects KEK or DEK of the wrong length.
- `BucketSession.open` rejects an empty `bucket_id`.
- A static AST scan asserts that the module has no `ClassVar` typed
  attribute at module scope (regression guard against the ADR-2 §7
  invariant).

`uv run pytest src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py -x -q` :
all green.

`uv run ruff check` and `uv run ty check` clean on the new modules.
