"""What a passphrase rotation may and may not change about key material.

Rotation re-wraps the SAME data-encryption key under a new password. These
tests pin the two substrate facts that decide whether it can be implemented
safely, both of which were established by measurement rather than by reading,
and both of which a future author could silently break.

Neither test drives a rotation function, because none exists yet. They
characterise the custody substrate the rotation will be built on, so the
constraints are already enforced when it arrives rather than discovered
afterwards by a taxpayer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody import (
    PROFILE_CUSTODY_RECOVERY_FILENAME,
    create_profile_custody_password_envelope,
    load_committed_profile_password_material,
    parse_profile_custody_recovery_envelope,
    unlock_profile_custody_recovery,
)
from ....tests.secure_sql import isolated_profile_storage_root
from .._capsule_record import ProfileRecordIntegrityError, ProfileRecordSession, ProfileRecordStore

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Rotation Contract Subject"
_PASSPHRASE = "rotation-contract-current-operator-secret"  # noqa: S105 - synthetic test credential
_NEW_PASSPHRASE = "rotation-contract-replacement-operator-secret"  # noqa: S105 - synthetic test credential


def test_rotation_must_preserve_the_dek_epoch_so_an_outstanding_recovery_artifact_still_opens(
    tmp_path: Path,
) -> None:
    """Minting a fresh DEK epoch during rotation would strand every recovery artifact.

    The recovery wrapper and the committed sentinel are both bound to
    ``(profile_id, dek_epoch)`` and to neither the password envelope's digest
    nor its generation. So a re-wrap that keeps the epoch leaves an
    already-issued recovery phrase working, and a re-wrap that mints a new one
    silently destroys the only second door a taxpayer holds — without any
    error, at the moment they change their password.

    This test exists to fail loudly for whoever writes ``dek_epoch=`` with a
    fresh value in the rotation path.
    """
    handed: list[str] = []

    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register(tmp_path, handed)
        profile_id = UUID(outcome.profile_id)
        material = load_committed_profile_password_material(profile_id)
        dek = _unlock_dek(material)

        rotated = create_profile_custody_password_envelope(
            profile_id=profile_id,
            password=_NEW_PASSPHRASE,
            dek=dek,
            dek_epoch=material.envelope.dek_epoch,
            kdf=material.envelope.kdf,
            password_generation=material.envelope.password_generation + 1,
        )

        assert rotated.self_digest != material.envelope.self_digest
        assert rotated.dek_epoch == material.envelope.dek_epoch

        recovery = parse_profile_custody_recovery_envelope(
            (material.capsule_path / "custody" / PROFILE_CUSTODY_RECOVERY_FILENAME).read_bytes(),
        )
        proved = unlock_profile_custody_recovery(recovery, handed[0], sentinel=material.sentinel)

        assert proved.dek == dek
        assert proved.dek_epoch == rotated.dek_epoch


def test_rotation_must_re_head_the_record_row_because_its_header_binds_the_envelope(
    tmp_path: Path,
) -> None:
    """A bare envelope re-wrap yields a profile that cannot read its own record.

    ``ProfileRecordSession.write_provenance`` folds the envelope digest and the
    password generation into the persisted row header, and every read
    recomputes that from the live session. After a re-wrap the recomputed
    witness no longer matches the stored one, so the record is refused — the
    operator authenticates under their new password and then finds their
    profile unreadable.

    Rotation must therefore re-head the current row inside the same
    transaction as the envelope swap. This test pins the reason that step
    cannot be dropped as an optimisation.
    """
    handed: list[str] = []

    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register(tmp_path, handed)
        profile_id = UUID(outcome.profile_id)
        material = load_committed_profile_password_material(profile_id)
        dek = _unlock_dek(material)

        rotated = create_profile_custody_password_envelope(
            profile_id=profile_id,
            password=_NEW_PASSPHRASE,
            dek=dek,
            dek_epoch=material.envelope.dek_epoch,
            kdf=material.envelope.kdf,
            password_generation=material.envelope.password_generation + 1,
        )

        # The control: the row is readable under the envelope it was written
        # with, so the refusal below is caused by the re-wrap and nothing else.
        current = ProfileRecordSession.from_envelope(envelope=material.envelope, dek=dek)
        try:
            assert ProfileRecordStore(session=current).load().record.profile_id == str(profile_id)
        finally:
            current.close()

        after = ProfileRecordSession.from_envelope(envelope=rotated, dek=dek)
        try:
            with pytest.raises(ProfileRecordIntegrityError, match="provenance"):
                ProfileRecordStore(session=after).load()
        finally:
            after.close()


def _register(tmp_path: Path, handed: list[str]):
    """Register one profile with recovery enrolled, capturing its phrase."""
    from .. import register_profile_with_credentials

    return register_profile_with_credentials(
        label=f"{_LABEL} {tmp_path.name}",
        passphrase=_PASSPHRASE,
        recovery_handover=lambda enrollment: handed.append(enrollment.recovery_key.mnemonic),
    )


def _unlock_dek(material) -> bytes:
    """Return the profile's DEK through the real password door."""
    from ...profile_custody import unlock_profile_custody_password

    return unlock_profile_custody_password(material, password=_PASSPHRASE).dek
