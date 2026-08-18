"""Restoring a profile from a capsule directory an operator can point at.

Real capsules on a real filesystem, real Argon2id envelopes, the real
recovery door. The subject is the orchestration a command line needs: a PATH
plus a credential, rather than three parsed custody records no CLI can obtain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from cadrumo.application.user_profile import profile_custody_recovery_envelope_path

from ....adapters.persistence.storage.custody import load_committed_profile_password_material
from ....tests.secure_sql import isolated_profile_storage_root
from .. import (
    ProfileCapsuleSourceError,
    read_profile_capsule_source,
    register_profile_with_credentials,
    restore_profile_from_source_with_password,
    restore_profile_from_source_with_recovery_artifact,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Capsule Restore Subject"
_PASSPHRASE = "capsule-restore-subject-operator-secret"  # noqa: S105 - synthetic test credential


def _published_capsule(tmp_path: Path, handed: list[str] | None = None) -> tuple[str, Path]:
    """Register a profile and return its id and published capsule directory."""
    outcome = register_profile_with_credentials(
        label=_LABEL,
        passphrase=_PASSPHRASE,
        recovery_handover=None if handed is None else (lambda e: handed.append(e.recovery_key.mnemonic)),
    )
    material = load_committed_profile_password_material(UUID(outcome.profile_id))
    return outcome.profile_id, material.capsule_path


def test_a_capsule_directory_restores_under_its_own_password(tmp_path: Path) -> None:
    """The orchestration a CLI needs: a path plus a password, nothing parsed."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id, capsule = _published_capsule(tmp_path)

        restored = restore_profile_from_source_with_password(
            label="Restored by password",
            source=capsule,
            password=_PASSPHRASE,
            root=tmp_path / "password-restored",
        )

        assert restored.profile_id == profile_id
        assert restored.authority == "password"


def test_a_restore_carries_the_recovery_wrapper_forward(tmp_path: Path) -> None:
    """A restored profile must not silently lose its second door.

    Recovery is installable only at publication, and a restore IS one, so a
    republished capsule that dropped the wrapper it had would leave the
    operator recovered and unrecoverable, with nothing said. This asserts the
    wrapper is on disk in the restored capsule and byte-identical, and that
    the outcome reports it.
    """
    handed: list[str] = []

    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id, capsule = _published_capsule(tmp_path, handed)
        original = profile_custody_recovery_envelope_path(capsule).read_bytes()
        destination = tmp_path / "recovery-preserved"

        restored = restore_profile_from_source_with_password(
            label="Restored keeping recovery",
            source=capsule,
            password=_PASSPHRASE,
            root=destination,
        )

        assert restored.recovery_enrolled is True
        carried = destination / "buckets" / profile_id / "custody" / "recovery.v1.json"
        assert carried.read_bytes() == original


def test_a_profile_that_never_enrolled_restores_and_says_so(tmp_path: Path) -> None:
    """Converse control: absence is a legitimate source, reported honestly.

    Without this the sibling test would pass identically if the outcome
    hardcoded enrolment, and a restore of a never-enrolled profile would
    claim a door it does not have.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _, capsule = _published_capsule(tmp_path)

        assert not profile_custody_recovery_envelope_path(capsule).exists()

        restored = restore_profile_from_source_with_password(
            label="Restored without recovery",
            source=capsule,
            password=_PASSPHRASE,
            root=tmp_path / "no-recovery",
        )

        assert restored.recovery_enrolled is False


def test_a_lost_password_is_recovered_through_the_artifact_and_the_source(tmp_path: Path) -> None:
    """The operator-facing point of the whole mechanism, end to end.

    An operator who has lost their password holds two things: the capsule
    directory from a backup, and the artifact plus its phrase. That must be
    enough to get their records back.
    """
    handed: list[str] = []

    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id, capsule = _published_capsule(tmp_path, handed)
        artifact = tmp_path / "exports" / "recovery.artifact.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)

        from .. import export_profile_recovery_artifact
        from .._recovery_custody import ProfileRecoveryEnrollment

        material = load_committed_profile_password_material(UUID(profile_id))
        source = read_profile_capsule_source(capsule)
        assert source.recovery_envelope is not None
        receipt = export_profile_recovery_artifact(
            ProfileRecoveryEnrollment(envelope=source.recovery_envelope, recovery_key=_ReplayedKey(handed[0])),
            current_password=_PASSPHRASE,
            password_envelope=material.envelope,
            sentinel=material.sentinel,
            target=artifact,
        )
        assert receipt.target == artifact

        restored = restore_profile_from_source_with_recovery_artifact(
            label="Recovered without the password",
            source=capsule,
            artifact_source=artifact,
            recovery_secret=handed[0],
            root=tmp_path / "artifact-restored",
        )

        assert restored.profile_id == profile_id
        assert restored.authority == "recovery_artifact"
        assert restored.recovery_enrolled is True


def test_a_source_missing_a_required_member_is_refused_by_name(tmp_path: Path) -> None:
    """A torn source refuses before publication, naming what it lacks.

    Discovering it afterwards would mean a capsule had already been committed
    against material that could not be read.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _, capsule = _published_capsule(tmp_path)
        (capsule / "data" / "dek.sentinel.v1.json").unlink()

        with pytest.raises(ProfileCapsuleSourceError, match="DEK sentinel"):
            read_profile_capsule_source(capsule)


class _ReplayedKey:
    """The operator's transcribed phrase, back in the container the export takes.

    The export door takes an enrollment because that is what a creation flow
    holds. A restore flow holds the phrase the operator wrote down and the
    wrapper from the capsule, which is the same material re-assembled -- so
    this carries the phrase rather than standing in for the mint.
    """

    __slots__ = ("_mnemonic",)

    def __init__(self, mnemonic: str) -> None:
        self._mnemonic = mnemonic

    @property
    def mnemonic(self) -> str:
        return self._mnemonic
