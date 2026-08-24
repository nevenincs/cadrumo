"""Cross-profile isolation: one profile's material can never open another.

The create-time guard (test_custody_transactions.py:687) refuses custody
material that names the wrong profile at registration. These cases prove the
UNLOCK and RESTORE doors hold the same boundary: profile A's password
envelope and recovery mnemonic must refuse to open profile B's capsule
through the real authorities, not merely through a create-time check.

Every case runs on a real isolated storage root with real supervised KDF
derivation; no mocks, no skips.
"""

from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from secrets import token_bytes
from uuid import UUID, uuid4

import pytest

from ......application.user_profile import (
    ProfileCapsuleLifecycle,
    ProfileRecordSession,
    create_profile_custody_registration_material,
    enroll_profile_recovery,
    export_profile_recovery_artifact,
    register_profile_with_credentials,
    restore_profile_from_source_with_recovery_artifact,
    unlock_profile_custody_password,
)
from ......domain.user_profile import ProfileSetupState, UserProfileRecord
from ......tests.secure_sql import isolated_profile_storage_root
from .. import (
    ProfileCustodyEnvelope,
    ProfileCustodyPasswordError,
    ProfileCustodyRecordError,
    load_committed_profile_password_material,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PASSPHRASE_A = "isolation-subject-a-operator-secret"  # noqa: S105 - synthetic test credential
_PASSPHRASE_B = "isolation-subject-b-operator-secret"  # noqa: S105 - synthetic test credential


def _register(label: str, passphrase: str) -> UUID:
    outcome = register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=label, passphrase=passphrase
    )
    return UUID(outcome.profile_id)


class _EnrolledProfile:
    """One really-created profile plus the recovery enrollment its export needs."""

    __slots__ = ("dek", "enrollment", "envelope", "password", "profile_id", "root", "sentinel")

    def __init__(self, root: Path, *, label: str, password: str) -> None:
        self.root = root
        self.password = password
        self.profile_id = uuid4()
        self.dek = token_bytes(32)
        dek_epoch = b64encode(token_bytes(16)).decode("ascii")
        material = create_profile_custody_registration_material(
            profile_id=self.profile_id,
            password=password,
            dek=self.dek,
            dek_epoch=dek_epoch,
            salt=token_bytes(16),
        )
        assert isinstance(material.envelope, ProfileCustodyEnvelope)
        self.envelope = material.envelope
        self.sentinel = material.sentinel
        self.enrollment = enroll_profile_recovery(
            profile_id=self.profile_id,
            dek=self.dek,
            dek_epoch=dek_epoch,
        )
        session = ProfileRecordSession.from_envelope(envelope=self.envelope, dek=self.dek)
        try:
            ProfileCapsuleLifecycle(root=root).create(
                label=label,
                profile_id=self.profile_id,
                password_envelope=self.envelope,
                sentinel=self.sentinel,
                data_files={},
                initial_record=UserProfileRecord(
                    profile_id=str(self.profile_id),
                    setup_state=ProfileSetupState.INCOMPLETE,
                ),
                record_session=session,
                recovery_envelope=self.enrollment.envelope,
            )
        finally:
            session.close()

    @property
    def capsule_path(self) -> Path:
        return self.root / "buckets" / str(self.profile_id)

    def export(self, target: Path) -> None:
        export_profile_recovery_artifact(
            self.enrollment,
            current_password=self.password,
            password_envelope=self.envelope,
            sentinel=self.sentinel,
            target=target,
        )


def test_one_profiles_password_envelope_cannot_unlock_another(tmp_path: Path) -> None:
    """A's envelope under B's passphrase refuses at the real unlock door."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_a = _register("Isolation A", _PASSPHRASE_A)
        _register("Isolation B", _PASSPHRASE_B)

        material = load_committed_profile_password_material(profile_a)
        with pytest.raises(ProfileCustodyPasswordError):
            unlock_profile_custody_password(material, password=_PASSPHRASE_B)


def test_one_profiles_recovery_artifact_cannot_restore_another(tmp_path: Path) -> None:
    """A's artifact and mnemonic cannot republish B's capsule.

    Both profiles are seeded through the real publication doors, and A
    carries a recovery wrapper it can export. Restoring B's capsule while
    proving A's artifact must refuse at the artifact-identity check: the
    artifact names the profile it wraps, and that is not B. The same door
    then restores A from the same artifact, so the refusal is the artifact's
    identity, not a broken restore path.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_a = _EnrolledProfile(root, label="Isolation A", password=_PASSPHRASE_A)
        profile_b = _EnrolledProfile(root, label="Isolation B", password=_PASSPHRASE_B)
        target = tmp_path / "exports" / "recovery.json"
        target.parent.mkdir()
        profile_a.export(target)

        with pytest.raises(ProfileCustodyRecordError, match="does not match its named target"):
            restore_profile_from_source_with_recovery_artifact(
                label="Isolation B restored",
                source=profile_b.capsule_path,
                artifact_source=target,
                recovery_secret=profile_a.enrollment.recovery_key.mnemonic,
                root=tmp_path / "restored-b",
            )

        restored = restore_profile_from_source_with_recovery_artifact(
            label="Isolation A restored",
            source=profile_a.capsule_path,
            artifact_source=target,
            recovery_secret=profile_a.enrollment.recovery_key.mnemonic,
            root=tmp_path / "restored-a",
        )
        assert restored.profile_id == str(profile_a.profile_id)
