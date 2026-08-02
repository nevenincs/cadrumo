"""DEK wrapping binds the canonical bucket identity, not the caller's spelling.

The AEAD associated data pins a wrapped DEK to one bucket, so the identity it
composes must be the same identity the storage layer recognises. Before the
canonicalization the wrap surface accepted any non-empty string, which split
the two apart in two ways this module pins:

- An identity the storage layer refuses outright -- whitespace-only, or longer
  than the 128-character cap -- still produced valid, unwrappable ciphertext.
- A whitespace-wrapped spelling of a *valid* id produced ciphertext reachable
  only under that odd spelling: AES-GCM compares AAD bytes, so the two
  spellings named two different buckets to the cipher and one identical bucket
  to everything else.

Every assertion runs real AES-256-GCM over real random keys. Nothing is
mocked, and the canonical-equivalence test is the discriminating one: a fix
that merely rejected malformed input without normalizing the valid case would
leave it red.
"""

from __future__ import annotations

import secrets

import pytest
from pydantic import TypeAdapter, ValidationError

from ......core.identity import BucketId
from ...errors import DecryptionError, EncryptionError
from .._dek_wrap import unwrap_dek, wrap_dek

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_CANONICAL_BUCKET = "77777777-7777-4777-8777-777777777777"
#: Refused by :data:`BucketId`: blank after stripping, and over the 128 cap.
_NONCANONICAL = ("", "   ", "\t\n", "b" * 129)

_bucket_adapter: TypeAdapter[str] = TypeAdapter(BucketId)


def _keys() -> tuple[bytes, bytes]:
    return secrets.token_bytes(32), secrets.token_bytes(32)


def _bucket_id_accepts(value: str) -> bool:
    try:
        _bucket_adapter.validate_python(value)
    except ValidationError:
        return False
    return True


@pytest.mark.parametrize("bucket_id", _NONCANONICAL)
def test_storage_identity_authority_refuses_these_values(bucket_id: str) -> None:
    """Positive control on the premise: these are not bucket identities.

    Without this the refusals below would prove only that *something* was
    rejected, not that the wrap surface now agrees with the storage layer.
    """
    assert not _bucket_id_accepts(bucket_id)
    assert _bucket_id_accepts(_CANONICAL_BUCKET)


@pytest.mark.parametrize("bucket_id", _NONCANONICAL)
def test_wrap_refuses_a_noncanonical_bucket_identity(bucket_id: str) -> None:
    """No ciphertext is minted for an identity storage would refuse."""
    kek, dek = _keys()
    with pytest.raises(EncryptionError):
        wrap_dek(kek=kek, dek=dek, bucket_id=bucket_id)


@pytest.mark.parametrize("bucket_id", _NONCANONICAL)
def test_unwrap_refuses_a_noncanonical_bucket_identity(bucket_id: str) -> None:
    """The read side refuses the same identities the write side does.

    Asserted separately because the two compose their AAD through the same
    helper but validate independently of one another; a fix applied to only
    one side would leave a surface that can open what it cannot create.
    """
    kek, dek = _keys()
    wrapped = wrap_dek(kek=kek, dek=dek, bucket_id=_CANONICAL_BUCKET)
    with pytest.raises(EncryptionError):
        unwrap_dek(kek=kek, wrapped=wrapped, bucket_id=bucket_id)


@pytest.mark.parametrize(
    "spelling",
    [f"  {_CANONICAL_BUCKET}  ", f"\t{_CANONICAL_BUCKET}", f"{_CANONICAL_BUCKET}\n"],
)
def test_whitespace_variants_open_ciphertext_wrapped_under_the_canonical_id(spelling: str) -> None:
    """Two spellings of one bucket are one bucket to the cipher.

    The discriminating case. A wrap that merely *validated* without
    normalizing would still bind the caller's raw bytes, stranding the DEK
    under a spelling no other layer can reproduce.
    """
    kek, dek = _keys()
    wrapped_canonically = wrap_dek(kek=kek, dek=dek, bucket_id=_CANONICAL_BUCKET)
    assert unwrap_dek(kek=kek, wrapped=wrapped_canonically, bucket_id=spelling) == dek

    wrapped_oddly = wrap_dek(kek=kek, dek=dek, bucket_id=spelling)
    assert unwrap_dek(kek=kek, wrapped=wrapped_oddly, bucket_id=_CANONICAL_BUCKET) == dek


def test_a_different_bucket_still_cannot_open_the_wrapped_dek() -> None:
    """Canonicalization must not weaken the binding it exists to enforce.

    Normalizing collapses whitespace variants of ONE identity; it must not
    collapse two distinct identities. Without this the test above could be
    satisfied by dropping the bucket from the AAD entirely.
    """
    kek, dek = _keys()
    wrapped = wrap_dek(kek=kek, dek=dek, bucket_id=_CANONICAL_BUCKET)
    other = "66666666-6666-4666-8666-666666666666"
    with pytest.raises(DecryptionError):
        unwrap_dek(kek=kek, wrapped=wrapped, bucket_id=other)


def test_valid_bucket_round_trips() -> None:
    """Positive control: the ordinary path is untouched."""
    kek, dek = _keys()
    wrapped = wrap_dek(kek=kek, dek=dek, bucket_id=_CANONICAL_BUCKET)
    assert unwrap_dek(kek=kek, wrapped=wrapped, bucket_id=_CANONICAL_BUCKET) == dek
