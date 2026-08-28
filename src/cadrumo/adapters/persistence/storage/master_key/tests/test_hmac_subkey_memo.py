"""The session-scoped HMAC sub-key memo must be exact, bucket-bound, and mortal.

The keyed-lookup digest recipe derives a per-consumer HKDF sub-key from the
session DEK before HMAC-ing its material. The derivation depends only on
``(DEK, context)``, so :meth:`BucketSession.hmac_subkey` memoises it for the
session's life. These tests pin the three properties that make the memo safe:
the cached value is byte-identical to the un-memoised derivation, two
sessions for two buckets never share an entry, and sealing the session both
refuses further reads and drops the cached material.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ...bucket import BucketLockedError
from ...crypto.aead import derive_key
from .._bucket_session import BucketSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "bafde89c-041e-4756-882b-933aaf16cad8"  # was '11111111-1111-1111-1111-111111111111'
_OTHER_BUCKET_ID = "05d17100-b346-429d-a760-a0fdedcf8623"  # was '22222222-2222-2222-2222-222222222222'
_KEK = b"k" * 32
_DEK = b"d" * 32
_OTHER_DEK = b"e" * 32
_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_CONTEXT = b"cadrumo.column.hashed_lookup.v1"
_OTHER_CONTEXT = b"cadrumo.tests.other_context.v1"


def _session(bucket_id: str = _BUCKET_ID, dek: bytes = _DEK) -> BucketSession:
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=_KEK,
        dek=dek,
        idle_minutes=30,
        opened_at=_NOW,
    )


def test_memoised_subkey_is_byte_identical_to_the_direct_derivation() -> None:
    """The memo is a cache, never a second derivation recipe."""
    session = _session()
    direct = derive_key(key_material=_DEK, salt=b"", context=_CONTEXT)
    assert session.hmac_subkey(_CONTEXT) == direct


def test_second_call_is_served_from_the_memo() -> None:
    """One derivation per (session, context); the repeat returns the cached bytes."""
    session = _session()
    first = session.hmac_subkey(_CONTEXT)
    assert session.hmac_subkey(_CONTEXT) is first
    assert len(session._hmac_subkeys) == 1


def test_distinct_contexts_yield_independent_entries() -> None:
    session = _session()
    assert session.hmac_subkey(_CONTEXT) != session.hmac_subkey(_OTHER_CONTEXT)
    assert len(session._hmac_subkeys) == 2


def test_two_buckets_never_share_an_entry() -> None:
    """The memo is keyed by the session's own DEK: no cross-bucket leakage."""
    one = _session()
    other = _session(bucket_id=_OTHER_BUCKET_ID, dek=_OTHER_DEK)
    assert one.hmac_subkey(_CONTEXT) != other.hmac_subkey(_CONTEXT)


def test_sealed_session_refuses_and_drops_cached_material() -> None:
    """Close both refuses further derivations and clears the memo."""
    session = _session()
    session.hmac_subkey(_CONTEXT)
    session.close()
    assert session._hmac_subkeys == {}
    with pytest.raises(BucketLockedError):
        session.hmac_subkey(_CONTEXT)
