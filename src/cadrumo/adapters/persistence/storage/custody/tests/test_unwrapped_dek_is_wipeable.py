"""Unwrapping a data-encryption key returns a buffer the caller can wipe.

The wipe primitive only overwrites a mutable ``bytearray`` and refuses anything
else, so a key handed back as immutable ``bytes`` is permanently unreachable by
any wipe and survives in memory at the collector's discretion. The session
acceleration receipt returns the live bucket key, so it is on this contract.

The sibling arm over the retired keystore's KEK-wrap went with that route when
it was deleted; the contract itself is unchanged, and this is now the one
unwrap path there is.

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
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ..acceleration_receipt import (
    delete_profile_session,
    mint_profile_session,
    resume_profile_session,
)
from ..acceleration_receipt_crypto import (
    unwrap_profile_session_dek,
    wrap_profile_session_dek,
)
from ..errors import WipeTypeError
from ..zeroise import zeroise

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_KEK = bytes(range(32))
_DEK = bytes(range(100, 132))
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

    # The load-bearing assertion: a later read sees the overwrite, so the key
    # material is gone from this buffer rather than merely declared wipeable.
    assert recovered == bytearray(32)
    assert recovered != _DEK


def test_the_resume_signature_declares_the_key_it_actually_yields() -> None:
    """The resume must not narrow its wipeable buffer to immutable ``bytes``.

    The unwrap above returns a wipeable buffer, but a caller only benefits if
    the signature it reaches through says so. While this declared ``bytes``,
    the login path did the reasonable thing for that contract and copied into a
    ``bytearray`` before wiping -- which zeroed the copy and left the real key
    resident and beyond any later reach. Narrowing it back would silently
    restore that, and no behavioural test would notice, because the copy makes
    the wipe *look* successful.

    Scoped to this package's own function on purpose. The two application-layer
    hops that carry the same value are held to it by the type checker, since
    ``bytearray`` is not a subtype of ``bytes``; asserting them here would mean
    an adapter test reaching across a layer boundary into private application
    modules to prove something the checker already refuses.
    """
    from typing import get_type_hints

    returned = get_type_hints(resume_profile_session)["return"]
    key_type = returned.__args__[1]

    assert bytearray in key_type.__args__, (
        f"resume_profile_session declares the resumed key as {key_type}; "
        "a caller typed to receive immutable bytes cannot wipe it"
    )


@pytest.mark.os_keychain
def test_the_resumed_key_is_a_buffer_whose_wipe_reaches_the_material(tmp_path: Path) -> None:
    """The resumed key is wipeable in FACT, not merely in its annotation.

    The sibling above reads the declaration, which is the only arm that can run
    on a host with no credential store -- but a declaration is not the property.
    A resume that annotated ``bytearray`` while yielding something else, or
    yielding a buffer holding other material, would satisfy it and still leave
    the real key resident. This arm takes the value the production mint/resume
    pair actually hands back, proves it holds the minted key, wipes it, and
    reads it again.

    Nothing here is substituted: a real receipt is minted through the
    production path, its session key is custodied in the real OS credential
    store, and the resume unwraps it under that key. That is why the case
    carries the keychain marker rather than living in the default lane.
    """
    profile_id = uuid4()
    try:
        mint_profile_session(
            storage_root=tmp_path,
            profile_id=profile_id,
            custody_generation=1,
            dek_epoch="epoch-1",
            dek=_DEK,
            now=_ISSUED_AT,
            idle_minutes=30,
            absolute_minutes=480,
        )

        outcome, resumed = resume_profile_session(
            storage_root=tmp_path,
            profile_id=profile_id,
            custody_generation=1,
            dek_epoch="epoch-1",
            now=_ISSUED_AT + timedelta(minutes=1),
        )

        assert outcome.resumed is True
        assert resumed is not None
        # Not a restatement of the annotation: this is the runtime object, and
        # a narrowed resume would hand back ``bytes`` here regardless of what
        # the signature claimed.
        assert isinstance(resumed, bytearray)
        assert resumed == _DEK

        zeroise(resumed)

        # The load-bearing assertion. It can only hold if the caller's own
        # reference reached the minted material -- which is the whole point of
        # yielding a buffer instead of a copy the caller cannot follow.
        assert resumed == bytearray(32)
        assert resumed != _DEK
    finally:
        delete_profile_session(storage_root=tmp_path, profile_id=profile_id)
