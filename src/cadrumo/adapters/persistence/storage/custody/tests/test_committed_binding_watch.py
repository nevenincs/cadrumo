"""The lifecycle watch re-reads committed custody exactly when a committed file changed.

Real capsules, real Argon2id envelopes and the real committed-material reader;
only the reader is counted.
"""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo_client.contracts.automation_codes import AutomationCustodyError

from ......application.user_profile.access_contracts import ProfileAccessBinding
from ......core.config import Settings
from ......core.hashing import prefixed_digest
from ......core.profile_publication import ProfilePublicationKind
from .. import automation_profile
from ..automation_profile import CommittedProfileBindingWatch, current_automation_profile_binding
from ..capsule import (
    publish_profile_custody_capsule,
    recognize_current_profile_capsule,
    replace_committed_profile_custody_envelope,
)
from ..capsule_records import ProfileCustodyPasswordMaterial
from ..envelope import create_profile_custody_password_envelope
from ..records import PROFILE_CUSTODY_ENVELOPE_FILENAME, ProfileCustodyKdfParameters, parse_profile_custody_envelope
from ..sentinel import create_profile_custody_sentinel

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("0b6f3c5e-2d41-4a8f-9e07-5c3a1d9b7e24")
_INSTALLATION_ID = UUID("7e2d9a41-63c5-4b0f-8a1e-2f5b9c0d4e63")
_OWNER = "synthetic-owner"
_DEK = bytes(range(32))
_EPOCH = base64.b64encode(b"w" * 16).decode("ascii")
_FIRST = "watch " + "password" + " one"
_SECOND = "watch " + "password" + " two"


def _kdf(salt: bytes) -> ProfileCustodyKdfParameters:
    return ProfileCustodyKdfParameters(
        algorithm="argon2id",
        version=19,
        memory_mib=19,
        iterations=2,
        parallelism=1,
        salt_b64=base64.b64encode(salt).decode("ascii"),
        output_bytes=32,
    )


def _publish(settings: Settings) -> None:
    envelope = create_profile_custody_password_envelope(
        profile_id=_PROFILE_ID, password=_FIRST, dek=_DEK, dek_epoch=_EPOCH, kdf=_kdf(b"a" * 16), settings=settings
    )
    publish_profile_custody_capsule(
        profile_id=_PROFILE_ID,
        transaction_id=uuid4(),
        publication_kind=ProfilePublicationKind.ENROLL,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        data_files={},
        settings=settings,
    )


def _envelope_path(settings: Settings) -> Path:
    capsule = recognize_current_profile_capsule(_PROFILE_ID, settings=settings)
    assert capsule is not None
    return capsule / "custody" / PROFILE_CUSTODY_ENVELOPE_FILENAME


def _rotate(settings: Settings) -> None:
    path = _envelope_path(settings)
    committed = path.read_bytes()
    parent = parse_profile_custody_envelope(committed)
    successor = create_profile_custody_password_envelope(
        profile_id=_PROFILE_ID,
        password=_SECOND,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(b"b" * 16),
        password_generation=parent.password_generation + 1,
        previous_envelope_digest=parent.self_digest,
        settings=settings,
    )
    replace_committed_profile_custody_envelope(
        _PROFILE_ID, successor.canonical_json_bytes(), expected_sha256=prefixed_digest(committed), settings=settings
    )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Settings, CommittedProfileBindingWatch, list[UUID]]:
    settings = Settings(cadrumo_storage_root=tmp_path / "state")
    _publish(settings)
    reads: list[UUID] = []
    load = automation_profile.load_committed_profile_password_material

    def counted(
        profile_id: UUID, *, settings: Settings | None = None, root: Path | None = None
    ) -> ProfileCustodyPasswordMaterial:
        reads.append(profile_id)
        return load(profile_id, settings=settings, root=root)

    monkeypatch.setattr(automation_profile, "load_committed_profile_password_material", counted)
    watch = CommittedProfileBindingWatch(
        profile_id=_PROFILE_ID, installation_id=_INSTALLATION_ID, os_owner_id=_OWNER, root=tmp_path / "state"
    )
    return settings, watch, reads


def _full_read(settings: Settings) -> ProfileAccessBinding:
    return current_automation_profile_binding(
        profile_id=_PROFILE_ID,
        installation_id=_INSTALLATION_ID,
        os_owner_id=_OWNER,
        root=settings.cadrumo_storage_root,
    )


def test_unchanged_custody_is_answered_without_another_read(
    world: tuple[Settings, CommittedProfileBindingWatch, list[UUID]],
) -> None:
    settings, watch, reads = world
    first = watch.current()
    assert watch.current() == first == _full_read(settings)
    assert reads.count(_PROFILE_ID) == 2, "one watched read and the independent full read"


def test_a_committed_rotation_is_read_on_the_next_look(
    world: tuple[Settings, CommittedProfileBindingWatch, list[UUID]],
) -> None:
    settings, watch, reads = world
    before = watch.current()
    _rotate(settings)
    after = watch.current()
    assert after.custody_generation == before.custody_generation + 1
    assert after == _full_read(settings)
    assert len(reads) == 3


def test_removed_custody_is_refused_and_nothing_stale_is_kept(
    world: tuple[Settings, CommittedProfileBindingWatch, list[UUID]],
) -> None:
    settings, watch, reads = world
    watch.current()
    path = _envelope_path(settings)
    committed = path.read_bytes()
    path.unlink()
    with pytest.raises(AutomationCustodyError):
        watch.current()
    path.write_bytes(committed)
    assert watch.current() == _full_read(settings)
    assert len(reads) == 4
