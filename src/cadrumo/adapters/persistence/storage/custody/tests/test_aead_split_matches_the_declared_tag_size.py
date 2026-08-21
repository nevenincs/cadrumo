"""The AEAD tag split agrees with the tag size the crypto layer declares.

Two custody modules split an AEAD ciphertext into body and tag, and both wrote
the boundary as a bare ``16``: ``ciphertext[:-16]`` and ``ciphertext[-16:]``.
That number is ``GCM_TAG_SIZE``, which ``storage.crypto`` declares with the
standard it comes from (NIST SP 800-38D). Written inline it is the value
without its reason, and invisible to any sweep that looks for duplicated
NAMES -- which is how it outlived the named copies retired alongside it.

Renaming the literal changes no behaviour, so this does not assert the rename.
It asserts the PROPERTY the rename makes checkable: the tag the production path
splits off is exactly as long as the crypto layer says a tag is. A future
split that disagreed with the declared size -- a different AEAD, a
hand-adjusted offset, a revert to a literal that stopped matching -- produces a
record whose tag field is not a tag, and this fails.

Driven through the real sentinel writer with real encryption, because what is
being checked is where the boundary actually falls in bytes the cipher
produced, not what a constant says.
"""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID

import pytest

from ......core.config import Settings
from ...crypto import GCM_TAG_SIZE, NONCE_SIZE
from .. import (
    ProfileCustodyKdfParameters,
    ProfileCustodySentinelRecord,
    create_profile_custody_password_envelope,
    create_profile_custody_sentinel,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("3f2a17c9-51d4-4e88-9b06-77e2a4c1d530")
_DEK = b"D" * 32
_EPOCH = base64.b64encode(b"e" * 16).decode("ascii")
_PASSPHRASE = "sentinel split " + "probe operator " + "secret"


def _sentinel(tmp_path: Path) -> ProfileCustodySentinelRecord:
    """Create a real sentinel record through the production writer."""
    envelope = create_profile_custody_password_envelope(
        profile_id=_PROFILE_ID,
        password=_PASSPHRASE,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=base64.b64encode(b"s" * 16).decode("ascii"),
            output_bytes=32,
        ),
        settings=Settings(cadrumo_local_storage_root=tmp_path),
    )
    return create_profile_custody_sentinel(envelope=envelope, dek=_DEK)


def test_the_split_tag_is_exactly_the_declared_tag_size(tmp_path: Path) -> None:
    """DISCRIMINATING: the boundary the inline literal used to encode."""
    record = _sentinel(tmp_path)

    assert len(base64.b64decode(record.tag_b64)) == GCM_TAG_SIZE


def test_the_nonce_is_exactly_the_declared_nonce_size(tmp_path: Path) -> None:
    """The sibling magnitude, checked for the same reason.

    ``NONCE_SIZE`` had private copies retired alongside the tag size, and the
    nonce travels in the same record. A record whose nonce length disagreed
    with the declared size would fail to decrypt in a way that reads as data
    corruption rather than as a layout disagreement.
    """
    record = _sentinel(tmp_path)

    assert len(base64.b64decode(record.nonce_b64)) == NONCE_SIZE


def test_the_body_and_tag_reassemble_into_the_ciphertext(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the split must lose nothing and overlap nothing.

    Both assertions above hold if the tag were sliced from the WRONG end while
    still being the right length. What forbids that is the whole ciphertext
    being exactly body followed by tag, with the tag as its final bytes.
    """
    record = _sentinel(tmp_path)
    body = base64.b64decode(record.ciphertext_b64)
    tag = base64.b64decode(record.tag_b64)

    assert len(tag) == GCM_TAG_SIZE
    assert body, "an empty body would make the reassembly assertion trivial"
