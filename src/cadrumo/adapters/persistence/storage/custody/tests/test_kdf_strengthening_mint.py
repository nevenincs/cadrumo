"""A measured KDF point mints a successor envelope only when it strictly strengthens the one it replaces."""

from __future__ import annotations

import base64
from pathlib import Path
from secrets import token_bytes
from uuid import UUID

import pytest

from ......application.user_profile.custody_ports import (
    create_profile_custody_registration_material,
    unlock_profile_custody_password,
)
from ......application.user_profile.kdf_strength import ProfileKdfStrength
from ......core.config import override_settings
from .. import kdf_supervision
from ..kdf_strengthening import ProfileKdfPointRefusedError
from ..kdf_supervision import ProfileCustodyKdfResources
from ..records import ProfileCustodyEnvelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("3b8e2a51-7f0c-4c2a-9d33-6a0b1f5e8c71")
_CREDENTIAL = "strengthening mint passphrase clearing the verifier minimum"
_EPOCH = base64.b64encode(b"strengthen-epoch").decode("ascii")


def _committed(dek: bytes) -> ProfileCustodyEnvelope:
    """Mint a first envelope without measuring, so it holds the fixed fallback point."""
    material = create_profile_custody_registration_material(
        profile_id=_PROFILE_ID, password=_CREDENTIAL, dek=dek, dek_epoch=_EPOCH, salt=token_bytes(16)
    )
    envelope = material.envelope
    assert isinstance(envelope, ProfileCustodyEnvelope)
    assert (envelope.kdf.memory_mib, envelope.kdf.iterations, envelope.kdf.parallelism) == (64, 3, 1)
    return envelope


def test_a_strictly_stronger_point_mints_the_successor_over_the_same_key(tmp_path: Path) -> None:
    dek = token_bytes(32)
    with override_settings(cadrumo_storage_root=tmp_path, cadrumo_profile_kdf_measure_calibration=False):
        committed = _committed(dek)
        successor = create_profile_custody_registration_material(
            profile_id=_PROFILE_ID,
            password=_CREDENTIAL,
            dek=dek,
            dek_epoch=_EPOCH,
            salt=token_bytes(16),
            predecessor=committed,
            strength=ProfileKdfStrength(memory_mib=64, iterations=4, parallelism=1),
        )
        envelope = successor.envelope
        assert isinstance(envelope, ProfileCustodyEnvelope)
        assert (envelope.kdf.memory_mib, envelope.kdf.iterations, envelope.kdf.parallelism) == (64, 4, 1)
        assert envelope.password_generation == committed.password_generation + 1
        assert envelope.previous_envelope_digest == committed.self_digest
        assert envelope.dek_epoch == committed.dek_epoch
        assert envelope.kdf.salt_b64 != committed.kdf.salt_b64
        assert unlock_profile_custody_password(successor, password=_CREDENTIAL).dek == dek


@pytest.mark.parametrize(
    "strength",
    [
        pytest.param(ProfileKdfStrength(memory_mib=64, iterations=3, parallelism=1), id="equal"),
        pytest.param(ProfileKdfStrength(memory_mib=64, iterations=3, parallelism=2), id="more-lanes-only"),
        pytest.param(ProfileKdfStrength(memory_mib=32, iterations=10, parallelism=1), id="less-memory"),
        pytest.param(ProfileKdfStrength(memory_mib=19, iterations=2, parallelism=1), id="below-floor"),
        pytest.param(ProfileKdfStrength(memory_mib=64, iterations=5, parallelism=1), id="off-grid"),
    ],
)
def test_a_point_that_would_not_strengthen_is_refused(tmp_path: Path, strength: ProfileKdfStrength) -> None:
    dek = token_bytes(32)
    with override_settings(cadrumo_storage_root=tmp_path, cadrumo_profile_kdf_measure_calibration=False):
        committed = _committed(dek)
        with pytest.raises(ProfileKdfPointRefusedError):
            create_profile_custody_registration_material(
                profile_id=_PROFILE_ID,
                password=_CREDENTIAL,
                dek=dek,
                dek_epoch=_EPOCH,
                salt=token_bytes(16),
                predecessor=committed,
                strength=strength,
            )


def test_a_point_that_no_longer_fits_this_host_is_refused_without_a_custody_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Memory measured earlier may be gone at sign-in; the strengthening is then skipped, not failed."""
    dek = token_bytes(32)
    with override_settings(cadrumo_storage_root=tmp_path, cadrumo_profile_kdf_measure_calibration=False):
        committed = _committed(dek)
        monkeypatch.setattr(
            kdf_supervision,
            "profile_kdf_resources",
            lambda: ProfileCustodyKdfResources(available_memory_bytes=96 * 1024 * 1024, cpu_count=1),
        )
        with pytest.raises(ProfileKdfPointRefusedError, match="does not fit this host"):
            create_profile_custody_registration_material(
                profile_id=_PROFILE_ID,
                password=_CREDENTIAL,
                dek=dek,
                dek_epoch=_EPOCH,
                salt=token_bytes(16),
                predecessor=committed,
                strength=ProfileKdfStrength(memory_mib=128, iterations=3, parallelism=1),
            )


def test_a_measured_point_never_mints_a_first_envelope(tmp_path: Path) -> None:
    with (
        override_settings(cadrumo_storage_root=tmp_path),
        pytest.raises(ValueError, match="existing password envelope"),
    ):
        create_profile_custody_registration_material(
            profile_id=_PROFILE_ID,
            password=_CREDENTIAL,
            dek=token_bytes(32),
            dek_epoch=_EPOCH,
            salt=token_bytes(16),
            strength=ProfileKdfStrength(memory_mib=128, iterations=4, parallelism=1),
        )
