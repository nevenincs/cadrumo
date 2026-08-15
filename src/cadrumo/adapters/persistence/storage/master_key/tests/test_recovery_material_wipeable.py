"""Unwrapped master-key material comes back in a buffer zeroise can reach.

The substrate's wipe primitive only operates on a mutable ``bytearray``; it
refuses anything else by design. Key material held as immutable ``bytes`` is
therefore permanently unreachable by any wipe, and survives in memory
entirely at the garbage collector's discretion.

This module covers the master-key wrapping half only. The BIP-39 codec that
mints the recovery key moved one level up to
:mod:`adapters.persistence.storage._recovery_key`, and its own wipe contract
is pinned beside it; the mint call below is a collaborator here, not the
subject.

The refusal test is what gives the assertion its teeth -- it proves
``zeroise`` genuinely rejects the immutable shapes, so a regression back to
``bytes`` fails this module rather than passing it vacuously.
"""

from __future__ import annotations

import pytest

from ..._recovery_key import generate_recovery_key
from ...custody import WipeTypeError, zeroise
from .._recovery import unwrap_master_key, wrap_master_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_DEK = bytes(range(32))


def test_zeroise_refuses_immutable_bytes_and_str() -> None:
    """The wipe primitive cannot reach immutable material.

    The anti-tautology proof for the assertion below: it establishes that
    "``zeroise`` accepted this buffer" is a real claim about the value's
    type, not a vacuous one.
    """
    with pytest.raises(WipeTypeError):
        zeroise(bytes(32))
    with pytest.raises(WipeTypeError):
        zeroise("abandon abandon abandon")


def test_unwrap_master_key_returns_a_buffer_zeroise_accepts() -> None:
    """The unwrapped master key comes back wipeable."""
    recovery_key = generate_recovery_key()
    wrapped = wrap_master_key(master_key=_DEK, recovery_key=recovery_key)

    recovered = unwrap_master_key(wrapped=wrapped, recovery_key_bytes=recovery_key.raw)

    assert isinstance(recovered, bytearray)
    assert recovered == _DEK
    zeroise(recovered)
    assert recovered == bytearray(32)
