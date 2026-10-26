"""Read the keychain-held sign-in proof a frontend presents to the runtime, and nothing more.

This is a frontend's whole share of a stored sign-in: the receipt locator and
the keychain entry it names. It reads no custody envelope, never unwraps or
decrypts the receipt, and deletes neither half. The runtime verifies the proof
and deletes a receipt it refuses. The proof is a secret capability for one
protected frame, never a public result.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import (
    borrow_profile_session_key,
    probe_profile_session_keychain,
)
from cadrumo.adapters.persistence.storage.custody.zeroise import zeroise
from cadrumo.core.paths import effective_storage_root
from cadrumo.core.profile_session import KeychainUnavailability, ProfileSessionRefusalReason

from ..contracts.sign_in_outcomes import ProfileReceiptRefusedError


@contextmanager
def borrow_receipt_proof(*, profile_id: UUID, storage_root: Path | None = None) -> Generator[bytearray]:
    """Lend the proof the profile's receipt names, wiping its buffer on every exit.

    Raises:
        ProfileReceiptRefusedError: No proof could be read: the receipt is
            absent, unreadable or names no keychain entry, or this process
            cannot use the keychain. The refusal names which.
    """
    outcome, key = borrow_profile_session_key(storage_root=effective_storage_root(storage_root), profile_id=profile_id)
    if not outcome.resumed or key is None:
        if key is not None:
            zeroise(key)
        raise ProfileReceiptRefusedError(
            outcome.refusal or ProfileSessionRefusalReason.ABSENT, binding=outcome.binding, keychain=outcome.keychain
        )
    try:
        yield key
    finally:
        zeroise(key)


def keychain_unavailability() -> KeychainUnavailability | None:
    """Return why this process cannot keep or present a sign-in, or ``None`` when it can.

    The probe reads only an account no receipt names, so it changes nothing.
    """
    return probe_profile_session_keychain()
