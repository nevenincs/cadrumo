"""Real filesystem contracts for the committed-capsule lifecycle surface."""

from __future__ import annotations

from base64 import b64encode
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodySentinelRecord,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
)
from ....core import read_pointer
from ....domain.user_profile import UserProfileRecord
from .._capsule_record import PROFILE_RECORD_DATA_FILENAME, ProfileRecordSession
from .._lifecycle import ProfileCapsuleLifecycle
from .._profile_record_repository import ProfileRecordRepository, bound_profile_record_session
from .._profile_repository import CommittedProfileRepository, ProfileNotFoundError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("327b296d-8377-4be0-b13a-ca4d8f692e1d")


def _current_capsule_input() -> tuple[ProfileCustodyEnvelope, ProfileCustodySentinelRecord, dict[str, bytes], bytes]:
    envelope = ProfileCustodyEnvelope.create(
        profile_id=_PROFILE_ID,
        password_generation=1,
        dek_epoch=b64encode(b"e" * 16).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=b64encode(b"c" * 32).decode("ascii"),
            tag_b64=b64encode(b"t" * 16).decode("ascii"),
        ),
    )
    dek = bytes(range(32))
    return (
        envelope,
        create_profile_custody_sentinel(envelope=envelope, dek=dek),
        {"state/payload.bin": b"x"},
        dek,
    )


def test_lifecycle_projects_only_its_committed_capsule_and_owns_selection(tmp_path) -> None:
    envelope, sentinel, data_files, dek = _current_capsule_input()
    service = ProfileCapsuleLifecycle(root=tmp_path)

    record_session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    created = service.create(
        label="Capsule operator",
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files=data_files,
        initial_record=UserProfileRecord(profile_id=str(_PROFILE_ID)),
        record_session=record_session,
    )

    assert created.profile_id == str(_PROFILE_ID)
    assert created.label == "Capsule operator"
    assert CommittedProfileRepository(root=tmp_path).list() == (created,)
    assert service.select("Capsule operator") == created
    pointer = read_pointer(tmp_path)
    assert pointer is not None
    assert pointer.bucket_id == str(_PROFILE_ID)
    assert (tmp_path / "buckets" / str(_PROFILE_ID) / "data" / PROFILE_RECORD_DATA_FILENAME).is_file()
    with bound_profile_record_session(record_session):
        assert ProfileRecordRepository.for_current_session(_PROFILE_ID, root=tmp_path).load(_PROFILE_ID).profile_id == str(
            _PROFILE_ID
        )


def test_repository_refuses_retired_or_uncommitted_bucket_directories(tmp_path) -> None:
    retired = tmp_path / "buckets" / str(_PROFILE_ID)
    retired.mkdir(parents=True)
    (retired / "manifest.toml").write_text("label = 'Retired'\n", encoding="utf-8")

    repository = CommittedProfileRepository(root=tmp_path)

    assert repository.list() == ()
    with pytest.raises(ProfileNotFoundError):
        repository.load(_PROFILE_ID)
