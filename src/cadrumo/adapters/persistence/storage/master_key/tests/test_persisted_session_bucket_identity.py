"""The persisted profile session binds the canonical bucket identity.

The bucket id is load-bearing three times over in this module: it is bound
into the AEAD associated data of the session-wrapped DEK, it is stored on the
record whose own fields ``unwrap`` recomputes that AAD from, and it is the
OS-keychain *account* under which the session key is custodied. All three
accepted any non-blank string.

That split the identity in the two ways this module pins. An id the storage
layer refuses outright -- whitespace-only, or past the 128-character cap --
still minted a real session record and a real keychain entry. And a
whitespace-wrapped spelling of a *valid* id produced artefacts addressable
only under that spelling: the record could not be unwrapped from the canonical
spelling, and a key stored under one spelling was invisible to a lookup under
the other, surfacing as an unexplained resume failure rather than as the
identity error it is.

Canonicalizing at the AEAD boundary is what makes the record self-consistent
at all: the record's ``bucket_id`` is normalized by its type, and ``unwrap``
rebuilds the AAD from that stored field -- so a wrap that bound the caller's
raw spelling would produce a record nothing could ever open. The
``test_a_whitespace_wrapped_id_round_trips`` case is the one that notices.

Real AES-256-GCM over real random keys; the keychain-touching surfaces are not
exercised here because they require an OS credential store this process may
not reach, so their canonicalization is asserted at the refusal boundary only.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import TypeAdapter, ValidationError

from ......core.config import SecretStoreBackend
from ......core.identity import BucketId
from ...errors import DecryptionError, EncryptionError, StorageValidationError
from .._persisted_session import (
    PersistedProfileSession,
    delete_profile_session_key,
    unwrap_profile_session_dek,
    wrap_profile_session_dek,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_CANONICAL_BUCKET = "55555555-5555-4555-8555-555555555555"
_OTHER_BUCKET = "44444444-4444-4444-8444-444444444444"
#: Refused by :data:`BucketId`: blank after stripping, and over the 128 cap.
_NONCANONICAL = ("", "   ", "\t\n", "b" * 129)
_WHITESPACE_SPELLINGS = (
    f"  {_CANONICAL_BUCKET}  ",
    f"\t{_CANONICAL_BUCKET}",
    f"{_CANONICAL_BUCKET}\n",
)

_AUTHENTICATED_AT = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_IDLE_DEADLINE = _AUTHENTICATED_AT + timedelta(minutes=15)
_ABSOLUTE_DEADLINE = _AUTHENTICATED_AT + timedelta(hours=8)

_bucket_adapter: TypeAdapter[str] = TypeAdapter(BucketId)


def _bucket_id_accepts(value: str) -> bool:
    try:
        _bucket_adapter.validate_python(value)
    except ValidationError:
        return False
    return True


def _wrap(bucket_id: str, *, session_key: bytes, dek: bytes) -> PersistedProfileSession:
    return wrap_profile_session_dek(
        session_key=session_key,
        dek=dek,
        bucket_id=bucket_id,
        backend_kind=SecretStoreBackend.KEYRING,
        authenticated_at=_AUTHENTICATED_AT,
        idle_deadline=_IDLE_DEADLINE,
        absolute_deadline=_ABSOLUTE_DEADLINE,
    )


def _keys() -> tuple[bytes, bytes]:
    return secrets.token_bytes(32), secrets.token_bytes(32)


@pytest.mark.parametrize("bucket_id", _NONCANONICAL)
def test_storage_identity_authority_refuses_these_values(bucket_id: str) -> None:
    """Positive control on the premise: these are not bucket identities."""
    assert not _bucket_id_accepts(bucket_id)
    assert _bucket_id_accepts(_CANONICAL_BUCKET)


@pytest.mark.parametrize("bucket_id", _NONCANONICAL)
def test_wrap_refuses_a_noncanonical_bucket_identity(bucket_id: str) -> None:
    """No session record is minted for an identity storage would refuse."""
    session_key, dek = _keys()
    with pytest.raises(EncryptionError):
        _wrap(bucket_id, session_key=session_key, dek=dek)


@pytest.mark.parametrize("bucket_id", _NONCANONICAL)
def test_the_record_model_refuses_a_noncanonical_bucket_identity(bucket_id: str) -> None:
    """The persisted record cannot even represent a noncanonical identity.

    Asserted separately from the wrap refusal: the record is also constructed
    when a session document is read back from disk, so a check placed only in
    ``wrap`` would leave the load path able to materialise one.
    """
    with pytest.raises(ValidationError):
        PersistedProfileSession(
            schema_version=1,
            bucket_id=bucket_id,
            backend_kind=SecretStoreBackend.KEYRING,
            authenticated_at=_AUTHENTICATED_AT,
            idle_deadline=_IDLE_DEADLINE,
            absolute_deadline=_ABSOLUTE_DEADLINE,
            nonce=b"n" * 12,
            ciphertext=b"c" * 32,
            tag=b"t" * 16,
        )


@pytest.mark.parametrize("bucket_id", _NONCANONICAL)
def test_keychain_deletion_refuses_a_noncanonical_bucket_identity(bucket_id: str) -> None:
    """The keychain account name is canonicalized before it addresses anything.

    Deletion is the one keychain surface that reaches its validation before
    touching the OS credential store, so it is the surface where this can be
    asserted without a live keychain.
    """
    with pytest.raises(StorageValidationError):
        delete_profile_session_key(bucket_id=bucket_id)


@pytest.mark.parametrize("spelling", _WHITESPACE_SPELLINGS)
def test_a_whitespace_wrapped_id_round_trips(spelling: str) -> None:
    """A record wrapped under an odd spelling is still openable.

    The discriminating case. ``unwrap`` rebuilds the AAD from the record's own
    ``bucket_id``, which the model normalizes -- so binding the caller's raw
    spelling at wrap time would produce a record that nothing, including its
    own unwrap path, could ever open. Canonicalizing before composing the AAD
    is what makes wrap and unwrap agree.
    """
    session_key, dek = _keys()

    record = _wrap(spelling, session_key=session_key, dek=dek)

    assert record.bucket_id == _CANONICAL_BUCKET
    assert unwrap_profile_session_dek(session_key=session_key, record=record) == dek


def test_a_canonical_record_still_refuses_a_foreign_bucket() -> None:
    """Normalization collapses spellings of one bucket, never two buckets.

    Without this the round-trip above could be satisfied by dropping the
    bucket id from the associated data entirely.
    """
    session_key, dek = _keys()
    record = _wrap(_CANONICAL_BUCKET, session_key=session_key, dek=dek)
    foreign = record.model_copy(update={"bucket_id": _OTHER_BUCKET})

    with pytest.raises(DecryptionError):
        unwrap_profile_session_dek(session_key=session_key, record=foreign)


def test_valid_bucket_round_trips() -> None:
    """Positive control: the ordinary path is untouched."""
    session_key, dek = _keys()
    record = _wrap(_CANONICAL_BUCKET, session_key=session_key, dek=dek)

    assert record.bucket_id == _CANONICAL_BUCKET
    assert unwrap_profile_session_dek(session_key=session_key, record=record) == dek
