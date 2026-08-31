"""The master key stays immutable, and the reason is ownership rather than habit.

The two DEK unwraps return wipeable ``bytearray`` buffers, so the obvious next
step is to do the same for the master key and the key-encryption key derived
from it. This module records why that is refused, and pins the property the
refusal depends on, so the question is closed by a failing test rather than by
anyone remembering the argument.

A caller may only wipe key material it OWNS. An unwrapped DEK is minted for one
caller and handed over outright, so wiping it is that caller's business and
returning immutable ``bytes`` there was a real defect: the caller was left
unable to clean what it exclusively held.

Master-key material is not owned that way. ``UnsecuredMasterKeyProvider``
returns a module-level constant, so every consumer receives *the same object*;
the keychain provider resolves afresh per call, but the protocol cannot promise
that on behalf of implementations that do not. Were the contract mutable, one
consumer wiping what it received would zero the key for every later caller of a
sharing provider -- silently, and with no way for the victim to attribute it.
Immutability is what makes returning a shared object safe.

That also explains a defensive copy that would otherwise look like the defect
found on the session-receipt path. ``BucketSession.open`` copies the KEK into a
mutable buffer and zeroes it on close. There the copy is CORRECT, precisely
because the session does not own the key it was handed and must not wipe the
caller's object. Same shape, opposite verdict, and the discriminator is
ownership rather than mutability.
"""

from __future__ import annotations

import pytest

from ...custody.errors import WipeTypeError
from ...custody.zeroise import zeroise
from ..master_key import UnsecuredMasterKeyProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_a_provider_hands_the_same_object_to_every_consumer() -> None:
    """The sharing that makes mutable master-key material unsafe.

    This is the load-bearing fact behind the ruling. If it ever stops being
    true for every provider, the ownership argument weakens and the question of
    wipeable master-key material is worth reopening.
    """
    provider = UnsecuredMasterKeyProvider()

    first = provider.get_master_key()
    second = provider.get_master_key()

    assert first is second, "a shared object is what makes a consumer-side wipe everyone's problem"


def test_master_key_material_cannot_be_wiped_by_a_consumer() -> None:
    """The contract keeps one consumer from zeroing another consumer's key.

    Not a claim that master-key material never needs clearing -- it is a claim
    about WHO may clear it. A holder that owns its own copy can wipe that copy;
    what it cannot do is reach the object the provider shares.
    """
    provider = UnsecuredMasterKeyProvider()

    key = provider.get_master_key()

    with pytest.raises(WipeTypeError):
        zeroise(key)

    # Non-vacuity: the refusal is about this value's type, not a primitive that
    # rejects everything. A copy the consumer owns wipes normally, which is the
    # sanctioned way to clear held material.
    owned_copy = bytearray(key)
    zeroise(owned_copy)
    assert owned_copy == bytearray(len(key))
    assert provider.get_master_key() == key, "wiping an owned copy must not disturb the shared key"
