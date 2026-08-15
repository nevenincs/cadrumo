"""Unwrapping a data-encryption key returns a buffer the caller can wipe.

The wipe primitive only overwrites a mutable ``bytearray`` and refuses anything
else, so a key handed back as immutable ``bytes`` is permanently unreachable by
any wipe and survives in memory at the collector's discretion. Both unwrap
paths -- the password/KEK envelope and the session acceleration receipt --
return the live bucket key, so both are on this contract.

The proof deliberately does not stop at "``zeroise`` accepted it". Acceptance
alone is satisfied by a value that was never immutable in the first place and
says nothing about whether anything was overwritten; and asserting only that a
wipe *call succeeded* is vacuous in the opposite direction, because on an
immutable buffer the refusal is what fires. Each test below therefore reads the
buffer AFTER the wipe and asserts the contents changed, which can only pass if
the material was genuinely reachable and genuinely overwritten.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from ...master_key._dek_wrap import unwrap_dek, wrap_dek
from .. import WipeTypeError, zeroise
from .._acceleration_receipt import unwrap_profile_session_dek, wrap_profile_session_dek

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_KEK = bytes(range(32))
_DEK = bytes(range(100, 132))
_BUCKET = "11111111-1111-4111-8111-111111111111"
_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")
_SESSION_ID = UUID("22222222-2222-4222-8222-222222222222")
_ISSUED_AT = datetime(2026, 8, 15, 6, tzinfo=UTC)
_IDLE_DEADLINE = _ISSUED_AT + timedelta(minutes=30)
_ABSOLUTE_DEADLINE = _ISSUED_AT + timedelta(hours=8)


def test_zeroise_refuses_the_immutable_shape_these_tests_rule_out() -> None:
    """The anti-tautology arm: acceptance is a real claim about the type.

    Without this, "``zeroise`` did not raise" could mean the primitive tolerates
    anything. It does not: a regression that returned ``bytes`` from either
    unwrap would raise here rather than pass quietly.
    """
    with pytest.raises(WipeTypeError):
        zeroise(bytes(32))


def test_password_envelope_unwrap_returns_a_buffer_that_wipes() -> None:
    """The KEK-wrapped bucket key comes back mutable, and zeroing it is observable."""
    wrapped = wrap_dek(kek=_KEK, dek=_DEK, bucket_id=_BUCKET)

    recovered = unwrap_dek(kek=_KEK, wrapped=wrapped, bucket_id=_BUCKET)

    assert isinstance(recovered, bytearray)
    assert recovered == _DEK

    zeroise(recovered)

    # The load-bearing assertion: a later read sees the overwrite, so the key
    # material is gone from this buffer rather than merely declared wipeable.
    assert recovered == bytearray(32)
    assert recovered != _DEK


def test_session_receipt_unwrap_returns_a_buffer_that_wipes() -> None:
    """The acceleration receipt's bucket key is wipeable on the same terms.

    This path previously handed back ``bytes`` and its own caller copied the
    result into a ``bytearray`` to wipe it -- which left the original resident
    and unreachable. Returning the buffer directly is what removes that copy.
    """
    record = wrap_profile_session_dek(
        session_key=_KEK,
        dek=_DEK,
        profile_id=_PROFILE_ID,
        session_id=_SESSION_ID,
        custody_generation=1,
        dek_epoch="epoch-1",
        issued_at=_ISSUED_AT,
        idle_deadline=_IDLE_DEADLINE,
        absolute_deadline=_ABSOLUTE_DEADLINE,
    )

    recovered = unwrap_profile_session_dek(session_key=_KEK, record=record)

    assert isinstance(recovered, bytearray)
    assert recovered == _DEK

    zeroise(recovered)

    assert recovered == bytearray(32)
    assert recovered != _DEK
